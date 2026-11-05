"""The board and flow state read the hand-offs of refine and plan (ADR-045, ADR-091).

`lifecycle.state_of`, which the board and `compass flow` show, read refine and plan
as finished only from a registered requirements review or technical design. 9.0.0
writes neither, so an issue whose refine and plan were handed off stayed in
`backlog`. The hand-off in `checkpoint_outcomes:` now counts, as `compass next`
reads it. An issue made before 9.0.0 keeps the answer its registered documents give.

Issue: ayeo-io/compass-delivery#353.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

import compass_pkg  # noqa: E402,F401  (the bundled PyYAML first)
from compass_pkg import lifecycle  # noqa: E402

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


# --- the board and flow state -------------------------------------------------------------

def test_an_issue_with_refine_handed_off_is_ready(tmp_path):
    assert lifecycle.state_of(_task("define", "refine"), str(tmp_path)) == "ready"


def test_an_issue_with_plan_handed_off_is_in_progress(tmp_path):
    task = _task("define", "refine", "plan")
    assert lifecycle.state_of(task, str(tmp_path)) == "in-progress"


def test_an_older_issue_with_a_registered_review_is_ready(tmp_path):
    task = _task(artifacts=[
        {"kind": "requirements-review", "path": "docs/rr.md", "status": "approved"}])
    assert lifecycle.state_of(task, str(tmp_path)) == "ready"


def test_an_issue_with_nothing_handed_off_is_backlog(tmp_path):
    assert lifecycle.state_of(_task("define"), str(tmp_path)) == "backlog"
