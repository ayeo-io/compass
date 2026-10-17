"""The assessment rubric describes the dimensions the evaluator scores.

Role left the assessment in 7.0.0 (ADR-070). What remains is three scored
dimensions that the evaluator refuses an assessment without, two switches
that each select a reference shape, and domain labels. A session reads the
rubric and the adaptive-routing skill at assess, so wording that still says
"four dimensions" leads it to score a dimension the evaluator does not need.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "cli"))

from compass_pkg.classify import EVALUATOR_REQUIRED  # noqa: E402

RUBRIC_FILES = ("approaches/rubric.md", "skills/adaptive-routing/SKILL.md")

FOUR_DIMENSIONS = re.compile(r"\bfour\s+(?:assessment\s+)?dimension", re.I)


def _text(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


def _switches() -> list[str]:
    """The dimensions a shipped default shape reads that are not scored."""
    policy = yaml.safe_load(_text("governance/routing-policy.yml"))
    keys = []
    for shape in policy["routing_strategies"]["default_shapes"]:
        for key in shape["when"]:
            if key not in EVALUATOR_REQUIRED and key not in keys:
                keys.append(key)
    return keys


def test_the_switches_are_goal_and_urgency():
    assert EVALUATOR_REQUIRED == ("risk", "familiarity", "size")
    assert _switches() == ["goal", "urgency"]


def test_rubric_names_three_scored_dimensions():
    for rel in RUBRIC_FILES:
        text = _text(rel)
        assert not FOUR_DIMENSIONS.search(text), (
            f"{rel} still says four dimensions")
        assert re.search(r"three scored dimensions", text, re.I), (
            f"{rel} does not name the three scored dimensions")
        assert re.search(r"two switches", text, re.I), (
            f"{rel} does not name the two switches")
        for switch in _switches():
            assert f"`{switch}`" in text, (rel, switch)
        assert "domain label" in text, (rel, "domain label")
