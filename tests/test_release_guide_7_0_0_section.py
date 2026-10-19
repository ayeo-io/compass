"""docs/releasing.md has a "What changed at 7.0.0" section (issue
`release-7-0-0-prep`).

Scenario ids: `TRC-019` to `TRC-024` in release-7-0-0-prep/acceptance-criteria.md.
Each check takes the text it reads, so a planted guide can show it fails.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HEADING = "### What changed at 7.0.0"
NEXT_HEADING = "### What changed at 6.0.0"

# Each removed spelling beside its new one, as the guide writes the pair.
PAIRS = [
    ("`approach summary`", "`approach show`"),
    ("`issue set-status`", "`issue status set`"),
    ("`policy review-rules`", "`review-rule list`"),
    ("`issue dashboard`", "`issue render`"),
    ("`issue artifact`", "`issue artifact set`"),
    ("`migrate`", "`issue migrate`"),
    ("`issue subtask update`", "`issue subtask set`"),
    ("`run --stage build`", "`run --stage implement`"),
]


def guide():
    return (ROOT / "docs" / "releasing.md").read_text(encoding="utf-8")


def section(text):
    """The text of the 7.0.0 section, or "" when the guide has none."""
    if HEADING not in text:
        return ""
    return text.split(HEADING, 1)[1].split(NEXT_HEADING, 1)[0]


def problems_with_heading(text):
    headings = [line for line in text.splitlines() if line.startswith("### ")]
    found = [i for i, line in enumerate(headings) if line == HEADING]
    wanted = [i for i, line in enumerate(headings) if line == NEXT_HEADING]
    if len(found) != 1 or not wanted or found[0] > wanted[0]:
        return [f"{len(found)} heading(s) {HEADING!r}, or not before {NEXT_HEADING!r}"]
    return []


def problems_with_removals(text):
    body = section(text)
    missing = [old for old, new in PAIRS
               if not any(old in line and new in line for line in body.splitlines())]
    if "removed" not in body:
        missing.append("the word removed")
    return missing


def problems_with_kept_readers(text):
    body = re.sub(r"\s+", " ", section(text))
    return [p for p in ("old words", "old approach names", "copied 5.x governance",
                        ".compass/config.yml", "8.0.0") if p not in body]


def problems_with_upgrade_steps(text):
    body = section(text)
    return [p for p in ("compass issue migrate", "compass policy migrate --words",
                        "compass policy update", "--i-have-a-copy") if p not in body]


def problems_with_rollback(text):
    body = re.sub(r"\s+", " ", section(text))
    return [p for p in ("no supported rollback", "the copy of the two issue folders",
                        "`.compass/work`", "`docs/compass`",
                        "Do not run a 6.x CLI on a 7.0.0 tree") if p not in body]


def test_the_guide_has_a_what_changed_at_7_0_0_section():
    """Scenario id: `TRC-019` in release-7-0-0-prep/acceptance-criteria.md."""
    assert problems_with_heading(guide()) == []


def test_the_section_names_each_removed_spelling():
    """Scenario id: `TRC-020` in release-7-0-0-prep/acceptance-criteria.md."""
    assert problems_with_removals(guide()) == []
    assert "| `run --stage build` | `run --stage implement` |" in section(guide())


def test_the_section_names_each_reader_kept_until_8_0_0():
    """Scenario id: `TRC-021` in release-7-0-0-prep/acceptance-criteria.md."""
    assert problems_with_kept_readers(guide()) == []


def test_the_section_gives_the_migrate_commands():
    """Scenario id: `TRC-022` in release-7-0-0-prep/acceptance-criteria.md."""
    assert problems_with_upgrade_steps(guide()) == []


def test_the_section_says_there_is_no_supported_rollback():
    """Scenario id: `TRC-023` in release-7-0-0-prep/acceptance-criteria.md."""
    assert problems_with_rollback(guide()) == []


def test_the_owed_tool_sentence_is_gone():
    """Scenario id: `TRC-024` in release-7-0-0-prep/acceptance-criteria.md."""
    assert "is owed before 7.0.0" not in guide()


def test_a_planted_guide_with_a_gap_is_reported():
    """Each check reports a planted fault, so none of them passes on its own."""
    planted = f"{HEADING}\n\nThe spelling `approach summary` is `approach show`.\n\n{NEXT_HEADING}\n"
    assert problems_with_heading(planted) == []
    assert "`migrate`" in problems_with_removals(planted)
    assert problems_with_kept_readers(planted)
    assert problems_with_upgrade_steps(planted)
    assert problems_with_rollback(planted)
    assert problems_with_heading(f"{NEXT_HEADING}\n\n{HEADING}\n")
    assert problems_with_heading("### Something else\n")
