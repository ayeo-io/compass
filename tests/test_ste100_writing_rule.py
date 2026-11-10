"""The contract, CLAUDE.md and AGENTS.md tell a session to write in the spirit
of ASD-STE100, name things by their Compass term, and re-pitch when a person is
lost.

Nothing mechanical reads a conversation, so these tests check that the
instruction is where every session reads it: the contract for every project,
and the Plain English section of CLAUDE.md and AGENTS.md for this repository.

Scenario ids: `STE-1`, `STE-2` and `STE-3` (issue `ste100-writing-rule`).
`STE-6`, the resident words as a target that warns, is now the hard limit in
`tests/test_resident_text.py` (#358).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CONTRACT = ROOT / "compass-contract.md"
BUDGET_TEST = ROOT / "tests" / "test_context_budget.py"
BOOTSTRAP_TEST = ROOT / "tests" / "test_session_bootstrap.py"
HEADING = "### Plain English"


def _flat(text):
    return " ".join(text.split())


def _plain_english(path):
    """The Plain English section alone, up to the next heading."""
    text = path.read_text(encoding="utf-8")
    start = text.find("\n" + HEADING + "\n")
    if start == -1:
        return ""
    body = text[start + len(HEADING) + 2:]
    end = re.search(r"^#{1,6} ", body, re.M)
    return _flat(body[: end.start()] if end else body)


def test_ste_1_the_contract_carries_the_writing_rule():
    contract = _flat(CONTRACT.read_text(encoding="utf-8"))
    # The contract reaches user projects, which have no governance/ folder of
    # this repository's, so it names the command rather than the file.
    for phrase in ("ASD-STE100", "`compass terminology`", "re-pitch"):
        assert phrase in contract, f"compass-contract.md does not say {phrase!r}"
    assert "**Write for someone with no context.**" not in contract


@pytest.mark.parametrize("name", ["CLAUDE.md", "AGENTS.md"])
def test_ste_3_the_instructions_carry_the_writing_rule(name):
    section = _plain_english(ROOT / name)
    for phrase in ("ASD-STE100", "`governance/terminology.yml`", "re-pitch"):
        assert phrase in section, (
            f"the '{HEADING}' section of {name} does not say {phrase!r}")


def _target(path, name):
    source = path.read_text(encoding="utf-8")
    return int(re.search(rf"^{name} = (\d+)$", source, re.M).group(1))


def test_ste_2_the_targets_fit_the_rule():
    """The contract with the writing rule was 2,873 characters and 442
    words. #358 cut it to 2,191 characters and 342 words, with the rule
    kept, and the targets moved down with it. A target far above the text
    would never warn and stop meaning anything. ADR-099 cut the contract to
    1,697 characters and 275 words, and the character target moved to 1,750."""
    assert _target(BUDGET_TEST, "CONTRACT_TARGET") == 1750
    assert _target(BOOTSTRAP_TEST, "CONTRACT_WORD_TARGET") == 350
