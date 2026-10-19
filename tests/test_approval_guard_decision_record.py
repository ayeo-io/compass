"""Scenario `TRC-055` of issue `hooks-stop-refusing-harmless-work`: one new
decision record states the rule that the approval guard judges words, not text.

The record is made by `compass decision record the-approval-guard-judges-words-not-text`,
which dates the file for the day it runs, so the test finds it by the slug and
never by a date. It holds six statements. Each is checked by a phrase, with
letter case, backticks and line breaks ignored. A merged record never changes,
so a later rule is a new record; `compass decision check` guards the older
files, and this test does not repeat it.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PATTERN = "*-the-approval-guard-judges-words-not-text.md"

#: Statement -> the phrases that show the record makes it.
STATEMENTS = {
    "what is text and what is judged again": ("what is text", "judged again"),
    "the table of nine loosenings": ("nine loosenings",),
    "why an unknown command stays refused": ("an unknown command stays refused",),
    "the accepted write-then-run limit": ("written by one command and run by another",),
    "no exemption applies inside a pipe or a substitution": (
        "no exemption applies inside a pipe or a substitution",),
    "the replaced rule, with the older decisions left standing": (
        "any text that names the folder is refused", "adr-068 decision 10",
        "adr-069 decisions 4 and 8"),
}


def _normal(text):
    return re.sub(r"\s+", " ", text.replace("`", "")).lower()


def test_trc_055_a_new_decision_record_states_the_rule():
    found = sorted((ROOT / "governance" / "decisions").glob(PATTERN))
    assert len(found) == 1, (
        f"governance/decisions holds {len(found)} files that match {PATTERN}; expected one")
    text = _normal(found[0].read_text(encoding="utf-8"))
    missing = {name: [p for p in phrases if p not in text]
               for name, phrases in STATEMENTS.items()}
    missing = {name: phrases for name, phrases in missing.items() if phrases}
    assert not missing, f"{found[0].name} lacks: {missing}"
