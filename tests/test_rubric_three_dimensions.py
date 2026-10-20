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

FOUR_DIMENSIONS = re.compile(
    r"\bfour[\s-]+(?:assessment\s+|scored\s+)?dimension", re.I)

# "risk, familiarity, size and goal" names goal as a scored dimension.
GOAL_AS_SCORED = re.compile(
    r"risk,\s+familiarity,\s+size,?\s+(?:and\s+)?goal", re.I)

# The docs and agents a session or an adopter reads to learn how Compass
# assesses a change. governance/routing-policy.yml is generated from the
# default preset, so it is checked here and fixed at its source.
DESCRIBING_FILES = (
    "AGENTS.md",
    "README.md",
    "agents/router.md",
    "approaches/README.md",
    "approaches/assess-procedure.md",
    "approaches/composition-reference.md",
    "approaches/hotfix.md",
    "approaches/spike.md",
    "commands/assess.md",
    "commands/status.md",
    "docs/approach-diagram.html",
    "docs/five-minutes.md",
    "docs/index.md",
    "docs/methodology.md",
    "docs/portability.md",
    "docs/quickstart.md",
    "docs/receipt.md",
    "docs/routing-deep-dive.md",
    "docs/safety-contract.md",
    "governance/routing-policy.md",
    "governance/routing-policy.yml",
    "skills/quick-fix/SKILL.md",
)


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


def test_docs_and_agents_name_no_fourth_dimension():
    """No doc or agent tells a reader to score four dimensions or goal."""
    found = []
    for rel in DESCRIBING_FILES:
        text = _text(rel)
        for pattern in (FOUR_DIMENSIONS, GOAL_AS_SCORED):
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                found.append(f"{rel}:{line}: {match.group(0)!r}")
    assert not found, "four scored dimensions still described:\n" + "\n".join(found)
