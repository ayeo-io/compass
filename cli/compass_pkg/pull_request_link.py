# compass_pkg.pull_request_link - an issue's pull request and the commit it merged as
"""Records the pull request that carries an issue, and moves `land_commit` to its merge.

`compass ship-commit` writes `land_commit` from the commit it made on the
branch. A repository that squash-merges pull requests never puts that commit
on the default branch, so the record names a commit a reader cannot find
there. `compass issue link set --pr <n>` asks `gh pr view` for the pull
request and writes it to the manifest as `pull_request: {repo, number}`. When
the pull request is merged and the issue has landed, it also writes the merge
commit GitHub reports to `land_commit`. Run it when the pull request opens to
record the link, and again after the merge.

After the merge it also reads the pull request's reviews (`gh api --paginate
repos/<r>/pulls/<n>/reviews`) and the login `gh` reads as (`gh api user`),
before anything is written. Each review that counts as the ship approval
(`ship_approval.select`) becomes a `pr-approval` evidence record, and
`pull_request` gains `merged_at`, `merge_commit` and `author`. Compass writes
nothing to GitHub, and `compass check` never calls `gh`: it reads these
records (#355).

`on_default_branch` is what `compass check` reads: for a landed issue, whether
origin's default branch reaches `land_commit`. A finding is advice and never
fails the run, because a record written before the merge, or in a clone that
has not fetched, is not wrong work.
"""
# DEPENDENCY: standard library (json, re, subprocess, dataclasses, datetime)
# and compass_pkg.core, check_results, status_words, ship_approval (which
# reviews count), issue_link (the `gh` runner and the target
# patterns) and github_links (origin's repository and default branch).
# Imported by issue_link.cmd_issue_link and check_cmd, inside functions.
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone

from compass_pkg import issue_link, landing, ship_approval, status_words
from compass_pkg.check_results import ADVISORY_FAILURE
from compass_pkg.core import CompassError, find_upwards
from compass_pkg.github_links import link_base

_PR_URL = re.compile(rf"https://github\.com/({issue_link._OWNER}/{issue_link._NAME})"
                     rf"/pull/({issue_link._NUMBER})/?")
_BARE = re.compile(issue_link._NUMBER)
_OID = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
#: The id of a `pr-approval` record, followed by a number.
_ID_PREFIX = "EV-PR-APPROVAL-"
#: Seconds one `git` call may take.
_TIMEOUT = 15


def parse_pr(text, project_root):
    """`(repo, number)` from `owner/repo#number`, a pull request URL on github.com,
    or a bare number in origin's repository; None for anything else."""
    text = text or ""
    for pattern in (issue_link._SHORT, _PR_URL):
        found = pattern.fullmatch(text)
        if found and issue_link._repo_ok(found.group(1)):
            return found.group(1), int(found.group(2))
    if _BARE.fullmatch(text):
        repo = link_base(project_root).repo
        return (repo, int(text)) if repo else None
    return None


#: The fields of the pull request `read_pr` asks `gh pr view` for.
PR_FIELDS = "number,state,mergeCommit,mergedAt,author,headRefOid,url"
#: The `--jq` filter of the reviews call: one JSON object per review, with only
#: the fields `ship_approval.select` reads and the record copies.
REVIEWS_JQ = (".[] | {id, state, submitted_at, commit_id, html_url, "
              "user: {login: .user.login, type: .user.type}}")


@dataclass
class PullRequest:
    """What `read_pr` read. `merge_commit`, `merged_at`, `reviews` and
    `read_as` are None until GitHub reports the pull request merged."""
    repo: str
    number: int
    merge_commit: str | None = None
    merged_at: str | None = None
    author: str | None = None
    head_commit: str | None = None
    reviews: list | None = None
    read_as: str | None = None
    read_at: str | None = None


def _text(value):
    return value if isinstance(value, str) and value else None


def _reviews(repo, number):
    """The pull request's reviews, one dict per review. Raises SyncError when
    `gh` fails or prints a line that is not a JSON object."""
    answer = issue_link._gh(["api", "--paginate", f"repos/{repo}/pulls/{number}/reviews",
                             "--jq", REVIEWS_JQ])
    out = []
    for line in answer.splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except ValueError:
            raise issue_link.SyncError("gh printed a review that is not JSON") from None
        if not isinstance(item, dict):
            raise issue_link.SyncError("gh printed a review that is not a JSON object")
        out.append(item)
    return out


def _reader():
    """The login `gh` reads as. Raises SyncError when `gh` cannot say."""
    login = issue_link._gh(["api", "user", "--jq", ".login"]).strip()
    if not login:
        raise issue_link.SyncError("gh api user gave no login")
    return login


def read_pr(text, project_root, verb):
    """The `PullRequest` that `text` names. Once GitHub reports it merged, it
    also holds the reviews and the login that read them. Raises CompassError,
    having written nothing, when `text` names no pull request or `gh` cannot
    read it or its reviews."""
    target = parse_pr(text, project_root)
    if target is None:
        raise CompassError(
            f"{verb}: '{text}' is not a pull request; use owner/repo#number, "
            "https://github.com/owner/repo/pull/number, or a number when origin "
            "is on github.com. Nothing was written.")
    repo, number = target
    try:
        answer = issue_link._gh(["pr", "view", str(number), "--repo", repo,
                                  "--json", PR_FIELDS])
        data = json.loads(answer)
        if not isinstance(data, dict):
            raise ValueError("not a JSON object")
    except (issue_link.SyncError, ValueError) as exc:
        raise CompassError(f"{verb}: cannot read pull request {repo}#{number}: {exc}. "
                           "Nothing was written.") from None
    author = data.get("author")
    pr = PullRequest(repo, number,
                     author=_text(author.get("login")) if isinstance(author, dict) else None,
                     head_commit=_text(data.get("headRefOid")))
    merged = data.get("mergeCommit")
    oid = merged.get("oid") if isinstance(merged, dict) else None
    if data.get("state") != "MERGED" or not (isinstance(oid, str) and _OID.fullmatch(oid)):
        return pr
    pr.merge_commit, pr.merged_at = oid, _text(data.get("mergedAt"))
    if pr.merged_at is None or pr.author is None:
        raise CompassError(f"{verb}: gh reports pull request {repo}#{number} merged but "
                           "gives no merge time or author, so its reviews cannot be "
                           "judged. Nothing was written.")
    try:
        pr.reviews = _reviews(repo, number)
        pr.read_as = _reader()
    except issue_link.SyncError as exc:
        raise CompassError(f"{verb}: cannot read the reviews of pull request "
                           f"{repo}#{number}: {exc}. Nothing was written.") from None
    pr.read_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return pr


