# compass_pkg.outer_loop - the outer-loop check of the four-layer acceptance strategy
"""The checks `outer-loop-recorded` (ADR-080) and `outer-loop-attempts-recorded`
(ADR-084) of strategy `S17`, the four-layer acceptance strategy.

An issue the strategy applies to must show the outer loop: a red and a green of
the acceptance suite, driven through a client interface, with the green on the
tree as it is now. A unit-test green meets guardrail `G1`, so `suite-passed` cannot
tell the two loops apart. This check reads the `loop` field `compass tdd-red` and
`compass tdd-green` write. A record with no field reads as inner
(`acceptance_strategy.loop_of`). Each registered outer-loop green must also name
its candidate and client (`candidate_client`, ADR-085).

The check judges the issue, not each scenario: a test-run record holds one exit
code for one command and does not list the tests that ran. Whether the strategy
applies is `acceptance_strategy.in_scope`, the one scope rule (ADR-079); this
module adds none. Compass reads records here, never project code.

The `attempts` check needs `attempts` on every registered outer-loop green of an
in-scope issue. `no-trusted-rerun` is locked and passes a record with no
`attempts`, for records written before the field; the `attempts` check closes
that gap where the strategy applies, and leaves `no-trusted-rerun` as it is.
"""
# DEPENDENCY: standard library (json, os); compass_pkg.acceptance_strategy, binding,
# candidate_client, check_results, core and status_words. It imports no command module, so the check
# registry can import it.
from __future__ import annotations

import json
import os

from compass_pkg import acceptance_strategy, candidate_client, status_words
from compass_pkg.binding import claimed_paths, work_tree_id
from compass_pkg.candidate_client import green_records
from compass_pkg.check_results import NOTHING_TO_CHECK
from compass_pkg.core import find_upwards

CHECK = "outer-loop-recorded"


def _inner(records, what):
    """`no outer-loop <what>` and how many records were read as inner, and why."""
    if not records:
        return f"no outer-loop {what}: no {what} record is on record"
    unmarked = sum(1 for _, r in records if "loop" not in r)
    text = f"no outer-loop {what}: {len(records)} {what} record(s) read as inner"
    if unmarked:
        text += f" ({unmarked} with no loop field, read as inner)"
    return text + f"; record the acceptance suite's run with `compass tdd-{what} --loop outer`"


def _tree(task, task_dir, greens):
    """`(fault, note)` about the tree the outer-loop greens ran on. `fault` is text
    when no outer-loop green is on the current tree. `note` is text when the tree
    could not be compared."""
    # A landed issue's working tree moves on after the land: ship-commit itself
    # commits the re-derived living spec. `evidence-matches-tree` compares the
    # issue's own files with the land commit, so this check does not compare trees.
    if status_words.is_completed(task):
        return None, ("the issue has landed, so the tree was not compared; "
                      "`evidence-matches-tree` compares the landed files")
    root = find_upwards(task_dir, ".compass") or task_dir
    now = work_tree_id(root, claimed_paths(task))
    bound = [(p, r) for p, r in greens if isinstance(r.get("tree_id"), str) and r["tree_id"]]
    if now is None:
        return None, "git cannot name the tree now, so the tree was not compared"
    if not bound:
        return None, "no outer-loop green names its tree, so the tree was not compared"
    if any(r["tree_id"] == now for _, r in bound):
        return None, None
    path, record = max(bound, key=lambda pr: str(pr[1].get("timestamp") or ""))
    return (f"no outer-loop green on the current tree: {path} was recorded on tree "
            f"{record['tree_id'][:12]}, "
            f"a different tree from the current one ({now[:12]}), so it does not count; "
            f"run the acceptance suite again with `compass tdd-green --loop outer`"), None


