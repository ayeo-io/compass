#!/usr/bin/env python3
"""Decide whether a tree was already tested green on its pull request.

Usage: ci-already-tested.py --repo OWNER/NAME --commit M --output FILE
                            [--branch main]
       ci-already-tested.py --repo OWNER/NAME --pull-request N --head H
                            --this-run RUN_ID

The push skip (first form). The `already-tested` job in
.github/workflows/compass.yml runs this on a push to main. When it appends
`skip=true` to FILE (the job's $GITHUB_OUTPUT), every other job in the run
skips. A wrong skip puts an untested tree on main with a green check, so
every condition below must hold, and any error or unknown answer appends
`skip=false`:

1. Exactly one pull request listed for M by the GitHub API has merge
   commit M, a merge time, and base branch --branch.
2. Its head sha is 40 hex characters and the head commit is in the local
   history, fetched from refs/pull/<number>/head when missing (the number
   checked as a whole number first).
3. M's tree equals the head's tree.
4. M's first parent is an ancestor of the head. A pull-request run tests
   the head merged into the base as it stood then; when the base had not
   moved past the head's own history, that merge has the head's tree, so
   equal trees mean the tested tree.
5. The head's `self-check` check runs from the GitHub Actions app are all
   completed, and the latest (by start time, then id) has conclusion
   success. A later failed run must win over an earlier success.
6. The pull request's timeline shows no base change at or after the time
   that run started. A pull-request run tests the head merged into the
   base it had then, so a run from before a retarget says nothing about
   the base the pull request merged into. A timeline that cannot be read
   fails this condition.

Exit 0 whenever it wrote the line, 1 when it could not write it.

The earlier result (second form). On a title or body edit the suite jobs
skip, and GitHub counts a skipped required check as passed, so the
`self-check` job runs this instead of the aggregator. It exits 0 only when
conditions 5 and 6 hold for head H and pull request N, leaving out the
check runs of workflow run RUN_ID, which is this run. The earlier run's
`self-check` needed every required job, so its result carries theirs.
Exit 1 otherwise, including on any error.

Only two values read from the API or the event reach a command, the head
sha and the pull-request number, each checked first and passed as one
argument in an argument list, never through a shell.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime

SHA = re.compile(r"^[0-9a-f]{40}$")
NUMBER = re.compile(r"^[1-9][0-9]{0,9}$")
# The timeline events that mean the pull request's base branch changed: a
# person retargeted it, or GitHub did when the old base was merged and
# deleted.
BASE_CHANGES = ("base_ref_changed", "automatic_base_change_succeeded")


class Unknown(Exception):
    """An answer this decision cannot rely on."""


def _gh(*args: str):
    try:
        r = subprocess.run(["gh", *args], capture_output=True, text=True,
                           timeout=120)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise Unknown(f"gh {' '.join(args)} did not run: {exc}") from exc
    if r.returncode != 0:
        raise Unknown(f"gh {' '.join(args)} exited {r.returncode}: "
                      f"{r.stderr.strip()[:300]}")
    try:
        return json.loads(r.stdout)
    except ValueError as exc:
        raise Unknown(f"gh {' '.join(args)} did not answer JSON: "
                      f"{r.stdout.strip()[:120]!r}") from exc


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True,
                          timeout=300)


def _tree(commit: str) -> str:
    r = _git("rev-parse", "--verify", f"{commit}^{{tree}}")
    if r.returncode != 0:
        raise Unknown(f"git cannot read the tree of {commit}: {r.stderr.strip()}")
    return r.stdout.strip()


def _has_commit(sha: str) -> bool:
    return _git("cat-file", "-e", f"{sha}^{{commit}}").returncode == 0


def _whole_number(value):
    """The value as an int from 1 up, or None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 1 else None
    if isinstance(value, str) and NUMBER.match(value):
        return int(value)
    return None


def _time(text) -> datetime:
    if not isinstance(text, str):
        raise Unknown(f"the time {text!r} is not text")
    try:
        when = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Unknown(f"the time {text!r} cannot be read") from exc
    if when.tzinfo is None:
        raise Unknown(f"the time {text!r} has no time zone")
    return when


class Decision:
    def __init__(self):
        self.lines = {
            "Pull request": "not read",
            "Merged tree": "not read",
            "Head tree": "not read",
            "First parent is an ancestor of the head": "not read",
            "Latest self-check conclusion": "not read",
            "Base changes since that run started": "not read",
        }
        self.reasons: list[str] = []

    def no(self, reason: str):
        self.reasons.append(reason)


