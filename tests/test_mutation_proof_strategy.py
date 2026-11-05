"""Mutation proof is standing practice, not this cycle's habit.

A passing test proves the guard runs. It does not prove the guard is
connected to the thing it names. `governance/strategies-rationale.md` holds
the incident that established the practice.

Scenario ids: see the issue's acceptance criteria.
"""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
STRATEGIES = ROOT / "governance" / "strategies.md"
VERIFY_COMMAND = ROOT / "commands" / "verify.md"
EVIDENCE_GATES_DIR = ROOT / "skills" / "evidence-gates"


class _SkillDir:
    """Reads SKILL.md and its sibling files, because the long skills are
    split and a guard reading only SKILL.md reports content missing when it
    has moved to a sibling file."""

    def __init__(self, d):
        self._d = d

    def read_text(self, *a, **k):
        return "\n".join(sorted(
            p.read_text(encoding="utf-8") for p in self._d.glob("*.md")))


EVIDENCE_GATES = _SkillDir(EVIDENCE_GATES_DIR)



def _rationale_section(s_number: str) -> str:
    """The rationale file's section for one strategy, isolated from the rest.

    `governance/strategies.md` states the rules; the incidents and worked
    examples that justify them are in `governance/strategies-rationale.md`,
    one `## ...(`Sn`)` section each. Both halves are needed - a rule with no
    incident behind it is an assertion.

    Scoped to the one section on purpose. Searching the whole file would let a
    phrase in an unrelated strategy's evidence satisfy this one, which is the
    same loose-match failure these guards exist to catch.
    """
    text = (ROOT / "governance" / "strategies-rationale.md").read_text(
        encoding="utf-8")
    for sec in re.split(r"(?m)^## ", text)[1:]:
        if "`%s`" % s_number in sec.split("\n", 1)[0]:
            return _flat(sec).lower()
    return ""

def _flat(text: str) -> str:
    """Whitespace-collapsed, so an assertion about what the prose says does
    not break when a paragraph is re-wrapped. Three assertions in this
    repository have broken that way already."""
    return " ".join(text.split())


def _strategy_entry() -> str:
    """The mutation-proof strategy's own section.

    Found by its heading rather than by body text, so a coincidental match
    elsewhere in the file cannot grab the wrong section.
    """
    text = STRATEGIES.read_text(encoding="utf-8")
    for section in re.split(r"(?m)^### ", text)[1:]:
        heading = section.split("\n", 1)[0]
        if "mutation" in heading.lower():
            return "### " + section
    return ""


def test_trc_1_the_strategy_states_the_method_and_the_reason():
    entry = _strategy_entry()
    assert entry, (
        "no strategy in governance/strategies.md states the mutation-proof "
        "practice"
    )
    flat = _flat(entry).lower()

    assert re.search(r"\bS\d+\b", entry.split("\n", 1)[0]), (
        "the heading must carry an S-number, matching the file's convention"
    )

    # The four steps must be one sentence, because each word also occurs
    # elsewhere in the entry.
    method = re.search(
        r"break[^.]*?\bred\b[^.]*?restore[^.]*?\bgreen\b[^.]*?record",
        flat,
    )
    assert method, (
        "the strategy does not state the method as one instruction - break "
        "the subject, watch it go red, restore, watch it go green, record "
        "the result. Scattered mentions of those words are not the method."
    )

    # The reason, which is the part that makes the rule stick. It sits in
    # strategies-rationale.md, next to the rule it backs.
    flat = flat + " " + _rationale_section("S10")
    # Asserts the proposition, because "passing test" also occurs in the
    # 2.1.0 count.
    assert re.search(r"passing test proves[^.]*runs\.\s*it does not prove[^.]*"
                     r"connected", flat), (
        "the strategy must say what a passing test does and does not prove - "
        "that it shows the guard runs, not that it is connected to the thing "
        "it names"
    )
    assert "record" in flat, (
        "the strategy must require the result to be recorded, not just done"
    )

    assert "*Why a strategy and not a guardrail:*" in entry, (
        "the entry must carry the file's own convention"
    )


def test_trc_2_the_verify_guidance_points_at_the_strategy():
    entry = _strategy_entry()
    match = re.search(r"`(S\d+)`", entry.split("\n", 1)[0])
    assert match, "TRC-1 must land before this scenario can"
    s_number = match.group(1)

    for name, path in (("commands/verify.md", VERIFY_COMMAND),
                       ("skills/evidence-gates/SKILL.md", EVIDENCE_GATES)):
        text = _flat(path.read_text(encoding="utf-8"))
        assert s_number in text, (
            f"{name} does not name {s_number}, so a reviewer at the verify "
            f"stage has no pointer to the practice"
        )
