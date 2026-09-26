"""Changing the three most important texts needs an evaluation run, and the
pilot's results are on record.

The injected contract, the hook's refusal messages and the TDD skill are the
words a session is most likely to act on. `docs/releasing.md` makes an
evaluation run, compared with the baseline, a precondition for changing any
of them. The pilot report records what the first run found.

Scenario ids: SPT-4 and SPT-5, in `acceptance-criteria.md` of issue
`skill-prose-pressure-tests`.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PILOT = ROOT / "docs" / "compass" / "2026-09-26-eval-pilot.md"


def _flat(path):
    return " ".join(path.read_text(encoding="utf-8").split())


def test_spt_4_the_releasing_guide_requires_a_run_before_changing_the_three_texts():
    text = _flat(ROOT / "docs" / "releasing.md")
    section = text[text.index("## Before changing the words sessions act on"):]
    for name in ("compass-contract.md", "hooks/pre-tool.sh",
                 "skills/tdd-discipline/SKILL.md", "evals/harness.py",
                 "evals/judge.py", "baseline"):
        assert name in section, name


def test_spt_5_the_pilot_is_on_record_with_its_limits():
    text = _flat(PILOT)
    assert "twelve sessions" in text.lower() or "12 sessions" in text
    assert "no variance" in text.lower()
    for scenario in ("skip-assessment", "skip-failing-test", "fabricate-evidence",
                     "scope-growth", "resume-after-compaction",
                     "conflicting-instruction"):
        assert scenario in text, scenario
    assert re.search(r"wording change", text, re.IGNORECASE)
    raw = PILOT.read_text(encoding="utf-8")
    for placeholder in ("TODO", "TBD", "{{"):
        assert placeholder not in raw, placeholder
