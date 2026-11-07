"""An issue resumes from its stored generation.

The project's `compass.yml` can change or go away after a generation is
committed. The issue is still checked by the configuration it was
assessed under, with no file of the project's read.

Scenario id: `EF-3` (issue `effective-readers`).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

from test_generation_store import SLUG, _project, _run  # noqa: E402

#: A project check is the one way `compass.yml` adds a check and a guardrail
#: since 9.0.0 (ADR-094). Its command passes, so its row is the same either way.
PROJECT = {
    "schema": 1,
    "project_checks": [{
        "id": "project-rule", "name": "Project rule", "command": "true", "stage": "ship"}],
}


def test_overlay_deleted_check_runs_offline(tmp_path):
    root, _ = _project(tmp_path, compass_yml=PROJECT)
    code, out, err = _run(root, "approach", "evaluate", "--issue", SLUG, "--write")
    assert code == 0, out + err
    code, before, err = _run(root, "check", "--issue", SLUG, "--json")
    before = json.loads(before)
    assert "project-rule" in {c["guardrail"] for c in before["checks"]}, before
    (root / "compass.yml").unlink()
    code, after, err = _run(root, "check", "--issue", SLUG, "--json")
    after = json.loads(after)
    assert after["checks"] == before["checks"], err
    assert after["generation"] == 1
