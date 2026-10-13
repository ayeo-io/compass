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
         run_id=1, app="github-actions"):
    return {"id": run_id, "name": "self-check", "status": status,
            "conclusion": conclusion, "started_at": started,
            "app": {"slug": app}}


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


def _decide(tmp_path: Path, history: dict, row):
    name, merged_key, pulls, head_key, checks, _ = row
    merged = history[merged_key]
    head = history.get(head_key, head_key)
    work = tmp_path / "gh"
    work.mkdir()
    shim = work / "bin" / "gh"
    shim.parent.mkdir()
    shim.write_text(SHIM.format(python=sys.executable))
    shim.chmod(shim.stat().st_mode | stat.S_IEXEC)
    if isinstance(pulls, str):
        pulls = _pulls(pulls, dict(history, merged=merged, head=head))
    table = [
        {"argv": ["api", f"repos/{REPO}/commits/{merged}/pulls"], **_answer(pulls)},
        {"argv": ["api", "-X", "GET", f"repos/{REPO}/commits/{head}/check-runs",
                  "-f", "check_name=self-check", "-f", "filter=all",
                  "-f", "per_page=100"], **_answer(checks)},
    ]
    (work / "table.json").write_text(json.dumps(table))
    output = tmp_path / "github_output"
    output.write_text("earlier=line\n")
    env = dict(os.environ, FAKE_GH_DIR=str(work),
               PATH=f"{shim.parent}{os.pathsep}{os.environ['PATH']}",
               GIT_TERMINAL_PROMPT="0")
    r = subprocess.run([sys.executable, str(SCRIPT), "--repo", REPO,
                        "--commit", merged, "--output", str(output)],
                       cwd=history["repo"], capture_output=True, text=True,
                       env=env, timeout=60)
    unexpected = (work / "unexpected.jsonl")
    return r, output.read_text(), unexpected.read_text() if unexpected.exists() else ""


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
                  "Latest self-check conclusion:", "Decision:"):
        assert label in r.stdout, (label, r.stdout)
    assert not (history["repo"] / "planted").exists()


def test_crt_7_runs_no_shell():
    """No text read from the API reaches a shell: every command runs as an
    argument list."""
    source = SCRIPT.read_text(encoding="utf-8")
    for banned in ("shell=True", "os.system", "os.popen"):
        assert banned not in source, banned
