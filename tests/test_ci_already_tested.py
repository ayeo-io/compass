"""The decisions of `scripts/ci-already-tested.py`.

On a push to main, `.github/workflows/compass.yml` skips every other job
when the command writes `skip=true`. A wrong skip lets an untested tree
onto main with a green tick, so the decision takes four conditions and
answers "run" on anything unknown. Only a green merge-group run of the
whole suite on the pushed commit lets a push skip
(ayeo-io/compass-delivery#362). On a title or body edit, the command
reports the earlier result instead.

The tests run the command with a `gh` stand-in on PATH that answers from a
table and records any call the table does not hold, so the test fails on
it.
"""
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "ci-already-tested.py"
REPO = "owner/name"

SHIM = '''#!{python}
import json, os, sys
base = os.environ["FAKE_GH_DIR"]
argv = sys.argv[1:]
with open(os.path.join(base, "calls.jsonl"), "a") as log:
    log.write(json.dumps(argv) + "\\n")
table = json.load(open(os.path.join(base, "table.json")))
for index, entry in enumerate(table):
    if entry["argv"] == argv:
        # An entry with "answers" gives the next one on each call and then
        # repeats the last, so a test can show a run that later completes.
        if "answers" in entry:
            seen = os.path.join(base, "seen-%d" % index)
            n = int(open(seen).read()) if os.path.exists(seen) else 0
            open(seen, "w").write(str(n + 1))
            entry = entry["answers"][min(n, len(entry["answers"]) - 1)]
        sys.stdout.write(entry.get("stdout", ""))
        sys.stderr.write(entry.get("stderr", ""))
        sys.exit(entry.get("exit", 0))
with open(os.path.join(base, "unexpected.jsonl"), "a") as log:
    log.write(json.dumps(argv) + "\\n")
sys.stderr.write("gh stand-in: no answer for " + " ".join(argv) + "\\n")
sys.exit(97)
'''


def _answer(value):
    if isinstance(value, tuple):
        return {"stdout": value[0], "exit": value[1]}
    return {"stdout": json.dumps(value), "exit": 0}


# The pull request's timeline, as `gh api --paginate --slurp` prints it: a
# list of pages. The default holds events that are not base changes, one of
# them after every run in the rows, and a commit event with no time.
QUIET_TIMELINE = [[{"event": "committed"},
                   {"event": "labeled", "created_at": "2026-10-13T09:00:00Z"}],
                  [{"event": "head_ref_force_pushed",
                    "created_at": "2026-10-13T11:00:00Z"}]]


def _timeline(*events):
    return [[{"event": "committed"}, *({"event": e, "created_at": at}
                                       for e, at in events)]]


def _timeline_argv(number=7):
    return ["api", "--paginate", "--slurp", "-X", "GET",
            f"repos/{REPO}/issues/{number}/timeline", "-f", "per_page=100"]


def _shim(tmp_path: Path, table: list) -> tuple[Path, dict]:
    work = tmp_path / "gh"
    work.mkdir()
    shim = work / "bin" / "gh"
    shim.parent.mkdir()
    shim.write_text(SHIM.format(python=sys.executable))
    shim.chmod(shim.stat().st_mode | stat.S_IEXEC)
    (work / "table.json").write_text(json.dumps(table))
    env = dict(os.environ, FAKE_GH_DIR=str(work),
               PATH=f"{shim.parent}{os.pathsep}{os.environ['PATH']}",
               GIT_TERMINAL_PROMPT="0")
    return work, env


def _unexpected(work: Path) -> str:
    path = work / "unexpected.jsonl"
    return path.read_text() if path.exists() else ""


HEAD = "ab" * 20
THIS_RUN = 555
WORKFLOW = 99

# The text-edit form reads workflow runs and their jobs from the Actions API.
# A suite run's `checks` job runs; a text-edit run skips it. The check-runs
# API cannot be used: it lists no check run for a job still waiting on the
# jobs it needs, so a suite run in progress has no `self-check` there
# (ayeo-io/compass#578, run 38849230839).


