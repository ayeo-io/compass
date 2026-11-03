# compass_pkg.strategy_records - what the isolation and layering records share
"""The parts the `isolation-proof` and `layering` records of strategy `S17`,
the four-layer acceptance strategy, have in common (ADR-086).

Each record is written only by its command, `compass isolation record` or
`compass layering record`, which runs the project's own commands through
`tdd._run_test` and records their exit codes. `compass evidence add` refuses
both types, so a written note cannot stand in for one. The two checks,
`isolation-proven` and `layering-test-passed`, read the registered record,
never the project's test code, and share the rules here:

- whether the strategy and the issue's routing ask for the record;
- which registered record is the issue's, and whether it can be read;
- whether it was made on the tree as it is now.

An issue the strategy does not apply to still lists a record it holds, with
its result, and the result judges nothing (TRC-A4).
"""
# DEPENDENCY: standard library (json, os); compass_pkg.acceptance_strategy,
# binding, check_results, core and status_words. It imports no command module,
# so the check registry can import it.
from __future__ import annotations

import json
import os

from compass_pkg import acceptance_strategy, status_words
from compass_pkg.binding import claimed_paths, work_tree_id
from compass_pkg.check_results import NOTHING_TO_CHECK
from compass_pkg.core import (CompassError, find_upwards, load_manifest, manifest_path,
                              save_manifest)

#: The routings that need each record (ADR-086): the
#: isolation proof on `on` and on the hotfix's `existing-dsl-isolation`, the
#: layering record on `on` only.
NEEDED_ON = {"isolation-proof": ("on", "existing-dsl-isolation"), "layering": ("on",)}


class Unreadable(Exception):
    """A registered record that cannot be read as a JSON object."""


def registered(task, task_dir, ev_type):
    """`(path, full path)` of the newest registered record of `ev_type` inside the
    issue folder, or None. A path outside the issue folder is not read."""
    root = os.path.realpath(task_dir)
    found = None
    for entry in (task or {}).get("evidence") or []:
        if not isinstance(entry, dict) or entry.get("type") != ev_type:
            continue
        path = str(entry.get("path") or "")
        full = os.path.realpath(os.path.join(task_dir, path))
        if path and os.path.commonpath([root, full]) == root:
            found = (path, full)
    return found


def read(full):
    """The record at `full` as a dict. Raises `Unreadable` when it is missing, not
    JSON, or not an object."""
    try:
        with open(full, encoding="utf-8") as fh:
            record = json.load(fh)
    except (OSError, ValueError) as exc:
        raise Unreadable(str(exc)) from exc
    if not isinstance(record, dict):
        raise Unreadable("it holds no JSON object")
    return record


def whole(value):
    """True for a whole number that is not a bool: a bool is an int in Python."""
    return isinstance(value, int) and not isinstance(value, bool)


def outcome(task, task_dir, ev_type, faults):
    """`(path, record, faults)` of the issue's record of `ev_type`: `path` None when
    none is registered; `faults` the reasons it does not hold, from `faults(path,
    record)` once it reads. A record that cannot be read has one fault."""
    found = registered(task, task_dir, ev_type)
    if found is None:
        return None, None, []
    path, full = found
    try:
        record = read(full)
    except Unreadable as exc:
        return path, None, [f"{path} could not be read: it is not valid JSON ({exc})"]
    return path, record, faults(path, record)


def result_text(path, faults):
    """`<path> is on record: passed`, or `failed` with the reasons."""
    if not faults:
        return f"{path} is on record: passed"
    return f"{path} is on record: failed - " + "; ".join(faults)


def declined(task, task_dir, ev_type, faults):
    """The decline of a check the issue does not need, or None when it needs it:
    the strategy does not apply, or the issue's routing does not ask for the
    record. A record the issue holds is listed with its result."""
    applies, why = acceptance_strategy.in_scope(task, task_dir)
    if not applies:
        reason = f"not required: the strategy does not apply - {why}"
    else:
        routing = (acceptance_strategy.stored(task) or {}).get("routing") or "on"
        if routing in NEEDED_ON[ev_type]:
            return None
        words = acceptance_strategy.ROUTINGS.get(routing, routing)
        reason = (f"not required: the issue's approach routes the strategy as "
                  f"{words}, which needs no {ev_type} record")
    path, _record, found = outcome(task, task_dir, ev_type, faults)
    if path is not None:
        reason += f"; {result_text(path, found)}"
    return NOTHING_TO_CHECK, reason


def tree_fault(task, task_dir, path, record):
    """Why the record was not made on the tree as it is now, or None. A landed
    issue, or a tree git cannot name, is not compared: `evidence-matches-tree`
    compares a landed issue's files with the land commit."""
    if status_words.is_completed(task):
        return None
    root = find_upwards(task_dir, ".compass") or task_dir
    now = work_tree_id(root, claimed_paths(task))
    made_on = record.get("tree_id")
    if now is None or not (isinstance(made_on, str) and made_on):
        return None
    if made_on == now:
        return None
    return (f"{path} was made on tree {made_on[:12]}, a different tree from the current "
            f"one ({now[:12]}), so it does not count; record it again")


def register(task_dir, ev_type, ev_id, rel_path, record_id, content_digest):
    """Add or replace the issue's one registry entry of `ev_type`, carrying the
    identity of the record it was created from."""
    path = manifest_path(task_dir)
    if not os.path.isfile(path):
        return
    try:
        task, _ = load_manifest(task_dir)
    except CompassError:
        return
    reg = [e for e in (task.get("evidence") or [])
           if not (isinstance(e, dict) and e.get("type") == ev_type)]
    reg.append({"id": ev_id, "type": ev_type, "path": rel_path, "record_id": record_id,
                "content_digest": content_digest})
    task["evidence"] = reg
    save_manifest(task, path)
