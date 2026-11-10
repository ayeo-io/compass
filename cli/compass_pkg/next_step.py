# compass_pkg.next_step - the one command that comes next on an issue
"""Decide the `next:` command from an issue's records (ADR-092).

`compass next` prints the issue's stage and then `next: <command>`. One
function, `next_command`, decides the command, so `compass next` and the verbs
that will print the same part cannot disagree. The rows below are read top to
bottom, and the first that matches gives the command:

| Records show | `next:` |
|---|---|
| no manifest | `/compass:go "<what you want>"` |
| landed, `ship-approval` owed, none on record | `compass issue link set --pr <n> --issue <slug>` after the merge, or `compass evidence request --ship` (only the second once the merge is recorded) |
| landed with its record (`landed_with_record`), the issue folder holds a change git has not committed | `compass record commit --issue <slug>` |
| closed | none |
| a spike with no conclusion | `compass evidence add EV-SPIKE --type spike-conclusion ...` |
| `request` owed, the link or the requester not recorded, no waiver in force | `compass issue link set --issue <slug> --request <url> --requester <name>` |
| assessed, no scenario | `compass scenario add TRC-001 ...` |
| a scenario with no test | `compass scenario tests set <id> --test <path::name>` |
| `nfr-rows-resolved` fails (a path issue) | `fill the Non-functional requirements rows of <spec>: ...` |
| `scenario-approval` owed, no outcome | `compass evidence request --checkpoint specify` |
| `S17` applies, no outer-loop red | `compass tdd-red --loop outer --scenario <id> -- ...`, after writing and staging the layering test where `layering` is owed |
| a scenario with no red | `compass tdd-red --scenario <id> -- <test command>` |
| `S17` applies, no outer-loop green | `compass tdd-green --loop outer --scenario <id> --candidate ... --client ... -- ...` |
| a red with no green | `compass tdd-green --scenario <id> -- <test command>` |
| `isolation` owed | `compass isolation record --candidate ... --client ... --parallel ... --repeat ...` |
| `layering` owed | `compass layering record --test-path <path> -- <layering test command>` |
| a Definition of Done item open | `compass evidence add <EV-id> ... --meets <item>` |
| a review gate pending | `compass gate pass <gate> --evidence <EV-id>` (on a path issue, not one of the three immovable gates) |
| `human-approval` owed | `compass evidence request --check human-approval-present` |
| a listed checkpoint with no outcome | `compass evidence request --checkpoint <stage>` |
| a path issue, only the three immovable gates pending | `compass quick-fix finish -m "<commit message>" --no-commit -- <test command>`, with `--candidate ... --client ...` where its green is an in-scope outer-loop green |
| every gate passes | `compass check, then git add <the traced files>, then compass ship-commit --issue <slug> -m "<message>"`, with `--release-note "<release line>"` when the issue owes a release line and holds none; in committed mode the traced files under the issue and documents folders are left out, because `compass ship-commit` stages them |

What is owed comes from `evidence_required` on a path issue. An issue assessed
before the path has no such list, so its owed evidence is read from the records
it has: the `S17` rows from its stored `acceptance_strategy` block and the
Definition of Done from a `thorough` verify stage, as `compass check` judges
them. The rows that only the path adds (`scenario-approval`, `human-approval`)
are not owed on an old issue; `compass check` still judges its own rules.

The words in angle brackets are for the reader to fill in. This module reads
records only and never writes. `announce` prints the `next:` line at the end of
each verb that writes a record, and `owed_commands` lists what `compass
quick-fix finish` refuses on while it is owed.
"""
# DEPENDENCY: standard library (os, shlex); compass_pkg.next_line, path_stages, red_first,
# stable_ids and status_words, and inside functions the readers of
# acceptance_strategy, checkpoint_outcomes, checks, effective, gate_status, release_line,
# request_link, ship_approval, tdd, tdd_green, waiver_records and item_records, and core, next_cmd and
# terminal for `announce`. It must not import next_cmd at load time: next_cmd imports it.
from __future__ import annotations

import os
import shlex

