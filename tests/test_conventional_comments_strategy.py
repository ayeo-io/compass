"""Review comments carry a plain-word label.

A review thread where "this will crash on an empty list" and "I'd have named
this differently" look identical costs the author a decision they should not
have to make: which of these blocks the merge. The convention answers it in
one word at the front of the comment.

Adopted as a SHIPPED DEFAULT rather than a project preference, on two
grounds. It serves the review gate, which is the centre of the pipeline. And
the labels are ordinary English - issue, suggestion, nitpick, question,
praise - so an adopting team inherits no jargon with them.

Scenario ids: see the issue's acceptance criteria.
"""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
STRATEGIES = ROOT / "governance" / "strategies.md"

# The labels themselves. A strategy that named three of them would leave an
# author guessing at the rest.
LABELS = ("issue", "suggestion", "nitpick", "question", "praise")

# Where a session needs the pointer: the command whose review writes the
# comments (the reviewer agent until 9.0.0, ADR-090), and the skill for the
# person answering them.
POINTER_SURFACES = (
    ("commands/ship.md", ROOT / "commands" / "ship.md"),
    ("skills/receiving-code-review/SKILL.md",
     ROOT / "skills" / "receiving-code-review" / "SKILL.md"),
)


def _flat(text: str) -> str:
    return " ".join(text.split())


def _strategy_entry() -> str:
    """Found by heading, so a coincidental match elsewhere cannot be taken
    for the entry."""
    text = STRATEGIES.read_text(encoding="utf-8")
    for section in re.split(r"(?m)^### ", text)[1:]:
        heading = section.split("\n", 1)[0]
        if "comment" in heading.lower() and "review" in heading.lower():
            return "### " + section
    return ""


def test_the_strategy_names_every_label_and_the_reason():
    entry = _strategy_entry()
    assert entry, (
        "no strategy in governance/strategies.md states the review-comment "
        "labelling convention"
    )
    flat = _flat(entry)
    lower = flat.lower()

    assert re.search(r"\bS\d+\b", entry.split("\n", 1)[0]), (
        "the heading must carry an S-number, matching the file's convention"
    )

    # Each label must be DEFINED - a bullet that names it and says what it
    # means - not merely mentioned somewhere in the prose. Checking for the
    # bare word passes while the definition list is being deleted: the entry
    # discusses nitpicks and blocking in its rationale, so "nitpick" and
    # "issue" survive the removal of their own bullets.
    undefined = [
        w for w in LABELS
        if not re.search(rf"^\s*[-*]\s+\*\*{w}\*\*\s*-\s*\S", entry,
                         re.MULTILINE | re.IGNORECASE)
    ]
    assert not undefined, (
        f"the strategy does not DEFINE every label - missing a bullet for "
        f"{undefined}. A partial list leaves an author guessing at the rest, "
        f"which is the ambiguity the convention exists to remove."
    )

    # The reason, in one instruction rather than three scattered words: the
    # label makes blocking and non-blocking distinguishable at a glance.
    assert re.search(r"block[^.]*?(?:non-block|not block)|"
                     r"(?:non-block|not block)[^.]*?block", lower), (
        "the strategy does not say what the label is FOR - telling a blocking "
        "comment from a non-blocking one without reading the whole thread"
    )

    assert "*Why a strategy and not a guardrail:*" in entry, (
        "the entry must carry the file's own convention"
    )


def test_the_reviewer_and_the_receiver_both_point_at_it():
    entry = _strategy_entry()
    match = re.search(r"`(S\d+)`", entry.split("\n", 1)[0])
    assert match, "test_the_strategy_names_every_label_and_the_reason must pass first"
    s_number = match.group(1)

    for name, path in POINTER_SURFACES:
        assert path.is_file(), f"{name} is missing"
        text = _flat(path.read_text(encoding="utf-8"))
        assert s_number in text, (
            f"{name} does not name {s_number}. The convention needs both "
            f"ends: the agent writing the comments and the person answering "
            f"them."
        )
