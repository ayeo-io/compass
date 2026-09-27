"""The pre-tool hook's "not assessed" refusal names the light path too.

A session refused for an unassessed change is told to assess. For a small,
low-risk change, `/compass:quick-fix` is the lighter way to do that, and
the pilot sessions reached for it on their own. Naming it in the refusal
is the wording change measured against the pilot's baseline.

Scenario id: SPT-5, in `acceptance-criteria.md` of issue
`skill-prose-pressure-tests`.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "hooks" / "pre-tool.sh"


def _refusal(project: Path) -> str:
    payload = {"tool_name": "Edit",
               "tool_input": {"file_path": str(project / "src" / "app.py"),
                              "old_string": "a", "new_string": "b"},
               "cwd": str(project)}
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(project))
    proc = subprocess.run(["bash", str(HOOK)], input=json.dumps(payload),
                          capture_output=True, text=True, env=env,
                          cwd=project)
    assert proc.returncode == 2, proc.stderr
    return proc.stderr


def _opted_in(tmp_path: Path, with_work: bool) -> Path:
    project = tmp_path / "project"
    (project / "src").mkdir(parents=True)
    (project / "src" / "app.py").write_text("a\n")
    compass = project / ".compass"
    compass.mkdir()
    (compass / "config.yml").write_text("version: 1.0.0\n")
    if with_work:
        (compass / "work").mkdir()
    return project


def test_spt_5_refusal_with_no_issue_names_quick_fix(tmp_path):
    message = _refusal(_opted_in(tmp_path, with_work=True))
    assert "/compass:assess" in message
    assert "/compass:quick-fix" in message


def test_spt_5_refusal_with_no_work_directory_names_quick_fix(tmp_path):
    message = _refusal(_opted_in(tmp_path, with_work=False))
    assert "/compass:assess" in message
    assert "/compass:quick-fix" in message