from compass_pkg import next_line, path_stages, red_first, status_words
from compass_pkg.stable_ids import (APPROACH_SPIKE, GATE_VERIFY_CORRECTNESS,
                                    GATE_VERIFY_GOVERNANCE, GATE_VERIFY_TRACEABILITY,
                                    MODE_THOROUGH, REMOVED_GATE_IDS,
                                    STAGE_SPECIFY, STAGE_VERIFY)

GO = '/compass:go "<what you want>"'
#: The gates `compass quick-fix finish` passes itself (`quick_fix_cmd.THREE_GATES`).
IMMOVABLE_GATES = (GATE_VERIFY_CORRECTNESS, GATE_VERIFY_GOVERNANCE, GATE_VERIFY_TRACEABILITY)
FINISH = 'compass quick-fix finish -m "<commit message>" --no-commit -- <test command>'
FIRST_SCENARIO = "TRC-001"
SPIKE_GATE = "spike.conclude"
#: The routings of `S17` that owe each strategy record on an old issue, as the
#: preset routed them (`acceptance_strategy.ROUTINGS`).
_LEGACY_ROUTINGS = {"outer-loop": ("existing-dsl", "existing-dsl-isolation", "on"),
                    "isolation": ("existing-dsl-isolation", "on"),
                    "layering": ("on",)}
#: The interfaces an outer-loop run can drive (`candidate_client.CLIENTS`).
_CLIENTS = ("api", "web", "cli")
_LAYERING_COMMAND = ("compass layering record --test-path <layering test path> "
                     "-- <layering test command>")
#: The record file each strategy command writes.
_ISOLATION_RECORD = "isolation-proof.json"
_LAYERING_RECORD = "layering.json"


def next_command(task, task_dir, done=None):
    """The command that comes next on the issue, or None for a closed issue.

    The first argument is the loaded manifest, or None when there is none.
    `done` is the set of stages the records show as done, when the caller
    already has it; the checkpoint row reads it. A fault in a reader gives `compass check`, which
    says what is missing, so `compass next` still prints a line.
    """
    if not isinstance(task, dict):
        return GO
    if status_words.is_closed(task):
        try:
            return (ship_approval_command(task, task_dir)
                    or record_commit_command(task, task_dir))
        except Exception:  # noqa: BLE001 - a closed issue's line must still print
            return None
    try:
        return _first_match(task, task_dir, done)
    except Exception:  # noqa: BLE001 - the stage line must still print
        return "compass check"


def _first_match(task, task_dir, done):
    if task.get("delivery_approach") == APPROACH_SPIKE:
        spike = _spike(task)
        if spike:
            return spike
    else:
        # The request comes first, so assess asks for it (#356). A waiver a person
        # approved excuses it, and then `next` stops asking.
        if _request_missing(task, task_dir):
            from compass_pkg import request_link
            return request_link.command(task_dir)
        if path_stages.is_path_issue(task):
            return _lean(task, task_dir)
        for row in (_specify, _build, _ship):
            command = row(task, task_dir)
            if command:
                return command
    # On the path `compass quick-fix finish` passes the three immovable gates
    # itself, so they come last, once nothing else is owed.
    on_path = path_stages.is_path_issue(task) and task.get("delivery_approach") != APPROACH_SPIKE
    gate = _pending_gate(task, skip=IMMOVABLE_GATES if on_path else ())
    if gate:
        return f"compass gate pass {gate} --evidence <EV-id>"
    if _owed(task, task_dir, "human-approval") and not _human_approval(task, task_dir):
        return "compass evidence request --check human-approval-present"
    stage = _checkpoint_waiting(task, done)
    if stage:
        return f"compass evidence request --checkpoint {stage}, then stop for /compass:approve"
    if on_path and _pending_gate(task):
        return _finish(task_dir)
    return _ship_commit(task, task_dir)


LEAN_FINISH = 'compass quick-fix finish -m "<commit message>" -- <test command>'


