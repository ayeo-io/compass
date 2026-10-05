"""The maintainer's answers to four triage questions are on record.

A triage of open issues 98 to 156 on 4 October left four questions only the
maintainer could answer. On 5 October the maintainer took the
recommendation on each. The ledger holds them so a reviewer and a later
session read the choice, not the open question.

Scenario id: TD-1 (issue `record-triage-decisions`).
"""
from __future__ import annotations

from pathlib import Path

import pytest

DECISIONS = Path(__file__).resolve().parent.parent / "governance" / "decisions"

ENTRIES = {
    "no-project-guardrails-in-this-repository": "#100",
    "guardrails-merge-routing-policy-replaces": "#105",
    "keep-receipt-pending-cold-readers": "#116",
    "remind-when-the-review-page-goes-stale": "#121",
}


@pytest.mark.parametrize("slug", sorted(ENTRIES))
def test_td_1_each_decision_is_in_the_ledger(slug):
    path = DECISIONS / f"2026-10-05-{slug}.md"
    text = path.read_text(encoding="utf-8")
    assert "jed72" in text
    for section in ("## Decision", "## Why", "## Evidence"):
        assert section in text, section
    assert ENTRIES[slug] in text
