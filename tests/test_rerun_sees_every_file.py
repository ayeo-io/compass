"""A green after a change to any tracked file is not a re-run without change.

`compass tdd-green` marks a green `rerun_without_change: true` when the same
command runs again on an unchanged tree. "Unchanged" is judged by the tree's
`tree_id` - every tracked file on disk, whatever its type - as well as the
source-file hash, which also sees untracked source files.

Scenario ids: RSE-1 and RSE-2, in the delivery approach of issue
`rerun-check-misses-script-changes`.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

CLI = Path(__file__).resolve().parent.parent / "cli" / "compass"
SLUG = "rse"


def _git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                          text=True, check=True)


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "proj"
    task = root / ".compass" / "work" / SLUG
    task.mkdir(parents=True)
    (task / "manifest.yml").write_text(
        f"schema_version: '2.0'\nissue: {SLUG}\ncreated: '2026-09-25'\n"
        "status: active\n")
    (root / ".gitignore").write_text("/.compass/\n")
    (root / "tool.sh").write_text("echo one\n")
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    return root


def _green(root):
    result = subprocess.run(
        [sys.executable, str(CLI), "tdd-green", "--issue", SLUG, "--",
         sys.executable, "-c", "pass"],
        cwd=root, capture_output=True, text=True,
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(root)})
    assert result.returncode == 0, result.stderr
    path = root / ".compass" / "work" / SLUG / "evidence" / "green.json"
    return json.loads(path.read_text())


def test_rse_1_a_green_after_a_script_edit_is_not_a_rerun(project):
    _green(project)
    (project / "tool.sh").write_text("echo two\n")
    record = _green(project)
    assert record.get("rerun_without_change") is False, record


def test_rse_2_a_green_with_nothing_changed_is_still_a_rerun(project):
    _green(project)
    record = _green(project)
    assert record.get("rerun_without_change") is True, record
