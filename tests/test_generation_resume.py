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

PROJECT = {
    "schema": 1,
    "checks": {"project-rule": {
        "statement": "A project rule.", "kind": "deterministic", "impl": "suite-passed",
        "severity": "blocking", "on_skipped": "fail"}},
    "gates": {"P1": {
        "kind": "guardrail", "name": "Project rule", "statement": "A project rule.",
        "stage": "verify", "applies_to": {"ships": True}, "checks": ["project-rule"]}},
}


def test_overlay_deleted_check_runs_offline(tmp_path):
    root, _ = _project(tmp_path, compass_yml=PROJECT)
    code, out, err = _run(root, "approach", "evaluate", "--issue", SLUG, "--write")
    assert code == 0, out + err
    code, before, err = _run(root, "check", "--issue", SLUG, "--json")
    before = json.loads(before)
    assert "P1" in {c["guardrail"] for c in before["checks"]}, before
    (root / "compass.yml").unlink()
    code, after, err = _run(root, "check", "--issue", SLUG, "--json")
    after = json.loads(after)
    assert after["checks"] == before["checks"], err
    assert after["generation"] == 1