def _wrun(run_id=444, status="completed", conclusion="success",
          created="2026-10-13T10:00:00Z", prs=(7,), head=HEAD):
    return {"id": run_id, "status": status,
            "conclusion": conclusion if status == "completed" else None,
            "created_at": created, "head_sha": head, "event": "pull_request",
            "pull_requests": [{"number": n, "head": {"sha": head}} for n in prs]}


def _wruns(*runs):
    return {"total_count": len(runs), "workflow_runs": list(runs)}


def _job(name, status="completed", conclusion="success"):
    return {"name": name, "status": status,
            "conclusion": conclusion if status == "completed" else None}


def _jobs(kind, self_check="success"):
    """The jobs of one run, as `actions/runs/<id>/jobs` lists them."""
    if kind == "suite":
        jobs = [_job("already-tested", conclusion="skipped"), _job("checks"),
                _job("shard (0)"), _job("self-check", conclusion=self_check)]
    elif kind == "suite, no self-check":
        jobs = [_job("already-tested", conclusion="skipped"), _job("checks")]
    elif kind == "running":
        jobs = [_job("already-tested", conclusion="skipped"), _job("checks"),
                _job("shard (0)", status="in_progress")]
    elif kind == "starting":
        jobs = [_job("already-tested", conclusion="skipped")]
    elif kind == "text edit":
        jobs = [_job("already-tested", conclusion="skipped"),
                _job("checks", conclusion="skipped"),
                _job("self-check", conclusion=self_check)]
    elif kind == "text edit, running":
        jobs = [_job("already-tested", conclusion="skipped"),
                _job("checks", conclusion="skipped"),
                _job("self-check", status="in_progress")]
    else:
        raise ValueError(kind)
    return {"total_count": len(jobs), "jobs": jobs}


def _this_run_argv():
    return ["api", f"repos/{REPO}/actions/runs/{THIS_RUN}"]


def _runs_argv(head=HEAD):
    return ["api", "-X", "GET", f"repos/{REPO}/actions/workflows/{WORKFLOW}/runs",
            "-f", f"head_sha={head}", "-f", "event=pull_request", "-f", "per_page=100"]


def _jobs_argv(run_id):
    return ["api", "-X", "GET", f"repos/{REPO}/actions/runs/{run_id}/jobs",
            "-f", "filter=latest", "-f", "per_page=100"]


class Polls(list):
    """Answers to one call, given in turn on each poll; the last repeats."""


def _answers(value):
    """One answer, or a Polls of answers given on successive calls."""
    if isinstance(value, Polls):
        return {"answers": [_answer(v) for v in value]}
    return _answer(value)


def _earlier(tmp_path: Path, runs, jobs=None, timeline=QUIET_TIMELINE, *,
             number="7", head=HEAD, this_run=str(THIS_RUN), extra=()):
    """Run the text-edit form. `runs` answers the run list and `jobs` maps
    a run id to its jobs answer; either may be a Polls of answers."""
    table = [
        {"argv": ["api", f"repos/{REPO}/actions/runs/{this_run}"],
         **_answer({"id": int(this_run) if this_run.isdigit() else 0,
                    "workflow_id": WORKFLOW})},
        {"argv": _runs_argv(head), **_answers(runs)},
        {"argv": _timeline_argv(), **_answer(timeline)},
    ]
    for run_id, answer in (jobs or {}).items():
        table.append({"argv": _jobs_argv(run_id), **_answers(answer)})
    work, env = _shim(tmp_path, table)
    r = subprocess.run([sys.executable, str(SCRIPT), "--repo", REPO,
                        "--pull-request", number, "--head", head,
                        "--this-run", this_run, *extra],
                       cwd=tmp_path, capture_output=True, text=True, env=env,
                       timeout=60)
    return r, _unexpected(work)


SUITE = {444: _jobs("suite")}
THIS = _wrun(THIS_RUN, status="in_progress", created="2026-10-13T10:20:00Z")
WAIT = ("--wait-minutes", "5", "--poll-seconds", "0")

