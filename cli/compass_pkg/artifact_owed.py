# compass_pkg.artifact_owed - whether an issue owes a registered document
"""One function answers "is this document owed?" for every reader.

A catalogue entry can carry `required_when: {subtasks: {min: 2}}`. The document
is owed only while the issue meets the condition. `compass check`, `compass
next`, the issue page, the board panel and the receipt all ask `owed`, so they
cannot disagree (ADR-053).

A person's record wins over the condition: an entry recorded as `omitted` is
judged as it always was, with its reason shown, and is never called "not
needed". A condition that is false leaves the entry out of `artifacts-approved`
whether or not a file exists. A reader shows the text only when the entry has
no path, because a document written anyway shows its own status.
"""
# DEPENDENCY: compass_pkg.artifact_kinds (the catalogue entry). It is a leaf: it
# imports no command module.
from __future__ import annotations

from dataclasses import dataclass

from compass_pkg import artifact_kinds


@dataclass(frozen=True)
class Owed:
    owed: bool
    #: "not needed: one subtask" or "not needed: no subtasks recorded" when not owed, else None.
    text: object = None


def subtask_count(task):
    """The subtasks the manifest records. An absent or empty list counts as zero."""
    listed = task.get("subtasks") if isinstance(task, dict) else None
    return len(listed) if isinstance(listed, list) else 0


def _subtasks_phrase(count):
    if count == 0:
        return "no subtasks recorded"
    return "one subtask" if count == 1 else "%d subtasks" % count


#: The facts a `required_when` key can name. A later condition is one entry here and
#: one name in `catalogue_spec.REQUIRED_WHEN_CONDITIONS`.
CONDITIONS = {"subtasks": (subtask_count, _subtasks_phrase)}


def owed(task, view, kind, entry=None):
    """Whether the issue owes `kind`. `entry` is the registered entry, when the caller
    holds it. A kind the catalogue does not declare, or declares with no condition, is
    always owed; so is any kind when no configuration can be read."""
    if isinstance(entry, dict) and entry.get("status") == "omitted":
        return Owed(True)
    declared = artifact_kinds.entry(view, kind)
    required = declared.get("required_when") if isinstance(declared, dict) else None
    if not isinstance(required, dict):
        return Owed(True)
    for key, condition in required.items():
        if key not in CONDITIONS or not isinstance(condition, dict):
            continue
        count_of, phrase = CONDITIONS[key]
        count = count_of(task)
        if isinstance(condition.get("min"), int) and count < condition["min"]:
            return Owed(False, "not needed: " + phrase(count))
    return Owed(True)


def not_needed(task, view, entry):
    """The text a reader shows for a registered `entry` that has no file and whose
    condition is false, else None."""
    if not isinstance(entry, dict) or entry.get("path") or entry.get("status") == "omitted":
        return None
    return owed(task, view, str(entry.get("kind") or ""), entry).text
