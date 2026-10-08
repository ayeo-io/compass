#!/usr/bin/env python3
# =============================================================================
# compass_pkg.checks - the check registry
# =============================================================================
#
# DEPENDENCY: PyYAML, bundled at cli/vendor/yaml/ and pinned in
# THIRD-PARTY-NOTICES.md. cli/compass_pkg/__init__.py resolves it, and it is
# the only third-party code Compass ships; everything else is the Python 3
# standard library.
# =============================================================================

import argparse
import datetime
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile

# --- dependency check --------------------------------------------------------
# cli/compass_pkg/__init__.py already checked that the bundled copy resolves,
# or exited 3 naming the absolute path it checked, before this module's own
# code runs, so this is never anything but a normal import.
import yaml


import re as _re


import fnmatch
import re as _re
from compass_pkg.stable_ids import GATE_VERIFY_ANALYZE, GATE_VERIFY_CORRECTNESS
from compass_pkg.core import CompassError, artifact_location, artifact_path, find_compass_dir, find_governance, load_yaml, manifest_path, normalize_spine
from compass_pkg.manifest import TERMINAL_STATUSES
from compass_pkg.tdd import _read_config, settings_hint
from compass_pkg.trust import UNKNOWN, UNTRUSTED, contribution_trust, is_ci
from compass_pkg.check_results import NOTHING_TO_CHECK  # re-exported: callers still import it from here
from compass_pkg.evidence_identity import _check_evidence_identity_matches
from compass_pkg.project_commands import _contained_script, _project_commands_allowed



# --- command: check ----------------------------------------------------------

def _scenario_documented_in_spec(spec_path, scenario_id):
    """A `verifiable: narrative` scenario is 'documented' when its gherkin
    block in acceptance-criteria.md has a non-empty When AND Then. The
    When/Then is documentation-as-acceptance and lives only in
    acceptance-criteria.md (it has no structured home to duplicate), so
    reading it there is correct - not the mistake of grepping prose for a
    fact the manifest holds."""
    if not spec_path or not os.path.isfile(spec_path):
        return False
    try:
        lines = open(spec_path, encoding="utf-8").read().splitlines()
    except OSError:
        return False
    idx = None
    for i, ln in enumerate(lines):
        m = _re.search(r"<!--\s*traceability\s+id:\s*(\S+)", ln)
        if m and m.group(1).rstrip(" ·,") == scenario_id:
            idx = i
            break
    if idx is None:
        return False
    has_when = has_then = in_block = False
    for ln in lines[idx + 1:]:
        if _re.search(r"<!--\s*traceability\s+id:", ln):
            break                       # reached the next scenario
        if ln.strip().startswith("```"):
            if not in_block:
                in_block = True
                continue
            break                       # end of this scenario's gherkin block
        if in_block:
            if _re.match(r"\s*When\b", ln):
                has_when = True
            if _re.match(r"\s*Then\b", ln):
                has_then = True
    return has_when and has_then


def _check_declared_tests_resolve(task, task_dir):
    """`G1`: a scenario's declared test id must point at a test that exists.

    Without this, `compass check` reports green for a scenario naming a test
    nobody wrote - a test that is only *named* satisfies `G1` and `G3`, so the
    hole is invisible by construction.

    Scoped to issues that are still `active` AND have already claimed
    `verify.correctness: pass`. Both conditions matter:

      * Before correctness is claimed, a declared test legitimately does not
        exist yet - TDD writes the id at define and the test at implement.
      * After an issue lands, its manifest is a historical record. Tests get renamed
        afterwards, and re-checking history against a moving codebase produces
        failures nobody can act on (ADR-006).
    """
    # Scoped to the TERMINAL statuses, not to "not active". The vocabulary has
    # five, and `queued` and `parked` issues are still being worked on, so
    # the check must apply to them.
    status = (task.get("status") or "active").strip()
    if status in TERMINAL_STATUSES:
        return True, ("issue is %s - declared test ids are a historical record"
                      % status)

    gates = {g.get("id"): g.get("status") for g in (task.get("gates") or [])}
    if gates.get(GATE_VERIFY_CORRECTNESS) != "pass":
        return True, ("correctness not yet claimed - declared tests are still a "
                      "plan, not a claim")

    project_root = os.path.dirname(find_compass_dir())
    broken, skipped, checked = [], [], 0
    for s in (task.get("scenarios") or []):
        if s.get("verifiable") == "narrative":
            continue
        for tid in (s.get("tests") or []):
            verdict = _test_id_resolves(tid, project_root)
            if verdict is None:
                continue
            checked += 1
            if not verdict:
                broken.append(f"{s.get('id', '?')}: {tid}")
            elif _test_is_skipped(tid, project_root):
                skipped.append(f"{s.get('id', '?')}: {tid}")

    if broken:
        return False, ("declared test(s) do not resolve to a test on disk: "
                       + "; ".join(broken))
    if skipped:
        return False, ("declared test(s) resolve but are marked skipped, so "
                       "they never run and prove nothing: "
                       + "; ".join(skipped))
    return True, f"all {checked} declared test id(s) resolve and are runnable"


