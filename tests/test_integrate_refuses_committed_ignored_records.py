"""Integration refuses a branch that committed a record the project ignores.

When a project ignores `.compass/work/`, the main checkout's issue record is
an ignored, untracked file. A builder that force-adds its own copy on its
branch would have a clean merge replace the orchestrator's record with it.
`scripts/integrate.sh` refuses such a branch before merging, and names the
files; a branch that commits no ignored record merges as before.

Scenario ids: MIR-1 and MIR-2, in the delivery approach of issue
`merge-overwrites-an-ignored-record`.
"""
from __future__ import annotations

import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
INTEGRATE = ROOT / "scripts" / "integrate.sh"
MAP = ("| Subtask | Owns work unit(s) | Owns scenario ids | Branch name |\n"
       "|---|---|---|---|\n"
       "| subtask-1 | U1 | S1 | compass/demo/subtask-1 |\n")


def _git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args],
                          capture_output=True, text=True, check=True)


def _repo(tmp_path, *, branch_commits_record):
    repo = tmp_path / "proj"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "T")
    (repo / ".gitignore").write_text("/.compass/work/\n/.compass/current-task\n")
    (repo / ".compass").mkdir()
    (repo / ".compass" / "config.yml").write_text(
        "version: 1.0.0\nmode: enforced\nworktree_root: ../wt\n")
    (repo / "app.py").write_text("x = 1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")
    task = repo / ".compass" / "work" / "demo"
    task.mkdir(parents=True)
    (task / "manifest.yml").write_text(
        "task: demo\nassessment: {risk: contained}\nfired_guardrails: []\n"
        "note: the orchestrator's record\n")
    (task / "distribution-map.md").write_text(MAP)
    # The builder works in its own worktree, as the protocol has it, so the
    # main checkout's ignored record is never touched while the branch is made.
    wt = tmp_path / "builder"
    _git(repo, "worktree", "add", "-q", "-b", "compass/demo/subtask-1", str(wt))
    (wt / "app.py").write_text("x = 2\n")
    _git(wt, "add", "app.py")
    if branch_commits_record:
        (wt / ".compass" / "work" / "demo").mkdir(parents=True)
        (wt / ".compass" / "work" / "demo" / "manifest.yml").write_text(
            "task: demo\nnote: the builder's copy\n")
        _git(wt, "add", "-f", ".compass/work/demo/manifest.yml")
    _git(wt, "commit", "-q", "-m", "subtask work")
    return repo


def _integrate(repo):
    return subprocess.run(["bash", str(INTEGRATE), "demo", "--no-clean"],
                          cwd=str(repo), capture_output=True, text=True, timeout=120)


def test_mir_1_a_branch_that_committed_an_ignored_record_is_refused(tmp_path):
    repo = _repo(tmp_path, branch_commits_record=True)
    head = _git(repo, "rev-parse", "HEAD").stdout
    result = _integrate(repo)
    out = result.stdout + result.stderr
    assert result.returncode != 0, out
    assert ".compass/work/demo/manifest.yml" in out, out
    assert _git(repo, "rev-parse", "HEAD").stdout == head
    manifest = (repo / ".compass" / "work" / "demo" / "manifest.yml").read_text()
    assert "the orchestrator's record" in manifest


def test_mir_2_a_branch_with_no_ignored_record_merges(tmp_path):
    repo = _repo(tmp_path, branch_commits_record=False)
    result = _integrate(repo)
    out = result.stdout + result.stderr
    assert "merged cleanly" in out, out
    assert (repo / "app.py").read_text() == "x = 2\n"
