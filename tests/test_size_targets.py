"""The size limits on the contract and the Writing voice section are targets.

A file over its target passes the test and pytest prints a warning naming the
file, its size and the target. Each test below lowers one target to 1 and
runs the real size test, which must warn and not fail.

Scenario id: TRC-001 (issue `size-caps-as-targets`).
"""
from __future__ import annotations

import pytest

import test_context_budget
import test_human_voice
import test_prompt_layer
import test_session_bootstrap
from size_targets import OverTarget


def test_contract_characters_over_target_warns(monkeypatch):
    monkeypatch.setattr(test_context_budget, "CONTRACT_TARGET", 1)
    with pytest.warns(OverTarget, match=r"compass-contract\.md is \d+ characters, over its target of 1"):
        test_context_budget.test_tc_1_the_contract_keeps_every_rule_within_its_budget()


def test_contract_words_over_bootstrap_target_warns(monkeypatch):
    monkeypatch.setattr(test_session_bootstrap, "CONTRACT_WORD_TARGET", 1)
    with pytest.warns(OverTarget, match=r"compass-contract\.md is \d+ words, over its target of 1"):
        test_session_bootstrap.test_sb_a2_the_contract_is_short_enough_to_always_carry()


def test_contract_words_over_prompt_layer_target_warns(monkeypatch):
    monkeypatch.setattr(test_prompt_layer, "CONTRACT_WORD_TARGET", 1)
    with pytest.warns(OverTarget, match=r"compass-contract\.md is \d+ words, over its target of 1"):
        test_prompt_layer.test_trc_f5_the_contract_is_measured_separately_and_reported()


def test_writing_voice_over_target_warns(monkeypatch):
    monkeypatch.setattr(test_human_voice, "VOICE_WORD_TARGET", 1)
    with pytest.warns(OverTarget) as caught:
        test_human_voice.test_trc_b1_claude_md_and_agents_md_carry_the_voice_paragraph()
    messages = [str(w.message) for w in caught]
    for name in ("CLAUDE.md", "AGENTS.md"):
        assert any(m.startswith(f"{name}'s Writing voice section is ")
                   and "over its target of 1 words" in m
                   for m in messages), (name, messages)
