"""Four comparison scenarios where careful process should beat careless change.

The published scenarios were small enough that no condition made a careless
change (docs/compass/2026-09-30-eval-comparison-discriminating.md). These
four are risky, interrupted or sequenced: a requested tidy-up that undoes a
fix, a shared helper whose change breaks a consumer, a cold resume whose
pricing rule exists only in the record, and a second change that must
follow a rounding rule the first one recorded (issue #340). Their seeds,
reference solutions and careless changes are checked with the other
comparison scenarios in tests/test_eval_comparison_tasks.py; this module
checks each condition's record and the decision rule.

Scenario ids: PS-1 to PS-4 (issue `premium-scenario-classes`).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from test_eval_comparison_tasks import (CONDITION_OVERLAY_DIRS, TASK_IDS,
                                        _overlay_dir, _overlay_markdown_text)

ROOT = Path(__file__).resolve().parent.parent
NEW = ("cmp-late-tidy", "cmp-shared-helper", "cmp-resume-decision",
       "cmp-second-change")
WITH_RECORDS = ("cmp-resume-decision", "cmp-second-change")

# What the hidden test checks, which every condition's record must state.
RULE_WORDS = {
    "cmp-resume-decision": ("a fifth", "rounded up to the next 10 pence",
                            "345", "595", "1095"),
    "cmp-second-change": ("whole pence", "rounds half up"),
}

# Each framework's usual place for a record.
USUAL_PLACE = {
    "bare": "NOTES.md",
    "compass": (".compass/work/*/devlog.md", "governance/decisions/*.md"),
    "R1": "docs/R1/*/*.md",
    "R3": "specs/*/spec.md",
}


def test_ps_1_the_four_scenarios_are_in_the_suite():
    for task_id in NEW:
        assert task_id in TASK_IDS, task_id


def test_ps_2_each_scenario_has_a_reference_and_a_careless_change():
    from test_eval_comparison_tasks import CARELESS_CHANGES, REFERENCE_SOLUTIONS
    for task_id in NEW:
        assert task_id in REFERENCE_SOLUTIONS, task_id
        assert task_id in CARELESS_CHANGES, task_id


@pytest.mark.parametrize("task_id", WITH_RECORDS)
@pytest.mark.parametrize("condition", sorted(CONDITION_OVERLAY_DIRS))
def test_ps_3_each_condition_finds_the_work_in_its_usual_place(task_id, condition):
    overlay = _overlay_dir(task_id, condition)
    places = USUAL_PLACE[condition]
    places = places if isinstance(places, tuple) else (places,)
    assert any(list(overlay.glob(p)) for p in places), (task_id, condition)


@pytest.mark.parametrize("task_id", WITH_RECORDS)
@pytest.mark.parametrize("condition", sorted(CONDITION_OVERLAY_DIRS))
def test_ps_3_every_record_states_the_rule(task_id, condition):
    text = " ".join(_overlay_markdown_text(_overlay_dir(task_id, condition)).split())
    for words in RULE_WORDS[task_id]:
        assert words in text, (task_id, condition, words)


@pytest.mark.parametrize("task_id", WITH_RECORDS)
def test_ps_3_no_record_names_a_hidden_test(task_id):
    hidden = next((ROOT / "evals" / "scenarios" / task_id / "hidden_tests")
                  .rglob("test_*.py")).read_text(encoding="utf-8")
    names = re.findall(r"^def (test_\w+)", hidden, re.M)
    for condition in CONDITION_OVERLAY_DIRS:
        text = _overlay_markdown_text(_overlay_dir(task_id, condition))
        for name in names:
            assert name not in text, (task_id, condition, name)


def test_ps_4_the_decision_rule_is_written_before_any_run():
    readme = (ROOT / "evals" / "README.md").read_text(encoding="utf-8")
    assert "## Decision rule" in readme
    rule = readme.split("## Decision rule", 1)[1].split("\n## ", 1)[0]
    for task_id in NEW:
        assert task_id in rule, task_id
    assert "two runs" in rule and "within one week" in rule, rule
