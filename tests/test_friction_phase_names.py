"""Friction entries use the current stage names.

The manifest schema listed only the retired stage names for a friction
entry's stage key, so `compass issue lint` refused `implement`, and
the CLI itself wrote the retired `frame` (#156). The schema now takes the
current names, a retired name loads as its current one, and the CLI
writes `assess`. The key is `stage`; an entry stored under its old name
`phase` is read as `stage`.

Scenario id: FP-1 (issue `friction-phase-takes-v2-stages`).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

from test_quick_fix_verbs import _manifest_path, _run, _start, repo  # noqa: E402,F401

CURRENT = ("assess", "define", "refine", "plan", "breakdown", "implement",
           "verify", "ship")


def _add_friction(root, slug, stage):
    path = _manifest_path(root, slug)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["friction"] = [{"stage": stage, "category": "tooling",
                         "observation": "x", "source": "human"}]
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def test_fp_1_the_schema_takes_every_current_stage_name():
    import json
    schema = json.loads((ROOT / "schemas" / "manifest.schema.json")
                        .read_text(encoding="utf-8"))
    properties = schema["properties"]["friction"]["items"]["properties"]
    assert "phase" not in properties
    stages = properties["stage"]["enum"]
    for stage in CURRENT:
        assert stage in stages, stage


def test_fp_1_issue_lint_accepts_a_current_stage(repo):
    pytest.importorskip("jsonschema")
    assert _start(repo, "greeting-fix").returncode == 0
    _add_friction(repo, "greeting-fix", "implement")
    result = _run(repo, "issue", "lint", "--issue", "greeting-fix")
    assert result.returncode == 0, result.stdout + result.stderr


def test_fp_1_a_retired_stage_loads_as_its_current_name():
    from compass_pkg.core import normalize_spine
    task = normalize_spine({"friction": [{"phase": "frame", "category": "other",
                                          "source": "human"},
                                         {"phase": "build", "category": "other",
                                          "source": "human"},
                                         {"stage": "build", "category": "other",
                                          "source": "human"}]})
    assert [f["stage"] for f in task["friction"]] == ["assess", "implement", "implement"]
    assert all("phase" not in f for f in task["friction"])


def test_fp_1_derived_friction_is_written_in_the_current_name(tmp_path):
    from compass_pkg.calibration import derive_friction
    task = {"reassessments": [{"from_route": "quick-fix", "to_route": "feature",
                               "reason": "grew"}]}
    entries = derive_friction("demo", task, str(tmp_path))
    assert entries and all(e["stage"] == "assess" and "phase" not in e for e in entries)
