"""The push-skip decision of the `already-tested` job.

On a push to main, `.github/workflows/compass.yml` skips every other job
when `scripts/ci-already-tested.py` writes `skip=true`. A wrong skip lets an
untested tree onto main with a green tick, so the decision takes five
conditions and answers "run" on anything unknown.

The tests run the command in a temporary git repository with no remote,
with a `gh` stand-in on PATH that answers from a table and records any call
the table does not hold, so the test fails on it.
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


def _git(cwd: Path, *args: str) -> str:
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com",
               GIT_AUTHOR_DATE="2026-10-13T10:00:00Z",
               GIT_COMMITTER_DATE="2026-10-13T10:00:00Z")
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                       env=env, check=True)
    return r.stdout.strip()


def _tree_commit(repo: Path, files: dict, parent: str, message: str) -> str:
    """A commit with exactly these files, made without touching the index
    of the checked-out branch."""
    env = dict(os.environ, GIT_INDEX_FILE=str(repo / ".git" / "tmp-index"))
    subprocess.run(["git", "read-tree", "--empty"], cwd=repo, env=env, check=True)
    for name, text in files.items():
        blob = subprocess.run(["git", "hash-object", "-w", "--stdin"], cwd=repo,
                              input=text, capture_output=True, text=True,
                              check=True).stdout.strip()
        subprocess.run(["git", "update-index", "--add", "--cacheinfo",
                        f"100644,{blob},{name}"], cwd=repo, env=env, check=True)
    tree = subprocess.run(["git", "write-tree"], cwd=repo, env=env,
                          capture_output=True, text=True, check=True).stdout.strip()
    return _git(repo, "commit-tree", tree, "-p", parent, "-m", message)


@pytest.fixture(scope="module")
def history(tmp_path_factory):
    """main at A; a pull request head H on A; and the merge commits the rows
    use:
    - M, a squash of H onto A (same tree as H, first parent A);
    - M_other_tree, a commit on A whose tree differs from H's;
    - M_not_ancestor, H's tree on B, where B is a commit on A that H does
      not contain, so M's first parent is not an ancestor of the head."""
    repo = tmp_path_factory.mktemp("history")
    _git(repo, "init", "-q", "-b", "main")
    # The root commit has no parent, so it is made with plain git.
    (repo / "a.txt").write_text("1\n")
    _git(repo, "add", "a.txt")
    _git(repo, "commit", "-q", "-m", "A")
    a = _git(repo, "rev-parse", "HEAD")
    h = _tree_commit(repo, {"a.txt": "1\n", "b.txt": "2\n"}, a, "H")
    m = _tree_commit(repo, {"a.txt": "1\n", "b.txt": "2\n"}, a, "M squash of H")
    m_other = _tree_commit(repo, {"a.txt": "1\n", "c.txt": "3\n"}, a, "M other tree")
    b = _tree_commit(repo, {"a.txt": "1\n", "d.txt": "4\n"}, a, "B")
    m_not_anc = _tree_commit(repo, {"a.txt": "1\n", "b.txt": "2\n"}, b, "M on B")
    return {"repo": repo, "A": a, "H": h, "M": m, "M_other_tree": m_other,
            "M_not_ancestor": m_not_anc}


def _pull(merge, head, *, number=7, base="main", merged=True):
    return {"number": number, "merge_commit_sha": merge,
            "merged_at": "2026-10-13T10:05:00Z" if merged else None,
            "base": {"ref": base}, "head": {"sha": head}}


def _run(conclusion="success", status="completed", started="2026-10-13T10:00:00Z",
         run_id=1, app="github-actions", workflow_run=444):
    return {"id": run_id, "name": "self-check", "status": status,
            "conclusion": conclusion, "started_at": started,
            "app": {"slug": app},
            "details_url": f"https://github.com/{REPO}/actions/runs/"
                           f"{workflow_run}/job/{run_id}"}


def _checks(*runs):
    return {"total_count": len(runs), "check_runs": list(runs)}


MISSING_HEAD = "1234567890abcdef1234567890abcdef12345678"