def _check_scenarios_have_tests(task, task_dir):
    scns = task.get("scenarios") or []
    if not scns:
        return False, "no scenarios in manifest.yml"
    spec_path = artifact_path(task_dir, "acceptance-criteria.md")
    missing_test, undocumented, documented_narr = [], [], 0
    for s in scns:
        sid = s.get("id", "?")
        # Narrative scenarios are assessed on documentation, never on a
        # test - so an incidental command does not buy a pass, and a documented
        # playbook does not need a fabricated one.
        if s.get("verifiable") == "narrative":
            if _scenario_documented_in_spec(spec_path, sid):
                documented_narr += 1
            else:
                undocumented.append(sid)
        elif not s.get("tests"):
            missing_test.append(sid)
    problems = []
    if missing_test:
        problems.append(f"scenarios with no test: {', '.join(missing_test)}")
    if undocumented:
        problems.append(
            f"narrative scenario(s) not documented (empty When/Then in "
            f"acceptance-criteria.md): {', '.join(undocumented)}")
    if problems:
        return False, "; ".join(problems)
    if documented_narr:
        return True, (f"all {len(scns)} scenario(s) accounted for "
                      f"({documented_narr} documented narrative, exempt from "
                      f"tests-required)")
    return True, f"all {len(scns)} scenario(s) list a test"


def _spec_sha256(task_dir):
    """Hash of the issue's acceptance-criteria.md, or None when there is no spec.

    This is what makes a recorded BDD run verifiable later. Comparing the
    record's timestamp against the spec's mtime would be simpler and wrong:
    `git checkout` and `git clone` rewrite mtimes, so a fresh CI clone would
    read every stale record as current - a false green in exactly the place it
    matters most.
    """
    path = artifact_path(task_dir, "acceptance-criteria.md")
    if not os.path.isfile(path):
        return None
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _check_scenarios_are_executable(task, task_dir):
    """Every scenario in manifest.yml was accounted for by the project's BDD runner.

    Reads the record written by `compass bdd verify`; never runs the suite.
    `compass check` is the fast mechanical gate - it runs in CI, in hooks, and
    on machines that never installed the project's dev dependencies, so it
    cannot depend on a BDD runner being present.

    The overwhelmingly common case is a project that has wired no runner at
    all. That passes, with a reason. A check that penalised projects for not
    opting in would be worse than no check (ADR-006).
    """
    proj = _read_config(task_dir).get("project") or {}
    runner = (proj.get("bdd_runner") or "").strip()
    if not runner:
        return NOTHING_TO_CHECK, ("no BDD runner wired (project.bdd_runner is unset) - "
                         "nothing to verify; see examples/bdd-adapters/ to opt in")

    scenario_ids = [s.get("id") for s in (task.get("scenarios") or [])
                    if isinstance(s, dict) and s.get("id")]
    if not scenario_ids:
        return NOTHING_TO_CHECK, "no scenarios recorded yet - nothing to verify"

    record_path = os.path.join(task_dir, "evidence", "bdd-run.json")
    if not os.path.isfile(record_path):
        return False, (f"project.bdd_runner is '{runner}' but no BDD run is on "
                       f"record - run `compass bdd verify -- <run command>`")
    try:
        with open(record_path, "r", encoding="utf-8") as fh:
            record = json.load(fh)
    except Exception as exc:                            # noqa: BLE001
        return False, f"evidence/bdd-run.json is unreadable ({exc})"

    current = _spec_sha256(task_dir)
    recorded = record.get("spec_sha256")
    if not current or not recorded:
        # A record with no spec hash cannot be shown to describe the spec it
        # claims to check. A record that cannot be checked is not a pass -
        # treating it as a pass is how a run made before the spec existed
        # stays green through every later edit.
        return False, ("the BDD run on record carries no spec hash, so it "
                       "cannot be shown to match the current acceptance-criteria.md - "
                       "re-run `compass bdd verify`")
    if current != recorded:
        return False, ("the recorded BDD run describes a different "
                       "acceptance-criteria.md than the one on disk - the spec has "
                       "changed since it ran, so the record is stale. Re-run "
                       "`compass bdd verify`.")

    if record.get("method") == "unverified":
        return True, ("the BDD run passed, but this runner does not report "
                      "which scenarios it bound and Compass has no tag selector "
                      "for it - so the binding is unverified rather than "
                      "unmet. See examples/bdd-adapters/ for a runner Compass "
                      "can verify.")

    seen = set(record.get("scenarios_seen") or [])
    missing = [sid for sid in scenario_ids if sid not in seen]
    if missing:
        return False, ("the BDD runner never accounted for: %s. Each needs a "
                       "step definition the runner can bind."
                       % ", ".join(missing))
    return True, ("all %d scenario(s) accounted for by %s"
                  % (len(scenario_ids), runner))


from compass_pkg.test_ids import _test_id_resolves, _test_is_skipped
from compass_pkg.red_first import missing_first_failure




