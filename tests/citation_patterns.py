"""Shared by the three eval test files' own citation guards -
`tests/test_eval_harness.py`, `tests/test_eval_judge.py` and
`tests/test_eval_scenarios.py` - so the pattern list, the matcher and the
file scan exist in one place, not three copies that can drift apart.

A delivery design and a set of dated reviews live only under
`docs/compass/*/`, which `.gitignore` excludes: unopenable outside this
issue's own checkout. A comment or a docstring in the eval harness, the
judge, or the three files that test them must never point a cold reader at
one of those. A test's own name is not scanned - only its comments and its
docstring are (see "Only a `.py` file's own comments and docstrings" below)
- so `def test_the_fix_from_verify_security_3_md_section_4():` passes.

This guard catches four things it can name exactly, and nothing else:

- a bare, hyphenated `.md` file name - the shape a delivery document or a
  dated review takes in this project (`verify-security-2.md`,
  `integrated-review-8.md`) - that names no `.md` file this repository's
  git index tracks under that exact name. A delivery document whose name a
  tracked template shares - `acceptance-criteria.md`, `technical-design.md`,
  `delivery-approach.md`, `requirements-review.md` - passes: the base name
  is tracked, under `templates/` or `examples/`, even though this issue's
  own copy is not;
- a path naming a dated issue directory under `docs/compass/`
  (`docs/compass/2026-09-26-some-issue/`) - always ignored, per
  `.gitignore`, unlike a flat report such as `docs/compass/2026-09-26-
  eval-pilot.md`, which this pattern leaves alone;
- `§` or the word "section" directly before a digit;
- "review" or "round" directly before a digit, with a space or a hyphen
  between them (`round 5`, `round-5`, `review 3`).

It does **not** catch:

- a citation that uses none of these forms - a bare "the review found
  this", "per the audit", "the plan's second point", or a number spelled as
  a word ("section two");
- a single-word file name such as `report.md` or `PLAN.md` - built as an
  ordinary output path in most tests, but also the shape a real, untracked
  gate document elsewhere in this project can take;
- a section or round number split from its word by a line wrap
  ("the threshold in section\n2.2 sets it");
- an upper-case extension, such as `verify-security-3.MD`;
- a delivery document whose name a tracked template shares, listed above.

Those pass. A human reviewer is the check for them, the same as for any
prose a regular expression cannot safely tell apart from a citation. The
trade-off runs the other way too: `section N` and `round N` also catch
ordinary sentences that are not a citation at all - "round 2 decimal
places", "see section 3 of evals/README.md" (a tracked file), "the pull
request fixes review 2 comments". A line like this needs `ALLOW_MARKER`,
the same as a line that legitimately needs one of the banned words.

Only a `.py` file's own comments and docstrings are scanned - never its
executable code - because a realistic test fixture routinely carries a
string that merely looks like one of these forms: a dated issue path used
as sample `changed_paths` data, or `report.md` as a temporary output file,
with no citation intended either way. A `.yml` or other non-Python file is
scanned whole, since a scenario's own prose - its `prompt` field most of
all - has no code around it to separate it from.

`CITATION_PATTERNS` is the one set used for every scanned file: the eval
harness, the judge, the three test files that test them, and a scenario's
own data files alike - the same patterns for every file, rather than one
set loosened for a class of file that turns out to need it.

The five scanned files themselves must not contain a citation this module
bans, except on a line carrying `ALLOW_MARKER` with a reason after it -
for the rare case where the word is needed for an ordinary purpose
unrelated to citing either document. The reason itself is checked against
every pattern above: a reason that is itself a citation is not an ordinary
purpose, so the line is still reported rather than exempted. This module is
not one of those five files, so it is free to name what it bans.
"""
from __future__ import annotations

import ast
import io
import re
import subprocess
import tokenize
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

CITATION_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE) for pattern in (
        r"§\s*\d",
        r"\bsection\s*\d",
        r"docs/compass/\d{4}-\d{2}-\d{2}-[\w-]+/",
        r"\b(?:review|round)[\s-]+\d",
    )
)

# A bare `.md` file name with at least one hyphen - the shape every
# delivery document and dated review in this project takes
# (`verify-security-2.md`, `acceptance-criteria.md`, `integrated-
# review-8.md`) - never a single word such as `report.md` or `PLAN.md`,
# which a test can legitimately use as an ordinary path with no citation
# meant at all.
_HYPHENATED_MD_FILENAME = re.compile(r"\b[\w]+(?:-[\w]+)+\.md\b")

# A line ending with this marker, with a reason after the colon, exempts
# the line from every pattern above, unless the reason itself names an
# unopenable document - checked by `cited_unopenable_document` below,
# which is what makes this an exemption for an ordinary reason and not a
# way to carry a citation past the guard inside its own reason. Matched
# against the line with its trailing whitespace stripped, so the marker
# and its reason must be the last thing on the line, not merely present
# somewhere in it.
ALLOW_MARKER = "citation-guard-allow:"
_ALLOW_MARKER_WITH_REASON = re.compile(
    re.escape(ALLOW_MARKER) + r"\s*(?P<reason>\S.*)$"
)