# Each row: (name, merged commit key, pulls answer, head key or sha,
#            check-runs answer, expected skip). An answer is a JSON value,
#            or a (stdout, exit) pair for a raw answer.
ROWS = [
    ("tested green", "M", "pulls:ok", "H", _checks(_run()), True),
    ("head tree differs", "M_other_tree", "pulls:ok", "H", _checks(_run()), False),
    ("no pull request", "M", [], "H", _checks(_run()), False),
    ("merge commit is not M", "M", "pulls:other-merge", "H", _checks(_run()), False),
    ("two pull requests", "M", "pulls:two", "H", _checks(_run()), False),
    ("merged into another branch", "M", "pulls:base-release", "H", _checks(_run()), False),
    ("first parent not an ancestor", "M_not_ancestor", "pulls:ok", "H",
     _checks(_run()), False),
    ("latest failure", "M", "pulls:ok", "H", _checks(_run("failure")), False),
    ("latest cancelled", "M", "pulls:ok", "H", _checks(_run("cancelled")), False),
    ("latest skipped", "M", "pulls:ok", "H", _checks(_run("skipped")), False),
    ("latest neutral", "M", "pulls:ok", "H", _checks(_run("neutral")), False),
    ("one still in progress", "M", "pulls:ok", "H",
     _checks(_run(), _run(None, status="in_progress", run_id=2,
                          started="2026-10-13T10:09:00Z")), False),
    ("earlier success, latest failure", "M", "pulls:ok", "H",
     _checks(_run("success", started="2026-10-13T10:00:00Z", run_id=1),
             _run("failure", started="2026-10-13T10:30:00Z", run_id=2)), False),
    ("same start, the higher id failed", "M", "pulls:ok", "H",
     _checks(_run("success", run_id=1), _run("failure", run_id=2)), False),
    ("success only from another app", "M", "pulls:ok", "H",
     _checks(_run(app="some-other-app")), False),
    ("no self-check run", "M", "pulls:ok", "H", _checks(), False),
    ("an API call exits non-zero", "M", ("", 1), "H", _checks(_run()), False),
    ("an API answer is not JSON", "M", ("<html>rate limited</html>", 0), "H",
     _checks(_run()), False),
    ("check-runs call exits non-zero", "M", "pulls:ok", "H", ("", 1), False),
    ("head missing and cannot be fetched", "M", "pulls:missing-head", MISSING_HEAD,
     _checks(_run()), False),
    ("head sha is not 40 hex characters", "M", "pulls:bad-head", "H",
     _checks(_run()), False),
    ("pull request number is not a whole number", "M", "pulls:bad-number",
     MISSING_HEAD, _checks(_run()), False),
    ("a pull request with no merged_at", "M", "pulls:not-merged", "H",
     _checks(_run()), False),
]


def _pulls(kind, h):
    merged, head = h["merged"], h["head"]
    return {
        "pulls:ok": [_pull(merged, head)],
        "pulls:other-merge": [_pull(h["H"], head)],
        "pulls:two": [_pull(merged, head, number=7), _pull(merged, head, number=8)],
        "pulls:base-release": [_pull(merged, head, base="release")],
        "pulls:missing-head": [_pull(merged, MISSING_HEAD)],
        "pulls:bad-head": [_pull(merged, "$(touch planted)")],
        "pulls:bad-number": [_pull(merged, MISSING_HEAD, number="7; touch planted")],
        "pulls:not-merged": [_pull(merged, head, merged=False)],
    }[kind]


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


def _checks_argv(head):
    return ["api", "-X", "GET", f"repos/{REPO}/commits/{head}/check-runs",
            "-f", "check_name=self-check", "-f", "filter=all", "-f", "per_page=100"]


