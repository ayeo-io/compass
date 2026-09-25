"""The post-tool hook logs an edit to the current issue only when the file is
inside the project.

`hooks/post-tool.sh` appends a line to the current issue's devlog after
every Edit or Write. The devlog is the record a later session reads to pick
the issue up, so a line naming a file outside the project - a scratch file,
a worktree of another branch - is a false record of the issue's work. A path
inside the project is logged relative to it.

Scenario ids: DLO-1 to DLO-3, in the delivery approach of issue
`devlog-logs-edits-outside-the-project`.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "hooks" / "post-tool.sh"
SLUG = "logged"


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "proj"
    task = root / ".compass" / "work" / SLUG
    task.mkdir(parents=True)
    (root / ".compass" / "current-task").write_text(SLUG + "\n")
    (task / "devlog.md").write_text("# Devlog\n")
    (root / "src").mkdir()
    return root


def _edit(project, target, cwd=None):
    payload = json.dumps({"tool_name": "Edit", "tool_input": {"file_path": str(target)}})
    result = subprocess.run(["bash", str(HOOK)], input=payload, text=True,
                            capture_output=True, cwd=str(cwd or project),
                            env={**os.environ, "CLAUDE_PROJECT_DIR": str(project)})
    assert result.returncode == 0, result.stderr
    return (project / ".compass" / "work" / SLUG / "devlog.md").read_text()


def test_dlo_1_an_edit_outside_the_project_is_not_logged(project, tmp_path):
    outside = tmp_path / "scratch" / "notes.md"
    log = _edit(project, outside)
    assert "edit:" not in log, log


def test_dlo_2_an_edit_inside_the_project_is_logged_relative_to_it(project):
    log = _edit(project, project / "src" / "app.py")
    assert "edit: src/app.py" in log, log
    assert str(project) not in log, log


@pytest.mark.parametrize("target, logged", [
    ("src/app.py", True),
    ("src/../../outside.py", False),
])
def test_dlo_3_a_relative_path_is_judged_by_where_it_resolves(project, target, logged):
    log = _edit(project, target)
    assert ("edit:" in log) is logged, log


def test_dlo_3_the_no_project_message_names_the_devlog(tmp_path):
    payload = json.dumps({"tool_name": "Edit", "tool_input": {"file_path": "x.py"}})
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}
    (tmp_path / ".git").mkdir()
    result = subprocess.run(["bash", str(HOOK)], input=payload, text=True,
                            capture_output=True, cwd=str(tmp_path), env=env)
    assert result.returncode == 0
    assert "devlog" in result.stderr and "end-of-session" not in result.stderr, \
        result.stderr