def _check_outer_loop_recorded(task, task_dir):
    """The outer-loop check: an in-scope issue has an outer-loop red, and an
    outer-loop green on the current tree."""
    applies, why = acceptance_strategy.in_scope(task, task_dir)
    if not applies:
        return NOTHING_TO_CHECK, f"not required: the strategy does not apply - {why}"
    slug = (task or {}).get("issue") or os.path.basename(os.path.normpath(task_dir))
    reds = acceptance_strategy.red_records(task_dir)
    greens = green_records(task, task_dir)
    outer_reds = [(n, r) for n, r in reds if acceptance_strategy.loop_of(r) == "outer"]
    outer_greens = [(p, r) for p, r in greens if acceptance_strategy.loop_of(r) == "outer"]
    faults = []
    if not outer_reds:
        faults.append(_inner(reds, "red"))
    note = None
    if not outer_greens:
        faults.append(_inner(greens, "green"))
    else:
        fault, note = _tree(task, task_dir, outer_greens)
        if fault:
            faults.append(fault)
        # Each registered outer-loop green names its candidate and client (ADR-085).
        # `tdd-green` and `evidence add` refuse one that does not; this finds one
        # registered another way, such as by editing the manifest.
        faults += [f for f in (candidate_client.fault(p, r) for p, r in outer_greens) if f]
    if faults:
        return False, f"issue {slug} has " + "; and ".join(faults)
    detail = (f"issue {slug} has an outer-loop red ({outer_reds[0][0]}) and an "
              f"outer-loop green ({outer_greens[-1][0]})")
    return True, detail + (f"; {note}" if note else " on the current tree")


# --- registering a test-run record ------------------------------------------------------

def test_run_refusal(task, task_dir, path, abs_path):
    """Why `compass evidence add` must not register `path` as a `test-run` record,
    or None: it is not a run record, or it is an outer-loop green with no
    candidate or no client on an issue the strategy applies to (ADR-085)."""
    try:
        with open(abs_path, encoding="utf-8") as fh:
            record = json.load(fh)
    except (ValueError, OSError):
        return (f"compass evidence add: '{path}' is not a run record. `test-run` means "
                f"the JSON that `compass tdd-green` writes (command, exit_code, passed), "
                f"because the tested-before-ship checks read those fields.\n"
                f"  For a raw log, use --type command-output.\n"
                f"  For a real run, record it with `compass tdd-green -- <cmd>` and it "
                f"registers itself.")
    if not isinstance(record, dict) or acceptance_strategy.loop_of(record) != "outer":
        return None
    return candidate_client.registration_refusal(
        path, record, acceptance_strategy.in_scope(task, task_dir)[0])


# --- the `attempts` check --------------------------------------------------------------------

ATTEMPTS_CHECK = "outer-loop-attempts-recorded"


def _attempts_fault(path, record):
    """Why an outer-loop green's `attempts` does not hold, or None."""
    if "attempts" not in record:
        return (f"{path} has no attempts; attempts is required on an in-scope outer-loop "
                f"record, so `no-trusted-rerun` can tell a first pass from a rerun")
    value = record["attempts"]
    # A bool is an int in Python, and 1.0 is not a count of runs.
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        return (f"{path} has attempts {json.dumps(value)}; attempts must be a whole "
                f"number of 1 or more")
    return None


def _check_outer_loop_attempts_recorded(task, task_dir):
    """The `attempts` check (strategy `S5` on the outer loop, ADR-084): on an in-scope
    issue, every registered outer-loop green has `attempts`, a whole number of 1 or
    more. `no-trusted-rerun` passes a record with no `attempts`, so an outer-loop
    green written without one would hide a rerun."""
    applies, why = acceptance_strategy.in_scope(task, task_dir)
    if not applies:
        return NOTHING_TO_CHECK, f"not required: the strategy does not apply - {why}"
    outer = [(p, r) for p, r in green_records(task, task_dir)
             if acceptance_strategy.loop_of(r) == "outer"]
    if not outer:
        return NOTHING_TO_CHECK, ("no outer-loop green is registered; "
                                  "`outer-loop-recorded` reports that")
    faults = [f for f in (_attempts_fault(p, r) for p, r in outer) if f]
    if faults:
        return False, "; ".join(faults)
    return True, "every outer-loop green records its attempts: " + ", ".join(
        f"{p} ({r['attempts']})" for p, r in outer)