# Each row: (name, run list answer, jobs answers, timeline, passes, words).
# Suite run 444 was created at 10:00:00.
EARLIER_ROWS = [
    ("a green earlier run, no base change since",
     _wruns(_wrun()), SUITE, QUIET_TIMELINE, True, ["success", "444"]),
    ("this run is still in progress",
     _wruns(_wrun(), THIS), SUITE, QUIET_TIMELINE, True, ["success"]),
    ("the latest earlier run failed",
     _wruns(_wrun(443, created="2026-10-13T09:00:00Z"),
            _wrun(445, conclusion="failure")),
     {443: _jobs("suite"), 445: _jobs("suite", self_check="failure")},
     QUIET_TIMELINE, False, ["failure", "445"]),
    ("an earlier run is still running and no wait is allowed",
     _wruns(_wrun(), _wrun(446, status="in_progress",
                           created="2026-10-13T10:05:00Z")),
     {444: _jobs("suite"), 446: _jobs("running")},
     QUIET_TIMELINE, False, ["still running", "446"]),
    ("no earlier run", _wruns(THIS), {}, QUIET_TIMELINE, False, ["no suite run"]),
    ("a base change after the earlier run was created",
     _wruns(_wrun()), SUITE, _timeline(("base_ref_changed", "2026-10-13T10:01:00Z")),
     False, ["base_ref_changed"]),
    ("an automatic base change after the earlier run was created",
     _wruns(_wrun()), SUITE,
     _timeline(("automatic_base_change_succeeded", "2026-10-13T10:01:00Z")),
     False, ["automatic_base_change_succeeded"]),
    ("the timeline cannot be read", _wruns(_wrun()), SUITE, ("", 1), False, ["error"]),
    ("the run list call exits non-zero", ("", 1), {}, QUIET_TIMELINE, False, ["error"]),
    ("the run list is short of its total",
     {"total_count": 2, "workflow_runs": [_wrun()]}, SUITE, QUIET_TIMELINE, False,
     ["error"]),
    ("a jobs call exits non-zero", _wruns(_wrun()), {444: ("", 1)}, QUIET_TIMELINE,
     False, ["error"]),
    ("a jobs list is short of its total", _wruns(_wrun()),
     {444: {"total_count": 9, "jobs": _jobs("suite")["jobs"]}}, QUIET_TIMELINE,
     False, ["error"]),
]


@pytest.mark.parametrize("row", EARLIER_ROWS, ids=[r[0] for r in EARLIER_ROWS])
def test_crt_21_earlier_result(tmp_path, row):
    """On a title or body edit, self-check passes only when the latest
    earlier suite run on the head succeeded and the base has not changed
    since it was created."""
    name, runs, jobs, timeline, passes, words = row
    r, unexpected = _earlier(tmp_path, runs, jobs, timeline)
    assert unexpected == "", unexpected
    assert r.returncode == (0 if passes else 1), (r.returncode, r.stdout, r.stderr)
    for label in ("Pull request:", "Latest suite run:",
                  "Base changes since that run was created:", "Decision:"):
        assert label in r.stdout, (label, r.stdout)
    for word in words:
        assert word in r.stdout, (word, r.stdout)


@pytest.mark.parametrize("number,head", [("7; touch planted", HEAD),
                                         ("0", HEAD), ("7", "$(touch planted)")])
def test_crt_21_earlier_result_refuses_bad_input(tmp_path, number, head):
    """A pull request number or head that is not what it claims to be fails
    the check before any call uses it."""
    r, _ = _earlier(tmp_path, _wruns(_wrun()), SUITE, number=number, head=head)
    assert r.returncode == 1, (r.stdout, r.stderr)
    assert "Decision:" in r.stdout
    assert not (tmp_path / "planted").exists()
    assert not (tmp_path / "gh" / "calls.jsonl").exists(), "gh was called"


