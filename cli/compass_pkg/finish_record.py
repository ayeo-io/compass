# compass_pkg.finish_record - `compass quick-fix finish` on a delivery issue
"""`compass quick-fix finish` writes the record of a delivery issue itself (ADR-099).

`finish_record` is the whole of the call: it reads the scenarios and the
changed files, proves the red on a copy of the base commit, records the green,
runs `compass check`, passes the three gates, asks for the approvals a person
owes and, once a person has approved, commits. `compass_pkg.lean` holds the
parts; this module holds their order and what the call prints.

The lines it prints are context the session pays for on every later call, so
there are few of them: `tests/test_two_command_change.py` bounds the count.
"""
# DEPENDENCY: standard library (os); compass_pkg.binding, check_cmd, core, lean,
# manifest, quick_fix_cmd (`_quiet_run`, `_at_project_root`, `THREE_GATES`),
# release_line, stable_ids, tdd and tdd_green; inside the function
# approval_requests, next_step and status_words.
from __future__ import annotations

import os

from compass_pkg import lean, release_line
from compass_pkg.binding import ids_for
from compass_pkg.check_cmd import cmd_check
from compass_pkg.core import (CompassError, find_upwards, load_manifest, resolve_issue_dir,
                              save_manifest)
from compass_pkg.manifest import cmd_evidence_add, cmd_gate_pass, cmd_land_commit
from compass_pkg.path_stages import is_path_issue
from compass_pkg.quick_fix_cmd import (THREE_GATES, _at_project_root, _quiet_run,
                                       _reusable_green, _finish_earlier_issue)
from compass_pkg.stable_ids import APPROACH_DELIVERY
from compass_pkg.stable_ids import (GATE_VERIFY_CORRECTNESS, GATE_VERIFY_GOVERNANCE,
                                    GATE_VERIFY_TRACEABILITY)
from compass_pkg.tdd import (_acceptance_state, _neutralise_coverage, _run_test,
                             cmd_acceptance_record)
from compass_pkg.tdd_green import _red_record_for, cmd_tdd_green


def register(subs, issue_arg):
    """Add `finish` to the subparsers of `compass quick-fix`."""
    import argparse
    fi = subs.add_parser(
        "finish", help="write the record of the change in one call: the scenarios, the changed "
                       "files, the red on a copy of the base commit, the green, the check and "
                       "the approval requests; commit once a person has approved")
    fi.add_argument("-m", "--message", required=True, help="the commit message")
    fi.add_argument("--no-commit", action="store_true",
                    help="write the record and leave the commit to `compass ship-commit`")
    from compass_pkg.acceptance_strategy import LOOPS
    fi.add_argument("--loop", choices=LOOPS, default=None,
                    help="outer: the acceptance suite; inner: a unit test")
    fi.add_argument("--candidate", metavar="ID|local", help="outer loop: the build")
    fi.add_argument("--client", metavar="api|web|cli", help="outer loop: the interface")
    from compass_pkg.release_line import add_argument as add_release_note
    add_release_note(fi)
    issue_arg(fi)
    fi.add_argument("command", nargs=argparse.REMAINDER,
                    help="the test command (after --): it must fail on a copy of the base "
                         "commit and pass on the working tree")
    fi.set_defaults(func=cmd_quick_fix_finish, output_kind="hand-off")


