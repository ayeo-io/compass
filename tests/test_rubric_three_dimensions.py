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

sys.path.insert(0, str(REPO_ROOT / "tests"))
from check_set_files import shipped  # noqa: E402
# The dimensions the evidence evaluator refuses an assessment without. The
# classifier held the same tuple until 9.0.0 removed it (ADR-094).
from compass_pkg.evidence_required import _REQUIRED as EVALUATOR_REQUIRED  # noqa: E402

RUBRIC_FILES = ("approaches/rubric.md", "skills/adaptive-routing/SKILL.md")

FOUR_DIMENSIONS = re.compile(
    r"\bfour[\s-]+(?:assessment\s+|scored\s+)?dimension", re.I)

# "risk, familiarity, size and goal" names goal as a scored dimension.
GOAL_AS_SCORED = re.compile(
    r"risk,\s+familiarity,\s+size,?\s+(?:and\s+)?goal", re.I)

# The docs and agents a session or an adopter reads to learn how Compass
# assesses a change. The check set is read in its routing-policy shape below.
DESCRIBING_FILES = (
    "AGENTS.md",
    "README.md",
    "approaches/README.md",
    "approaches/assess-procedure.md",
    "approaches/composition-reference.md",
    "approaches/path.md",
    "approaches/spike.md",
    "commands/assess.md",
    "commands/status.md",
    "docs/approach-diagram.html",
    "docs/five-minutes.md",
    "docs/index.md",
    "docs/methodology.md",
    "docs/portability.md",
    "docs/quickstart.md",
    "docs/routing-deep-dive.md",
    "docs/safety-contract.md",
    "governance/routing-policy.md",
    "commands/quick-fix.md",
)


def _text(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


def _switches() -> list[str]:
    """The closed dimensions of the shipped default that are not scored. Since 9.0.0
    the shapes read only `goal` (the spike) and the evidence rows read `urgency`
    (ADR-092), so the switches are read from the dimensions catalogue."""
    dims = shipped("dimensions.yml")["dimensions"]
    return [name for name, body in dims.items()
            if name not in EVALUATOR_REQUIRED and body.get("type") != "set"]


def test_the_switches_are_goal_and_urgency():
    assert EVALUATOR_REQUIRED == ("risk", "familiarity", "size")
    assert _switches() == ["goal", "urgency"]
    # The spike shape reads `goal`, and the evidence rows read `urgency`.
    from check_set_files import view as shipped_view
    policy = shipped_view("routing-policy.yml")
    read = {key for shape in policy["routing_strategies"]["default_shapes"]
            for key in shape["when"]}
    assert read == {"goal"}, read
    assert '"urgency"' in _text("cli/compass_pkg/evidence_required.py")


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