# GitHub Actions run ids passed 10 digits in October 2026: run 38832496788
# failed self-check on pull request #573 with "--this-run '38832496788' is
# not a whole number". 19 digits is the most a signed 64-bit id holds.
@pytest.mark.parametrize("this_run", ["38832496788", "9" * 19])
def test_crt_21_earlier_result_long_ids(tmp_path, this_run):
    """A run id of 11 to 19 digits is a whole number: this run is left out
    and the earlier green run passes."""
    runs = _wruns(_wrun(38832490000),
                  _wrun(int(this_run), status="in_progress",
                        created="2026-10-13T10:20:00Z"))
    r, unexpected = _earlier(tmp_path, runs, {38832490000: _jobs("suite")},
                             this_run=this_run)
    assert unexpected == "", unexpected
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert "success" in r.stdout, r.stdout


@pytest.mark.parametrize("this_run", ["1" + "0" * 19, "038832496788"])
def test_crt_21_earlier_result_refuses_bad_run_id(tmp_path, this_run):
    """A run id of 20 digits, or one with a leading zero, fails the check."""
    r, _ = _earlier(tmp_path, _wruns(_wrun()), SUITE, this_run=this_run)
    assert r.returncode == 1, (r.stdout, r.stderr)
    assert "is not a whole number" in r.stdout, r.stdout


# --- the head's suite run still running (SER-1, SER-2) ----------------------

RUNNING = _wrun(status="in_progress")

# Each row: (name, run list answers, jobs answers for run 444, passes, words).
WAIT_ROWS = [
    ("the suite run completes green",
     Polls([_wruns(RUNNING, THIS), _wruns(_wrun(), THIS)]),
     Polls([_jobs("running"), _jobs("suite")]), True, ["success", "444"]),
    ("the suite run completes red",
     Polls([_wruns(RUNNING, THIS), _wruns(_wrun(conclusion="failure"), THIS)]),
     Polls([_jobs("running"), _jobs("suite", self_check="failure")]), False,
     ["failure", "444"]),
    ("the suite run has not listed its checks job yet",
     Polls([_wruns(RUNNING, THIS), _wruns(RUNNING, THIS), _wruns(_wrun(), THIS)]),
     Polls([_jobs("starting"), _jobs("running"), _jobs("suite")]), True,
     ["success", "444"]),
]


@pytest.mark.parametrize("row", WAIT_ROWS, ids=[r[0] for r in WAIT_ROWS])
def test_ser_1_waits_for_the_suite_run(tmp_path, row):
    """A text edit made while the head's suite run is running waits for it,
    then passes or fails with it (ayeo-io/compass#578, run 38849230839)."""
    name, runs, jobs, passes, words = row
    r, unexpected = _earlier(tmp_path, runs, {444: jobs}, extra=WAIT)
    assert unexpected == "", unexpected
    assert r.returncode == (0 if passes else 1), (r.returncode, r.stdout, r.stderr)
    assert "Waiting for workflow run 444" in r.stdout, r.stdout
    assert r.stdout.count("Decision:") == 1, r.stdout
    # The workflow id is read once, however many times the wait polls: the
    # token allows 1,000 API requests an hour for the whole repository.
    calls = (tmp_path / "gh" / "calls.jsonl").read_text().splitlines()
    assert calls.count(json.dumps(_this_run_argv())) == 1, calls
    assert calls.count(json.dumps(_runs_argv())) >= 2, calls
    for word in words:
        assert word in r.stdout, (word, r.stdout)


def test_ser_2_wait_has_a_limit(tmp_path):
    """A suite run that never completes fails the check once the wait runs
    out, and with no wait limit the check fails without waiting."""
    runs, jobs = _wruns(RUNNING, THIS), {444: _jobs("running")}
    r, unexpected = _earlier(tmp_path, runs, jobs,
                             extra=("--wait-minutes", "0.02", "--poll-seconds", "0.2"))
    assert unexpected == "", unexpected
    assert r.returncode == 1, (r.stdout, r.stderr)
    assert "Waiting for workflow run 444" in r.stdout, r.stdout
    assert "still running" in r.stdout and "0.02 minutes" in r.stdout, r.stdout

    (tmp_path / "no-wait").mkdir()
    r, _ = _earlier(tmp_path / "no-wait", runs, jobs)
    assert r.returncode == 1, (r.stdout, r.stderr)
    assert "Waiting" not in r.stdout, r.stdout
    assert "still running" in r.stdout, r.stdout


