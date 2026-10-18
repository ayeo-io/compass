"""The contract, CLAUDE.md and AGENTS.md tell a session to write in the spirit
of ASD-STE100, name things by their Compass term, and re-pitch when a person is
lost.

Nothing mechanical reads a conversation, so these tests check that the
instruction is where every session reads it: the contract for every project,
and the Plain English section of CLAUDE.md and AGENTS.md for this repository.

Scenario ids: `STE-1`, `STE-2`, `STE-3` and `STE-6` (issue `ste100-writing-rule`).
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
    """The contract with the writing rule is 2,873 characters and 442
    words. Targets it always exceeded would warn on every run and stop
    meaning anything, so they move to fit it."""
    assert _target(BUDGET_TEST, "CONTRACT_TARGET") == 2900
    assert _target(BOOTSTRAP_TEST, "CONTRACT_WORD_TARGET") == 450


def test_ste_6_resident_words_over_target_warns(monkeypatch):
    """The words every session keeps loaded - skill, command and agent
    descriptions plus the contract - are a target like the contract's own
    size: over it, the test passes and pytest warns."""
    import test_instruction_volume as volume
    from size_targets import OverTarget
    monkeypatch.setattr(volume, "RESIDENT_TARGET", 1)
    with pytest.warns(OverTarget, match=r"The resident text \(.*\) is \d+ words, over its target of 1 words"):
        volume.test_iv_a1_resident_cost_is_bounded()