def _lean(task, task_dir):
    """The next step of a delivery issue on the lean path (branch exp-lean):
    the scenario approval where it is owed, then the tests and the code, then
    `compass quick-fix finish`, then the approvals a person owes, then
    `compass ship-commit`. No row names `tdd-red`, `tdd-green`, `scenario add`,
    `changed-file add`, `evidence add` or `gate pass`: `finish` does their work."""
    from compass_pkg import approval_requests, lean
    owed = lean.specify_owed(task, task_dir) if task_dir else None
    if owed:
        return owed
    if _pending_gate(task) or not greens(task):
        return f"write the tests and the code, then {LEAN_FINISH}"
    waiting = []
    if task_dir:
        subjects = {("guardrail", "G5"): "the `G5` sign-off", ("ship", None): "the ship approval"}
        # A request answered in the person's terminal stays pending, so a
        # request counts only while its approval is not on record.
        from compass_pkg import ship_approval
        if not (_owed(task, task_dir, "human-approval") and not _human_approval(task, task_dir)):
            subjects.pop(("guardrail", "G5"))
        if not ship_approval.owed(task) or \
                ship_approval._check_ship_approval_present(task, task_dir)[0] is True:
            subjects.pop(("ship", None))
        waiting = [(r.get("number"), subjects[(r.get("form"), r.get("value"))])
                   for r in approval_requests.pending(task_dir)
                   if (r.get("form"), r.get("value")) in subjects]
    if waiting:
        asks = " and ".join(f"/compass:approve {n} ({what})" for n, what in waiting)
        return (f"stop and ask the person to type {asks}. After the approval, run the same "
                "finish again: it commits")
    if _owed(task, task_dir, "human-approval") and not _human_approval(task, task_dir):
        return f"{LEAN_FINISH}, which asks for the `G5` sign-off"
    return (f"{LEAN_FINISH} (it commits), or compass ship-commit on the branch the "
            "person names")


def ship_approval_command(task, task_dir):
    """On a landed issue that owes `ship-approval` and has none on record, the
    command that records it; else None (#355, ADR-095).

    The approval comes after the landing: `ship-commit` closes the issue before
    the pull request merges, and `compass issue link set --pr` reads the review
    after the merge. Once the merge is recorded the reviews have been read, so
    only the typed approval is left. An issue closed for another reason owes
    nothing more."""
    from compass_pkg import ship_approval
    if not status_words.is_completed(task) or not ship_approval.owed(task) or not task_dir:
        return None
    if ship_approval._check_ship_approval_present(task, task_dir)[0] is True:
        return None
    typed = "compass evidence request --ship, then stop for /compass:approve"
    pr = task.get("pull_request") if isinstance(task.get("pull_request"), dict) else {}
    if pr.get("merged_at"):
        return typed
    number = pr.get("number") if pr.get("number") is not None else "<n>"
    slug = os.path.basename(os.path.normpath(task_dir))
    return (f"compass issue link set --pr {number} --issue {slug} after the merge, "
            f"or {typed}")


def record_commit_command(task, task_dir):
    """On an issue whose record landed with the code, `compass record commit`
    when its folder holds a change git has not committed; else None (#356).

    `compass issue link set --pr` writes the merge fields after the commit
    that holds the record, so they reach the record by a second commit. This
    reads `git status` of the issue folder and writes nothing; git leaves out
    the files `.compass/work/.gitignore` names."""
    from compass_pkg import record_mode
    from compass_pkg.core import find_upwards
    if (not task_dir or task.get("landed_with_record") is not True
            or not status_words.is_completed(task)):
        return None
    root = find_upwards(task_dir, ".compass")
    if not root or record_mode.mode(root, task_dir).mode != record_mode.COMMITTED:
        return None
    found = record_mode._git(["--literal-pathspecs", "status", "--porcelain",
                              "--untracked-files=all", "--", str(task_dir)], root)
    if found is None or found.returncode != 0 or not found.stdout.strip():
        return None
    return f"compass record commit --issue {os.path.basename(os.path.normpath(task_dir))}"


def _finish(task_dir):
    """`compass quick-fix finish`, with `--candidate` and `--client` where it needs
    them: `finish` records its green on the loop `tdd.default_loop` picks, and an
    outer-loop green on an issue `S17` applies to is refused without both
    (ADR-085, `candidate_client.named`)."""
    from compass_pkg.tdd import default_loop
    from compass_pkg.tdd_green import strategy_applies
    if default_loop(task_dir) == "outer" and strategy_applies(task_dir):
        return FINISH.replace(
            " --no-commit ",
            f" --no-commit --candidate <build id>|local --client {'|'.join(_CLIENTS)} ")
    return FINISH


