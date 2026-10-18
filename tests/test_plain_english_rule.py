"""CLAUDE.md and AGENTS.md tell a session to write plain English.

Nothing mechanical reads a conversation, so what is checked here is the
instruction, not the writing. A session can have this rule in front of it and
still write "low-hanging fruit". These tests establish only that the rule is
where every session in this repository reads it: CLAUDE.md for Claude Code,
AGENTS.md for any other runtime.

Each test reads the "Plain English" section alone, up to the next heading. A
word such as "idiom" appearing somewhere else in the file must not satisfy it.

Scenario ids:
- PE-1, in claude-md-plain-english/delivery-approach.md
- PFR-1, in plain-english-full-rules/delivery-approach.md
- `STE-4`, in ste100-writing-rule/acceptance-criteria.md: the section names
  ASD-STE100 and drops the rules the standard states directly, such as the
  active voice
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CLAUDE_MD = ROOT / "CLAUDE.md"
AGENTS_MD = ROOT / "AGENTS.md"
HEADING = "### Plain English"

# Each entry is one rule and a phrase that only that rule's wording contains.
# The shorter-word table is checked by two of its rows, not by its heading, so
# a heading with no table under it fails.
FULL_RULES = {
    "lead with the point": "lead with the point",
    "the ASD-STE100 standard": "ASD-STE100",
    "the ban on idiom": "idiom",
    "the ban on metaphor": "metaphor",
    "saying what happens instead": "say what happens",
    "the rule for must, can and do not": '"must" for a requirement',
    "the shorter-word table, utilise row": "utilise",
    "the shorter-word table, in order to row": "in order to",
    "the artifact exception to British English": '"artifact"',
}


def _section(path: Path = CLAUDE_MD) -> str:
    """The section's text with whitespace collapsed, or "" when it is absent.

    The prose is hard-wrapped, so a phrase often straddles a line break.
    Collapsing whitespace keeps every word and its order.
    """
    text = path.read_text(encoding="utf-8")
    start = text.find("\n" + HEADING + "\n")
    if start == -1:
        return ""
    body = text[start + len(HEADING) + 2:]
    end = re.search(r"^#{1,6} ", body, re.M)
    return " ".join((body[: end.start()] if end else body).split())


def test_pe_1_claude_md_has_a_plain_english_section():
    assert _section(), f"CLAUDE.md has no '{HEADING}' section with text under it"


def test_pe_1_the_section_bans_idiom_and_metaphor():
    section = _section().lower()
    missing = [w for w in ("idiom", "metaphor", "say what happens") if w not in section]
    assert not missing, (
        f"the '{HEADING}' section does not say: {', '.join(missing)}. It must ban "
        "idiom and metaphor and tell the writer to state what happens instead.")


def test_pe_1_the_section_says_lead_with_the_point():
    section = _section().lower()
    missing = [w for w in ("lead with the point", "asd-ste100") if w not in section]
    assert not missing, f"the '{HEADING}' section does not say: {', '.join(missing)}"


@pytest.mark.parametrize("path", [CLAUDE_MD, AGENTS_MD], ids=lambda p: p.name)
def test_pfr_1_the_file_has_a_plain_english_section(path):
    assert _section(path), f"{path.name} has no '{HEADING}' section with text under it"


@pytest.mark.parametrize("path", [CLAUDE_MD, AGENTS_MD], ids=lambda p: p.name)
def test_pfr_1_the_section_carries_the_full_rules(path):
    section = _section(path).lower()
    missing = [rule for rule, phrase in FULL_RULES.items() if phrase.lower() not in section]
    assert not missing, (
        f"the '{HEADING}' section of {path.name} is missing: {'; '.join(missing)}")