def _check_suite_passed(task, task_dir):
    # Read test-run entries from the registry. An issue may have multiple
    # test-run entries (one per scenario binding); at least one must resolve
    # to a green-recorded file (exit_code 0), and any scenario binding must be
    # a real scenario in manifest.yml. A green shows the suite passes, not
    # that a test failed first, so a newer issue with scenarios also needs a
    # red or an acceptance record (red_first.py).
    registry = [e for e in (task.get("evidence") or [])
                if isinstance(e, dict) and e.get("type") == "test-run"]
    if not registry:
        return False, ("no test-run evidence in the registry - run "
                       "`compass tdd-green` to record a passing suite")
    scn_ids = {s.get("id") for s in (task.get("scenarios") or []) if isinstance(s, dict)}
    green = []
    for entry in registry:
        path = entry.get("path")
        if not path:
            return False, f"test-run evidence {entry.get('id', '?')} has no `path`"
        full = path if os.path.isabs(path) else os.path.join(task_dir, path)
        if not os.path.isfile(full):
            return False, f"test-run evidence {entry.get('id', '?')} path does not resolve: {path}"
        try:
            data = json.load(open(full, encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return False, f"test-run evidence {entry.get('id', '?')} unreadable: {exc}"
        if data.get("exit_code") != 0:
            return False, (f"test-run evidence {entry.get('id', '?')} records "
                           f"exit_code {data.get('exit_code')} - not green")
        scn = entry.get("scenario") or data.get("scenario")
        if scn and scn_ids and scn not in scn_ids:
            return False, (f"test-run evidence {entry.get('id', '?')} is bound "
                           f"to scenario '{scn}' which is not in manifest.yml")
        green.append(entry)
    missing = missing_first_failure(task, task_dir)
    if missing:
        return False, missing
    # What this establishes, stated exactly. A test-run record holds ONE exit
    # code for ONE command; it does not enumerate the tests that ran. So a
    # green suite does not establish which scenarios it exercised, and naming
    # the scenarios an evidence entry happens to be labelled with invited
    # exactly that reading. Per-scenario coverage needs the runner's own
    # result output parsed.
    return True, (f"{len(green)} test-run(s) on record, all green. This does "
                  f"not record which scenarios the run exercised")


def _git_out(args, cwd):
    """Run a git command, returning stdout or "" - never raising."""
    try:
        r = subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                           text=True, timeout=10)
        return r.stdout if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _path_was_deleted(path, project_root):
    """Did git record this path being deleted? Then its absence IS the change.

    Removing dead code is legitimate work, and the file it removes is
    legitimately absent afterwards. Only git can tell that apart from a
    record that is out of date. A deletion staged for the ship commit counts
    too: ship-commit needs the deleted path to be traced, so check must
    accept it before the commit as well as after (#368).
    """
    if _git_out(["diff", "--cached", "--diff-filter=D", "--name-only", "--",
                 path], project_root).strip():
        return True
    return bool(_git_out(["log", "--diff-filter=D", "--oneline", "-1", "--", path],
                         project_root).strip())


def _renamed_to(path, project_root):
    """Where git thinks a vanished path moved to, or None.

    A moved file is the common case and the fix is mechanical, so the error
    hands over the new path rather than starting an investigation.

    Rename records are read from history rather than with `--follow <path>`:
    `--follow` on a path that no longer exists reports the move as a delete
    plus an add, which is exactly the distinction being drawn here. The scan is
    bounded to the most recent rename commits - this is a hint, not an audit.
    """
    out = _git_out(["log", "--diff-filter=R", "-M", "--name-status",
                    "--format=", "-50"], project_root)
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) == 3 and parts[0].startswith("R") and parts[1] == path:
            return parts[2]
    return None


def _check_changed_code_traces(task, task_dir):
    changed = task.get("changed_files") or []
    scn_ids = {s.get("id") for s in (task.get("scenarios") or [])}
    if not changed:
        return True, "no changed_files recorded yet"
    problems = []
    for cf in changed:
        path = cf.get("path", "?")
        refs = cf.get("scenarios") or []
        if not refs:
            problems.append(f"{path} (no scenario)")
        else:
            dangling = [r for r in refs if r not in scn_ids]
            if dangling:
                problems.append(f"{path} -> unknown scenario(s) {', '.join(dangling)}")
    if problems:
        return False, "changed files not traced: " + "; ".join(problems)

    # A trace to a file that is no longer there is not a trace. The mapping
    # can be correct while every path points at nothing, because a refactor
    # moved the files. A guard that cannot fail is not a guard.
    #
    # Scoped the same way as `declared-tests-resolve`, and for the same reasons:
    #   * A landed issue's manifest is a historical record. Files move afterwards,
    #     and re-checking history against a moving codebase produces failures
    #     nobody can act on (ADR-006) - so it is reported, never failed.
    #   * Before correctness is claimed the record is still being built.
    project_root = os.path.dirname(find_compass_dir())
    missing = []
    for cf in changed:
        path = cf.get("path")
        if not path or os.path.exists(os.path.join(project_root, path)):
            continue
        # Rename first: `git log --diff-filter=D -- <path>` reports a rename as
        # a deletion too, so asking "was it deleted?" first would silently
        # excuse every moved file - the out-of-date path this check exists
        # to catch.
        moved_to = _renamed_to(path, project_root)
        if moved_to:
            missing.append(f"{path} (moved to {moved_to}?)")
            continue
        if _path_was_deleted(path, project_root):
            continue          # the deletion WAS the change
        missing.append(path)

    landed = (task.get("status") or "active") != "active"
    gates = {g.get("id"): g.get("status") for g in (task.get("gates") or [])}
    claimed = gates.get(GATE_VERIFY_CORRECTNESS) == "pass"

    if missing and not landed and claimed:
        return False, (
            f"{len(missing)} traced path(s) no longer exist: "
            + "; ".join(missing)
            + " - update changed_files to the current path, or remove the entry "
              "if the file was deleted"
        )
    if missing:
        why = "landed - historical record" if landed else "correctness not yet claimed"
        return True, (
            f"all {len(changed)} changed file(s) trace to a scenario, but "
            f"{len(missing)} no longer exist ({'; '.join(missing)}) - reported "
            f"only, because the issue is {why}"
        )
    return True, (f"all {len(changed)} changed file(s) trace to a scenario "
                  f"and are present on disk")


def _check_scenario_has_id_and_intent(task, task_dir):
    scns = task.get("scenarios") or []
    if not scns:
        return False, "no scenarios in manifest.yml"
    ids = {s.get("id") for s in scns if isinstance(s, dict)}
    problems = []
    for i, s in enumerate(scns):
        if not s.get("id"):
            problems.append(f"scenario #{i + 1} has no id")
        if not s.get("intent"):
            problems.append(f"scenario {s.get('id', '#' + str(i + 1))} has no linked intent")
        # A supersession pointing at nothing records nothing. The whole value of
        # the link is that a future reader can tell "this baseline failed
        # because the change landed as intended" from "something broke".
        for sup in (s.get("superseded_by") or []):
            if sup not in ids:
                problems.append(
                    f"scenario {s.get('id', '?')} is superseded_by "
                    f"'{sup}', which is not a scenario in this issue")
    if problems:
        return False, "; ".join(problems)
    return True, f"all {len(scns)} scenario(s) have an id and a linked intent"