def _next_id(registry):
    taken = {e.get("id") for e in registry}
    n = 1
    while f"{_ID_PREFIX}{n}" in taken:
        n += 1
    return f"{_ID_PREFIX}{n}"


def _same(a, b):
    """Two records of one review that differ only in when and as whom they were read."""
    drop = ("id", "read_at", "read_as")
    return ({k: v for k, v in a.items() if k not in drop}
            == {k: v for k, v in b.items() if k not in drop})


def _record_approvals(task, slug, pr):
    """Write a `pr-approval` record per counting review, replacing the record of
    the same review in place. Returns the lines that say what counted and what
    was set aside."""
    counting, set_aside = ship_approval.select(pr.reviews, pr.author, pr.merged_at)
    registry = task.setdefault("evidence", [])
    facts = {"repo": pr.repo, "number": pr.number, "author": pr.author,
             "head_commit": pr.head_commit, "merge_commit": pr.merge_commit,
             "merged_at": pr.merged_at}
    lines = []
    for review in counting:
        record = ship_approval.record_for(review, facts, slug, task.get("generation"),
                                          pr.read_at, pr.read_as)
        at = next((i for i, e in enumerate(registry)
                   if isinstance(e, dict) and e.get("type") == ship_approval.PR_APPROVAL
                   and e.get("review_id") == review["id"]), None)
        if at is None:
            record = {"id": _next_id(registry), **record}
            registry.append(record)
            said = "recorded as"
        elif _same(registry[at], record):
            record = registry[at]
            said = "already on record as"
        else:
            record = {"id": registry[at].get("id") or _next_id(registry), **record}
            registry[at] = record
            said = "recorded again as"
        lines.append(f"Ship approval: {record['approver']}, review {review['id']}, "
                     f"{said} {record['id']}.")
    for review, reason in set_aside:
        lines.append(f"Set aside: {ship_approval.reviewer_login(review)}, review "
                     f"{review['id']}: {reason}.")
    if not counting:
        # Two lines, so neither is cut at the terminal width.
        lines += ["No approving review by a person other than the author.",
                  "A person approves with `/compass:approve` after `compass evidence "
                  "request --ship`."]
    return lines


def apply(task, slug, pr):
    """Write the pull request, its approving reviews and the merge commit, where
    each applies, into the issue's manifest. Returns the lines that say what
    was written."""
    link = {"repo": pr.repo, "number": pr.number}
    if pr.merge_commit is not None:
        link.update(merged_at=pr.merged_at, merge_commit=pr.merge_commit, author=pr.author)
    task["pull_request"] = link
    lines = [f"{slug} -> pull request {pr.repo}#{pr.number}."]
    oid = pr.merge_commit
    if oid is None:
        lines += ["The pull request is not merged, so land_commit does not change.",
                  "The ship approval is read after the merge. Run this again then."]
        return lines
    lines += _record_approvals(task, slug, pr)
    if not status_words.is_completed(task):
        lines.append("The issue has not landed, so land_commit is left to "
                     "`compass ship-commit`.")
    else:
        before = task.get("land_commit")
        task["land_commit"] = oid
        if before == oid:
            lines.append(f"land_commit already names the merge commit {oid[:8]}.")
        else:
            was = before[:8] if isinstance(before, str) and before else "nothing"
            lines.append(f"land_commit moved from {was} to {oid[:8]}, the merge commit.")
    return lines


def _git(args, root):
    try:
        return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True,
                              timeout=_TIMEOUT, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None


def on_default_branch(task, task_dir):
    """`(passed, detail)`: whether origin's default branch reaches a landed issue's
    `land_commit`. None when there is nothing to judge: the issue has not landed,
    has no land commit (`landing.land_commit`), or the clone records no default
    branch for origin."""
    land = landing.land_commit(task, task_dir)
    if not status_words.is_completed(task) or not isinstance(land, str) or not land:
        return None
    root = find_upwards(task_dir, ".compass") or task_dir
    branch = link_base(root).branch
    if not branch:
        return None
    done = _git(["merge-base", "--is-ancestor", "--end-of-options", land,
                 "refs/remotes/origin/" + branch], root)
    if done is not None and done.returncode == 0:
        return True, f"land_commit {land[:12]} is on origin/{branch}"
    linked = task.get("pull_request")
    target = ("%s#%s" % (linked.get("repo"), linked.get("number"))
              if isinstance(linked, dict) and linked.get("repo") else "<n>")
    return ADVISORY_FAILURE, (
        f"land_commit {land[:12]} is not on origin/{branch}. A squash merge leaves the "
        "commit ship-commit made off the default branch. After the merge, run "
        f"`compass issue link set --pr {target} --issue {task.get('issue') or '<slug>'}` "
        f"to record the merge commit, or `git fetch` if origin/{branch} is behind")
