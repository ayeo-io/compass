"""Breakdown is done once plan is handed off (ADR-090, ADR-091).

Breakdown writes nothing of its own: one session builds the units (ADR-090), and
9.0.0 writes no distribution map. So `compass next` counts breakdown as done once
plan's hand-off is in `checkpoint_outcomes:`. An issue made before 9.0.0 whose
route earned a distribution map keeps the answer it had: breakdown waits for the
map or the subtasks.

Issue: ayeo-io/compass-delivery#353.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

import compass_pkg  # noqa: E402,F401  (the bundled PyYAML first)
from compass_pkg import next_cmd  # noqa: E402

STAGES = {"assess": "thorough", "define": "thorough", "refine": "thorough",
          "plan": "thorough", "breakdown": "multiagent", "implement": "thorough",
          "verify": "thorough", "ship": "thorough"}


def _handed_off(*stages):
    return [{"stage": s, "outcome": "waited", "by": "jed", "at": "2026-11-05T00:00:00Z",
             "evidence": "EV-X"} for s in stages]


def _task(*stages, **extra):
    task = {"created": "2026-11-05", "delivery_approach": "full", "stages": dict(STAGES),
            "scenarios": [{"id": "TRC-001", "tests": ["tests/test_x.py::test_x"]}],
            "gates": [{"id": "verify.correctness", "status": "pending"}],
            "checkpoint_outcomes": _handed_off(*stages)}
    task.update(extra)
    return task


# --- breakdown in compass next ------------------------------------------------------------

def test_breakdown_is_done_once_plan_is_handed_off():
    task = _task("define", "refine", "plan")
    assert "breakdown" in next_cmd._stages_on_record(task, None)
    assert next_cmd._current_phase_from_task(task, None) == "implement"


def test_breakdown_waits_while_plan_is_not_handed_off():
    task = _task("define", "refine")
    assert next_cmd._current_phase_from_task(task, None) == "plan"


def test_an_older_issue_that_earned_a_distribution_map_keeps_its_answer():
    task = _task("define", "refine", "plan", artifacts=[
        {"kind": "technical-design", "path": "docs/td.md", "status": "approved"},
        {"kind": "distribution-map", "status": "pending"}])
    assert next_cmd._current_phase_from_task(task, None) == "breakdown"


def test_an_older_issue_with_a_registered_distribution_map_keeps_its_answer():
    task = _task("define", "refine", "plan", artifacts=[
        {"kind": "distribution-map", "path": "docs/dm.md", "status": "approved"}])
    assert next_cmd._current_phase_from_task(task, None) == "implement"