def _check_claim_traces(task, task_dir):
    claims = task.get("claims") or []
    scn_ids = {s.get("id") for s in (task.get("scenarios") or [])}
    if not claims:
        return NOTHING_TO_CHECK, "no claims recorded (no marketer in play, or none yet)"
    problems = []
    for c in claims:
        ref = c.get("scenario")
        if not ref:
            problems.append(f"claim {c.get('id', '?')} has no backing scenario")
        elif ref not in scn_ids:
            problems.append(f"claim {c.get('id', '?')} -> unknown scenario {ref}")
    if problems:
        return False, "; ".join(problems)
    return True, f"all {len(claims)} claim(s) trace to a scenario"


def _check_gate_evidence(task, task_dir):
    gates = task.get("gates") or []
    if not gates:
        return False, "no gates in manifest.yml - has the delivery approach been evaluated?"
    registry = {e.get("id"): e for e in (task.get("evidence") or [])
                if isinstance(e, dict) and e.get("id")}
    # Load the evidence typing rules. The one extra yaml load per `check` run is
    # negligible, and it keeps the check signature simple.
    from compass_pkg import effective
    view = effective.view_or_legacy(task_dir)
    if view is not None:
        requirements, known_types = view.gate_requirements()
    else:
        try:
            gpolicy = load_yaml(os.path.join(find_governance(), "guardrails.yml"))
        except CompassError:
            gpolicy = {}
        known_types = set((gpolicy.get("evidence_types") or {}).keys())
        requirements = gpolicy.get("gate_evidence_requirements") or {}

    problems = []
    for g in gates:
        if g.get("status") != "pass":
            continue
        gid = g.get("id", "?")
        ev = g.get("evidence")
        # Gates reference evidence by id (a list). Reject the older inline
        # {type, path} dict form explicitly - the registry is the model.
        if isinstance(ev, dict):
            problems.append(f"{gid} uses the old inline-evidence shape "
                            f"({{type, path}}); convert to evidence ids "
                            f"referencing entries in the top-level "
                            f"`evidence:` registry. See templates/manifest.yml.")
            continue
        if isinstance(ev, str):
            ev = [ev]   # tolerate a bare id string as a one-element list
        if not ev:
            problems.append(f"{gid} marked pass with no evidence")
            continue
        accepted = requirements.get(gid)
        types_seen = set()
        for ev_id in ev:
            entry = registry.get(ev_id)
            if not entry:
                problems.append(f"{gid} references evidence id '{ev_id}' which "
                                f"is not in the issue's evidence registry")
                continue
            etype = entry.get("type")
            epath = entry.get("path")
            if not etype:
                problems.append(f"evidence {ev_id} has no `type`")
                continue
            if known_types and etype not in known_types:
                problems.append(f"evidence {ev_id} type '{etype}' is not a "
                                f"known type ({sorted(known_types)})")
                continue
            types_seen.add(etype)
            if epath and not os.path.exists(os.path.join(task_dir, epath)) \
                    and not os.path.exists(epath):
                problems.append(f"evidence {ev_id} ({etype}) path does not "
                                f"resolve: {epath}")
        if accepted and not (types_seen & set(accepted)):
            problems.append(f"{gid} requires evidence of type {accepted} but "
                            f"its referenced evidence is {sorted(types_seen)} - "
                            f"a mechanical gate cannot be cleared with the "
                            f"wrong kind of evidence")
    if problems:
        # Enumerate one problem per line so two mismatched gates surface
        # as two distinct, readable failures - not one concatenated string.
        return False, "\n         ".join(problems)
    passed = [g.get("id") for g in gates if g.get("status") == "pass"]
    return True, f"{len(passed)}/{len(gates)} pass gate(s), all backed by registry evidence of accepted type"


def _parse_dod_lines(task_dir):
    """Read verification-report.md from task_dir and return a list of DoD
    line strings found under the "Definition of Done" heading.

    Returns an empty list if the file is absent or the section is missing.
    This is the correct backward-compat behaviour (TRC-X4): no file → no
    items → check passes.
    """
    # Through the resolver, not a join. The report may live under
    # `docs/compass/<created>-<slug>/`, and a reader that builds its own path
    # to it does not fail when it moves - it finds nothing, returns no items,
    # and `dod-evidence-typed` passes on every issue in the repository.
    report_path = artifact_path(task_dir, "verification-report.md")
    if not os.path.isfile(report_path):
        return []
    with open(report_path, "r", encoding="utf-8") as fh:
        lines = fh.readlines()
    in_dod = False
    dod_lines = []
    for line in lines:
        stripped = line.rstrip("\n")
        # Detect the heading - allow any heading level (##, ###, ####)
        if stripped.strip().lstrip("#").strip() == "Definition of Done":
            in_dod = True
            continue
        if in_dod:
            # A new heading (line starting with #) ends the section
            if stripped.strip().startswith("#"):
                break
            dod_lines.append(stripped)
    return dod_lines

_DOD_ITEM_RE = _re.compile(r"^\s*-\s+\[([ xX])\]\s*(.*)")
_EVIDENCE_TAG_RE = _re.compile(r"\(evidence:\s*(EV-[^\)]+)\)")
# Both id spellings and both tag words. FU- is what the templates write
# now; BF- is what every archived verification report on disk says, and
# ADR-006 keeps the read side tolerant so those keep resolving.
_BACKFILL_TAG_RE = _re.compile(r"\((?:follow-up|backfill):\s*((?:FU|BF)-[^\)]+)\)")

