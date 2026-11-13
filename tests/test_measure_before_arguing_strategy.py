"""Measure before arguing is standing practice, not one issue's lesson.

When a recommendation and an instruction disagree, the cheap move is to
restate the recommendation more forcefully. Measuring the disputed quantity
instead is the practice; `governance/strategies-rationale.md` holds the
incidents that established it.

The practice is written down because it has to reach a session that has never
read this file's history.

Scenario ids: see the issue's acceptance criteria.
"""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
STRATEGIES = ROOT / "governance" / "strategies.md"

# Where a session needs the pointer. CLAUDE.md is loaded every session, and
# the review dimensions file is where the reviewer assesses the practice (the
# review method moved there from commands/ship.md with ADR-099) - the same
# two-surface pattern `S10` (mutation proof) uses.
#
# skills/receiving-code-review/SKILL.md would be the natural third home, since
# disagreeing with a reviewer is exactly its subject. It is deliberately not
# used: that file sits against a 320-word bound its own test enforces, and
# trimming its prose to make room for a cross-reference would cost more than
# the pointer is worth.
POINTER_SURFACES = (
    ("CLAUDE.md", ROOT / "CLAUDE.md"),
    ("skills/evidence-gates/review-dimensions.md",
     ROOT / "skills" / "evidence-gates" / "review-dimensions.md"),
)



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
    not break when a paragraph is re-wrapped."""
    return " ".join(text.split())


def _strategy_entry() -> str:
    """The measure-before-arguing strategy's own section.

    Found by its heading rather than by body text, so a coincidental match
    elsewhere in the file cannot grab the wrong section.
    """
    text = STRATEGIES.read_text(encoding="utf-8")
    for section in re.split(r"(?m)^### ", text)[1:]:
        heading = section.split("\n", 1)[0]
        if "measure" in heading.lower():
            return "### " + section
    return ""


def test_rr_6_strategy_states_method_and_reason():
    entry = _strategy_entry()
    assert entry, (
        "no strategy in governance/strategies.md states the "
        "measure-before-arguing practice"
    )
    flat = _flat(entry)
    lower = flat.lower()

    assert re.search(r"\bS\d+\b", entry.split("\n", 1)[0]), (
        "the heading must carry an S-number, matching the file's convention"
    )

    # Checks the method as one sentence, because each word also occurs
    # elsewhere in the entry.
    method = re.search(
        r"measure[^.]*?disputed[^.]*?report[^.]*?number[^.]*?"
        r"before[^.]*?defend",
        lower,
    )
    assert method, (
        "the strategy does not state the method as one instruction - measure "
        "the disputed quantity and report the numbers before defending "
        "either position. Scattered mentions of those words are not the "
        "method."
    )

    # The trigger, without which the rule has no moment to fire in.
    assert re.search(r"recommendation[^.]*?instruction[^.]*?disagree", lower), (
        "the strategy must name its trigger - a recommendation and an "
        "instruction that disagree"
    )

    # The reason, which is the part that makes the rule stick. The worked
    # instance lives in strategies-rationale.md beside the rule it backs.
    lower = lower + " " + _rationale_section("S11")
    assert "changed the outcome" in lower or "changed two" in lower, (
        "the strategy must say why it exists - that measuring has actually "
        "changed decisions, not that it is good practice in the abstract"
    )

    assert "*Why a strategy and not a guardrail:*" in entry, (
        "the entry must carry the file's own convention"
    )


def test_rr_6_the_operating_model_points_at_the_strategy():
    entry = _strategy_entry()
    match = re.search(r"`(S\d+)`", entry.split("\n", 1)[0])
    assert match, "test_rr_6_strategy_states_method_and_reason must pass first"
    s_number = match.group(1)

    for name, path in POINTER_SURFACES:
        assert path.is_file(), f"{name} is missing"
        text = _flat(path.read_text(encoding="utf-8"))
        assert s_number in text, (
            f"{name} does not name {s_number}, so a session that has not read "
            f"governance/strategies.md has no pointer to the practice"
        )