@lru_cache(maxsize=1)
def _tracked_markdown_basenames() -> frozenset[str]:
    """Every `.md` file this repository's git index tracks, by its bare
    name only - read once per process with `git ls-files`, so checking one
    citation never walks the tree. Empty, rather than raising, if git
    cannot be run here - every hyphenated `.md` name then fails the check
    tracked names would otherwise pass, since none is tracked: this fails
    closed, not open. In a copy with no `.git` at all - a `git archive`
    export - the four citation scan tests then fail on names that are
    genuinely tracked in the source repository."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "*.md"], cwd=REPO_ROOT,
            capture_output=True, text=True, check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return frozenset()
    return frozenset(Path(line).name for line in result.stdout.splitlines() if line)


def _cites_a_hyphenated_md_file_this_repository_does_not_track(line: str) -> bool:
    tracked = _tracked_markdown_basenames()
    return any(name not in tracked for name in _HYPHENATED_MD_FILENAME.findall(line))


def _matched_citation(
    line: str, patterns: tuple[re.Pattern[str], ...]
) -> str | None:
    """`line` against every pattern, then the hyphenated-`.md`-file check -
    the one thing `cited_unopenable_document` reports for a line, and the
    one thing checked against a marker's own reason so a citation cannot
    hide there instead."""
    for pattern in patterns:
        if pattern.search(line):
            return pattern.pattern
    if _cites_a_hyphenated_md_file_this_repository_does_not_track(line):
        return "a hyphenated .md file name this repository does not track"
    return None


def cited_unopenable_document(
    text: str, patterns: tuple[re.Pattern[str], ...] = CITATION_PATTERNS
) -> str | None:
    """The first thing in `text` that names an unopenable document - a
    compiled pattern's own `.pattern`, or a fixed message for the
    hyphenated-`.md`-file check, which needs a lookup a regular expression
    cannot do alone - or `None`. Checked line by line, so a line carrying
    `ALLOW_MARKER` with a reason after it is skipped whole, while the rest
    of `text` is still checked - unless that reason is itself a citation,
    in which case the line is checked in full like any other, rather than
    exempted on the strength of the very thing it is citing."""
    for line in text.splitlines():
        stripped = line.rstrip()
        marker_match = _ALLOW_MARKER_WITH_REASON.search(stripped)
        if marker_match and _matched_citation(marker_match.group("reason"), patterns) is None:
            continue
        hit = _matched_citation(line, patterns)
        if hit is not None:
            return hit
    return None


def _prose_lines(path: Path, text: str) -> list[str]:
    """Every comment and every docstring in `text`, if `path` is a `.py`
    file - never its executable code, where a realistic test fixture can
    carry a string that merely looks like a path or a file name. Anything
    else - a `scenario.yml`, a seed's plain-text file - is prose with
    nothing to separate it from code, so it is returned whole. Falls back
    to the whole text for a `.py` file that does not parse, rather than
    scanning nothing."""
    if path.suffix != ".py":
        return text.splitlines()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return text.splitlines()
    lines: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            docstring = ast.get_docstring(node, clean=False)
            if docstring:
                lines.extend(docstring.splitlines())
    try:
        for token in tokenize.generate_tokens(io.StringIO(text).readline):
            if token.type == tokenize.COMMENT:
                lines.append(token.string)
    except (tokenize.TokenizeError, IndentationError, SyntaxError):
        pass
    return lines


def scan_file_for_unopenable_citation(
    path: Path, patterns: tuple[re.Pattern[str], ...] = CITATION_PATTERNS
) -> str | None:
    """`cited_unopenable_document` against `path`'s own prose - the scan a
    guard test must run, not only the matcher, so a guard that reads the
    wrong file, or none at all, cannot pass by accident. `None` for a file
    that is not text, the same as a caller that never finds a citation."""
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None
    return cited_unopenable_document("\n".join(_prose_lines(path, text)), patterns)


# One planted citation per form the guard must catch, built from parts so a
# guard's own source is never itself a hit.
PLANTED_CITATION_FORMS: tuple[str, ...] = (
    "See " + "verify" + "-" + "security" + "-" + "9" + ".md" + " for the attack.",
    "See " + "docs/compass/" + "2026-01-01-a-made-up-issue" + "/" + " for the source.",
    "the threshold " + "§" + "2.2 sets",
    "the plan's " + "section" + " 4 sets it",
    "see the " + "review" + " " + "round" + " 5 result",
    "the " + "round" + "-5 result",
    "the " + "review" + " 3 finding",
)
