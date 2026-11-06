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

`on_default_branch` is what `compass check` reads: for a landed issue, whether
origin's default branch reaches `land_commit`. A finding is advice and never
fails the run, because a record written before the merge, or in a clone that
has not fetched, is not wrong work.
"""
# DEPENDENCY: standard library (json, re, subprocess) and compass_pkg.core,
# check_results, status_words, issue_link (the `gh` runner and the target
# patterns) and github_links (origin's repository and default branch).
# Imported by issue_link.cmd_issue_link and check_cmd, inside functions.
from __future__ import annotations

import json
import re
import subprocess

from compass_pkg import issue_link, status_words
from compass_pkg.check_results import ADVISORY_FAILURE
from compass_pkg.core import CompassError, find_upwards
from compass_pkg.github_links import link_base

_PR_URL = re.compile(rf"https://github\.com/({issue_link._OWNER}/{issue_link._NAME})"
                     rf"/pull/({issue_link._NUMBER})/?")
_BARE = re.compile(issue_link._NUMBER)
_OID = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
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


def read_pr(text, project_root, verb):
    """`(repo, number, merge_commit)` for the pull request `text` names, where
    `merge_commit` is None until GitHub reports it merged. Raises CompassError,
    having written nothing, when `text` names no pull request or `gh` cannot
    read it."""
    target = parse_pr(text, project_root)
    if target is None:
        raise CompassError(
            f"{verb}: '{text}' is not a pull request; use owner/repo#number, "
            "https://github.com/owner/repo/pull/number, or a number when origin "
            "is on github.com. Nothing was written.")
    repo, number = target
    try:
        answer = issue_link._gh(["pr", "view", str(number), "--repo", repo,
                                  "--json", "number,state,mergeCommit"])
        data = json.loads(answer)
    except (issue_link.SyncError, ValueError) as exc:
        raise CompassError(f"{verb}: cannot read pull request {repo}#{number}: {exc}. "
                           "Nothing was written.") from None
    merged = data.get("mergeCommit") if isinstance(data, dict) else None
    oid = merged.get("oid") if isinstance(merged, dict) else None
    if data.get("state") != "MERGED" or not (isinstance(oid, str) and _OID.fullmatch(oid)):
        oid = None
    return repo, number, oid


def apply(task, slug, repo, number, oid):
    """Write the pull request, and the merge commit when it applies, into the
    issue's manifest. Returns the lines that say what was written."""
    task["pull_request"] = {"repo": repo, "number": number}
    lines = [f"{slug} -> pull request {repo}#{number}."]
    if oid is None:
        lines.append("The pull request is not merged, so land_commit does not change. "
                     "Run this again after the merge.")
    elif not status_words.is_completed(task):
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
    has no `land_commit`, or the clone records no default branch for origin."""
    land = task.get("land_commit")
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
