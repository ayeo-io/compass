"""This repository's CLAUDE.md holds three of the contract's four rules.

The contract (`compass-contract.md`) is the one rules file. CLAUDE.md repeats
the sign-off, staging and lint-fix rules for sessions in this repository, so a
test pins one phrase per rule in both files: a rule edited in one file and not
the other fails here.

Scenario ids: CHS-11, CHS-12 and CHS-13 (issue
`contract-handoff-and-staging-rules`).
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTRACT = ROOT / "compass-contract.md"
CLAUDE_MD = ROOT / "CLAUDE.md"

# One phrase per shared rule, present in both files.
SHARED = {
    "sign-off handoff": ("ask the person to type `/compass:approve` or "
                         "`/compass:reject`, and stop."),
    "staging": "Stage each file by its path",
    "lint fix": "A lint fix never weakens an assertion",
}

SECTION = "## Commits and sign-off"


def _flat(text):
    return " ".join(text.split())


def drift(contract_text, claude_text):
    """(file, phrase) for each shared phrase a file lacks."""
    missing = []
    for label, text in (("compass-contract.md", contract_text),
                        ("CLAUDE.md", claude_text)):
        for phrase in SHARED.values():
            if phrase not in _flat(text):
                missing.append((label, phrase))
    return missing


def _section(text):
    """The body of the `## Commits and sign-off` section, to the next `## `."""
    match = re.search(r"^## Commits and sign-off\n(.*?)(?=^## |\Z)", text,
                      re.S | re.M)
    assert match, "CLAUDE.md has no '## Commits and sign-off' section"
    return match.group(1)


def test_claude_md_has_commits_and_signoff_section():
    text = CLAUDE_MD.read_text(encoding="utf-8")
    body = _flat(_section(text))
    for phrase in SHARED.values():
        assert phrase in body, phrase
    assert ".compass/private/" in body
    assert "untracked" in body
    # A level-two heading, so it is not one of the "Three house rules", whose
    # heading counts its items.
    house = text.index("### Three house rules")
    next_section = re.search(r"^## ", text[house:], re.M).start() + house
    assert not (house < text.index(SECTION) < next_section)


def test_claude_md_omits_rule_four():
    text = CLAUDE_MD.read_text(encoding="utf-8")
    assert "Settle edge cases before scenarios" not in text


def test_shared_phrases_are_in_both_files():
    assert drift(CONTRACT.read_text(encoding="utf-8"),
                 CLAUDE_MD.read_text(encoding="utf-8")) == []


def test_shared_phrase_drift_fails():
    contract = CONTRACT.read_text(encoding="utf-8")
    claude = CLAUDE_MD.read_text(encoding="utf-8")
    for phrase in SHARED.values():
        assert drift(_flat(contract).replace(phrase, ""), claude) == [
            ("compass-contract.md", phrase)]
        assert drift(contract, _flat(claude).replace(phrase, "")) == [
            ("CLAUDE.md", phrase)]
