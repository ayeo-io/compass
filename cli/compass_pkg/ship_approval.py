# compass_pkg.ship_approval - the ship approval every delivery issue owes
"""The check `ship-approval-present`: a person approved the change at ship (#355).

Every delivery row of `evidence_required` owes the token `ship-approval`; a
spike owes nothing. An issue owes it only when its stored `evidence_required`
lists it, so an issue assessed before the token existed gains no row.
`compass check` runs the check outside every gate and adds no row when the
token is not owed. No waiver excuses it (`never_waived` in the check set),
because the typed approval is already the way a person stands in for a
missing review.

Two records count, and nothing else:

- a `pr-approval` record for the pull request the manifest links, which
  `compass issue link set --pr <n>` copies from GitHub after the merge: the
  latest review of a person other than the pull request's author was an
  approval;
- a `human-approval` record with `ship: <slug>`, given for this issue and its
  generation, that no `approval-withdrawal` names. A person types it.

A sign-off of guardrail `G5` does not count. It is given at specify, before
code exists, and a labelled change must not owe less at ship than an
ordinary one (VD-029).

The check fails only when the manifest records the pull request as merged
(`pull_request.merged_at`) and no approval is on record. Otherwise it has
nothing to check and names the command that records the approval. It never
refuses a landing: `ship-commit` lands the issue before a pull request
merges, so a refusal there would stop every project that uses pull requests.
`compass check` never calls `gh`; it reads what the manifest holds.
"""
# DEPENDENCY: standard library (os); compass_pkg.approval_records (`not_withdrawn`,
# `provenance`), check_results and status_words. It imports no command module,
# so the check registry can import it.
from __future__ import annotations

import os

from compass_pkg import approval_records, status_words
from compass_pkg.check_results import NOTHING_TO_CHECK

#: The token every delivery issue owes.
TOKEN = "ship-approval"
#: The check of the token.
CHECK = "ship-approval-present"
#: The evidence type of an approving review copied from the merged pull request.
PR_APPROVAL = "pr-approval"
#: The subject key of a typed ship approval on a `human-approval` record.
SHIP = "ship"
#: The fields an approval needs before it counts.
REQUIRED = ("approver", "timestamp")


def owed(task):
    """True when the issue's stored `evidence_required` lists the token."""
    owed_tokens = task.get("evidence_required") if isinstance(task, dict) else None
    return isinstance(owed_tokens, list) and TOKEN in owed_tokens


def _slug(task_dir):
    return os.path.basename(os.path.normpath(task_dir))


def _linked(task):
    """`(repo, number)` of the linked pull request, or None."""
    pr = task.get("pull_request")
    if not isinstance(pr, dict) or not pr.get("repo") or pr.get("number") is None:
        return None
    return pr["repo"], pr["number"]


def _complete(record):
    return record.get("decision") == approval_records.APPROVED and all(
        record.get(k) for k in REQUIRED)


def _pr_approvals(task, registry):
    """The `pr-approval` records of the linked pull request."""
    linked = _linked(task)
    if linked is None:
        return []
    out = []
    for e in registry:
        pr = e.get("pull_request")
        if (e.get("type") == PR_APPROVAL and isinstance(pr, dict)
                and (pr.get("repo"), pr.get("number")) == linked and _complete(e)):
            out.append(e)
    return out


def _typed_approvals(task, task_dir, registry):
    """The typed ship approvals given for this issue and its generation."""
    slug = _slug(task_dir)
    return [e for e in registry
            if e.get("type") == "human-approval" and e.get(SHIP) == slug
            and e.get("issue") == slug and e.get("generation") == task.get("generation")
            and _complete(e)]


def _withdrawn(registry):
    return {e.get("withdraws"): e.get("id") for e in registry
            if e.get("type") == approval_records.WITHDRAWAL}


def _pr_detail(record):
    pr = record["pull_request"]
    detail = (f"{record.get('id', '?')}: {record['approver']} approved pull request "
              f"{pr['repo']}#{pr['number']} at {record['timestamp']}")
    reviewed, head = record.get("reviewed_commit"), record.get("head_commit")
    if reviewed and head and reviewed != head:
        detail += (f"; the review approved commit {str(reviewed)[:12]}, and the merged "
                   f"head is {str(head)[:12]}")
    return detail


def _typed_detail(record):
    return (f"{record.get('id', '?')}: {record['approver']} approved the change at ship "
            f"{approval_records.provenance(record)} at {record['timestamp']}")


def _how(task_dir, task):
    """The commands that record the approval, for a detail."""
    linked = _linked(task)
    number = linked[1] if linked else "<n>"
    return (f"run `compass issue link set --pr {number} --issue {_slug(task_dir)}` after "
            f"the merge, or ask with `compass evidence request --ship`")


def _check_ship_approval_present(task, task_dir):
    """The verdict of `ship-approval-present` 1.0.0 (#355, VD-029), in order:
    an approval on record passes; a merged pull request with none fails; an
    issue in flight, or landed with no merge recorded, has nothing to check."""
    if not owed(task):
        return NOTHING_TO_CHECK, "this issue does not owe the ship approval"
    registry = [e for e in task.get("evidence") or [] if isinstance(e, dict)]
    withdrawn = _withdrawn(registry)
    typed = _typed_approvals(task, task_dir, registry)
    standing = ([(r, _pr_detail) for r in _pr_approvals(task, registry)]
                + [(r, _typed_detail) for r in typed])
    standing = [(r, show) for r, show in standing if r.get("id") not in withdrawn]
    if standing:
        record, show = standing[0]
        return True, "ship approval on record: " + show(record)
    gone = [r.get("id", "?") for r in typed if r.get("id") in withdrawn]
    note = (f" ({approval_records.WITHDRAWN}: {', '.join(gone)})" if gone else "")
    pr = task.get("pull_request") if isinstance(task.get("pull_request"), dict) else {}
    if pr.get("merged_at"):
        return False, (f"pull request {pr.get('repo', '?')}#{pr.get('number', '?')} merged "
                       f"with no approving review by a person other than its author{note}; "
                       f"a person approves with `/compass:approve` after `compass evidence "
                       f"request --ship`. A `G5` sign-off does not count")
    if task.get("land_commit") or status_words.is_completed(task):
        return NOTHING_TO_CHECK, (f"the issue has landed and no merge is recorded{note}; "
                                  f"{_how(task_dir, task)}")
    return NOTHING_TO_CHECK, (f"due at ship; read from the merged pull request{note}: "
                              f"{_how(task_dir, task)}")
