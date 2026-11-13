# compass_pkg.tdd_green - `compass tdd-green`
"""`compass tdd-green`: run a test command, check that it passes, and record the
green for each scenario it is bound to.

A bound green needs a red bound to the same scenario. With `--loop outer`, one
run can stand for several scenarios: `--scenario` repeats, and
`--every-scenario` names every scenario the manifest declares. One record is
written per scenario, each with the same `run_id` and `scenarios_in_run`
(ADR-085, as `compass tdd-red` does under ADR-081). An outer-loop green names
its candidate and client (`candidate_client`, ADR-085).

The command lived in `tdd.py` until the green grew several scenarios; it moved
here so `tdd.py` stays under the module line limit. `tdd.py` keeps the helpers
the red, the green and `compass acceptance` share.
"""
# DEPENDENCY: standard library (os, sys, uuid); compass_pkg.tdd, candidate_client,
# core, green_attempts, binding and red_first. `tdd` does not import this module.
from __future__ import annotations

import os
import sys
import uuid

from compass_pkg import candidate_client, green_attempts
from compass_pkg.binding import files_key, ids_for
from compass_pkg.core import CompassError, find_upwards, load_manifest, now_iso, resolve_issue_dir
from compass_pkg.red_first import carried_first, has_red, load_record, record_paths, record_stem
from compass_pkg.tdd import (
    _VERIFIED_BY_KINDS, _acceptance_state, _bind_to_tree, _loop, _micro_command,
    _neutralise_coverage, _output_fail_token, _red_scenarios, _run_test, _scenario_line,
    _source_tree_hash, _upsert_test_run_evidence, _write_evidence, settings_hint)
from compass_pkg.terminal import say


def _attempt_tree(task_dir, tree_ids):
    """The tree a green's run is compared on. Its identity is the git tree id -
    every tracked file, whatever its type - with the source-file hash of the
    project root beside it, which also sees untracked source files; outside git the
    hash alone decides. The files the record covers are part of what it asserts:
    after a file is traced to the issue, the same command covers more files, a
    new assertion and not a retry of a flaky test."""
    out = _source_tree_hash(find_upwards(task_dir, ".compass") or task_dir)
    if tree_ids.get("tree_id"):
        out = "%s+%s" % (tree_ids["tree_id"], out)
    if tree_ids.get("file_sha256") is not None:
        out = "%s+%s" % (out, files_key(tree_ids["file_sha256"], tree_ids.get("file_modes")))
    return out


def _red_record_for(task_dir, scenario, loop=None):
    """The red record a green bound to `scenario` needs, or None if unbound.

    Same binding, same file: only `evidence/red-X.json`, or the outer-loop
    `red-X.outer.json` (ADR-082), answers `--scenario X` - not an unbound
    `red.json`, and not a red recorded for a different scenario. The file of
    the green's own loop comes first; the path returned when neither exists
    is that one.

    The looser rule, "any red on this issue", lets a red recorded for one
    scenario clear a green for another. That is the same class of error as a
    green with no red at all, one step quieter, and quieter is worse because
    nothing reports it.
    """
    if not scenario:
        return None
    paths = record_paths(task_dir, "red", scenario)
    paths = paths[::-1] if loop == "outer" else paths
    return next((p for p in paths if os.path.isfile(p)), paths[0])


def strategy_applies(task_dir):
    """True when the four-layer acceptance strategy applies to the issue, the one
    scope rule (`acceptance_strategy.in_scope`, ADR-079). No manifest: False."""
    from compass_pkg.acceptance_strategy import in_scope
    try:
        task, _ = load_manifest(task_dir)
    except (CompassError, OSError, ValueError):
        return False
    return isinstance(task, dict) and in_scope(task, task_dir)[0]