def _pull_request(args, d: Decision):
    pulls = _gh("api", f"repos/{args.repo}/commits/{args.commit}/pulls")
    if not isinstance(pulls, list):
        raise Unknown("the pull requests answer is not a list")
    matching = []
    for pr in pulls:
        if not isinstance(pr, dict):
            raise Unknown("a pull request in the answer is not an object")
        base = pr.get("base") if isinstance(pr.get("base"), dict) else {}
        if (pr.get("merge_commit_sha") == args.commit and pr.get("merged_at")
                and base.get("ref") == args.branch):
            matching.append(pr)
    listed = ", ".join(f"#{p.get('number')}" for p in pulls if isinstance(p, dict))
    if len(matching) != 1:
        d.lines["Pull request"] = (f"{len(matching)} merged into {args.branch} "
                                   f"with merge commit {args.commit} "
                                   f"(listed: {listed or 'none'})")
        d.no("not exactly one pull request was merged into "
             f"{args.branch} as {args.commit}")
        return None
    pr = matching[0]
    head = (pr.get("head") or {}).get("sha") if isinstance(pr.get("head"), dict) else None
    d.lines["Pull request"] = f"#{pr.get('number')}, head {head}"
    return pr


def _head_commit(pr: dict, d: Decision):
    head = pr["head"].get("sha")
    if not isinstance(head, str) or not SHA.match(head):
        d.no(f"the head sha {head!r} is not 40 hex characters")
        return None
    if _has_commit(head):
        return head
    number = pr.get("number")
    if isinstance(number, bool) or not isinstance(number, int) or number < 1:
        d.no(f"the pull request number {number!r} is not a whole number, "
             "so the missing head is not fetched")
        return None
    fetched = _git("fetch", "--no-tags", "origin", f"refs/pull/{number}/head")
    if fetched.returncode != 0 or not _has_commit(head):
        d.no(f"the head {head} is not in the local history and could not be "
             f"fetched: {' '.join(fetched.stderr.split())[:200]}")
        return None
    return head


def _workflow_run(run: dict, repo: str):
    """The workflow run id in a check run's details URL, or None."""
    url = run.get("details_url")
    if not isinstance(url, str):
        return None
    m = re.match(rf"^https://github\.com/{re.escape(repo)}/actions/runs/(\d+)/", url)
    return int(m.group(1)) if m else None


def _latest_self_check(repo: str, head: str, d: Decision, *, leave_out=None):
    """Condition 5. The latest self-check run on the head when it
    succeeded, else None with the reason recorded. The check runs of
    workflow run `leave_out` are left out."""
    answer = _gh("api", "-X", "GET", f"repos/{repo}/commits/{head}/check-runs",
                 "-f", "check_name=self-check", "-f", "filter=all",
                 "-f", "per_page=100")
    if not isinstance(answer, dict) or not isinstance(answer.get("check_runs"), list):
        raise Unknown("the check-runs answer has no check_runs list")
    runs = answer["check_runs"]
    if answer.get("total_count", len(runs)) != len(runs):
        raise Unknown(f"the check-runs answer lists {len(runs)} of "
                      f"{answer.get('total_count')} runs")
    ours = []
    for run in runs:
        if not isinstance(run, dict):
            raise Unknown("a check run in the answer is not an object")
        app = run.get("app") if isinstance(run.get("app"), dict) else {}
        if run.get("name") != "self-check" or app.get("slug") != "github-actions":
            continue
        if leave_out is not None and _workflow_run(run, repo) == leave_out:
            continue
        ours.append(run)
    label = "Latest self-check conclusion"
    if not ours:
        d.lines[label] = "no self-check run from GitHub Actions"
        d.no("the head has no self-check run from GitHub Actions"
             + (" other than this run's" if leave_out is not None else ""))
        return None
    running = [r for r in ours if r.get("status") != "completed"]
    if running:
        d.lines[label] = f"{len(running)} of {len(ours)} runs not completed"
        d.no("a self-check run on the head is not completed")
        return None
    for run in ours:
        if not isinstance(run.get("started_at"), str) or not isinstance(run.get("id"), int):
            raise Unknown("a self-check run has no start time or id")
    latest = max(ours, key=lambda r: (_time(r["started_at"]), r["id"]))
    conclusion = latest.get("conclusion")
    workflow_run = _workflow_run(latest, repo)
    d.lines[label] = (
        f"{conclusion} (run {latest['id']}"
        + (f" in workflow run {workflow_run}" if workflow_run else "")
        + f", started {latest['started_at']}, latest of {len(ours)})")
    if conclusion != "success":
        d.no(f"the latest self-check run on the head ended {conclusion}")
        return None
    return latest


def _base_unchanged_since(repo: str, number: int, run: dict, d: Decision):
    """Condition 6: no base change at or after the run started."""
    label = "Base changes since that run started"
    pages = _gh("api", "--paginate", "--slurp", "-X", "GET",
                f"repos/{repo}/issues/{number}/timeline", "-f", "per_page=100")
    if not isinstance(pages, list) or not all(isinstance(p, list) for p in pages):
        raise Unknown("the timeline answer is not a list of pages")
    started = _time(run["started_at"])
    later = []
    for event in (e for page in pages for e in page):
        if not isinstance(event, dict):
            raise Unknown("an event in the timeline is not an object")
        if event.get("event") in BASE_CHANGES:
            if _time(event.get("created_at")) >= started:
                later.append(f"{event['event']} at {event['created_at']}")
    if later:
        d.lines[label] = ", ".join(later)
        d.no("the base branch changed after the self-check run started: "
             + ", ".join(later))
    else:
        d.lines[label] = "none"


