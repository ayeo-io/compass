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
for entry in table:
    if entry["argv"] == argv:
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

# Each row: (name, check-runs answer, timeline answer, passes, words named).
# The run that this self-check reports is run 444; its self-check started
# at 10:00:00.
EARLIER_ROWS = [
    ("a green earlier run, no base change since",
     _checks(_run()), QUIET_TIMELINE, True, ["success", "444"]),
    ("this run's own self-check is still in progress",
     _checks(_run(), _run(None, status="in_progress", run_id=9,
                          started="2026-10-13T10:20:00Z", workflow_run=THIS_RUN)),
     QUIET_TIMELINE, True, ["success"]),
    ("the latest earlier run failed",
     _checks(_run("success", run_id=1, started="2026-10-13T09:00:00Z"),
             _run("failure", run_id=2, workflow_run=445)),
     QUIET_TIMELINE, False, ["failure"]),
    ("an earlier run is still in progress",
     _checks(_run(), _run(None, status="in_progress", run_id=3,
                          started="2026-10-13T10:05:00Z", workflow_run=446)),
     QUIET_TIMELINE, False, ["not completed"]),
    ("no earlier run",
     _checks(_run(None, status="in_progress", run_id=9, workflow_run=THIS_RUN)),
     QUIET_TIMELINE, False, ["no self-check"]),
    ("a base change after the earlier run started",
     _checks(_run()), _timeline(("base_ref_changed", "2026-10-13T10:01:00Z")),
     False, ["base_ref_changed"]),
    ("an automatic base change after the earlier run started",
     _checks(_run()),
     _timeline(("automatic_base_change_succeeded", "2026-10-13T10:01:00Z")),
     False, ["automatic_base_change_succeeded"]),
    ("the timeline cannot be read", _checks(_run()), ("", 1), False, ["error"]),
    ("the check-runs call exits non-zero", ("", 1), QUIET_TIMELINE, False, ["error"]),
]


def _earlier(tmp_path: Path, checks, timeline, *, number="7", head=HEAD):
    work, env = _shim(tmp_path, [
        {"argv": _checks_argv(head), **_answer(checks)},
        {"argv": _timeline_argv(), **_answer(timeline)},
    ])
    r = subprocess.run([sys.executable, str(SCRIPT), "--repo", REPO,
                        "--pull-request", number, "--head", head,
                        "--this-run", str(THIS_RUN)],
                       cwd=tmp_path, capture_output=True, text=True, env=env,
                       timeout=60)
    return r, _unexpected(work)


@pytest.mark.parametrize("row", EARLIER_ROWS, ids=[r[0] for r in EARLIER_ROWS])
def test_crt_21_earlier_result(tmp_path, row):
    """On a title or body edit, self-check passes only when the latest earlier
    self-check on the head succeeded and the base has not changed since it
    started."""
    name, checks, timeline, passes, words = row
    r, unexpected = _earlier(tmp_path, checks, timeline)
    assert unexpected == "", unexpected
    assert r.returncode == (0 if passes else 1), (r.returncode, r.stdout, r.stderr)
    for label in ("Pull request:", "Latest self-check conclusion:",
                  "Base changes since that run started:", "Decision:"):
        assert label in r.stdout, (label, r.stdout)
    for word in words:
        assert word in r.stdout, (word, r.stdout)


@pytest.mark.parametrize("number,head", [("7; touch planted", HEAD),
                                         ("0", HEAD), ("7", "$(touch planted)")])
def test_crt_21_earlier_result_refuses_bad_input(tmp_path, number, head):
    """A pull request number or head that is not what it claims to be fails
    the check before any call uses it."""
    r, _ = _earlier(tmp_path, _checks(_run()), QUIET_TIMELINE, number=number,
                    head=head)
    assert r.returncode == 1, (r.stdout, r.stderr)
    assert "Decision:" in r.stdout
    assert not (tmp_path / "planted").exists()