# Evidence types accepted for DoD evidence (all types that represent real,
# typed evidence - not the catch-all `artifact` which is the weakest).
_DOD_ACCEPTED_EVIDENCE_TYPES = {
    "test-run",
    "command-output",
    "manual-review",
    "human-approval",
    "security-review",
    "migration-plan",
    "rollback-plan",
    "claim-review",
    "artifact",  # weakest but still typed - accepted for DoD
    "spike-conclusion",
}


def dod_tag_problems(rest, ev_registry, backfills):
    """The typed inline tag of an unchecked Definition of Done item, resolved.

    `rest` is the text after the checkbox. Returns None when it carries no
    evidence or follow-up tag, and otherwise the list of problems with the tag
    (empty when it resolves). The second and third arguments map ids to the
    manifest's evidence and follow-up entries. `dod-evidence-typed` and the
    stage lists both call this, so a tag means one thing."""
    ev_match = _EVIDENCE_TAG_RE.search(rest)
    bf_match = _BACKFILL_TAG_RE.search(rest)
    if not ev_match and not bf_match:
        return None
    problems = []
    if ev_match:
        ev_id = ev_match.group(1).strip()
        entry = ev_registry.get(ev_id)
        if not entry:
            problems.append(
                f"DoD item references evidence id '{ev_id}' which is not "
                f"in manifest.yml evidence registry"
            )
        elif entry.get("type") not in _DOD_ACCEPTED_EVIDENCE_TYPES:
            problems.append(
                f"DoD item references evidence '{ev_id}' with type "
                f"'{entry.get('type')}' which is not an accepted DoD "
                f"evidence type"
            )
    if bf_match:
        bf_id = bf_match.group(1).strip()
        bf_entry = backfills.get(bf_id)
        if not bf_entry:
            problems.append(
                f"DoD item references follow-up id '{bf_id}' which is not "
                f"in manifest.yml follow-ups"
            )
        elif bf_entry.get("status") not in ("outstanding", "resolved"):
            problems.append(
                f"follow-up '{bf_id}' has unrecognised status "
                f"'{bf_entry.get('status')}' (must be 'outstanding' "
                "or 'resolved')"
            )
        # outstanding and resolved both pass here; resolving is a
        # separate concern tracked by _check_backfills_paid
    return problems


def _check_dod_evidence_typed(task, task_dir):
    """Parse the DoD section of verification-report.md and enforce the
    inline-tag rule:

    - `- [x] ...`                  → passes (human ticked it)
    - `- [ ] (evidence: EV-id) ...` → passes if EV-id is in the evidence
                                       registry with an accepted type
    - `- [ ] (follow-up: FU-id) ...` → passes if FU-id is in manifest.yml
                                       follow_ups with status: outstanding
    - `- [ ] <bare description>`   → FAILS (evidence, not assertion - `G4`)

    Cross-issue half: scan sibling manifest.yml files for follow-ups with
    target_task equal to this issue's slug and status: outstanding - any such entry
    blocks shipping this issue.
    """
    dod_lines = _parse_dod_lines(task_dir)

    # Build lookup structures from this issue
    ev_registry = {
        e.get("id"): e
        for e in (task.get("evidence") or [])
        if isinstance(e, dict) and e.get("id")
    }
    backfills = {
        b.get("id"): b
        for b in (task.get("follow_ups") or [])
        if isinstance(b, dict) and b.get("id")
    }

    problems = []
    item_count = 0

    for raw in dod_lines:
        m = _DOD_ITEM_RE.match(raw)
        if not m:
            continue  # not a checklist item - skip (comments, blank lines, etc.)
        item_count += 1
        checked, rest = m.group(1), m.group(2)

        if checked.lower() == "x":
            # Human-ticked - passes unconditionally
            continue

        # Unchecked - must have an inline tag
        tag_problems = dod_tag_problems(rest, ev_registry, backfills)
        if tag_problems is None:
            # Bare unchecked - fails `G4` (evidence, not assertion)
            desc = rest.strip() or raw.strip()
            problems.append(
                f"bare unchecked DoD item (no evidence or follow-up tag): "
                f"'{desc}' - add (evidence: EV-<id>) or (follow-up: BF-<id>) "
                f"inline tag, or tick the box if done. Evidence, not "
                f"assertion."
            )
            continue
        problems.extend(tag_problems)

    # Cross-issue check: scan sibling issues for follow-ups that
    # target this issue and are still outstanding. Use the directory name as the slug
    # (authoritative) in preference to task.get("task") which may be a
    # template placeholder; the directory name is always the true slug.
    this_slug = os.path.basename(task_dir) or task.get("task") or ""
    sibling_problems = _check_inbound_backfills(task_dir, this_slug)
    problems.extend(sibling_problems)

    if problems:
        return False, "; ".join(problems)

    # "Nothing to evidence" and "everything is typed" print the same green
    # line. A check that never found the report says the first. So print
    # the report's path; `artifact_location` says where it looked when
    # there is nothing there.
    where = artifact_location(task_dir, "verification-report.md")
    if item_count == 0:
        return True, ("DoD section is empty or absent - nothing to evidence "
                      "(read %s)" % where)
    return True, ("all %d DoD item(s) are typed or human-ticked (read %s)"
                  % (item_count, where))