def cmd_quick_fix_finish(args):
    """`compass quick-fix finish`. A delivery issue on the path gets its record
    written here; an issue assessed before 9.0.0 goes to the handler it had."""
    task_dir = resolve_issue_dir(getattr(args, "task", None))
    task, _ = load_manifest(task_dir)
    command = list(getattr(args, "command", None) or [])
    if command and command[0] == "--":
        command = command[1:]
    if not (command and is_path_issue(task)
            and task.get("delivery_approach") == APPROACH_DELIVERY):
        return _finish_earlier_issue(args)
    from compass_pkg.terminal import mark_handled, resolve_mode
    if resolve_mode(args) != "json":
        return finish_record(args, task_dir, task.get("issue"), command)
    # `--json`: the same lines as one document, with the owed items as `owed`.
    import contextlib
    import io
    import json
    held, owed = io.StringIO(), []
    with contextlib.redirect_stdout(held):
        code = finish_record(args, task_dir, task.get("issue"), command, owed)
    lines = [ln for ln in held.getvalue().splitlines() if ln.strip()]
    steps = [ln.split(": ", 1)[1] for ln in lines if ln.startswith(("next: ", "done: "))]
    mark_handled()
    print(json.dumps({"outcome": lines[0] if lines else "", "owed": owed, "next": steps,
                      "detail": [ln.strip() for ln in lines[1:]
                                 if not ln.startswith(("next: ", "done: "))]}, indent=2))
    return code


#: The checks only a person can clear. `finish` asks for the approval and goes on.
_PERSON_CHECKS = frozenset({"human-approval-present", "ship-approval-present"})


