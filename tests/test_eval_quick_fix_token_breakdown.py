"""Where a Compass quick fix spends its tokens is on record by source.

The 4 October comparison run measured Compass's quick-fix premium and its
split by stage. This document breaks one scenario's sessions down by what
entered the model's context, before anything is cut (#377).

Scenario id: TB-1 (issue `cmp-refactor-token-breakdown`).
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "docs" / "compass" / "2026-10-04-eval-quick-fix-token-breakdown.md"


def test_tb_1_the_breakdown_is_on_record():
    raw = REPORT.read_text(encoding="utf-8")
    text = " ".join(raw.split())
    assert "`cmp-refactor`" in text
    for heading in ("## Result", "## By source", "## How it was measured",
                    "## What this does not show"):
        assert heading in raw, heading
    for source in ("Resident load", "Compass CLI output", "Skill text"):
        assert source in text, source
    assert "Rival products appear as codes R1 to R9" in text
    for placeholder in ("TODO", "TBD", "{{"):
        assert placeholder not in raw, placeholder