# --- which earlier runs count (SER-3) ---------------------------------------

TEXT_EDIT = _wrun(446, created="2026-10-13T10:10:00Z")

# Each row: (name, run list, jobs answers, passes, words).
COUNT_ROWS = [
    ("a suite run green", _wruns(_wrun(), THIS), SUITE, True, ["444"]),
    ("a suite run green, then a text-edit run red",
     _wruns(_wrun(), dict(TEXT_EDIT, conclusion="failure"), THIS),
     {444: _jobs("suite"), 446: _jobs("text edit", self_check="failure")},
     True, ["444"]),
    ("a suite run green, then a text-edit run cancelled",
     _wruns(_wrun(), dict(TEXT_EDIT, conclusion="cancelled"), THIS),
     {444: _jobs("suite"), 446: _jobs("text edit", self_check="cancelled")},
     True, ["444"]),
    ("a suite run green, and a text-edit run still running",
     _wruns(_wrun(), dict(TEXT_EDIT, status="in_progress", conclusion=None), THIS),
     {444: _jobs("suite"), 446: _jobs("text edit, running")}, True, ["444"]),
    ("a text-edit run red only",
     _wruns(dict(TEXT_EDIT, conclusion="failure"), THIS),
     {446: _jobs("text edit", self_check="failure")}, False, ["no suite run"]),
    ("a text-edit run green only",
     _wruns(TEXT_EDIT, THIS), {446: _jobs("text edit")}, False, ["no suite run"]),
    ("a suite run cancelled only",
     _wruns(_wrun(conclusion="cancelled"), THIS),
     {444: _jobs("suite", self_check="skipped")}, False, ["no suite run"]),
    ("a suite run green, then a suite run cancelled",
     _wruns(_wrun(), _wrun(445, conclusion="cancelled",
                           created="2026-10-13T10:05:00Z"), THIS),
     {444: _jobs("suite"), 445: _jobs("suite", self_check="skipped")},
     True, ["444"]),
    ("a suite run green, then a suite run red",
     _wruns(_wrun(), _wrun(445, conclusion="failure",
                           created="2026-10-13T10:05:00Z"), THIS),
     {444: _jobs("suite"), 445: _jobs("suite", self_check="failure")},
     False, ["445", "failure"]),
    ("a suite run green on another pull request",
     _wruns(_wrun(prs=(8,)), THIS), {}, False, ["no suite run"]),
    ("a suite run green that lists no pull request",
     _wruns(_wrun(prs=()), THIS), {}, False, ["no suite run"]),
    ("a suite run green on another head",
     _wruns(_wrun(head="cd" * 20), THIS), {}, False, ["no suite run"]),
    ("a suite run green with no self-check job",
     _wruns(_wrun(), THIS), {444: _jobs("suite, no self-check")}, False,
     ["444", "no self-check job"]),
    ("no earlier run", _wruns(THIS), {}, False, ["no suite run"]),
]


@pytest.mark.parametrize("row", COUNT_ROWS, ids=[r[0] for r in COUNT_ROWS])
def test_ser_3_which_runs_count(tmp_path, row):
    """Only a completed, uncancelled suite run of this pull request and head
    is the earlier result: text-edit runs, cancelled runs and runs of other
    pull requests are left out."""
    name, runs, jobs, passes, words = row
    r, unexpected = _earlier(tmp_path, runs, jobs)
    assert unexpected == "", unexpected
    assert r.returncode == (0 if passes else 1), (r.returncode, r.stdout, r.stderr)
    for word in words:
        assert word in r.stdout, (word, r.stdout)


# --- the push skip (CRT-7) ---------------------------------------------------

MERGED = "cd" * 20