def _check_inbound_backfills(task_dir, this_slug):
    """Scan sibling issue directories for follow-ups with target_task == this_slug
    and status: outstanding. Each such entry is a blocking cross-issue
    debt."""
    problems = []
    # task_dir is .compass/work/<slug>/; sibling dirs are alongside it
    work_dir = os.path.dirname(task_dir)
    if not os.path.isdir(work_dir):
        return problems
    for entry in os.listdir(work_dir):
        sibling = os.path.join(work_dir, entry)
        if sibling == task_dir:
            continue
        tp = manifest_path(sibling)
        if not os.path.isfile(tp):
            continue
        try:
            with open(tp, "r", encoding="utf-8") as fh:
                try:
                    import yaml as _yaml
                    sibling_task = normalize_spine(_yaml.safe_load(fh) or {})
                except Exception:
                    continue
        except OSError:
            continue
        for bf in (sibling_task.get("follow_ups") or []):
            if not isinstance(bf, dict):
                continue
            if (bf.get("target_task") == this_slug
                    and bf.get("status") == "outstanding"):
                src_slug = sibling_task.get("task") or entry
                problems.append(
                    f"cross-issue block: issue '{src_slug}' has follow-up "
                    f"'{bf.get('id', '?')}' (status: outstanding) targeting this "
                    f"issue - resolve it with `compass follow-up resolve "
                    f"--issue {src_slug} {bf.get('id', '?')}` before shipping"
                )
    return problems


def _check_human_approval(task, task_dir):
    # Approvals are typed evidence in the registry. `G5` applies when the issue
    # touches irreversible surface (the routing policy sets its approach to
    # initiative at least); this check looks for a `human-approval` entry
    # with decision=approved and the needed structured fields.
    registry = task.get("evidence") or []
    approvals = [e for e in registry if isinstance(e, dict)
                 and e.get("type") == "human-approval"]
    approved = [a for a in approvals if a.get("decision") == "approved"]
    if not approved:
        # `G5` also fires on critical risk. A landed issue cleared the gates in
        # force when it landed, so report this and do not fail it. There is
        # no gap: an issue becomes `landed` only after the gates pass while
        # it is active.
        if (task.get("status") or "active") != "active":
            return True, ("no human-approval evidence on record, and the issue "
                          "has landed - reported only, because its gates were "
                          "cleared under the trigger in force at the time")
        return False, ("no human-approval evidence with decision=approved - "
                       "the human-sign-off guardrail applies because this issue "
                       "touches irreversible surface, or its risk is critical "
                       "(which the "
                       "router defines as: can lose data, lose money, breach "
                       "auth/privacy, or resist a clean rollback). Add a "
                       "`human-approval` entry to the evidence registry with "
                       "approver, role, scope, decision, and timestamp.")
    a = approved[0]
    missing = [k for k in ("approver", "role", "scope", "timestamp")
               if not a.get(k)]
    if missing:
        return False, (f"approval {a.get('id', '?')} is missing required "
                       f"field(s): {', '.join(missing)}. A human-approval "
                       f"evidence entry must record who approved, in what role, "
                       f"the scope, and when.")
    return True, (f"approval on record: {a.get('approver')} "
                  f"({a.get('role')}) - scope: {a.get('scope')}")


def _check_backfills_paid(task, task_dir):
    bfs = task.get("follow_ups") or []
    unpaid = [b.get("id", "?") for b in bfs if b.get("status") != "resolved"]
    if unpaid:
        return False, f"outstanding follow-up(s): {', '.join(unpaid)}"
    return True, ("no outstanding follow-ups" if not bfs
                  else f"all {len(bfs)} follow-up(s) resolved")


def _check_spike_conclusion_present(task, task_dir):
    registry = task.get("evidence") or []
    concs = [e for e in registry if isinstance(e, dict)
             and e.get("type") == "spike-conclusion"]
    if not concs:
        return False, ("no `spike-conclusion` evidence on record - a Spike "
                       "must record what it learned and a close-out decision "
                       "(discard | graduate-to-delivery | defer) before it "
                       "closes")
    c = concs[0]
    valid = ["discard", "graduate-to-delivery", "defer"]
    decision = c.get("decision")
    if decision not in valid:
        return False, (f"spike-conclusion {c.get('id', '?')} has "
                       f"decision={decision!r}; it must be one of {valid}")
    if decision == "graduate-to-delivery" and not c.get("next_task"):
        return False, (f"spike-conclusion {c.get('id', '?')} graduates to "
                       f"delivery, but `next_task:` is empty - link the new "
                       f"issue (e.g. .compass/work/<new-slug>/). Graduation is "
                       f"a fresh assessment, not a merge.")
    nt = f" -> {c['next_task']}" if c.get("next_task") else ""
    return True, f"spike close-out on record: {decision}{nt}"


def _check_spike_no_production_changes(task, task_dir):
    cf = task.get("changed_files") or []
    if cf:
        paths = [c.get("path", "?") for c in cf if isinstance(c, dict)]
        return False, (f"a Spike must not list production changed_files "
                       f"(found: {paths}). Exploration code stays on a scratch "
                       f"branch; if the finding is acted on, a fresh "
                       f"assessment owns the code under a real route's "
                       f"guardrails. This is the safety model - a Spike "
                       f"cannot silently become delivery.")
    return True, "no production changed_files (correct - a Spike ships nothing)"


def _load_quarantine_registry(gov_dir):
    """Load governance/quarantine.yml and return a dict of test id -> entry.

    Returns a dict mapping test id -> entry, so callers can check for
    tracking_task presence. Returns an empty dict if quarantine.yml is absent
    (zero-setup default, ADR-006).
    """
    path = os.path.join(gov_dir, "quarantine.yml")
    if not os.path.isfile(path):
        return {}
    try:
        data = load_yaml(path)
    except CompassError:
        return {}
    result = {}
    for entry in (data.get("quarantined") or []):
        if isinstance(entry, dict) and entry.get("test"):
            result[entry["test"]] = entry
    return result