def finish_record(args, task_dir, slug, command, owed_out=None):
    """`compass quick-fix finish` on a delivery issue: one call writes the record
    (ADR-099).

    It reads the scenarios from the acceptance criteria and the changed files
    from git, proves the red on a copy of the base commit, records the green
    on the working tree, runs `compass check`, passes the three gates and asks
    for the approvals a person owes. Once a person has given the first
    approvals it commits on the branch in the same call. Running it again
    after more edits replaces the red and the green; when the change then
    differs from the one approved, it commits, asks for a new approval and
    `compass check` fails on the approval until a person gives it."""
    invoked_from = os.getcwd()
    project_root = find_upwards(task_dir, ".compass") or invoked_from
    task, task_path = load_manifest(task_dir)

    def refuse(why, step):
        print(f"compass quick-fix finish: '{slug}' is not checked - {why}")
        print(f"next: {step}")
        return 1

    owed = lean.specify_owed(task, task_dir)
    if owed:
        return refuse("a person has not approved its scenarios.", owed)

    # Where a project's settings add the outer loop, the green is the outer
    # loop's unless `--loop inner` is given, and an outer-loop green on an
    # issue `S17` applies to names its candidate and client (ADR-085). Each is
    # refused here, before anything is traced or run. On the inner loop the
    # two flags are taken and not written; an unknown client is always refused.
    from compass_pkg import candidate_client, next_step
    from compass_pkg.tdd_green import strategy_applies
    loop = next_step.finish_loop(task, task_dir, getattr(args, "loop", None))
    flags = ((getattr(args, "candidate", None), getattr(args, "client", None))
             if loop == "outer" else (None, None))
    candidate_client.named("quick-fix finish", "outer", None, getattr(args, "client", None),
                           False, {})
    candidate_client.named("quick-fix finish", loop, *flags,
                           loop == "outer" and strategy_applies(task_dir), ids_for(task_dir))
    # An inner-loop finish cannot give the outer-loop red the issue owes.
    if loop == "inner" and next_step._owed(task, task_dir, "outer-loop") \
            and not next_step._outer_red(task_dir):
        scenario = next((s["id"] for s in next_step.needing_tests(task)), "<id>")
        step = next_step._outer_red_command(task, task_dir, scenario)
        if owed_out is not None:
            owed_out.append(step)
        return refuse("it owes an outer-loop red, which an inner-loop finish does not "
                      "record.", step)

    base = lean.base_commit(task, project_root, slug)
    added = lean.sync_scenarios(task, lean.spec_of(task_dir))
    task[lean.MESSAGE_KEY] = args.message
    if base and not task.get(lean.BASE_KEY):
        task[lean.BASE_KEY] = base
    save_manifest(task, task_path)
    scenario_ids = [s["id"] for s in task.get("scenarios") or []
                    if isinstance(s, dict) and s.get("id")
                    and s.get("verifiable") != "narrative"]
    if not scenario_ids:
        raise CompassError(f"compass quick-fix finish: '{slug}' has no scenario; write one "
                           f"in its acceptance-criteria.md, then run finish again.")

    # What the manifest traces already, and the test files the scenarios
    # declare: the change's by declaration, committed or not.
    keep = {cf.get("path") for cf in task.get("changed_files") or [] if isinstance(cf, dict)}
    keep |= {t.split("::", 1)[0] for sc in task.get("scenarios") or [] if isinstance(sc, dict)
             for t in sc.get("tests") or [] if isinstance(t, str)}
    with _at_project_root(project_root):
        code_paths, documents, left_out = lean.changed_paths(
            project_root, base, slug, lean.doc_prefix(task_dir), keep)
        test_paths = [p for p in code_paths if lean.is_test_path(p)]
        tests = [p for p in test_paths if os.path.isfile(os.path.join(project_root, p))]
        lean.record_change(task_dir, project_root, code_paths, documents, tests)

    argv = _neutralise_coverage(list(command))
    ids = ids_for(task_dir)
    proved, earlier = None, False
    # Work with no natural red (a refactor, a configuration change) declares an
    # acceptance before the change with `compass acceptance start`. Its record,
    # run here on the tree that lands, stands in place of the red and the green.
    # A validation must run the command that was declared.
    accepted = _acceptance_state(task_dir) if not any(
        os.path.isfile(_red_record_for(task_dir, sid)) for sid in scenario_ids) else {}
    try:
        if accepted:
            if accepted.get("kind") == "validation" \
                    and " ".join(command) != accepted.get("command"):
                raise CompassError(
                    f"compass quick-fix finish: this issue declared the validator "
                    f"`{accepted.get('command')}`; run finish with that command after `--`.")
            for sid in scenario_ids:
                if not _reusable_green(task_dir, sid, command, ids):
                    _quiet_run(cmd_acceptance_record, task=slug, scenario=sid,
                               command=list(command))
        else:
            # A red that `compass tdd-red` recorded stays; `finish` proves the
            # red only for the scenarios that hold none.
            named = candidate_client.named("quick-fix finish", loop, *flags, False, ids)
            kept = [sid for sid in scenario_ids if lean.recorded_red(
                task_dir, sid, ids,
                lambda sid: _reusable_green(task_dir, sid, command, ids, loop, named))]
            fresh = [sid for sid in scenario_ids if sid not in kept]
            shared = None

            def green(sid, sid_loop):
                nonlocal shared
                if shared is None:
                    shared = {"argv": argv, "tree_ids": ids_for(task_dir),
                              "result": _run_test(argv)}
                    if shared["result"][0] != 0:
                        tail = "\n".join(shared["result"][1].splitlines()[-12:])
                        raise CompassError(
                            f"compass quick-fix finish: the tests fail on the working tree "
                            f"(exit {shared['result'][0]}); nothing is checked.\n{tail}")
                _quiet_run(cmd_tdd_green, task=slug, scenario=sid, verified_by=None,
                           command=list(command), loop=sid_loop,
                           candidate=flags[0], client=flags[1], prerun=shared)

            if fresh and not lean.records_current(task_dir, fresh, argv, ids, loop):
                red_code, red_out, kind = lean.prove_red(
                    project_root, base, test_paths, argv, invoked_from,
                    declared=ids.get("test_files") or ())
                lean.drop_greens(task_dir, fresh)
                lean.drop_stale_records(task_dir, scenario_ids, kept, loop)
                stamp = lean.write_reds(task_dir, fresh, argv, red_code, red_out, kind,
                                        base, tests, ids, loop)
                lean.wait_past(stamp)
                for sid in fresh:
                    green(sid, loop)
                proved = red_code
            for sid in kept:
                if not _reusable_green(task_dir, sid, command, ids, loop, named):
                    green(sid, loop)
                    earlier = True
    except CompassError as exc:
        # A refusal is short: the agent reads it again on every later call.
        lines = str(exc).splitlines()
        print("\n".join(lines[:1] + lines[1:][-12:]))
        print("next: fix what the line above names, then run the same finish again")
        return 1

    with _at_project_root(project_root):
        evidence_rel = "evidence/check-output.txt"
        counts = {}
        check_out, check_code = _quiet_run(
            cmd_check, mode="summary", answers=counts, task=slug,
            evidence_out=os.path.join(task_dir, evidence_rel))
        # An approval is a person's, and finish asks for it below. When the
        # approval checks are the only failures the record is complete but for
        # that answer, and `compass ship-commit` refuses to land until `compass
        # check` passes.
        failing = lean.failing_checks(check_out)
        # A missing request link is a failing check and not a stop (#356):
        # finish names it and goes on, and `compass check` keeps failing on it.
        no_request = "request-recorded" in failing
        failing -= lean.NOT_A_STOP
        check_code = check_code if failing else 0
        # An issue that landed and was then changed (a review fix) fails
        # `evidence-matches-tree` until `compass ship-commit` lands it again.
        from compass_pkg import status_words
        relanding = status_words.is_completed(task)
        if relanding:
            failing.discard("evidence-matches-tree")
            check_code = check_code if failing else 0
        person_only = check_code != 0 and failing <= _PERSON_CHECKS
        if check_code != 0 and not person_only:
            print(f"compass quick-fix finish: '{slug}' is not checked - `compass check` "
                  f"fails:")
            for line in lean.check_failures(check_out):
                print("  " + line)
            print("next: fix what the lines above name, then run the same finish again")
            return 1

        task, _ = load_manifest(task_dir)
        pending = [g.get("id") for g in task.get("gates") or []
                   if isinstance(g, dict) and g.get("status") != "pass"]
        if proved is not None or pending:
            taken = {e.get("id") for e in task.get("evidence") or [] if isinstance(e, dict)}
            n = 1
            while f"EV-CHECK-{n}" in taken:
                n += 1
            _quiet_run(cmd_evidence_add, task=slug, evidence_id=f"EV-CHECK-{n}",
                       type="command-output", path=evidence_rel, scenario=None)
            task, _ = load_manifest(task_dir)
            runs = sorted({e.get("id") for e in task.get("evidence") or []
                           if isinstance(e, dict) and e.get("type") == "test-run"
                           and e.get("scenario") in scenario_ids})
            _quiet_run(cmd_gate_pass, task=slug, gate_id=GATE_VERIFY_CORRECTNESS, evidence=runs)
            for gate in (GATE_VERIFY_GOVERNANCE, GATE_VERIFY_TRACEABILITY):
                _quiet_run(cmd_gate_pass, task=slug, gate_id=gate, evidence=[f"EV-CHECK-{n}"])
        task, _ = load_manifest(task_dir)
        if release_line.owes(task, task_dir) and not release_line.held(task):
            line = release_line.clean(getattr(args, "release_note", None)
                                      or (args.message or "").splitlines()[0])
            if line and not release_line.text_problem(task_dir, line, "compass quick-fix finish"):
                release_line.store(task_dir, line, "compass quick-fix finish")
        # Evidence a project's settings added (`require_evidence`, a gate of
        # its own) is not written by finish: the session records each item,
        # then runs finish again (ADR-099 decision 9).
        from compass_pkg.next_step import owed_commands
        added_by_settings = owed_commands(task, task_dir, THREE_GATES, approvals=False)
        if added_by_settings:
            print(f"compass quick-fix finish: '{slug}' is checked, but it owes "
                  f"{len(added_by_settings)} item(s) that the project's settings add. "
                  f"Nothing is committed.")
            for step in added_by_settings:
                print(f"next: {step}")
            if owed_out is not None:
                owed_out.extend(added_by_settings)
            print("next: then run the same finish again")
            return 1
        waiting = lean.request_owed_approvals(task_dir)

    # The change is committed here, in the same call, once a person has given
    # the first approvals: on that run, and on every later one. A later run
    # whose change differs from the one approved still commits on the branch,
    # and `waiting` then holds the request for the new state (ADR-099 decisions
    # 6 and 7). `--no-commit` leaves the commit to `compass ship-commit`.
    committed, branch_note, commit_error = False, "", None
    task, _ = load_manifest(task_dir)
    approved_once = lean.first_approvals_given(task, task_dir)
    if (approved_once or not (waiting or person_only)) \
            and not getattr(args, "no_commit", False):
        with _at_project_root(project_root):
            dirty = lean.traced_paths(task, project_root)
            if relanding and not dirty:
                committed = True        # a second finish with nothing new to commit
            else:
                if lean.branch_for_first_landing(project_root, slug):
                    branch_note = " (new)"
                skip = (".compass/work/", lean.doc_prefix(task_dir))
                try:
                    _out, code = _quiet_run(
                        cmd_land_commit, task=slug, message=args.message, message_file=None,
                        files=[p for p in dirty if not p.startswith(skip)],
                        release_note=None, record_checked=True, quiet_report=True)
                    committed = code == 0
                    commit_error = None if committed else _out.strip()
                except CompassError as exc:
                    commit_error = str(exc)

    state = ("checked and committed" if committed else
             "checked, but for a person's approval. Nothing is committed" if person_only
             else "checked. Nothing is committed")
    print(f"compass quick-fix finish: '{slug}' {state}.")
    if accepted:
        print(f"  accepted : the declared {accepted.get('kind')} acceptance passes on the "
              f"working tree; it stands in place of a red")
    elif earlier and proved is None:
        print("  red      : recorded earlier with compass tdd-red; it stays")
        print("  green    : the tests pass on the working tree")
    elif proved is not None:
        print(f"  red      : the tests fail on the base commit {str(base)[:8]} (exit {proved}), "
              f"with {len(tests)} test file(s) of the change")
        print("  green    : the tests pass on the working tree")
    else:
        print("  records  : the red and the green already cover these files")
    print(f"  scenarios: {', '.join(scenario_ids)}"
          + (f" ({len(added)} read from the acceptance criteria)" if added else ""))
    if left_out:
        print(f"  left out : {lean.short(', '.join(map(lean.shown, left_out)), 80)} "
              f"(changed before start; "
              f"`compass changed-file add` takes one in)")
    by_hand = lean.committed_untraced(project_root, base, set(keep) | set(code_paths),
                                      lean.doc_prefix(task_dir))
    if by_hand:
        print(f"  untraced : {lean.short(', '.join(map(lean.shown, by_hand)), 60)} "
              f"committed since start, not traced - compass changed-file add <path> "
              f"--scenario <id>")
    if no_request:
        from compass_pkg import request_link
        print(f"  request  : not recorded - `{request_link.command(task_dir)}`")
    asks = " and ".join(f"/compass:approve {number} ({what})" for number, what in waiting)
    from compass_pkg import approval_requests
    terminal = os.environ.get(approval_requests.CHANNEL_ENV) == "terminal"
    if terminal and waiting:
        # This host has no person-only approval event: the person runs the
        # command in their own terminal.
        held = {r.get("number"): r for r in approval_requests.pending(task_dir)}
        for number, _what in waiting:
            print("  approve  : " + approval_requests._terminal_command(held[number]))
        asks = "each `approve :` command above in their own terminal"
    if committed:
        for line in lean.commit_report(project_root, branch_note):
            print(line)
        if not waiting:
            print(lean.DONE)
            return 0
        # The change differs from the one a person approved.
        print(f"next: stop: the change differs from the one approved. Ask the person to "
              f"{'run' if terminal else 'type'} {asks}. Nothing else to run now.")
        return 0
    if commit_error:
        lines = commit_error.splitlines()
        print("  commit   : refused - " + lean.short(lines[0], 200))
        for line in lines[1:6]:
            print("    " + lean.short(line, 200))
        print("next: fix what the commit line names, then run the same finish again")
        return 1
    print(f"  files    : {len(code_paths) + len(documents)} traced from git")
    if not waiting:
        print("next: when the person asks for a commit, run compass ship-commit")
        return 0
    print(f"next: stop and ask the person to {'run' if terminal else 'type'} {asks}. "
          "Nothing else to run until then. After the approval, run the same finish again: "
          "it commits.")
    return 0
