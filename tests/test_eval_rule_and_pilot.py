"""Changing the three most important texts needs an evaluation run, and the
pilot's results are on record.

The injected contract, the hook's refusal messages and the TDD skill are the
words a session is most likely to act on. `docs/releasing.md` makes an
evaluation run, compared with the baseline, a precondition for changing any
of them. The pilot report records what the first run found.

SPT-4 - "The releasing guide needs a run": changing any of those three
texts must fail review without an evaluation run on record, compared with
the baseline.

SPT-5 - "The pilot and one measured change are on record": the twelve-session
pilot's results, and the one wording change it justified, are published
with no placeholder left in them.
"""
from __future__ import annotations

import re
from pathlib import Path

from citation_patterns import (
    PLANTED_CITATION_FORMS,
    cited_unopenable_document,
    scan_file_for_unopenable_citation,
)

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


def test_this_file_does_not_cite_documents_outside_the_repository():
    """This file's own comments and docstrings must never point a reader at
    a document this repository does not track - see `citation_patterns.py`
    for the rule and why. No guard scanned this file before; it names its
    own scenario ids in words instead of pointing at the ignored file that
    states them."""
    hit = scan_file_for_unopenable_citation(Path(__file__))
    assert hit is None, f"{__file__} matches {hit!r}"


def test_the_citation_guard_catches_a_planted_citation():
    """A regression guard that only ever passes proves nothing - check the
    matcher against every planted form `citation_patterns.py` carries."""
    for planted in PLANTED_CITATION_FORMS:
        assert cited_unopenable_document(planted) is not None, (
            f"the guard missed a planted citation: {planted!r}"
        )


def test_the_file_scan_catches_a_planted_citation(tmp_path):
    """Not only the matcher: a planted file, read by the same
    `scan_file_for_unopenable_citation` the guard above calls."""
    for planted in PLANTED_CITATION_FORMS:
        planted_file = tmp_path / "planted.py"
        planted_file.write_text(f"# {planted}\n", encoding="utf-8")
        assert scan_file_for_unopenable_citation(planted_file) is not None