def _mgrun(run_id=900, created="2026-11-01T10:00:00Z", head=MERGED,
           event="merge_group", status="in_progress"):
    """A merge-group run. Its status does not count: a job self-check does
    not need, such as harness-root, may still be running when the queue
    merges."""
    return {"id": run_id, "status": status, "conclusion": None,
            "created_at": created, "head_sha": head, "event": event,
            "pull_requests": []}


def _mgjobs(self_check="success", shards=("success",) * 4, self_check_status="completed",
            extra=()):
    jobs = [_job("already-tested", conclusion="skipped"), _job("checks"),
            _job("fast-tests", conclusion="skipped")]
    jobs += [_job(f"shard ({i})", conclusion=c) for i, c in enumerate(shards)]
    if self_check is not None:
        jobs.append(_job("self-check", status=self_check_status, conclusion=self_check))
    jobs += list(extra)
    return {"total_count": len(jobs), "jobs": jobs}


def _mgruns_argv(commit=MERGED):
    return ["api", "-X", "GET", f"repos/{REPO}/actions/workflows/{WORKFLOW}/runs",
            "-f", f"head_sha={commit}", "-f", "event=merge_group", "-f", "per_page=100"]


def _push(tmp_path: Path, runs, jobs=None, *, commit=MERGED, this_run=str(THIS_RUN)):
    table = [
        {"argv": ["api", f"repos/{REPO}/actions/runs/{this_run}"],
         **_answer({"id": THIS_RUN, "workflow_id": WORKFLOW})},
        {"argv": _mgruns_argv(commit), **_answers(runs)},
    ]
    for run_id, answer in (jobs or {}).items():
        table.append({"argv": _jobs_argv(run_id), **_answers(answer)})
    work, env = _shim(tmp_path, table)
    output = tmp_path / "github_output"
    output.write_text("earlier=line\n")
    r = subprocess.run([sys.executable, str(SCRIPT), "--repo", REPO, "--commit", commit,
                        "--this-run", this_run, "--output", str(output)],
                       cwd=tmp_path, capture_output=True, text=True, env=env, timeout=60)
    return r, output.read_text(), _unexpected(work)


GREEN = {900: _mgjobs()}

# Each row: (name, run list answer, jobs answers, expected skip, words).
PUSH_ROWS = [
    ("a green merge-group run on the commit", _wruns(_mgrun()), GREEN, True,
     ["900", "every one succeeded"]),
    ("a green merge-group run that has completed",
     _wruns(_mgrun(status="completed")), GREEN, True, ["900"]),
    ("no merge-group run", _wruns(), {}, False, ["no merge group run"]),
    ("the run list holds a pull-request run only",
     _wruns(_mgrun(event="pull_request")), {}, False, ["no merge group run"]),
    ("the run list holds a run on another commit",
     _wruns(_mgrun(head="ef" * 20)), {}, False, ["no merge group run"]),
    ("the run list holds this run only", _wruns(_mgrun(run_id=THIS_RUN)), {}, False,
     ["no merge group run"]),
    ("self-check failed", _wruns(_mgrun()), {900: _mgjobs(self_check="failure")},
     False, ["self-check", "failure"]),
    ("self-check still running", _wruns(_mgrun()),
     {900: _mgjobs(self_check=None, extra=[_job("self-check", status="in_progress")])},
     False, ["not completed"]),
    ("no self-check job", _wruns(_mgrun()), {900: _mgjobs(self_check=None)}, False,
     ["not exactly one self-check job"]),
    ("two self-check jobs", _wruns(_mgrun()),
     {900: _mgjobs(extra=[_job("self-check")])}, False,
     ["not exactly one self-check job"]),
    ("self-check green with no shard job, as on a pull request", _wruns(_mgrun()),
     {900: _mgjobs(shards=())}, False, ["no shard job"]),
    ("a shard job failed", _wruns(_mgrun()),
     {900: _mgjobs(shards=("success", "failure", "success", "success"))}, False,
     ["shard (1) failure"]),
    ("a shard job skipped", _wruns(_mgrun()),
     {900: _mgjobs(shards=("success", "success", "skipped", "success"))}, False,
     ["shard (2) skipped"]),
    ("an earlier green run, then a later red run",
     _wruns(_mgrun(899, created="2026-11-01T09:00:00Z"), _mgrun(900)),
     {900: _mgjobs(self_check="failure")}, False, ["900", "failure"]),
    ("the same creation time, the higher id red",
     _wruns(_mgrun(899), _mgrun(900)), {900: _mgjobs(self_check="failure")}, False,
     ["900"]),
    ("an earlier red run, then a later green run",
     _wruns(_mgrun(899, created="2026-11-01T09:00:00Z"), _mgrun(900)), GREEN, True,
     ["900"]),
    ("the run list call exits non-zero", ("", 1), {}, False, ["error"]),
    ("the run list answer is not JSON", ("<html>rate limited</html>", 0), {}, False,
     ["error"]),
    ("the run list is short of its total",
     {"total_count": 2, "workflow_runs": [_mgrun()]}, {}, False, ["error"]),
    ("a run has no creation time",
     _wruns(dict(_mgrun(), created_at=None)), {}, False, ["error"]),
    ("the jobs call exits non-zero", _wruns(_mgrun()), {900: ("", 1)}, False, ["error"]),
    ("the jobs list is short of its total", _wruns(_mgrun()),
     {900: {"total_count": 99, "jobs": _mgjobs()["jobs"]}}, False, ["error"]),
]


