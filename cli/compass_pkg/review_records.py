# compass_pkg.review_records - the review records of judged checks
"""Read the review record of a judged check and say whether it still stands.

A check of kind `judged` is a judgement a person or an agent makes, so the
CLI checks the record of it and never the reasoning. The record is a YAML file
in the issue's `evidence/` folder, registered in the manifest as
`manual-review` evidence with `check: <check id>`.
"""
# DEPENDENCY: standard library (hashlib, os); PyYAML, bundled at
# cli/vendor/yaml/, through compass_pkg.core. It imports no command module, so
# the evaluator and the command can both use it.
from __future__ import annotations

import hashlib
import os

import yaml

from compass_pkg.atomic_io import digest
from compass_pkg.core import FOUND, resolve_artifact
from compass_pkg.red_first import content_digest


#: The four reasons a judged check fails, as the first words of its detail.
NO_RECORD = "no review record"
FAILED = "verdict is fail"
NOT_LISTED = "reviewer not listed"
CHANGED = "input changed since review"
CAUSES = (NO_RECORD, FAILED, NOT_LISTED, CHANGED)


#: What `reviewers:` lists when it lists an agent session of any id.
AGENT = "agent"


def reviewer_listed(listed, reviewer):
    """Does a `reviewers:` list name this reviewer, `{kind, id}`? `agent`
    names any agent session and `agent:<id>` names one session. Any other
    entry names the person with that id, so a role is read as a person id
    until roles are resolved."""
    if not isinstance(reviewer, dict):
        return False
    if reviewer.get("kind") == "agent":
        return AGENT in listed or f"{AGENT}:{reviewer.get('id')}" in listed
    return reviewer.get("kind") == "person" and str(reviewer.get("id")) in listed \
        and str(reviewer.get("id")) != AGENT


def declared_inputs(check):
    """The ids a judged check reads: artifact ids and evidence ids."""
    return [str(one) for one in (check.get("inputs") or [])]


def file_digest(path):
    """`sha256:` and the hex digest of the file's bytes, or None when there is
    no such file."""
    if not path or not os.path.isfile(path):
        return None
    with open(path, "rb") as fh:
        return "sha256:" + hashlib.sha256(fh.read()).hexdigest()


def input_path(task, task_dir, input_id):
    """Where an input is: the file of the evidence entry with that id, else
    the issue's document of that name. None when there is none."""
    for entry in task.get("evidence") or []:
        if isinstance(entry, dict) and entry.get("id") == input_id:
            path = entry.get("path")
            if not path:
                return None
            return path if os.path.isabs(path) else os.path.join(task_dir, path)
    state, path, _ = resolve_artifact(task_dir, input_id)
    return path if state == FOUND else None


def current_digests(check, task, task_dir):
    """`{input id: digest or None}` for each input of the check, as it is now."""
    return {one: file_digest(input_path(task, task_dir, one))
            for one in declared_inputs(check)}


def definition_digest(check):
    """The digest of a check's definition, the one `results.yml` records."""
    return digest(check)


def changed_inputs(recorded, now):
    """One phrase for each input whose digest is not the one recorded. An
    input added to or dropped from the check since the review counts."""
    recorded = recorded if isinstance(recorded, dict) else {}
    found = []
    for one in list(now) + [i for i in recorded if i not in now]:
        before, after = recorded.get(one), now.get(one)
        if one not in now:
            found.append(f"{one} is no longer an input")
        elif after is None:
            found.append(f"{one} is missing now")
        elif before is None:
            found.append(f"{one} was not part of the review")
        elif before != after:
            found.append(f"{one} changed ({before[:19]} then {after[:19]})")
    return found


def _entries(task, check_id):
    return [e for e in task.get("evidence") or []
            if isinstance(e, dict) and e.get("type") == "manual-review"
            and e.get("check") == check_id]


def read_record(task_dir, entry, check_id):
    """`(record, problem)` for a registered review: the record, or None and why
    it is not one. A record is a file the registry names, that reads as a map
    for this check, and whose stamp still matches its content."""
    path = entry.get("path") or ""
    full = path if os.path.isabs(path) else os.path.join(task_dir, path)
    if not os.path.isfile(full):
        return None, f"{entry.get('id')} names {path or 'no path'}, and there is no file"
    try:
        with open(full, encoding="utf-8") as fh:
            record = yaml.safe_load(fh)
    except (OSError, yaml.YAMLError) as exc:
        return None, f"{path} cannot be read ({exc})"
    if not isinstance(record, dict) or record.get("check") != check_id:
        return None, f"{path} is not a review record of {check_id}"
    if not record.get("content_digest"):
        return None, f"{path} is not stamped, so it cannot be told from a note"
    if record["content_digest"] != content_digest(record):
        return None, f"{path} changed after it was written"
    return record, None


def _gather(task_dir, check_id, entries):
    """`[(entry, record or None, problem)]`, newest first."""
    return [(entry,) + read_record(task_dir, entry, check_id) for entry in reversed(entries)]


def judge(check_id, check, task, task_dir):
    """`(status, detail)` of a judged check: `pass`, or `fail` with the cause
    first in the detail. Only a record by a listed reviewer can decide: a
    record by anyone else is set aside, so it can neither clear nor block."""
    if not declared_inputs(check):
        return "fail", (f"declares no inputs, so no review of {check_id} can be recorded; "
                        f"a judged check lists the artifacts or evidence it reads")
    entries = _entries(task, check_id)
    if not entries:
        return "fail", (f"{NO_RECORD}: run `compass evidence review {check_id} "
                        f"--verdict pass|fail --reason TEXT --reviewer ID`")
    found = _gather(task_dir, check_id, entries)
    if found[0][1] is None:
        return "fail", f"{NO_RECORD}: the newest record is unusable - {found[0][2]}"
    slug = os.path.basename(os.path.normpath(task_dir))
    listed = [str(one) for one in (check.get("reviewers") or [AGENT])]
    usable = [(entry, record) for entry, record, _ in found if record is not None]
    mine = [(entry, record) for entry, record in usable
            if reviewer_listed(listed, record.get("reviewer"))]
    if not mine:
        entry, record = usable[0]
        who = record.get("reviewer") or {}
        return "fail", (f"{NOT_LISTED}: {entry.get('id')} was by {who.get('id')} "
                        f"({who.get('kind')}); {check_id} lists {', '.join(listed)}")
    entry, record = mine[0]
    who = (record.get("reviewer") or {}).get("id")
    if record.get("issue") != slug:
        return "fail", (f"{NO_RECORD}: {entry.get('id')} was written for issue "
                        f"{record.get('issue')}, not {slug}")
    if record.get("verdict") != "pass":
        return "fail", (f"{FAILED}: {entry.get('id')} by {who}: {record.get('reason')}")
    moved = changed_inputs(record.get("inputs"), current_digests(check, task, task_dir))
    if (record.get("generation") or None) != (task.get("generation") or None):
        moved.append(f"the generation changed (reviewed under {record.get('generation')}, "
                     f"now {task.get('generation')})")
    if record.get("definition_digest") != definition_digest(check):
        moved.append(f"the definition of {check_id} changed")
    if moved:
        return "fail", (f"{CHANGED}: {'; '.join(moved)} (record {entry.get('id')}); "
                        f"review again")
    return "pass", f"{entry.get('id')}: pass by {who}, inputs unchanged"