def decide(args) -> tuple[bool, Decision]:
    """The first form: may this push to main skip the suite?"""
    d = Decision()
    try:
        if not SHA.match(args.commit):
            raise Unknown(f"--commit {args.commit!r} is not 40 hex characters")
        pr = _pull_request(args, d)
        if pr is None:
            return False, d
        head = _head_commit(pr, d)
        if head is None:
            return False, d
        merged_tree, head_tree = _tree(args.commit), _tree(head)
        d.lines["Merged tree"] = merged_tree
        d.lines["Head tree"] = head_tree
        if merged_tree != head_tree:
            d.no("the merged tree differs from the head's tree")
        anc = _git("merge-base", "--is-ancestor", f"{args.commit}^1", head)
        if anc.returncode == 0:
            d.lines["First parent is an ancestor of the head"] = "yes"
        elif anc.returncode == 1:
            d.lines["First parent is an ancestor of the head"] = "no"
            d.no("the merge commit's first parent is not an ancestor of the head")
        else:
            raise Unknown(f"git merge-base failed: {anc.stderr.strip()}")
        latest = _latest_self_check(args.repo, head, d)
        if latest is not None:
            number = _whole_number(pr.get("number"))
            if number is None:
                d.no(f"the pull request number {pr.get('number')!r} is not a "
                     "whole number, so its timeline is not read")
            else:
                _base_unchanged_since(args.repo, number, latest, d)
    except Unknown as exc:
        d.no(f"error: {exc}")
        return False, d
    return not d.reasons, d


def earlier_result(args) -> tuple[bool, Decision]:
    """The second form: may self-check pass on a title or body edit?"""
    d = Decision()
    for label in ("Merged tree", "Head tree", "First parent is an ancestor of the head"):
        del d.lines[label]
    try:
        number = _whole_number(args.pull_request)
        if number is None:
            raise Unknown(f"--pull-request {args.pull_request!r} is not a whole number")
        if not SHA.match(args.head):
            raise Unknown(f"--head {args.head!r} is not 40 hex characters")
        this_run = _whole_number(args.this_run)
        if this_run is None:
            raise Unknown(f"--this-run {args.this_run!r} is not a whole number")
        d.lines["Pull request"] = f"#{number}, head {args.head}"
        latest = _latest_self_check(args.repo, args.head, d, leave_out=this_run)
        if latest is not None:
            _base_unchanged_since(args.repo, number, latest, d)
    except Unknown as exc:
        d.no(f"error: {exc}")
        return False, d
    return not d.reasons, d


def _print_lines(d: Decision):
    for label, value in d.lines.items():
        print(f"{label}: {value}")


def _push_skip(args) -> int:
    try:
        skip, d = decide(args)
    except Exception as exc:  # any surprise answers "run the suite"
        skip, d = False, Decision()
        d.no(f"error: {type(exc).__name__}: {exc}")
    print(f"Merged commit: {args.commit}")
    _print_lines(d)
    if skip:
        print("Decision: skip. This tree was tested green on its pull request.")
    else:
        print("Decision: run the suite, because " + "; ".join(d.reasons) + ".")
    try:
        with open(args.output, "a", encoding="utf-8") as out:
            out.write(f"skip={'true' if skip else 'false'}\n")
    except OSError as exc:
        sys.stderr.write(f"ci-already-tested.py: cannot write {args.output}: {exc}\n")
        return 1
    return 0


def _earlier(args) -> int:
    try:
        passes, d = earlier_result(args)
    except Exception as exc:  # any surprise fails the check
        passes, d = False, Decision()
        d.no(f"error: {type(exc).__name__}: {exc}")
    _print_lines(d)
    if passes:
        print("Decision: pass. The latest earlier self-check on this head "
              "succeeded, and the base has not changed since it started.")
        return 0
    print("Decision: fail, because " + "; ".join(d.reasons) + ".")
    return 1


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="ci-already-tested.py")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--commit")
    parser.add_argument("--output")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--pull-request")
    parser.add_argument("--head")
    parser.add_argument("--this-run")
    args = parser.parse_args(argv)
    push = (args.commit, args.output)
    edit = (args.pull_request, args.head, args.this_run)
    if all(push) and not any(edit):
        return _push_skip(args)
    if all(edit) and not any(push):
        return _earlier(args)
    parser.error("give either --commit and --output, "
                 "or --pull-request, --head and --this-run")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
