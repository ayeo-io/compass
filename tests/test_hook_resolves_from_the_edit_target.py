"""The pre-tool hook enforces the tree the edit is in, not the session's.

Compass creates git worktrees itself at breakdown, so on any multiagent
approach the session directory and the edited file are in different trees.
The hook resolved the project from `$(pwd)` or `$CLAUDE_PROJECT_DIR` - both
of which name the session - and so read the wrong `.compass/`.

It failed in both directions:

* **Closed.** A builder who had recorded a red in its worktree was blocked,
  and told "no failing test on record" while a valid `.red` and its evidence
  sat in that worktree's own issue directory.

* **Open.** A red recorded in the MAIN tree unlocked production edits in
  every worktree, including ones whose builder had no failing test at all.
  This is the fail-open the hook's own comment refuses for the parent walk,
  reached another way, and it appears only on the multiagent orchestration,
  where the work is most consequential.

Reproduced on 2026-08-27 before the fix: a valid red placed in the main tree
allowed an append to `cli/compass_pkg/core.py` inside a worktree that had no
red of its own.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
PRE_TOOL = REPO_ROOT / "hooks" / "pre-tool.sh"

pytestmark = pytest.mark.skipif(
    not PRE_TOOL.exists(), reason="hooks/pre-tool.sh missing")


def _run_hook(cwd, target, project_dir=None):
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    if project_dir:
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)
    payload = {"tool_name": "Edit", "tool_input": {"file_path": str(target)}}
    return subprocess.run(
        ["bash", str(PRE_TOOL)], input=json.dumps(payload),
        capture_output=True, text=True, env=env, cwd=str(cwd), timeout=60)


def _tree(root, slug="t", *, red=False):
    """A Compass project holding one issue, optionally mid-red."""
    root = root.resolve()
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "src" / "app.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    issue = root / ".compass" / "work" / slug
    (issue / "evidence").mkdir(parents=True, exist_ok=True)
    (root / ".compass" / "current-task").write_text(slug, encoding="utf-8")
    (issue / "manifest.yml").write_text(
        f"schema_version: '2.0'\nissue: {slug}\n"
        "assessment: {risk: contained, familiarity: brownfield-mapped, "
        "size: small, goal: delivery, role: engineer}\n"
        "delivery_approach: feature\n", encoding="utf-8")
    (issue / "delivery-approach.md").write_text(
        "# Delivery approach\n\nfeature\n", encoding="utf-8")
    if red:
        # A real red carries a record beside the marker; the hook reads both.
        subprocess.run(
            [str(REPO_ROOT / "cli" / "compass"), "tdd-red", "--",
             "python3", "-c", "print('1 failed'); import sys; sys.exit(1)"],
            capture_output=True, text=True, cwd=str(root), timeout=120)
    return root


def test_a_red_in_the_worktree_allows_an_edit_in_the_worktree(tmp_path):
    """The fail-closed half. The builder did the right thing and was blocked."""
    session = _tree(tmp_path / "main")
    worktree = _tree(tmp_path / "wt", red=True)
    r = _run_hook(session, worktree / "src" / "app.py",
                  project_dir=session)
    assert r.returncode == 0, (
        "an edit inside a worktree that has its own recorded red was blocked, "
        "because the hook read the session's tree instead:\n"
        f"{r.stdout}{r.stderr}")


def test_a_red_in_the_session_does_not_unlock_a_worktree(tmp_path):
    """The fail-open half, and the reason this is not merely an annoyance."""
    session = _tree(tmp_path / "main", red=True)
    worktree = _tree(tmp_path / "wt")          # no red of its own
    r = _run_hook(session, worktree / "src" / "app.py",
                  project_dir=session)
    assert r.returncode != 0, (
        "a red recorded in the session's tree unlocked a production edit in a "
        "worktree that has no failing test on record - the guard passed an "
        "untested change:\n"
        f"{r.stdout}{r.stderr}")


def test_a_call_naming_no_file_still_resolves_from_the_session(tmp_path):
    """The fallback. A Bash call carries no file_path, so the session remains
    the best available answer - and must keep working."""
    session = _tree(tmp_path / "main", red=True)
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = str(session)
    payload = {"tool_name": "Bash", "tool_input": {"command": "ls"}}
    r = subprocess.run(
        ["bash", str(PRE_TOOL)], input=json.dumps(payload),
        capture_output=True, text=True, env=env, cwd=str(session), timeout=60)
    assert r.returncode == 0, f"{r.stdout}{r.stderr}"
