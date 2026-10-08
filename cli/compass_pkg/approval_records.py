# compass_pkg.approval_records - the approvals of a human check
"""Say whether a `human` check that lists `approvers:` has a current approval.

A tick does not clear such a check. It also needs a `human-approval` entry in
the issue's evidence registry that:

- names the check (`check: <id>`),
- holds `decision: approved` and the fields every approval holds,
- is by a listed approver,
- is written for this issue (`issue: <slug>`), and
- is written for the issue's current generation (`generation: <n>`, absent
  when the issue has none).

A record that fails any of these is set aside: it cannot clear the check. An
approver's name is not authenticated, the same limit as every `human-approval`
record.
"""
# DEPENDENCY: standard library (os). It imports no command module, so the
# stage-list evaluator and `compass check` can both use it.
from __future__ import annotations

import os

#: The fields every `human-approval` record holds (the same four
#: `human-approval-present` and a waiver's approval need).
REQUIRED = ("approver", "role", "scope", "timestamp")

#: The first words of the detail of a failure, by cause.
NO_RECORD = "no approval record"
NOT_LISTED = "approver not listed"
OTHER_ISSUE = "approval is for another issue"
OTHER_GENERATION = "approval is for another generation"


def approver_listed(listed, approver):
    """Does an `approvers:` list name this approver? An entry names the person
    with that id. `agent` names no one: an approval is a person's. This is the
    person branch of the matching `reviewers:` uses, so both lists read a name
    the same way; a role is read as a person id until roles are resolved."""
    name = str(approver)
    return name != "agent" and name in [str(one) for one in listed]


def _claims(task, check_id):
    """The `human-approval` entries that name the check and say `approved`,
    with the fields every approval holds. Newest last."""
    return [e for e in task.get("evidence") or []
            if isinstance(e, dict) and e.get("type") == "human-approval"
            and e.get("check") == check_id and e.get("decision") == "approved"]


def judge(check_id, check, task, task_dir):
    """`(status, detail)` for the approval half of a human check: `pass`, or
    `fail` with the cause first and the approvers who may approve named."""
    listed = [str(one) for one in (check.get("approvers") or [])]
    who = f"{check_id} lists approvers {', '.join(listed)}"
    claims = _claims(task, check_id)
    if not claims:
        return "fail", (f"{NO_RECORD}: {who}; record a `human-approval` entry with "
                        f"check: {check_id}")
    slug = os.path.basename(os.path.normpath(task_dir))
    generation = task.get("generation") or None
    first = None
    for entry in reversed(claims):
        missing = [k for k in REQUIRED if not entry.get(k)]
        if missing:
            first = first or f"{NO_RECORD}: {entry.get('id')} is missing {', '.join(missing)}; {who}"
            continue
        if not approver_listed(listed, entry["approver"]):
            first = first or (f"{NOT_LISTED}: {entry.get('id')} was by {entry['approver']}; "
                              f"{who}")
            continue
        if entry.get("issue") != slug:
            first = first or (f"{OTHER_ISSUE}: {entry.get('id')} names issue "
                              f"{entry.get('issue')}, not {slug}; {who}")
            continue
        if (entry.get("generation") or None) != generation:
            first = first or (f"{OTHER_GENERATION}: {entry.get('id')} was given for "
                              f"{entry.get('generation')}, the issue is at {generation}; "
                              f"{who}")
            continue
        return "pass", f"{entry.get('id')}: approved by {entry['approver']}"
    return "fail", first
