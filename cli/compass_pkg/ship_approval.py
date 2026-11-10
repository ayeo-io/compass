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
  generation, that no `approval-withdrawal` names. A person types it. It holds
  `change_sha256`, the digest of the change it covers. When `compass quick-fix
  finish` records a change with another digest, the record no longer counts
  and the check fails until a person approves the new state (ADR-099
  decision 6). A record with no digest counts as it did before.

A sign-off of guardrail `G5` does not count. It is given at specify, before
code exists, and a labelled change must not owe less at ship than an
ordinary one (VD-029).

The check fails when the only typed approval was given for an earlier state
of the change, and when the manifest records the pull request as merged
(`pull_request.merged_at`) and no approval is on record. Otherwise it has
nothing to check and names the command that records the approval. It never
refuses a landing: `ship-commit` lands the issue before a pull request
merges, so a refusal there would stop every project that uses pull requests.
`compass check` never calls `gh`; it reads what the manifest holds.

`select` and `record_for` are the rules `compass issue link set --pr` uses
to pick, from the merged pull request's reviews, the ones that count, and to
write each as a `pr-approval` record (`docs/github-links.md`).
"""
# DEPENDENCY: standard library (os, datetime); compass_pkg.approval_records (`not_withdrawn`,
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
    # 1.1.0: a typed approval covers the change the person saw (ADR-099
    # decision 6). One given for an earlier state does not count. The approving
    # review of the merged pull request is read after the change stopped moving.
    earlier = [r for r, _show in standing if approval_records.for_earlier_state(task, r)]
    standing = [(r, show) for r, show in standing if r not in earlier]
    if standing:
        record, show = standing[0]
        return True, "ship approval on record: " + show(record)
    if earlier:
        return False, (approval_records.earlier_state_detail(task, earlier)
                       + ", or the approving review is read from the merged pull request")
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


# --- reading the approval from the merged pull request -------------------------
#
# `compass issue link set --pr <n>` (pull_request_link) reads the pull request's
# reviews with `gh` after the merge and calls `select` with them. The rules are
# GitHub's own idea of a reviewer's state at the merge, narrowed to a person
# other than the author, so neither the agent that opened the pull request with
# the person's login nor a bot can give the approval.

#: The review states that change a reviewer's state. A `COMMENTED` review does
#: not, as on GitHub, and a `PENDING` review was never submitted.
_STATE_CHANGING = ("APPROVED", "CHANGES_REQUESTED", "DISMISSED")
#: The account type of a person on GitHub. A GitHub App reviews as `Bot`.
PERSON = "User"


def _when(text):
    """A GitHub timestamp as a datetime, or None when it is not one."""
    from datetime import datetime
    if not isinstance(text, str) or not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def reviewer_login(review):
    """The reviewer's GitHub login, or None."""
    user = review.get("user") if isinstance(review, dict) else None
    login = user.get("login") if isinstance(user, dict) else None
    return login if isinstance(login, str) and login else None


def select(reviews, author, merged_at):
    """`(counting, set_aside)` from a pull request's reviews.

    `reviews` are the entries `gh api .../pulls/<n>/reviews` gives: `id`,
    `state`, `submitted_at`, `commit_id`, `html_url` and `user: {login, type}`.
    A reviewer counts when their latest state-changing review submitted at or
    before `merged_at` is `APPROVED`, their account is a `User`, and they are
    not `author` (compared without letter case, as GitHub compares logins).
    `counting` holds that review per counting reviewer, oldest first.
    `set_aside` holds `(review, reason)` for each other reviewer who approved
    at some time, so the person sees why the approval did not count. A review
    with no login, no id or no readable time is ignored."""
    merged = _when(merged_at)
    by_reviewer = {}
    for review in reviews or []:
        if not isinstance(review, dict) or review.get("state") not in _STATE_CHANGING:
            continue
        login, when = reviewer_login(review), _when(review.get("submitted_at"))
        if login is None or when is None or review.get("id") in (None, ""):
            continue
        by_reviewer.setdefault(login.casefold(), []).append((when, review))
    counting, set_aside = [], []
    for history in by_reviewer.values():
        history.sort(key=lambda pair: pair[0])
        approvals = [r for _w, r in history if r["state"] == "APPROVED"]
        if not approvals:
            continue
        before = [r for w, r in history if merged is not None and w <= merged]
        latest = before[-1] if before else None
        user = latest["user"] if latest else approvals[-1]["user"]
        if (author or "").casefold() == reviewer_login(approvals[-1]).casefold():
            set_aside.append((approvals[-1], "the pull request's author"))
        elif user.get("type") != PERSON:
            set_aside.append((approvals[-1],
                              f"account type {user.get('type') or 'unknown'}, not {PERSON}"))
        elif latest is None:
            set_aside.append((approvals[-1], "given after the merge"))
        elif latest["state"] != "APPROVED":
            set_aside.append((approvals[-1], "a later review is "
                              + latest["state"].lower().replace("_", " ")))
        else:
            counting.append(latest)
    counting.sort(key=lambda r: _when(r["submitted_at"]))
    return counting, set_aside


def record_for(review, pr, issue, generation, read_at, read_as):
    """The `pr-approval` evidence record of one counting review. `pr` holds the
    pull request's `repo`, `number`, `author`, `head_commit`, `merge_commit` and
    `merged_at`. The id is given by the caller."""
    record = {
        "type": PR_APPROVAL,
        "pull_request": {"repo": pr["repo"], "number": pr["number"]},
        "review_id": review["id"],
        "url": review.get("html_url"),
        "approver": reviewer_login(review),
        "pr_author": pr.get("author"),
        "decision": approval_records.APPROVED,
        "timestamp": review["submitted_at"],
        "reviewed_commit": review.get("commit_id"),
        "head_commit": pr.get("head_commit"),
        "merge_commit": pr.get("merge_commit"),
        "merged_at": pr.get("merged_at"),
        "read_at": read_at,
        "read_as": read_as,
        "via": "github",
        "issue": issue,
        "generation": generation,
    }
    return {k: v for k, v in record.items() if v is not None}
