"""The pre-tool hook ends on a relative path instead of looping.

Scenario id: `TRC-007` in worktree-issue-from-edited-path/acceptance-criteria.md

Every loop in `hooks/pre-tool.sh` that climbs a path with `dirname` must stop
when the parent equals the path. A relative path ends at `.`, and the parent
of `.` is `.`. A hook that hangs can fail open, because a timeout does not
block the tool call, so each case runs under a 10 second limit and a hang
fails the test.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
# The override lets a copy with a planted fault prove this test can fail.
PRE_TOOL = pathlib.Path(os.environ.get(
    "COMPASS_HOOK_UNDER_TEST", REPO_ROOT / "hooks" / "pre-tool.sh"))

pytestmark = pytest.mark.skipif(
    not PRE_TOOL.exists(), reason="hooks/pre-tool.sh missing")


def _project(root):
    root = root.resolve()
    (root / "src").mkdir(parents=True)
    (root / "src" / "app.py").write_text("x = 1\n", encoding="utf-8")
    (root / ".compass" / "work").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    return root


def _run(cwd, file_path, project_dir=None):
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    if project_dir is not None:
        env["CLAUDE_PROJECT_DIR"] = project_dir
    payload = {"tool_name": "Write", "cwd": str(cwd),
               "tool_input": {"file_path": file_path, "content": "x\n"}}
    return subprocess.run(
        ["bash", str(PRE_TOOL)], input=json.dumps(payload),
        capture_output=True, text=True, env=env, cwd=str(cwd), timeout=10)


@pytest.mark.parametrize("file_path", ["src/app.py", "missing/new.py"])
@pytest.mark.parametrize("project_dir", [".", "sub"])
def test_relative_target_outside_any_project_ends(
        tmp_path, file_path, project_dir):
    """Scenario id: `TRC-007` in worktree-issue-from-edited-path/acceptance-criteria.md

    Under a relative session project, with no `.compass/` or `.git` above
    the working directory, the climb for a Compass root reaches `.` and must
    stop there.
    """
    bare = tmp_path / "bare"
    (bare / "src").mkdir(parents=True)
    (bare / "sub").mkdir()
    try:
        result = _run(bare, file_path, project_dir)
    except subprocess.TimeoutExpired:
        pytest.fail(f"hook hung on {file_path!r} with project {project_dir!r}")
    assert result.returncode in (0, 2), result.stderr


@pytest.mark.parametrize("project_dir", [None, ".", "sub/.."])
@pytest.mark.parametrize("file_path", [
    "src/app.py", "src/new/deep/file.py", "missing/new.py", "app.py"])
def test_relative_target_path_ends(tmp_path, file_path, project_dir):
    """Scenario id: `TRC-007` in worktree-issue-from-edited-path/acceptance-criteria.md

    A relative target path, with or without a relative session project,
    returns an exit code instead of hanging.
    """
    root = _project(tmp_path / "proj")
    try:
        result = _run(root, file_path, project_dir)
    except subprocess.TimeoutExpired:
        pytest.fail(f"hook hung on {file_path!r} with project {project_dir!r}")
    assert result.returncode in (0, 2), result.stderr