@pytest.mark.parametrize("row", PUSH_ROWS, ids=[r[0] for r in PUSH_ROWS])
def test_crt_7_push_skip_decision(tmp_path, row):
    """Skip=true only for a commit the merge queue tested green with the
    whole suite."""
    name, runs, jobs, skip, words = row
    r, output, unexpected = _push(tmp_path, runs, jobs)
    assert unexpected == "", f"gh was called with arguments no row expects:\n{unexpected}"
    assert r.returncode == 0, r.stdout + r.stderr
    lines = output.splitlines()
    assert lines[0] == "earlier=line", "the output file was overwritten, not appended"
    assert lines[1:] == [f"skip={'true' if skip else 'false'}"], (lines, r.stdout)
    for label in ("Merged commit:", "Merge group runs on the commit:",
                  "Latest merge group run:", "Its self-check job:", "Its shard jobs:",
                  "Decision:"):
        assert label in r.stdout, (label, r.stdout)
    for word in words:
        assert word in r.stdout, (word, r.stdout)


@pytest.mark.parametrize("commit,this_run", [("$(touch planted)", str(THIS_RUN)),
                                             (MERGED, "1; touch planted"),
                                             (MERGED, "0")])
def test_crt_7_push_skip_refuses_bad_input(tmp_path, commit, this_run):
    """A commit or run id that is not what it claims to be answers "run the
    suite" before any call uses it."""
    work, env = _shim(tmp_path, [])
    output = tmp_path / "github_output"
    output.write_text("")
    r = subprocess.run([sys.executable, str(SCRIPT), "--repo", REPO, "--commit", commit,
                        "--this-run", this_run, "--output", str(output)],
                       cwd=tmp_path, capture_output=True, text=True, env=env, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    assert output.read_text() == "skip=false\n"
    assert not (tmp_path / "planted").exists()
    assert not (work / "calls.jsonl").exists(), "gh was called"


def test_crt_7_push_skip_needs_the_run_id(tmp_path):
    """Without --this-run the command cannot name its workflow, so it
    refuses its arguments."""
    r = subprocess.run([sys.executable, str(SCRIPT), "--repo", REPO, "--commit", MERGED,
                        "--output", str(tmp_path / "out")],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 2, r.stdout + r.stderr
    assert "--this-run" in r.stderr


def test_crt_7_runs_no_shell():
    """No text read from the API reaches a shell: every command runs as an
    argument list."""
    source = SCRIPT.read_text(encoding="utf-8")
    for banned in ("shell=True", "os.system", "os.popen"):
        assert banned not in source, banned
