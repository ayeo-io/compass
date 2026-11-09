"""`TRC-C5` - the coverage-floor example carries the floor-never-target caveat.

Serves: INT-7
Spec:
  - caveat: a floor, never a target - coverage is a side effect of test discipline, not a goal
    (the coverage-floor example of `guardrails.yml` went with that file
    in 9.0.0, ADR-098)
  - skills/evidence-gates/SKILL.md must also carry the coverage caveat paragraph
"""
from __future__ import annotations
from pathlib import Path

EVIDENCE_GATES = Path(__file__).parent.parent / "skills" / "evidence-gates" / "SKILL.md"

def _evidence_gates_text():
    """Reads SKILL.md and its sibling files, because the coverage notes live
    in a sibling - along with the review-dimension checklists, the evidence
    vocabulary and the architecture-check detail. A guard reading only
    SKILL.md reports content missing when it has moved to a sibling file.
    """
    import pathlib as _p
    d = _p.Path(__file__).resolve().parent.parent / "skills" / "evidence-gates"
    return "\n".join(sorted(p.read_text(encoding="utf-8") for p in d.glob("*.md")))



def test_evidence_gates_has_coverage_caveat():
    """skills/evidence-gates/SKILL.md must also carry the coverage caveat paragraph."""
    text = _evidence_gates_text()
    text_lower = text.lower()
    assert "coverage" in text_lower, (
        "evidence-gates/SKILL.md must mention coverage."
    )
    assert "floor" in text_lower, (
        "evidence-gates/SKILL.md must mention the coverage 'floor' concept."
    )
    assert "target" in text_lower or "goal" in text_lower, (
        "evidence-gates/SKILL.md must say coverage is not a target/goal."
    )
    assert "side effect" in text_lower or "never a target" in text_lower or "not a target" in text_lower, (
        "evidence-gates/SKILL.md must say coverage is a side effect (floor, never a target). "
        f"Coverage lines: {[l for l in text.splitlines() if 'coverage' in l.lower()]}"
    )
