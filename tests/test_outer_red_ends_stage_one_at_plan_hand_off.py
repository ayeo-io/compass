"""An outer-loop red ends stage 1 only before plan is handed off (ADR-081, ADR-091).

`acceptance_strategy.stage_one` says whether an outer-loop red is written before
implement. It read "before implement" as "no technical design, distribution map or
subtask registered". 9.0.0 registers no document, so every outer-loop red read as
written before implement, even one written during implement. Plan's hand-off in
`checkpoint_outcomes:` now ends stage 1 too. An issue made before 9.0.0 keeps the
answer its registered documents give.

Issue: ayeo-io/compass-delivery#353.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

import compass_pkg  # noqa: E402,F401  (the bundled PyYAML first)
from compass_pkg import acceptance_strategy  # noqa: E402

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


# --- the outer-loop red (stage 1) -----------------------------------------------------------

def test_an_outer_red_before_plan_is_handed_off_is_stage_one():
    assert acceptance_strategy.stage_one(_task("define", "refine"), "outer") is True


def test_an_outer_red_after_plan_is_handed_off_is_not_stage_one():
    assert acceptance_strategy.stage_one(_task("define", "refine", "plan"), "outer") is False


def test_an_older_issue_with_a_registered_design_keeps_its_answer():
    task = _task("define", "refine", artifacts=[
        {"kind": "technical-design", "path": "docs/td.md", "status": "approved"}])
    assert acceptance_strategy.stage_one(task, "outer") is False
