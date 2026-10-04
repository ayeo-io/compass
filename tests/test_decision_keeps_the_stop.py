"""The decision to keep Compass's stop before a breaking change is on record.

The comparison run's decision rule (`evals/README.md`) asks, for a scenario
with no edge for Compass, for a spec or a recorded decision to keep the
steps at their measured cost. For the shared-helper scenario the maintainer
chose to keep the stop.

Scenario id: KS-1 (issue `keep-the-stop-before-a-breaking-change`).
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENTRY = (ROOT / "governance" / "decisions"
         / "2026-10-04-keep-the-stop-before-a-breaking-change.md")


def test_ks_1_the_decision_is_in_the_ledger():
    text = ENTRY.read_text(encoding="utf-8")
    assert "jed72" in text
    for section in ("## Decision", "## Why", "## Evidence"):
        assert section in text, section
    assert "2026-10-04-eval-comparison-premium.md" in text
