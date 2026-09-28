"""The agent and skill prose state each rule the orchestrator loop adopted.

A multiagent run is carried out by agents reading these files, so a rule that
is not in the file an agent reads is not a rule. Each test reads one file,
whitespace collapsed, and looks for the wording of one rule. Rules that carry
code - the subtask record, the review package, the coaching refusal - are
tested in `test_subtask_record.py`.

Scenario id: OLH-7, in the acceptance criteria of the issue
`orchestrator-loop-hardening`.
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _text(rel):
    return " ".join((ROOT / rel).read_text(encoding="utf-8").split()).lower()


RULES = [
    ("agents/builder.md", "you never spawn a subagent"),
    ("agents/builder.md", "write your report to result.md"),
    ("agents/orchestrator.md", "hand each builder the path of its brief file, never a paste"),
    ("agents/orchestrator.md", "state the model and the budget for every dispatch"),
    ("agents/orchestrator.md", "compass issue subtask"),
    ("agents/orchestrator.md", "never tell a reviewer what not to flag"),
    ("agents/orchestrator.md", "decisions taken for the user"),
    ("agents/reviewer.md", "## acceptance"),
    ("agents/reviewer.md", "## code quality"),
    ("agents/reviewer.md", "follow_ups"),
    # One agent records each round: the orchestrator, from the report. Both
    # were told to, which would have counted each round twice.
    ("agents/reviewer.md", "the orchestrator records the round"),
    ("agents/orchestrator.md", "--head <the subtask's branch>"),
    ("agents/orchestrator.md", "matches a fixed list of phrases"),
    ("skills/worktree-multiagent/skill.md", "batches small same-shape work"),
    ("skills/worktree-multiagent/skill.md", "compass issue subtask next"),
    # Found in the rehearsal: Claude Code refuses a subagent a file named like
    # a report, so the builder's hand-back file has another name.
    ("skills/worktree-multiagent/skill.md", "result.md"),
    ("templates/verification-report.md", "decisions taken for the user"),
]


@pytest.mark.parametrize("rel, phrase", RULES,
                         ids=[f"{r.split('/')[-1]}:{p[:30]}" for r, p in RULES])
def test_olh_7_each_rule_is_where_its_agent_reads_it(rel, phrase):
    path = rel.replace("skill.md", "SKILL.md")
    assert phrase in _text(path), f"{path} does not state: {phrase!r}"


def test_olh_7_review_frequency_follows_the_assessed_risk():
    text = _text("skills/worktree-multiagent/SKILL.md")
    start = text.find("review frequency")
    assert start != -1, "the skill has no review-frequency rule"
    rule = text[start:start + 700]
    for risk in ("contained", "cross-cutting", "critical"):
        assert risk in rule, f"the review-frequency rule does not cover {risk}"


def test_olh_7_the_reviewer_keeps_the_two_answers_apart():
    text = _text("agents/reviewer.md")
    assert text.index("## acceptance") < text.index("## code quality")
    assert "separately" in text or "apart" in text


def test_olh_7_the_reviewer_is_not_told_to_record_the_round_itself():
    assert "--round pass|fail" not in _text("agents/reviewer.md")


def test_olh_7_briefs_are_written_before_the_builders_launch():
    text = _text("agents/orchestrator.md")
    assert text.index("brief file, never a paste") < text.index("launch one `builder`")