def _decide(tmp_path: Path, history: dict, row, timeline=QUIET_TIMELINE):
    name, merged_key, pulls, head_key, checks, _ = row
    merged = history[merged_key]
    head = history.get(head_key, head_key)
    if isinstance(pulls, str):
        pulls = _pulls(pulls, dict(history, merged=merged, head=head))
    work, env = _shim(tmp_path, [
        {"argv": ["api", f"repos/{REPO}/commits/{merged}/pulls"], **_answer(pulls)},
        {"argv": _checks_argv(head), **_answer(checks)},
        {"argv": _timeline_argv(), **_answer(timeline)},
    ])
    output = tmp_path / "github_output"
    output.write_text("earlier=line\n")
    r = subprocess.run([sys.executable, str(SCRIPT), "--repo", REPO,
                        "--commit", merged, "--output", str(output)],
                       cwd=history["repo"], capture_output=True, text=True,
                       env=env, timeout=60)
    return r, output.read_text(), _unexpected(work)


@pytest.mark.parametrize("row", ROWS, ids=[r[0] for r in ROWS])
def test_crt_7_push_skip_decision(tmp_path, history, row):
    """Skip=true only for a tree tested green on its pull request."""
    r, output, unexpected = _decide(tmp_path, history, row)
    assert unexpected == "", f"gh was called with arguments no row expects:\n{unexpected}"
    assert r.returncode == 0, r.stdout + r.stderr
    expected = "skip=true" if row[-1] else "skip=false"
    lines = output.splitlines()
    assert lines[0] == "earlier=line", "the output file was overwritten, not appended"
    assert lines[1:] == [expected], (lines, r.stdout, r.stderr)
    for label in ("Pull request:", "Merged tree:", "Head tree:",
                  "First parent is an ancestor of the head:",
                  "Latest self-check conclusion:",
                  "Base changes since that run started:", "Decision:"):
        assert label in r.stdout, (label, r.stdout)
    assert not (history["repo"] / "planted").exists()


def test_crt_7_runs_no_shell():
    """No text read from the API reaches a shell: every command runs as an
    argument list."""
    source = SCRIPT.read_text(encoding="utf-8")
    for banned in ("shell=True", "os.system", "os.popen"):
        assert banned not in source, banned


# --- a base change (CRT-21) -------------------------------------------------

GREEN_ROW = ROWS[0]
assert GREEN_ROW[0] == "tested green"

# Each row: (name, timeline answer, expected skip, words the output names).
# The green self-check run in GREEN_ROW started at 10:00:00.
TIMELINE_ROWS = [
    ("no base change", QUIET_TIMELINE, True, []),
    ("a base change before the run started",
     _timeline(("base_ref_changed", "2026-10-13T09:59:00Z")), True, []),
    ("a base change after the run started",
     _timeline(("base_ref_changed", "2026-10-13T10:01:00Z")), False,
     ["base_ref_changed", "2026-10-13T10:01:00Z"]),
    ("an automatic base change after the run started",
     _timeline(("automatic_base_change_succeeded", "2026-10-13T10:01:00Z")), False,
     ["automatic_base_change_succeeded"]),
    ("a base change with no time", [[{"event": "base_ref_changed"}]], False,
     ["error"]),
    ("the timeline call exits non-zero", ("", 1), False, ["error"]),
    ("the timeline answer is not JSON", ("<html>rate limited</html>", 0), False,
     ["error"]),
    ("the timeline answer is not a list of pages", {"message": "Not Found"}, False,
     ["error"]),
]


@pytest.mark.parametrize("row", TIMELINE_ROWS, ids=[r[0] for r in TIMELINE_ROWS])
def test_crt_21_push_skip_reads_the_timeline(tmp_path, history, row):
    """The push skip never trusts a green run that started before the pull
    request's last base change, or a timeline it cannot read."""
    name, timeline, skip, words = row
    r, output, unexpected = _decide(tmp_path, history, GREEN_ROW, timeline=timeline)
    assert unexpected == "", unexpected
    assert r.returncode == 0, r.stdout + r.stderr
    assert output.splitlines()[1:] == [f"skip={'true' if skip else 'false'}"], (
        output, r.stdout)
    assert "Base changes since that run started:" in r.stdout, r.stdout
    decision = [line for line in r.stdout.splitlines() if line.startswith("Decision:")]
    assert len(decision) == 1, r.stdout
    for word in words:
        assert word in r.stdout, (word, r.stdout)


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