def _check_no_trusted_rerun(task, task_dir):
    """`G4` extension: check that no test-run evidence records a
    rerun-to-green without either:
      (a) the test being listed in governance/quarantine.yml with a tracking_task, OR
      (b) evidence with `attempts`:1 (clean first pass), OR
      (c) no `attempts` field at all (old evidence - backward compat).

    Failure cases:
      - rerun_without_change: true AND test not quarantined → FAIL
      - `attempts` > 1 AND rerun_without_change absent → FAIL (incomplete evidence)

    This check reads governance/quarantine.yml at runtime; the registry is
    loaded lazily so zero-setup projects (no quarantine.yml) pass trivially.
    """
    registry_entries = [
        e for e in (task.get("evidence") or [])
        if isinstance(e, dict) and e.get("type") == "test-run"
    ]
    if not registry_entries:
        return True, "no test-run evidence to evaluate"

    # Load quarantine registry once
    try:
        gov = find_governance()
    except CompassError:
        gov = None
    quarantine = _load_quarantine_registry(gov) if gov else {}

    problems = []
    notes = []
    for entry in registry_entries:
        path = entry.get("path")
        ev_id = entry.get("id", "?")
        # Try to read the evidence file to get `attempts`/rerun_without_change
        green_data = {}
        if path:
            full = path if os.path.isabs(path) else os.path.join(task_dir, path)
            if os.path.isfile(full):
                try:
                    green_data = json.load(open(full, encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    green_data = {}
        # Also check the registry entry itself for the fields (tdd-green upserts
        # them there from the payload)
        attempts = green_data.get("attempts") if "attempts" in green_data else entry.get("attempts")
        rerun_flag = (green_data.get("rerun_without_change")
                      if "rerun_without_change" in green_data
                      else entry.get("rerun_without_change"))
        test_id = green_data.get("test") or entry.get("test")

        # Case 1: backward compat - no `attempts` field → trivial pass
        if attempts is None:
            continue

        # Case 2: `attempts` > 1, rerun_without_change absent → incomplete evidence
        if isinstance(attempts, int) and attempts > 1 and rerun_flag is None:
            problems.append(
                f"evidence {ev_id}: attempts={attempts} but rerun_without_change "
                f"marker is absent - incomplete evidence clears nothing. "
                f"Either add the marker (with evidence that no source change "
                f"intervened) or quarantine the test in governance/quarantine.yml "
                f"with a tracking_task (TRC-FM3)"
            )
            continue

        # Case 3: rerun_without_change: true → test must be quarantined
        if rerun_flag:
            if not test_id:
                problems.append(
                    f"evidence {ev_id}: rerun_without_change:true but no `test` "
                    f"field to look up in the quarantine registry - add the test "
                    f"id to the evidence record"
                )
                continue
            if test_id not in quarantine:
                problems.append(
                    f"evidence {ev_id}: test '{test_id}' ran {attempts} time(s) "
                    f"and passed without a source change (rerun_without_change:true) "
                    f"but is not in governance/quarantine.yml - a rerun-to-green is "
                    f"the loss of the most useful signal. Fix the root cause "
                    f"or add the test to governance/quarantine.yml with a "
                    f"tracking_task (TRC-A3)"
                )
            else:
                q_entry = quarantine[test_id]
                notes.append(
                    f"evidence {ev_id}: test '{test_id}' is quarantined "
                    f"(tracking: {q_entry.get('tracking_task', '?')}) - "
                    f"rerun-to-green noted; fix tracked"
                )

    if problems:
        return False, "; ".join(problems)
    note_str = f" (quarantine notes: {len(notes)})" if notes else ""
    return True, f"no trusted-rerun violations{note_str}"


def _check_coherence_check_passes(task, task_dir):
    """`G4` extension (ADR-007): verify.analyze needs a consistency-check
    evidence entry with zero findings. Only runs when verify.analyze is in the
    issue's gate set. If the gate is absent, this check trivially passes (the
    issue is not subject to the consistency-check requirement)."""
    gates = task.get("gates") or []
    gate_ids = [g.get("id") for g in gates if isinstance(g, dict)]
    if GATE_VERIFY_ANALYZE not in gate_ids:
        return True, "verify.analyze not in gate set - consistency check not required"
    # Gate is present: look for a consistency-check typed evidence entry
    registry = {e.get("id"): e for e in (task.get("evidence") or [])
                if isinstance(e, dict) and e.get("id")}
    coherence_entries = [e for e in registry.values()
                         if e.get("type") == "consistency-check"]
    if not coherence_entries:
        return False, ("no consistency-check evidence on record - run "
                       "`compass analyze` to produce the required "
                       "consistency-check evidence for verify.analyze")
    # Check that the most recent entry records zero findings
    entry = coherence_entries[-1]
    path = entry.get("path")
    if path:
        full = path if os.path.isabs(path) else os.path.join(task_dir, path)
        if os.path.isfile(full):
            try:
                data = json.load(open(full, encoding="utf-8"))
                n = data.get("finding_count", None)
                if n is not None and n != 0:
                    return False, (f"consistency-check evidence records "
                                   f"{n} finding(s) - resolve them before "
                                   f"clearing verify.analyze")
            except (OSError, json.JSONDecodeError):
                pass  # readable but corrupt - gate-evidence-present catches it
    return True, "consistency-check evidence on record - verify.analyze gate cleared"


def _check_command_passes(task, task_dir):
    """ADR-009: run each project guardrail's declared `command:`
    and report pass/fail.

    Behaviour:
    - When verify.architecture is in the gate set but zero project guardrails
      declare check: command-passes → nothing-to-check pass (DD-6).
    - For each project guardrail with check: command-passes, run
      subprocess.run(shell=True, timeout=timeout_seconds) from the project
      root (inferred as the directory 2 levels above task_dir, which is
      .compass/work/<slug>).
    - All commands must exit 0 for the check to pass.
    - If any command exits non-zero, the check fails with exit code + stderr.

    This check is purely mechanical: no network call, no LLM client (TRC-F2).
    """
    # Locate the project root (2 levels up from task_dir: .compass/work/<slug>)
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(task_dir)))
    if not os.path.isdir(project_root):
        project_root = os.getcwd()

    # Load the guardrails to find project guardrails with check: command-passes
    from compass_pkg import effective
    view = effective.view_or_legacy(task_dir)
    if view is not None:
        project_guardrails = view.command_checks()
    else:
        try:
            gov = find_governance()
            gpolicy = load_yaml(os.path.join(gov, "guardrails.yml"))
        except CompassError:
            gpolicy = {}
        project_guardrails = gpolicy.get("project") or []
    cp_guardrails = [
        g for g in project_guardrails
        if isinstance(g, dict) and "command-passes" in (g.get("checks") or [])
    ]

    # The trust decision comes BEFORE the opt-in, and that order is the whole
    # security property. A hostile pull request could add the command and
    # turn the opt-in on together; it cannot change what the CI runner
    # reports about where the contribution came from. See
    # cli/compass_pkg/trust.py.
    if cp_guardrails:
        state, reason = contribution_trust(project_root=project_root)
        # Fail closed on a runner we cannot read. UNKNOWN on a laptop is
        # ordinary and runs; UNKNOWN on CI means something is being checked and
        # Compass cannot tell whose work it is, which is the case that refuses.
        if state == UNKNOWN and is_ci():
            state = UNTRUSTED
        if state == UNTRUSTED:
            return False, (
                f"refused to run {len(cp_guardrails)} project command(s): "
                f"{reason}. Any `allow_project_commands` setting in this "
                f"repository is ignored here and was not read - the refusal "
                f"is decided from the CI runner's own environment, which a "
                f"contribution cannot edit"
            )

    # nothing-to-check pass (DD-6): verify.architecture in gate set, zero command-passes
    # guardrails declared → the gate has nothing to check; it passes without checking anything.
    if not cp_guardrails:
        return NOTHING_TO_CHECK, ("verify.architecture: this project declares no guardrail "
                         "that runs a command, so there was nothing to check "
                         "and this passed without checking anything. To add "
                         "architecture checks, declare a project guardrail with "
                         "`check: command-passes`")

    # The opt-in, read AFTER the trust decision above. Running a declared
    # command is a deliberate choice, and the default is off.
    #
    # This returns nothing-to-check rather than a pass or a failure, and the
    # distinction is the point. A pass would be a check that cannot fail - it
    # would report green having run nothing. A failure would turn red the
    # build of every project that declared a command before upgrading. Nothing-
    # to-check does not fail the run and is counted apart from the passes, so a
    # guardrail that stopped running is visible rather than silent.
    if not _project_commands_allowed(task_dir):
        names = ", ".join(
            f"{g.get('id', '?')} ({g.get('name', 'unnamed')})" for g in cp_guardrails)
        return NOTHING_TO_CHECK, (
            f"{len(cp_guardrails)} project guardrail(s) declare a command and "
            f"NONE were run, because project commands are disabled: {names}. "
            f"This is a declaration that exists and was not checked, not an "
            f"absence of declarations. To run them, set "
            + settings_hint(task_dir, "allow_project_commands", "true"))

    failures = []
    for g in cp_guardrails:
        params = g.get("params") or {}
        command = params.get("command")
        script = params.get("script")
        gid = g.get("id", "?")

        if script is not None and command is not None:
            failures.append(
                f"project guardrail {gid}: declares both `script` and "
                f"`command` - pick one. A precedence rule here would be a "
                f"quiet way to get the shell back"
            )
            continue

        if script is not None:
            resolved = _contained_script(script, project_root)
            if resolved is None:
                failures.append(
                    f"project guardrail {gid} ({g.get('name', 'unnamed')}): "
                    f"`script: {script}` resolves outside the project root and "
                    f"was not run. The check is made on the real path, so a "
                    f"symlink inside the project pointing out of it is refused "
                    f"too"
                )
                continue
            argv = [sys.executable, resolved] if resolved.endswith(".py") else [resolved]
            raw_args = params.get("args") or []
            if not isinstance(raw_args, list) or not all(
                    isinstance(a, str) for a in raw_args):
                failures.append(
                    f"project guardrail {gid}: `args` must be a list of "
                    f"strings - they are passed to the script as separate "
                    f"arguments, never joined into a command line"
                )
                continue
            argv.extend(raw_args)
        elif not command or not isinstance(command, str):
            failures.append(
                f"project guardrail {gid}: missing or non-string "
                f"`command` in params - declaration is malformed"
            )
            continue

        timeout = params.get("timeout_seconds", 300)
        if timeout == 0:
            timeout = None  # 0 = no timeout (discouraged)
        try:
            proc = subprocess.run(
                argv if script is not None else command,
                shell=script is None,
                timeout=timeout,
                capture_output=True,
                text=True,
                cwd=project_root,
            )
            if proc.returncode != 0:
                stderr_snippet = (proc.stderr or "").strip()[:200]
                failures.append(
                    f"project guardrail {g.get('id', '?')} "
                    f"({g.get('name', 'unnamed')}): command exited {proc.returncode}"
                    + (f"; stderr: {stderr_snippet}" if stderr_snippet else "")
                )
        except subprocess.TimeoutExpired:
            failures.append(
                f"project guardrail {g.get('id', '?')} "
                f"({g.get('name', 'unnamed')}): command timed out "
                f"after {timeout}s"
            )
        except Exception as exc:
            failures.append(
                f"project guardrail {g.get('id', '?')} "
                f"({g.get('name', 'unnamed')}): command error: {exc}"
            )

    if failures:
        return False, "; ".join(failures)

    n = len(cp_guardrails)
    return True, (f"{n} command-passes guardrail(s) all exited 0 - "
                  f"architectural fitness checks pass")
