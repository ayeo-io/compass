"""The comparison is on record, and no public claim outruns it.

The report names every condition, both pinned framework commits and the
model, says what two executions cannot show, and keeps its failures in.
The README makes no comparative claim about another framework that does
not cite the report.

Scenario ids: CMP-5 and CMP-6, for issue `comparison-suite`.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "docs" / "compass" / "2026-09-28-eval-comparison.md"
README = ROOT / "README.md"


def test_cmp_5_the_comparison_is_on_record_with_its_limits():
    raw = REPORT.read_text(encoding="utf-8")
    text = " ".join(raw.split())
    for name in ("Compass", "Superpowers", "Spec Kit", "no framework"):
        assert name in text, name
    for pin in ("8ca22dba", "3b895d16", "claude-opus-5-5"):
        assert pin in text, pin
    assert "48 sessions" in text
    assert "## What this does not show" in raw
    for placeholder in ("TODO", "TBD", "{{"):
        assert placeholder not in raw, placeholder


def test_cmp_6_no_readme_claim_about_another_framework_outruns_the_run():
    text = README.read_text(encoding="utf-8")
    mentions = re.findall(r"(?i)superpowers|spec[- ]?kit", text)
    if mentions:
        assert "2026-09-28-eval-comparison.md" in text, (
            "the README names another framework but does not cite the run")


# The second comparison: four scenarios where a careless change fails.
DISCRIMINATING = ROOT / "docs" / "compass" / "2026-09-30-eval-comparison-discriminating.md"
NEW_SCENARIOS = ("cmp-hidden-requirement", "cmp-call-sites", "cmp-refactor",
                 "cmp-edge-case")


def test_the_discriminating_comparison_is_on_record():
    raw = DISCRIMINATING.read_text(encoding="utf-8")
    text = " ".join(raw.split())
    for name in ("Compass", "Superpowers", "Spec Kit", "no framework"):
        assert name in text, name
    for scenario in NEW_SCENARIOS:
        assert f"`{scenario}`" in text, scenario
    assert "32 sessions" in text
    assert "## Did the conditions differ?" in raw
    per_scenario = raw.split("## Per scenario", 1)[1].split("\n## ", 1)[0]
    for scenario in NEW_SCENARIOS:
        assert f"| `{scenario}` |" in per_scenario, scenario
    assert "## What this does not show" in raw
    for placeholder in ("TODO", "TBD", "{{"):
        assert placeholder not in raw, placeholder
