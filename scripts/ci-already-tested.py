#!/usr/bin/env python3
"""Decide whether a tree was already tested green by the whole suite.

Usage: ci-already-tested.py --repo OWNER/NAME --commit M --this-run RUN_ID
                            --output FILE
       ci-already-tested.py --repo OWNER/NAME --pull-request N --head H
                            --this-run RUN_ID [--wait-minutes M]
                            [--poll-seconds S]

The push skip (first form). The `already-tested` job in
.github/workflows/compass.yml runs this on a push to main. When it appends
`skip=true` to FILE (the job's $GITHUB_OUTPUT), every other job in the run
skips. A wrong skip puts an untested tree on main with a green check, so
every condition below must hold, and any error or unknown answer appends
`skip=false`:

1. M is 40 hex characters and RUN_ID is a whole number.
2. The runs of this run's workflow (the workflow of RUN_ID) with event
   `merge_group` and head M, read from the Actions API on one full page,
   hold at least one run other than RUN_ID with head M and event
   `merge_group`. The merge queue tests the exact commit it then pushes to
   main, so a merge-group run on M tested M's tree on M's history.
3. The latest of those runs, by creation time then id, has exactly one
   `self-check` job, and it is completed with conclusion success. A later
   failed run must win over an earlier success.
4. That run has at least one `shard` job, and every one succeeded. A
   pull-request run passes `self-check` without the shards, so this proves
   the run was the whole suite.

A pull-request run no longer runs the whole suite, so a green pull-request
run never lets a push skip. A merge made without the queue runs the suite
on main.

Exit 0 whenever it wrote the line, 1 when it could not write it.

The earlier result (second form). On a title or body edit the jobs that
test a pull request skip, and GitHub counts a skipped required check as
passed, so the `self-check` job runs this instead of the aggregator. It
reads the runs of this run's workflow for head H from the Actions API, not
the `self-check` check runs: GitHub creates a job's check run only once the
jobs it needs have finished, so a suite run still in progress has no
`self-check` check run yet (ayeo-io/compass#578, run 38849230839). A run counts as the
earlier result only when all of these hold:

- it is not RUN_ID, which is this run;
- its head is H and it lists pull request N;
- its `checks` job ran. A title or body edit skips `checks`, and so does
  a run on a draft, so those runs never count, whatever their result. A
  "suite run" below is a run that ran `checks`: on a pull request, the
  fast jobs;
- it was not cancelled.

While such a run is still running, or a run has not yet listed its
`checks` job, the command waits: it polls every S seconds (60 by default)
for at most M minutes (0 by default), then fails, naming the run. With
nothing running it exits 0 only when the latest counted run, by creation
time then id, has a `self-check` job that succeeded, and the pull
request's timeline shows no base change at or after that run was created.
That `self-check` needed every required job, so its result carries theirs.
Exit 1 otherwise, including on any error.

Only these values read from the API or the event reach a command: the head
sha, the commit, the pull-request number and the run and workflow ids,
each checked first and passed as one argument in an argument list, never
through a shell.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime

SHA = re.compile(r"^[0-9a-f]{40}$")
# A run id or pull-request number. GitHub Actions run ids passed 10 digits
# in October 2026; 19 digits is the most a signed 64-bit id holds.
NUMBER = re.compile(r"^[1-9][0-9]{0,18}$")
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


PUSH_LINES = ("Merge group runs on the commit", "Latest merge group run",
              "Its self-check job", "Its shard jobs")
EDIT_LINES = ("Pull request", "Latest suite run",
              "Base changes since that run was created")


class Decision:
    def __init__(self, labels=PUSH_LINES):
        self.lines = {label: "not read" for label in labels}
        self.reasons: list[str] = []
        # The counted runs on the head that are still running. The text-edit
        # form waits while this is not empty.
        self.running: list[int] = []

    def no(self, reason: str):
        self.reasons.append(reason)


def _base_unchanged_since(repo: str, number: int, since: str, d: Decision,
                          label="Base changes since that run was created"):
    """No base change at or after the time `since`."""
    pages = _gh("api", "--paginate", "--slurp", "-X", "GET",
                f"repos/{repo}/issues/{number}/timeline", "-f", "per_page=100")
    if not isinstance(pages, list) or not all(isinstance(p, list) for p in pages):
        raise Unknown("the timeline answer is not a list of pages")
    started = _time(since)
    later = []
    for event in (e for page in pages for e in page):
        if not isinstance(event, dict):
            raise Unknown("an event in the timeline is not an object")
        if event.get("event") in BASE_CHANGES:
            if _time(event.get("created_at")) >= started:
                later.append(f"{event['event']} at {event['created_at']}")
    if later:
        d.lines[label] = ", ".join(later)
        d.no("the base branch changed after the suite run was created: "
             + ", ".join(later))
    else:
        d.lines[label] = "none"


def _listed(answer, key: str, what: str) -> list:
    """The list under `key` of a one-page API answer, refused unless the
    page holds every item the answer counts."""
    if not isinstance(answer, dict) or not isinstance(answer.get(key), list):
        raise Unknown(f"the {what} answer has no {key} list")
    items = answer[key]
    if answer.get("total_count") != len(items):
        raise Unknown(f"the {what} answer lists {len(items)} of "
                      f"{answer.get('total_count')!r}")
    for item in items:
        if not isinstance(item, dict):
            raise Unknown(f"an item in the {what} answer is not an object")
    return items


def _lists_pull_request(run: dict, number: int) -> bool:
    prs = run.get("pull_requests")
    if not isinstance(prs, list):
        raise Unknown(f"workflow run {run.get('id')!r} has no pull_requests list")
    return any(isinstance(pr, dict) and _whole_number(pr.get("number")) == number
               for pr in prs)


# This run's workflow id, read once: a wait polls many times, and the
# workflow token allows 1,000 API requests an hour for the whole repository.
_WORKFLOW_IDS: dict[int, int] = {}


def _workflow_id(repo: str, this_run: int) -> int:
    if this_run not in _WORKFLOW_IDS:
        this = _gh("api", f"repos/{repo}/actions/runs/{this_run}")
        workflow = (_whole_number(this.get("workflow_id"))
                    if isinstance(this, dict) else None)
        if workflow is None:
            raise Unknown(f"workflow run {this_run} names no workflow id")
        _WORKFLOW_IDS[this_run] = workflow
    return _WORKFLOW_IDS[this_run]


def _jobs(repo: str, run_id: int) -> list:
    return _listed(_gh("api", "-X", "GET",
                       f"repos/{repo}/actions/runs/{run_id}/jobs",
                       "-f", "filter=latest", "-f", "per_page=100"),
                   "jobs", f"jobs of run {run_id}")


def decide(args) -> tuple[bool, Decision]:
    """The first form: may this push to main skip the suite?"""
    d = Decision()
    try:
        if not SHA.match(args.commit):
            raise Unknown(f"--commit {args.commit!r} is not 40 hex characters")
        this_run = _whole_number(args.this_run)
        if this_run is None:
            raise Unknown(f"--this-run {args.this_run!r} is not a whole number")
        workflow = _workflow_id(args.repo, this_run)
        runs = _listed(_gh("api", "-X", "GET",
                           f"repos/{args.repo}/actions/workflows/{workflow}/runs",
                           "-f", f"head_sha={args.commit}", "-f", "event=merge_group",
                           "-f", "per_page=100"), "workflow_runs", "workflow runs")
        tested = []
        for run in runs:
            run_id = _whole_number(run.get("id"))
            if run_id is None:
                raise Unknown(f"a workflow run has the id {run.get('id')!r}")
            if (run_id != this_run and run.get("head_sha") == args.commit
                    and run.get("event") == "merge_group"):
                if not isinstance(run.get("created_at"), str):
                    raise Unknown(f"workflow run {run_id} has no creation time")
                tested.append((run_id, run["created_at"]))
        d.lines["Merge group runs on the commit"] = str(len(tested))
        if not tested:
            d.no(f"no merge group run of this workflow tested {args.commit}")
            return False, d
        run_id, created = max(tested, key=lambda r: (_time(r[1]), r[0]))
        d.lines["Latest merge group run"] = f"workflow run {run_id}, created {created}"
        jobs = _jobs(args.repo, run_id)
        self_check = [j for j in jobs if j.get("name") == "self-check"]
        if len(self_check) != 1:
            d.lines["Its self-check job"] = f"{len(self_check)} jobs named self-check"
            d.no(f"workflow run {run_id} has not exactly one self-check job")
        else:
            job = self_check[0]
            state = (job.get("conclusion") if job.get("status") == "completed"
                     else f"{job.get('status')}, not completed")
            d.lines["Its self-check job"] = str(state)
            if job.get("status") != "completed" or job.get("conclusion") != "success":
                d.no(f"the self-check job of workflow run {run_id} is {state}")
        shards = [j for j in jobs if j.get("name") == "shard"
                  or str(j.get("name", "")).startswith("shard (")]
        failed = [f"{j.get('name')} {j.get('conclusion') or j.get('status')}"
                  for j in shards if j.get("conclusion") != "success"]
        d.lines["Its shard jobs"] = (f"{len(shards)}, "
                                     + (", ".join(failed) if failed
                                        else "every one succeeded"))
        if not shards:
            d.no(f"workflow run {run_id} ran no shard job, so it was not the whole suite")
        elif failed:
            d.no(f"a shard job of workflow run {run_id} did not succeed: "
                 + ", ".join(failed))
    except Unknown as exc:
        d.no(f"error: {exc}")
        return False, d
    return not d.reasons, d


def _suite_runs(repo: str, number: int, head: str, this_run: int, d: Decision):
    """The completed runs of this run's workflow that count as the earlier
    result for pull request `number` at `head`, as (id, created_at,
    self-check conclusion). The runs still running go to d.running."""
    workflow = _workflow_id(repo, this_run)
    runs = _listed(_gh("api", "-X", "GET",
                       f"repos/{repo}/actions/workflows/{workflow}/runs",
                       "-f", f"head_sha={head}", "-f", "event=pull_request",
                       "-f", "per_page=100"), "workflow_runs", "workflow runs")
    counted = []
    for run in runs:
        run_id = _whole_number(run.get("id"))
        if run_id is None:
            raise Unknown(f"a workflow run has the id {run.get('id')!r}")
        if (run_id == this_run or run.get("head_sha") != head
                or not _lists_pull_request(run, number)):
            continue
        jobs = _jobs(repo, run_id)
        checks = [j for j in jobs if j.get("name") == "checks"]
        if checks and all(j.get("conclusion") == "skipped" for j in checks):
            continue  # a title or body edit: its result is not the suite's
        if run.get("status") != "completed":
            # Running, or too new to have listed its checks job yet.
            d.running.append(run_id)
            continue
        if run.get("conclusion") == "cancelled" or not checks:
            # A completed run with no checks job never ran the suite.
            continue
        if not isinstance(run.get("created_at"), str):
            raise Unknown(f"workflow run {run_id} has no creation time")
        self_check = [j for j in jobs if j.get("name") == "self-check"]
        conclusion = (self_check[0].get("conclusion") if len(self_check) == 1
                      else "missing: no self-check job")
        counted.append((run_id, run["created_at"], conclusion))
    return counted


def earlier_result(args) -> tuple[bool, Decision]:
    """The second form: may self-check pass on a title or body edit? A
    run still running fails it here and is named in d.running, so the
    caller can wait and ask again."""
    d = Decision(EDIT_LINES)
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
        label = "Latest suite run"
        counted = _suite_runs(args.repo, number, args.head, this_run, d)
        if d.running:
            runs = ", ".join(str(r) for r in d.running)
            d.lines[label] = f"workflow run {runs} still running"
            d.no(f"workflow run {runs} on the head is still running")
            return False, d
        if not counted:
            d.lines[label] = "none"
            d.no(f"the head has no suite run for #{number} other than this run")
            return False, d
        run_id, created, conclusion = max(
            counted, key=lambda r: (_time(r[1]), r[0]))
        d.lines[label] = (f"workflow run {run_id}, created {created}, self-check "
                          f"{conclusion} (latest of {len(counted)})")
        if conclusion != "success":
            d.no(f"the self-check of the latest suite run, {run_id}, "
                 f"ended {conclusion}")
            return False, d
        _base_unchanged_since(args.repo, number, created, d,
                              label="Base changes since that run was created")
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
        print("Decision: skip. The merge queue tested this commit green with the "
              "whole suite.")
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
    deadline = time.monotonic() + args.wait_minutes * 60
    while True:
        try:
            passes, d = earlier_result(args)
        except Exception as exc:  # any surprise fails the check
            passes, d = False, Decision(EDIT_LINES)
            d.no(f"error: {type(exc).__name__}: {exc}")
        if not d.running:
            break
        if time.monotonic() >= deadline:
            d.no(f"it was still running after a wait of {args.wait_minutes:g} minutes")
            break
        runs = ", ".join(str(r) for r in d.running)
        print(f"Waiting for workflow run {runs} on the head to finish; "
              f"checking again in {args.poll_seconds:g} seconds.", flush=True)
        time.sleep(args.poll_seconds)
    _print_lines(d)
    if passes:
        print("Decision: pass. The latest suite run on this head succeeded, "
              "and the base has not changed since it was created.")
        return 0
    print("Decision: fail, because " + "; ".join(d.reasons) + ".")
    return 1


def _not_negative(text: str) -> float:
    try:
        value = float(text)
    except ValueError:
        value = -1.0
    if not 0 <= value < float("inf"):
        raise argparse.ArgumentTypeError(f"{text!r} is not a number of 0 or more")
    return value


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="ci-already-tested.py")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--commit")
    parser.add_argument("--output")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--pull-request")
    parser.add_argument("--head")
    parser.add_argument("--this-run")
    parser.add_argument("--wait-minutes", type=_not_negative, default=0.0)
    parser.add_argument("--poll-seconds", type=_not_negative, default=60.0)
    args = parser.parse_args(argv)
    push = (args.commit, args.output)
    edit = (args.pull_request, args.head)
    if args.this_run and all(push) and not any(edit):
        return _push_skip(args)
    if args.this_run and all(edit) and not any(push):
        return _earlier(args)
    parser.error("give either --commit, --this-run and --output, "
                 "or --pull-request, --head and --this-run")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