def _ship_commit(task, task_dir):
    """The last step: `compass ship-commit` lands what is staged, and `quick-fix
    finish --no-commit` leaves the change unstaged, so the traced files are
    staged first. They are named when the issue traces any. In committed mode
    `compass ship-commit` stages the issue folder and the documents folder
    itself (#356), so the line leaves out the traced files under them."""
    record = _committed_record_folders(task_dir)
    traced = [cf["path"] for cf in _dicts(task.get("changed_files"))
              if isinstance(cf.get("path"), str) and cf["path"]
              and not cf["path"].startswith(record)]
    stage = ("git add -- " + " ".join(shlex.quote(p) for p in traced) if traced
             else "stage the changed files")
    return f"compass check, then {stage}, then {ship_commit_command(task, task_dir)}"


def ship_commit_command(task, task_dir):
    """The `compass ship-commit` command that lands the issue with its record.

    It names `--issue`: without it the landing commits the staged code but
    writes no record, no `trail.md`, and does not mark the issue done. It asks
    for `--release-note` when the issue owes a release line and holds none,
    because the landing refuses that issue (ADR-065). `compass quick-fix finish
    --no-commit` prints the same command on its `commit :` line."""
    from compass_pkg import release_line
    slug = os.path.basename(os.path.normpath(str(task_dir)))
    note = (' --release-note "<release line>"'
            if release_line.landing_refusal(task, task_dir) else "")
    return f'compass ship-commit --issue {slug} -m "<message>"{note}'


def _committed_record_folders(task_dir):
    """The issue folder and the documents folder, relative to the project root
    and each ending in `/`, when the record is committed with the code; else
    an empty tuple, which no path starts with."""
    from compass_pkg import record_mode
    from compass_pkg.core import docs_dir, find_upwards
    root = find_upwards(task_dir, ".compass")
    if not root or record_mode.mode(root, task_dir).mode != record_mode.COMMITTED:
        return ()
    folders = (os.path.relpath(os.path.abspath(task_dir), os.path.abspath(root)),
               docs_dir(task_dir))
    return tuple(f.replace(os.sep, "/").rstrip("/") + "/" for f in folders)


# --- the `next:` line of the verbs that write a record ------------------------------------

def announce(args, task_dir, code=0):
    """Print `next: <command>` as the verb's last stdout line, and return `code`.

    Every verb that writes a record of the issue calls this as it returns, so the
    agent reads the next step where it reads the result (ADR-092 decision 8). It
    prints only in a text mode (not `--json` or `--quiet`), only after success,
    and only on a path issue: an issue assessed before the path keeps the output
    it had."""
    from compass_pkg.terminal import resolve_mode
    if code not in (0, None) or resolve_mode(args) not in ("summary", "verbose"):
        return code
    try:
        from compass_pkg.core import load_manifest
        from compass_pkg.next_cmd import _stages_on_record
        task, _ = load_manifest(task_dir)
        if not path_stages.is_path_issue(task):
            return code
        command = next_command(task, task_dir, _stages_on_record(task, task_dir))
    except Exception:  # noqa: BLE001 - the record is written; the hint must not fail it
        return code
    if command:
        print(f"next: {command}")
    return code


def owed_commands(task, task_dir, cleared_gates=()):
    """One command for each item a path issue still owes, other than the gates in
    `cleared_gates` and the green, which `compass quick-fix finish` records
    itself. An empty list means nothing else is owed. A checkpoint is not listed:
    `compass ship-commit` judges it, as it judges every issue."""
    out = []
    if _owed(task, task_dir, "scenario-approval") and not _signed_off(task):
        out.append("compass evidence request --checkpoint specify, "
                   "then stop for /compass:approve")
    ids = [s["id"] for s in needing_tests(task)]
    if ids and _owed(task, task_dir, "outer-loop") and not _outer_red(task_dir):
        out.append(_outer_red_command(task, task_dir, ids[0]))
    if _owed(task, task_dir, "isolation") and not _record(task_dir, _ISOLATION_RECORD):
        out.append(_isolation_command(task, task_dir))
    if _owed(task, task_dir, "layering") and not _record(task_dir, _LAYERING_RECORD):
        out.append(_LAYERING_COMMAND)
    requirements = _open_requirements(task, task_dir)
    if requirements:
        out.append(requirements)
    if _owed(task, task_dir, "definition-of-done"):
        from compass_pkg import effective, item_records
        view = effective.effective_for(task_dir)
        out += [f"compass evidence add <EV-id> --type <type> --path <path> --meets {i.check}"
                for i in item_records.items(task, task_dir, view, "dod")
                if i.state == item_records.OPEN]
    out += [f"compass gate pass {g['id']} --evidence <EV-id>"
            for g in _dicts(task.get("gates"))
            if g.get("status") != "pass" and g.get("id") not in REMOVED_GATE_IDS
            and g.get("id") not in cleared_gates]
    if _owed(task, task_dir, "human-approval") and not _human_approval(task, task_dir):
        out.append("compass evidence request --check human-approval-present")
    return out


