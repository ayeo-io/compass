"""A distribution map's subtask ids and branch cells are checked before use.

`scripts/multiagent.sh` and `scripts/integrate.sh` build worktree paths from
a map's subtask ids and pass its branch cells to git. An id is accepted only
as `subtask-<name>`, where the name has letters, digits, spaces, `.`, `_`,
`(`, `)` or `-` and no `..`, and a branch only when git accepts it as a branch name
and it does not start with `-`. Either script refuses a map that breaks this,
naming the row, before it creates, merges or removes anything.

Scenario ids: MCC-1 and MCC-2, in the delivery approach of issue
`map-cells-reach-git-unchecked`.
"""
from __future__ import annotations

import pathlib
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS = {"multiagent": ROOT / "scripts" / "multiagent.sh",
           "integrate": ROOT / "scripts" / "integrate.sh"}


def _git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args],
                          capture_output=True, text=True, check=True)


def _repo_with_map(tmp_path, sid, branch):
    repo = tmp_path / "proj"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "T")
    (repo / ".gitignore").write_text("/.compass/work/\n/.compass/current-task\n")
    task = repo / ".compass" / "work" / "demo"
    task.mkdir(parents=True)
    (repo / ".compass" / "config.yml").write_text(
        "version: 1.0.0\nmode: enforced\nworktree_root: ../wt\nmax_worktrees: 4\n")
    (task / "manifest.yml").write_text(
        "task: demo\nassessment: {risk: contained}\nfired_guardrails: []\n")
    (task / "delivery-approach.md").write_text("# approach\n")
    (task / "distribution-map.md").write_text(
        "| Subtask | Owns work unit(s) | Owns scenario ids | Branch name |\n"
        "|---|---|---|---|\n"
        f"| {sid} | U1 | S1 | {branch} |\n")
    (repo / "README.md").write_text("# demo\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")
    return repo


def _run(script, repo):
    return subprocess.run(["bash", str(SCRIPTS[script]), "demo"], cwd=str(repo),
                          capture_output=True, text=True, timeout=120)


@pytest.mark.parametrize("script", ["multiagent", "integrate"])
@pytest.mark.parametrize("sid", ["subtask-../../escaped", "subtask-1/x", "subtask-", "subtask-1;rm"])
def test_mcc_1_a_subtask_id_that_could_leave_the_worktree_root_is_refused(tmp_path, script, sid):
    repo = _repo_with_map(tmp_path, sid, "compass/demo/subtask-1")
    result = _run(script, repo)
    assert result.returncode != 0, result.stdout + result.stderr
    assert "subtask id" in (result.stdout + result.stderr).lower()
    assert not (tmp_path / "wt").exists() and not (tmp_path / "escaped").exists()


@pytest.mark.parametrize("script", ["multiagent", "integrate"])
@pytest.mark.parametrize("branch", ["-D", "--orphan", "bad..name", "has space"])
def test_mcc_2_a_branch_git_would_not_accept_is_refused(tmp_path, script, branch):
    repo = _repo_with_map(tmp_path, "subtask-1", branch)
    before = _git(repo, "branch", "--list").stdout
    result = _run(script, repo)
    assert result.returncode != 0, result.stdout + result.stderr
    assert "branch" in (result.stdout + result.stderr).lower()
    assert _git(repo, "branch", "--list").stdout == before
    assert not (tmp_path / "wt").exists()


@pytest.mark.parametrize("sid", ["subtask-1", "subtask-A-analyze", "subtask-1 (wave 2)"])
def test_mcc_1_ids_that_maps_already_use_are_accepted(tmp_path, sid):
    repo = _repo_with_map(tmp_path, sid, "compass/demo/s1")
    result = subprocess.run(["bash", str(SCRIPTS["multiagent"]), "demo", "--dry-run"],
                            cwd=str(repo), capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "refused" not in result.stdout + result.stderr
