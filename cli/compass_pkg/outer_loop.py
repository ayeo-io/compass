# compass_pkg.outer_loop - the outer-loop check of the four-layer acceptance strategy
"""The check `outer-loop-recorded` of strategy `S17`, the four-layer acceptance
strategy (ADR-080).

An issue the strategy applies to must show the outer loop: a red and a green of
the acceptance suite, driven through a client interface, with the green on the
tree as it is now. A unit-test green meets guardrail `G1`, so `suite-passed` cannot
tell the two loops apart. This check reads the `loop` field `compass tdd-red` and
`compass tdd-green` write. A record with no field reads as inner
(`acceptance_strategy.loop_of`).

The check judges the issue, not each scenario: a test-run record holds one exit
code for one command and does not list the tests that ran. Whether the strategy
applies is `acceptance_strategy.in_scope`, the one scope rule (ADR-079); this
module adds none. Compass reads records here, never project code.
"""
# DEPENDENCY: standard library (os); compass_pkg.acceptance_strategy, binding,
# check_results, core, red_first and status_words. It imports no command module, so the check
# registry can import it.
from __future__ import annotations

import os

from compass_pkg import acceptance_strategy, status_words
from compass_pkg.binding import claimed_paths, work_tree_id
from compass_pkg.check_results import NOTHING_TO_CHECK
from compass_pkg.core import find_upwards
from compass_pkg.red_first import load_record

CHECK = "outer-loop-recorded"


def green_records(task, task_dir):
    """`[(path, record)]` of each registered test-run record that holds a passing
    run, in registry order. A path outside the issue folder is not read."""
    root = os.path.realpath(task_dir)
    out = []
    for entry in (task or {}).get("evidence") or []:
        if not isinstance(entry, dict) or entry.get("type") != "test-run":
            continue
        path = entry.get("path") or ""
        full = os.path.realpath(os.path.join(task_dir, path))
        if os.path.commonpath([root, full]) != root:
            continue
        record = load_record(full)
        if record.get("exit_code") == 0 and record.get("passed") is True:
            out.append((path, record))
    return out


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
    if faults:
        return False, f"issue {slug} has " + "; and ".join(faults)
    detail = (f"issue {slug} has an outer-loop red ({outer_reds[0][0]}) and an "
              f"outer-loop green ({outer_greens[-1][0]})")
    return True, detail + (f"; {note}" if note else " on the current tree")