# --- the rows of each stage ----------------------------------------------------------------

def _specify(task, task_dir):
    scenarios = needing_tests(task)
    if not _scenarios(task):
        return (f"compass scenario add {FIRST_SCENARIO} --intent <intent id> "
                "--test <path::name>")
    untested = [s["id"] for s in scenarios if not _tests_of(s)]
    if untested:
        return f"compass scenario tests set {untested[0]} --test <path::name>"
    # The requirement rows are part of the spec, and the spec is in the tree the
    # outer-loop green, the isolation proof and the layering record are bound to.
    # Resolved after them, they would make all three stale.
    requirements = _open_requirements(task, task_dir)
    if requirements:
        return requirements
    if _owed(task, task_dir, "scenario-approval") and not _signed_off(task):
        return ("compass evidence request --checkpoint specify, "
                "then stop for /compass:approve")
    return None


def _build(task, task_dir):
    ids = [s["id"] for s in needing_tests(task)]
    if ids and _owed(task, task_dir, "outer-loop") and not _outer_red(task_dir):
        return _outer_red_command(task, task_dir, ids[0])
    reds = red_first.scenario_reds(task, task_dir) if task_dir else {"no_red": ids}
    if reds["no_red"]:
        return f"compass tdd-red --scenario {reds['no_red'][0]} -- <test command>"
    greened = greens(task)
    no_green = [i for i in ids if i not in greened]
    # Where `S17` applies the green is the outer loop's: it names the candidate
    # and client that the isolation proof is then made on (ADR-085).
    if ids and _owed(task, task_dir, "outer-loop") and task_dir:
        outer = {r.get("scenario") for r in _outer_greens(task, task_dir)}
        no_outer = [i for i in ids if i not in outer]
        if no_outer:
            return (f"compass tdd-green --loop outer --scenario {no_outer[0]} "
                    f"--candidate <build id>|local --client {'|'.join(_CLIENTS)} "
                    "-- <acceptance test command>")
    if no_green:
        return f"compass tdd-green --scenario {no_green[0]} -- <test command>"
    if _owed(task, task_dir, "isolation") and not _record(task_dir, _ISOLATION_RECORD):
        return _isolation_command(task, task_dir)
    if _owed(task, task_dir, "layering") and not _record(task_dir, _LAYERING_RECORD):
        return _LAYERING_COMMAND
    return None


def _outer_red_command(task, task_dir, scenario):
    """The outer-loop red. Where `layering` is owed the layering test is written
    and staged first: the outer-loop green, the isolation proof and the layering
    record are bound to the tree, which holds the tracked and staged files. A test
    file added to it after the green makes all three stale."""
    red = f"compass tdd-red --loop outer --scenario {scenario} -- <acceptance test command>"
    if _owed(task, task_dir, "layering") and not _record(task_dir, _LAYERING_RECORD):
        return (f"write the layering test at <layering test path> and git add it, "
                f"then {red}")
    return red


def _outer_greens(task, task_dir):
    from compass_pkg import candidate_client
    return [r for _, r in candidate_client.green_records(task, task_dir)
            if r.get("loop") == "outer"]