def _refuse_without_red(task_dir, scenario, loop):
    """Refuse a bound green with no red for its scenario. The refusal is about what
    may be RECORDED, so it comes before anything runs: a bad record never exists,
    rather than being found afterwards by a check, already cited by a gate."""
    red_path = _red_record_for(task_dir, scenario, loop)
    if red_path and not os.path.isfile(red_path) and _acceptance_state(task_dir):
        # Telling a session that already declared an acceptance to declare
        # one sends it in a circle; name the step it has left instead.
        raise CompassError(
            f"compass tdd-green: no red is on record for {scenario}, and this "
            f"issue declared an acceptance instead. Close it with `compass "
            f"acceptance record --scenario {scenario} -- <the declared "
            f"command>`. On a quick fix, `compass quick-fix finish` does it.")
    if red_path and not os.path.isfile(red_path):
        raise CompassError(
            f"compass tdd-green: no red is on record for {scenario}, so there "
            f"is no failure for this green to be the other half of.\n"
            f"  expected : {red_path}\n"
            f"  Run `compass tdd-red --scenario {scenario} -- <test command>` "
            f"first. For work with no natural red - config, docs, a "
            f"behavior-preserving refactor - declare it before the change "
            f"with `compass acceptance start --kind validation|refactor -- "
            f"<command>`."
        )


def cmd_tdd_green(args):
    task_dir = resolve_issue_dir(args.task)
    loop = _loop(args, task_dir)
    scenarios = _red_scenarios(args, task_dir, loop, "tdd-green")
    several = len(scenarios) > 1 or bool(getattr(args, "every_scenario", False))
    verified_by = getattr(args, "verified_by", None)
    if verified_by and verified_by not in _VERIFIED_BY_KINDS:
        raise CompassError(
            f"compass tdd-green: --verified-by '{verified_by}' is not a "
            f"recognized kind. Allowed: {sorted(_VERIFIED_BY_KINDS)}.")
    command = _micro_command(args, task_dir)
    if not command:
        raise CompassError("compass tdd-green needs a test command (-- <cmd>) "
                           "or " + settings_hint(task_dir, "project.test_micro_command"))
    tree_ids = ids_for(task_dir)   # the tree the test runs on, named before it runs
    named = candidate_client.named(
        "tdd-green", loop, getattr(args, "candidate", None), getattr(args, "client", None),
        loop == "outer" and strategy_applies(task_dir), tree_ids)
    for one in scenarios:
        _refuse_without_red(task_dir, one, loop)

    command = _neutralise_coverage(command)
    # `quick-fix finish` records a green for several scenarios from one run.
    # It hands that run in, and it stands for this scenario only when it ran
    # this exact command on this exact tree; otherwise the command runs here.
    prerun = getattr(args, "prerun", None)
    if prerun and prerun["argv"] == command and prerun["tree_ids"] == tree_ids:
        code, out, warnings = prerun["result"]
    else:
        code, out, warnings = _run_test(command)
    for w in warnings:
        sys.stderr.write(f"compass tdd-green: warning - {w}\n")
    excerpt = "\n".join(out.splitlines()[-25:])
    # Output-token cross-check. A zero exit whose output carries
    # a known-runner fail-token is a suspected masked failure - refuse rather
    # than record a clean green on a contradictory signal.
    fail_token = _output_fail_token(out) if code == 0 else None
    # `attempts` and rerun_without_change: the tree the run left, with the command,
    # against the last run of this binding and loop. A failed outer-loop run
    # counts too (green_attempts, ADR-084).
    current_command = " ".join(command)
    if (code != 0 or fail_token) and loop == "outer":
        for one in scenarios or [None]:
            green_attempts.failed(task_dir, one, loop, _attempt_tree(task_dir, tree_ids),
                                  current_command)
    if code != 0:
        raise CompassError(
            f"compass tdd-green: the test command FAILED (exit {code}) - not "
            f"green yet. The .red marker is left in place.\n"
            f"--- output (tail) ---\n" + excerpt
        )
    if fail_token:
        raise CompassError(
            f"compass tdd-green: the command exited 0 but its output shows a "
            f"failure token ('{fail_token}') - a possible masked failure. "
            f"Refusing to record a green on a contradictory signal. The .red "
            f"marker is left in place.\n--- output (tail) ---\n" + excerpt
        )
    run = {"run_id": uuid.uuid4().hex[:16], "scenarios_in_run": list(scenarios)} \
        if several else {}
    ev_paths = [_record_green(task_dir, one, loop, command, out, excerpt, tree_ids,
                              dict(named, **run), verified_by)
                for one in scenarios or [None]]
    # Say "red -> green" only when a red was there to clear. An unbound green
    # needs no red, and printing the pair when none existed told the user a
    # failure had been observed when it had not. The last full-suite green
    # comes after the bound reds were cleared, so it names those instead of
    # denying them.
    red_marker = os.path.join(task_dir, ".red")
    if os.path.exists(red_marker):
        os.remove(red_marker)
        marker_line = "marker   : .red cleared - red -> green is on record."
    elif has_red(task_dir):
        marker_line = ("marker   : no .red marker to clear - a red for this "
                       "issue is already on record.")
    else:
        marker_line = ("marker   : no .red marker - no red is on record for "
                       "this issue.")
    bound = (f" (bound to {', '.join(scenarios)})" if scenarios
             else " (unbound - consider --scenario)")
    from compass_pkg.next_line import announce
    said = say(args,
               f"compass tdd-green: passing suite recorded (exit 0){bound}.",
               detail=[f"evidence : {p}" for p in ev_paths]
                      + ["registry : manifest.yml `evidence:` updated with the "
                         "test-run entry", marker_line]
                      + [x for x in [_scenario_line(task_dir, s) for s in scenarios] if x],
               scenario=scenarios[0] if scenarios else None, exit_code=0,
               evidence=ev_paths[0])
    return announce(args, task_dir, said)


