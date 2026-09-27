"""Shared by the three eval test files' own citation guards -
`tests/test_eval_harness.py`, `tests/test_eval_judge.py` and
`tests/test_eval_scenarios.py` - so the pattern list, the matcher and the
file scan exist in one place, not three copies that can drift apart.

Two kinds of document that live only under `docs/compass/*/`, which
`.gitignore` excludes, are unopenable outside this issue: a delivery design
and a set of dated reviews. A comment, a docstring or a test name in the
eval harness, the judge, or the three files that test them must never point
a cold reader at either one - it must state the rule the document was
explaining instead. This module is not one of those five files, so it is
free to name what it bans; the five files themselves must not contain any
of these words except on a line carrying `ALLOW_MARKER`, for the rare case
where the word is needed for an ordinary reason unrelated to citing either
document.

Every pattern is a class, not a list of exact spellings the previous try
used: a section sign before a digit, the word "section" before a number,
"design" or "review" in any form (a possessive, a plural, a different
tense), "round" before a number, the bare word "brief", and "Finding"
before a number.

`CITATION_PATTERNS` is for the five files themselves - `evals/harness.py`,
`evals/judge.py` and the three test files - where "design" or "review" as a
bare word never belongs. `DATA_FILE_CITATION_PATTERNS` leaves that one out:
a scenario's own `scenario.yml` is a simulated request a session reads, and
a real request can plainly say "the usual review steps" with no citation
in it at all - only the forms nobody writes by accident (a section number,
a round number, "the brief", "Finding N") stay banned there.
"""
from __future__ import annotations

import re
from pathlib import Path

CITATION_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE) for pattern in (
        r"§\s*\d",
        r"section\s*\d",
        r"\b(?:design|review)\w*",
        r"\bround\s+\d",
        r"\bbrief\b",
        r"\bfinding\s+\d",
    )
)

DATA_FILE_CITATION_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    pattern for pattern in CITATION_PATTERNS
    if pattern.pattern != r"\b(?:design|review)\w*"
)

# A line ending with this marker is exempt from every pattern above - for
# the rare line that needs one of the banned words for an ordinary reason.
# The marker must carry the reason, so an exemption is never silent.
ALLOW_MARKER = "citation-guard-allow:"


def cited_unopenable_document(
    text: str, patterns: tuple[re.Pattern[str], ...] = CITATION_PATTERNS
) -> str | None:
    """The first of `patterns` that matches `text`, or `None` - checked
    line by line, so a line carrying `ALLOW_MARKER` is skipped whole,
    reason and all, while the rest of `text` is still checked."""
    for line in text.splitlines():
        if ALLOW_MARKER in line:
            continue
        for pattern in patterns:
            if pattern.search(line):
                return pattern.pattern
    return None


def scan_file_for_unopenable_citation(
    path: Path, patterns: tuple[re.Pattern[str], ...] = CITATION_PATTERNS
) -> str | None:
    """`cited_unopenable_document` against one file's own text on disk -
    the scan a guard test must run, not only the matcher, so a guard that
    reads the wrong file, or none at all, cannot pass by accident. `None`
    for a file that is not text, the same as a caller that never finds a
    citation."""
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None
    return cited_unopenable_document(text, patterns)


# One planted citation per form the guard must catch, built from parts so
# a guard's own source is never itself a hit. Every entry here was, at some
# point, missed by an earlier version of the guard.
PLANTED_CITATION_FORMS: tuple[str, ...] = (
    "See " + "integrated" + "-" + "review" + " for background.",
    "See " + "design" + " " + "section" + " 4 for background.",
    "See " + "integrated" + " " + "review" + " for background.",
    "See the " + "review" + " " + "round" + " 3 result.",
    "See " + "round" + " 3 " + "review" + " result.",
    "See " + "the" + " " + "brief" + " for the source scenario.",
    "the threshold " + "§" + "2.2 sets",
    "the " + "design" + "'s " + "section" + " 2.3 puts",
    "the fix for the " + "review" + "'s first blocker",
    "the " + "design" + " lists for it",
    "(" + "Finding" + " 3)",
)