def _isolation_command(task, task_dir):
    """The isolation proof's command, on the candidate and client of the newest
    outer-loop green, which `isolation-proven` compares the proof with."""
    greens_ = [r for r in (_outer_greens(task, task_dir) if task_dir else [])
               if isinstance(r.get("candidate"), str) and r["candidate"]]
    newest = max(greens_, key=lambda r: str(r.get("timestamp") or "")) if greens_ else {}
    candidate = newest.get("candidate") or "<build id>|local"
    client = newest.get("client") or "|".join(_CLIENTS)
    return (f"compass isolation record --candidate {candidate} --client {client} "
            '--parallel "<acceptance suite command>" '
            '--repeat "<scenario test command> {tests}"')


def _ship(task, task_dir):
    if not _owed(task, task_dir, "definition-of-done"):
        return None
    item = _open_dod_item(task, task_dir)
    if item:
        return f"compass evidence add <EV-id> --type <type> --path <path> --meets {item}"
    return None


def _spike(task):
    concluded = any(e.get("type") == "spike-conclusion" for e in _dicts(task.get("evidence")))
    if not concluded:
        return ("compass evidence add EV-SPIKE --type spike-conclusion --path <file> "
                "--decision <discard|graduate-to-delivery|defer>")
    if _pending_gate(task) == SPIKE_GATE:
        return f"compass gate pass {SPIKE_GATE} --evidence EV-SPIKE"
    return None


# --- the records ---------------------------------------------------------------------------

def _dicts(value):
    return [e for e in value if isinstance(e, dict)] if isinstance(value, list) else []


def _scenarios(task):
    return [s for s in _dicts(task.get("scenarios")) if isinstance(s.get("id"), str) and s["id"]]


def needing_tests(task):
    """The scenarios that need a test, a red and a green: every one but a
    `verifiable: narrative` scenario, which its written body clears."""
    return [s for s in _scenarios(task) if s.get("verifiable") != "narrative"]


def _tests_of(scenario):
    tests = scenario.get("tests")
    return [t for t in tests if isinstance(t, str) and t] if isinstance(tests, list) else []


def specify_done(task):
    """True when a path issue's specify stage is done: it has a scenario, each
    scenario has an id and an intent, each one that is not `verifiable: narrative`
    declares a test, and a listed `specify` checkpoint has an outcome.

    `compass next` reads it for the stage it shows (`next_cmd`), and the
    acceptance strategy reads it for where stage 1 ends (`acceptance_strategy`).
    One rule serves both, so the stage `compass next` shows and the stage an
    outer-loop red is counted in cannot disagree. The checkpoint is read from the
    raw `checkpoints` and `checkpoint_outcomes` lists, so an issue whose manifest
    has no `checkpoint_outcomes` key still waits for a listed `specify`."""
    if not specify_written(task):
        return False
    listed = task.get("checkpoints")
    return not (isinstance(listed, list) and STAGE_SPECIFY in listed) or specify_handed_off(task)


def specify_written(task):
    """True when a path issue's scenarios are written: it has a scenario, each one
    has an id and an intent, and each one that is not `verifiable: narrative`
    declares a test. It is `specify_done` without the checkpoint, so a person can
    answer the `specify` hand-off once the work it hands off exists."""
    scenarios = _dicts(task.get("scenarios"))
    if not scenarios or not all(isinstance(s.get("id"), str) and s["id"] and s.get("intent")
                                for s in scenarios):
        return False
    # The lean path (branch exp-lean): a scenario needs no declared test yet.
    # `compass quick-fix finish` reads the changed test files from git.
    return True


def greens(task):
    """The scenario ids with a test-run bound to them, as `compass tdd-green`
    registers one."""
    return {e["scenario"] for e in _dicts(task.get("evidence"))
            if e.get("type") == "test-run" and isinstance(e.get("scenario"), str)}


def _signed_off(task):
    """True when a person answered the `specify` checkpoint. `compass tdd-red`
    refuses until then where `scenario-approval` is owed, so the row that asks
    for the answer reads the same rule (`scenario_freeze.refusal`)."""
    from compass_pkg import scenario_freeze
    return scenario_freeze.signed_off(task)


def specify_handed_off(task):
    """True when the `specify` checkpoint has an outcome. Read from the raw
    list, so it does not depend on which stages the checkpoint reader knows."""
    from compass_pkg.checkpoint_outcomes import KEY, OUTCOMES
    return any(e.get("stage") == STAGE_SPECIFY and e.get("outcome") in OUTCOMES
               for e in _dicts(task.get(KEY)))