def _record_green(task_dir, scenario, loop, command, out, excerpt, tree_ids, extra,
                  verified_by):
    """Write and register the green of one scenario from a passing run, and return
    the record's path. `extra` holds the candidate, the client and the run id."""
    attempts, rerun_without_change = green_attempts.count(
        task_dir, scenario, loop, _attempt_tree(task_dir, tree_ids), " ".join(command))
    payload = {
        "command": " ".join(command),
        # The argument list as given: two lists can join to the same text.
        "argv": list(command),
        "scenario": scenario,          # the scenario this green is evidence FOR
        "loop": loop,
        "exit_code": 0,
        "passed": True,
        "attempts": attempts,
        "timestamp": now_iso(),
        "log_excerpt": excerpt,
        "_full_log": out,
    }
    # Always record the marker when `attempts` > 1. Absence of the field on
    # a record of more than one try fails the no-trusted-rerun check
    # (incomplete evidence cannot clear `G4`). The marker is informative
    # either way - true means "no source change between tries" (the failure
    # mode `S5` protects against), false means "source did change" (a legitimate
    # red→green path).
    if attempts > 1:
        payload["rerun_without_change"] = rerun_without_change
    # An outer-loop green names its test, so a quarantine entry can match it.
    test = green_attempts.declared_test(task_dir, scenario) if loop == "outer" else None
    if test:
        payload["test"] = test
    payload.update(extra)
    # This record replaces the last one of its binding and loop. It keeps the
    # time of the first run, which `suite-passed` compares a scenario's red
    # with, so a later run cannot move the first green past the red (ADR-088).
    name = record_stem("green", scenario, loop)
    payload["first_timestamp"] = carried_first(
        load_record(os.path.join(task_dir, "evidence", name + ".json")), payload["timestamp"])
    _bind_to_tree(payload, tree_ids)
    if verified_by:
        payload["verified_by"] = verified_by   # carry the guard kind forward
    # THE BINDING DECIDES THE PATH. One record per scenario, and nothing else is
    # touched.
    #
    # A bound write touches only its own record and an unbound write only
    # the unbound one, so a scenario run cannot replace the record a
    # full-suite citation names. An outer-loop green has its own file (ADR-082).
    ev_path = _write_evidence(task_dir, name, payload)
    # Upsert a test-run entry in the issue's evidence registry - the registry
    # is what `compass check` reads, so the green has to land there.
    _upsert_test_run_evidence(task_dir, scenario, f"evidence/{name}.json",
                              record_id=payload.get("record_id"),
                              content_digest=payload.get("content_digest"))
    return ev_path
