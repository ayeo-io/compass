"""The 4 October comparison run is on record, an edge or not.

`evals/README.md`'s decision rule, written before the run, says every
result is published next to the 30 September run, and a scenario with no
edge for Compass gets a spec or a recorded decision within a week.

Scenario id: PR-1 (issue `premium-run`).
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "docs" / "compass" / "2026-10-04-eval-comparison-premium.md"
CAREFUL = ("cmp-late-tidy", "cmp-shared-helper", "cmp-resume-decision",
           "cmp-second-change")
ORIGINAL = ("cmp-hidden-requirement", "cmp-call-sites", "cmp-refactor",
            "cmp-edge-case")


def test_pr_1_the_run_is_on_record():
    raw = REPORT.read_text(encoding="utf-8")
    text = " ".join(raw.split())
    for name in ("Compass", "R1", "R3", "no framework"):
        assert name in text, name
    assert "64 sessions" in text
    assert "Rival products appear as codes R1 to R9" in text
    verdicts = raw.split("## The decision rule", 1)[1].split("\n## ", 1)[0]
    for scenario in CAREFUL:
        assert f"| `{scenario}` |" in verdicts, scenario
    assert "no edge" in verdicts
    for scenario in CAREFUL + ORIGINAL:
        assert f"`{scenario}`" in text, scenario
    assert "## Tokens by stage" in raw
    assert "## What this does not show" in raw
    for placeholder in ("TODO", "TBD", "{{"):
        assert placeholder not in raw, placeholder