def _outer_red(task_dir):
    if not task_dir:
        return False
    from compass_pkg import acceptance_strategy
    return any(name.endswith(red_first.OUTER + ".json")
               or acceptance_strategy.loop_of(record) == "outer"
               for name, record in acceptance_strategy.red_records(task_dir))


def _record(task_dir, name):
    return bool(task_dir) and os.path.isfile(os.path.join(task_dir, "evidence", name))


def _pending_gate(task, skip=()):
    for gate in task.get("gates") or []:
        if not isinstance(gate, dict):
            return None
        if (gate.get("status") != "pass" and gate.get("id") not in REMOVED_GATE_IDS
                and gate.get("id") not in skip):
            return gate.get("id")
    return None


def _owed(task, task_dir, token):
    """True when the issue owes the evidence `token` (an `evidence_required` value)."""
    if path_stages.is_path_issue(task):
        listed = task.get("evidence_required")
        if not isinstance(listed, list) or token not in listed:
            return False
        if token in _LEGACY_ROUTINGS:
            return _strategy_in_scope(task, task_dir, stored_needed=False)
        return True
    if token in _LEGACY_ROUTINGS:
        from compass_pkg import acceptance_strategy
        held = acceptance_strategy.stored(task) or {}
        return (held.get("routing") in _LEGACY_ROUTINGS[token]
                and _strategy_in_scope(task, task_dir, stored_needed=True))
    if token == "definition-of-done":
        stages = task.get("stages")
        weight = stages.get(STAGE_VERIFY) if isinstance(stages, dict) else None
        return isinstance(weight, str) and weight.strip().lower() == MODE_THOROUGH
    return False


def _strategy_in_scope(task, task_dir, stored_needed):
    """Does `S17` apply now? A path issue with no stored block owes what its
    list says; the records can still take it out of scope (an acceptance of kind
    validation or refactor and no red)."""
    from compass_pkg import acceptance_strategy
    if acceptance_strategy.stored(task) is None and not stored_needed:
        return True
    if not task_dir:
        return False
    return acceptance_strategy.in_scope(task, task_dir)[0]


def _open_requirements(task, task_dir):
    """On a path issue whose spec fails `nfr-rows-resolved`, the step that
    resolves its Non-functional requirements rows; else None. An old issue
    keeps the rows `compass check` already names for it."""
    if not path_stages.is_path_issue(task) or not task_dir:
        return None
    from compass_pkg import section_checks
    if section_checks._check_nfr_rows_resolved(task, task_dir)[0]:
        return None
    entry = section_checks.spec_entry(task, task_dir) or {}
    return (f"fill the {section_checks.NFR_HEADING} rows of {entry.get('path', 'the spec')}: "
            "the scenario ids that cover each concern, or the reason it does not apply")


def _open_dod_item(task, task_dir):
    from compass_pkg import effective, item_records
    view = effective.effective_for(task_dir)
    for item in item_records.items(task, task_dir, view, "dod"):
        if item.state == item_records.OPEN:
            return item.check
    return None


def _request_missing(task, task_dir):
    """True when the issue owes `request`, does not hold both parts, and no
    approved waiver excuses `request-recorded`."""
    from compass_pkg import request_link
    if not request_link.owed(task) or all(request_link.recorded(task)):
        return False
    if task_dir:
        from compass_pkg import waiver_records
        if request_link.CHECK in waiver_records.excused(task, task_dir):
            return False
    return True


def _human_approval(task, task_dir):
    from compass_pkg.checks import _check_human_approval
    return _check_human_approval(task, task_dir)[0]


def _checkpoint_waiting(task, done):
    """The first listed checkpoint whose hand-off is due and has no outcome."""
    from compass_pkg import checkpoint_outcomes
    missing = checkpoint_outcomes.missing(task)
    for stage in missing:
        if done is None or checkpoint_outcomes.reached(task, stage, done):
            return stage
    return None


# The verbs that write a record reach `announce` through `next_line`, which
# imports nothing, so no verb imports this module (see `next_line`).
next_line.register(announce)
