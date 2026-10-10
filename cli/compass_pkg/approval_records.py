# compass_pkg.approval_records - the approvals of a human check
"""Say whether a `human` check that lists `approvers:` has a current approval.

A tick does not clear such a check, and neither does a deferral tag. The check
also needs a `human-approval` entry in the issue's evidence registry (or an
`artifact-approval` entry, which `compass evidence approve --artifact` writes
and which needs no `scope`) that:

- names the check (`check: <id>`) and holds a decision, `approved` or
  `rejected`,
- holds `approver`, `role`, `scope` and `timestamp` (not `scope` for an
  `artifact-approval` entry),
- is by a listed approver,
- is written for this issue (`issue: <slug>`), and
- is written for the issue's current generation (`generation: <n>`, absent
  when the issue has none).

A record that fails any of these is set aside: it cannot clear the check and
it cannot block it. Of the records that remain, the newest decides, so a later
rejection withdraws an approval. An approver's name is not authenticated, the
same limit as every `human-approval` record. `compass evidence approve`
writes a record; anyone who can write `manifest.yml` can also add one.
"""
# DEPENDENCY: standard library (os); compass_pkg.layers (the project's owner).
# It imports no command module, so the stage-list evaluator and the
# `compass evidence approve` command can both use it.
from __future__ import annotations

import os

#: The fields every `human-approval` record holds (the same four
#: `human-approval-present` and a waiver's approval need).
REQUIRED = ("approver", "role", "scope", "timestamp")

#: The evidence type `compass evidence approve --artifact` and `--decisions`
#: write. It meets an artifact's human check here and is read nowhere else:
#: `human-approval-present`, the check of guardrail `G5`, reads only
#: `human-approval`, and a waiver's approval needs that type too.
ARTIFACT_APPROVAL = "artifact-approval"

#: What an `artifact-approval` record holds. It needs no `scope`: the document
#: is the scope.
ARTIFACT_REQUIRED = ("approver", "role", "timestamp")

#: The decisions a record can hold; `rejected` withdraws an earlier approval.
APPROVED, REJECTED = "approved", "rejected"
DECISIONS = (APPROVED, REJECTED)

#: What `approvers:` lists when it lists the project's owner.
OWNER = "owner"

#: The first words of the detail of a failure, by cause.
NO_RECORD = "no approval record"
NOT_LISTED = "approver not listed"
OTHER_ISSUE = "approval is for another issue"
OTHER_GENERATION = "approval is for another generation"
WITHDRAWN = "approval withdrawn"

#: What a person does to record an approval, for a failure detail.
HOW = ("run `compass evidence approve --check ID --approver NAME --role ROLE "
       "--scope TEXT`; a record holds check, decision, approver, role, scope, "
       "timestamp, issue and generation")


def project_owner(task_dir):
    """The `owner:` of the project file above the issue, or None when there is
    no project file or it names no owner. Waivers read the owner from the same
    file (`waivers.allowed_approvers`)."""
    from compass_pkg import layers
    try:
        loaded = layers.load_project_layer(layers.find_project_root(task_dir))
    except Exception:                                  # noqa: BLE001
        return None
    owner = loaded[0].doc.get("owner") if loaded else None
    return owner.strip() if isinstance(owner, str) and owner.strip() else None


def approver_listed(listed, approver, owner=None):
    """Does an `approvers:` list name this approver? The entry `owner` names
    the project's owner (and nobody when the project has none). Any other
    entry names the person with that id, a role included, until roles are
    resolved. `agent` names no one: an approval is a person's. This is the
    person branch of the matching `reviewers:` uses."""
    name = str(approver)
    if name == "agent" or name.startswith("agent:"):
        return False
    names = [owner if str(one) == OWNER else str(one) for one in listed]
    return name in [one for one in names if one]


def shown(value):
    """A value as the detail shows it: `none` when absent, else its repr."""
    return "none" if value is None else repr(value)


def _claims(task, check_id):
    """The `human-approval` and `artifact-approval` entries of the registry that
    name the check and hold a decision, oldest first. An entry that is not a map
    is skipped."""
    return [e for e in task.get("evidence") or []
            if isinstance(e, dict) and e.get("type") in ("human-approval", ARTIFACT_APPROVAL)
            and e.get("check") == check_id and e.get("decision") in DECISIONS]


def listing(check_id, listed, owner):
    """The approvers a check lists, with `owner` shown as the person it
    names."""
    named = [(f"owner ({owner})" if owner else "owner (no project owner is declared)")
             if one == OWNER else one for one in listed]
    return f"{check_id} lists approvers {', '.join(named)}"


def judge(check_id, check, task, task_dir):
    """`(status, detail)` for the approval half of a human check: `pass`, or
    `fail` with the cause first and the approvers who may approve named."""
    listed = [str(one) for one in (check.get("approvers") or [])]
    owner = project_owner(task_dir)
    who = listing(check_id, listed, owner)
    claims = _claims(task, check_id)
    if not claims:
        return "fail", f"{NO_RECORD}: {who}; {HOW}"
    slug = os.path.basename(os.path.normpath(task_dir))
    generation = task.get("generation")
    first = None
    for entry in reversed(claims):
        name = entry.get("id")
        needed = ARTIFACT_REQUIRED if entry.get("type") == ARTIFACT_APPROVAL else REQUIRED
        missing = [k for k in needed if not entry.get(k)]
        if missing:
            first = first or (f"{NO_RECORD}: {name} is missing {', '.join(missing)}; "
                              f"{who}")
            continue
        if not approver_listed(listed, entry["approver"], owner):
            first = first or (f"{NOT_LISTED}: {name} was by {shown(entry['approver'])}; "
                              f"{who}")
            continue
        if entry.get("issue") != slug:
            first = first or (f"{OTHER_ISSUE}: {name} names issue "
                              f"{shown(entry.get('issue'))}, not {slug}; {who}")
            continue
        if entry.get("generation") != generation:
            first = first or (f"{OTHER_GENERATION}: {name} was given for generation "
                              f"{shown(entry.get('generation'))}, the issue is at "
                              f"generation {shown(generation)}; {who}")
            continue
        if entry["decision"] == REJECTED:
            return "fail", (f"{WITHDRAWN}: {name} by {shown(entry['approver'])} "
                            f"rejected {check_id}; {who}")
        return "pass", f"{name}: approved by {entry['approver']}"
    return "fail", first
