"""An advisory strategy asking a design to name the patterns it uses.

No strategy asked implementations to prefer well-understood, named design
patterns, which left a reviewer judging maintainability with no stated
definition of good. The named-patterns strategy (`S16`) asks a design to
name its patterns and, where it chose, the one it rejected; the reviewer
flags a novel structure where a standard pattern fits, and a pattern where
none is needed. It advises and never gates (ADR-003). Issue
`named-patterns-strategy`.

Scenario id: NP-1.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _section():
    text = (ROOT / "governance" / "strategies.md").read_text(encoding="utf-8")
    return text.split("(`S16`)", 1)[1].split("\n---", 1)[0]


def test_np_1_the_strategy_asks_for_named_and_rejected_patterns():
    section = _section()
    assert "reject" in section and "ADR-003" in section, section
    assert "none is needed" in section or "no pattern" in section, section


def test_np_1_the_rationale_and_the_texts_point_to_it():
    rationale = (ROOT / "governance" / "strategies-rationale.md").read_text(encoding="utf-8")
    assert "(`S16`)" in rationale
    for rel in ("agents/reviewer.md", "skills/plan-authoring/SKILL.md",
                "templates/technical-design.md"):
        assert "S16" in (ROOT / rel).read_text(encoding="utf-8"), rel
