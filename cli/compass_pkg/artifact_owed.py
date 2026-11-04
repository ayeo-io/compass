# compass_pkg.artifact_owed - whether an issue owes a registered document
"""One function answers "is this document owed?" for every reader.

A catalogue entry can carry `required_when: {subtasks: {min: 2}}`. The document
is owed only while the issue meets the condition. The count is the manifest's
`subtasks:` list when it has one, as a record written before 9.0.0 does; with no
such key it is the units the registered distribution map declares on its
`units:` line, because 9.0.0 records no subtasks (ADR-090). `compass check`, `compass
next`, the issue page, the board panel and the receipt all ask `owed`, so they
cannot disagree (ADR-053).

A person's record wins over the condition: an entry recorded as `omitted` is
judged as it always was, with its reason shown, and is never called "not
needed". A condition that is false leaves the entry out of `artifacts-approved`
whether or not a file exists. A reader shows the text only when the entry has
no path, because a document written anyway shows its own status.
"""
# DEPENDENCY: standard library (os, re); compass_pkg.artifact_kinds (the catalogue
# entry) and compass_pkg.core (finding the map). It imports no command module.
from __future__ import annotations

import os
import re
from dataclasses import dataclass

from compass_pkg import artifact_kinds


@dataclass(frozen=True)
class Owed:
    owed: bool
    #: "not needed: one subtask" or "not needed: no subtasks recorded" when not owed, else None.
    text: object = None


#: A distribution map's `units:` line, alone on a line or as a list item.
_UNITS_LINE = re.compile(r"^units:\s*(\S.*?)\s*$")


def declared_units(path):
    """How many work units the distribution map at `path` declares on its `units:`
    line, or None when it has none. The first line whose value is a whole number or
    a bracketed list counts; a placeholder such as `{{N}}` is skipped."""
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except (OSError, UnicodeDecodeError, TypeError):
        return None
    for line in lines:
        found = _UNITS_LINE.match(line.strip().lstrip("-* ").strip("`"))
        if not found:
            continue
        value = found.group(1).strip("`").strip()
        if value.isdecimal():
            return int(value)
        if value.startswith("[") and value.endswith("]"):
            return len([u for u in value[1:-1].split(",") if u.strip()])
    return None


def _map_units(task_dir, entry):
    """The units the issue's distribution map declares, or 0 with no map or line."""
    if not task_dir:
        return 0
    from compass_pkg.core import FOUND, _registered_path, resolve_artifact
    path = None
    if isinstance(entry, dict) and entry.get("kind") == "distribution-map" and entry.get("path"):
        path, refused = _registered_path(task_dir, entry["path"])
        path = None if refused else path
    if path is None:
        state, found, _ = resolve_artifact(task_dir, "distribution-map")
        path = found if state == FOUND else None
    return (declared_units(path) or 0) if path and os.path.isfile(path) else 0


def subtask_count(task):
    """The subtasks the manifest records. An absent or empty list counts as zero."""
    listed = task.get("subtasks") if isinstance(task, dict) else None
    return len(listed) if isinstance(listed, list) else 0


def work_units(task, task_dir=None, entry=None):
    """`(count, noun)`: the subtasks the manifest records, or with no `subtasks:` key
    the units the distribution map declares (ADR-090). An empty list counts as zero."""
    if isinstance(task, dict) and "subtasks" in task:
        return subtask_count(task), "subtask"
    return _map_units(task_dir, entry), "unit"


def _subtasks_phrase(count, noun="subtask"):
    # Zero reads as it did before 9.0.0, so a page rendered then stays current.
    if count == 0:
        return "no subtasks recorded"
    return ("one %s" % noun) if count == 1 else "%d %ss" % (count, noun)


#: The facts a `required_when` key can name. A later condition is one entry here and
#: one name in `catalogue_spec.REQUIRED_WHEN_CONDITIONS`.
CONDITIONS = {"subtasks": (work_units, _subtasks_phrase)}


def owed(task, view, kind, entry=None, task_dir=None):
    """Whether the issue owes `kind`. `entry` is the registered entry, when the caller
    holds it. A kind the catalogue does not declare, or declares with no condition, is
    always owed. With no configuration to read, the shipped default's condition applies.
    `task_dir` lets the count read the distribution map's `units:` line."""
    if isinstance(entry, dict) and entry.get("status") == "omitted":
        return Owed(True)
    # With no configuration to read, the shipped default's condition applies, so a page
    # rendered before a project has a configuration reads as it does after.
    declared = artifact_kinds.entry(view, kind) if view is not None \
        else artifact_kinds.shipped().get(kind)
    required = declared.get("required_when") if isinstance(declared, dict) else None
    if not isinstance(required, dict):
        return Owed(True)
    for key, condition in required.items():
        if key not in CONDITIONS or not isinstance(condition, dict):
            continue
        count_of, phrase = CONDITIONS[key]
        count, noun = count_of(task, task_dir, entry)
        if isinstance(condition.get("min"), int) and count < condition["min"]:
            return Owed(False, "not needed: " + phrase(count, noun))
    return Owed(True)


def not_needed(task, view, entry, task_dir=None):
    """The text a reader shows for a registered `entry` that has no file and whose
    condition is false, else None."""
    if not isinstance(entry, dict) or entry.get("path") or entry.get("status") == "omitted":
        return None
    return owed(task, view, str(entry.get("kind") or ""), entry, task_dir).text
