"""The decision record for what the pre-tool hook lets through.

`governance/decisions/` is the project's ledger of decisions. The rules for a
comment-only Edit and for the exempt paths are one entry there, a new file: a
merged entry never changes, so ADR-068 and ADR-069, which this change builds
on, stay as they are.

Scenario ids: see hooks-comment-only-edits-and-prose/acceptance-criteria.md.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORD = (ROOT / "governance" / "decisions"
          / "2026-10-19-a-comment-only-edit-of-code-needs-no-failing-test.md")
EARLIER = (
    "architecture/decisions/ADR-068-a-person-approves-inside-claude-code-through-"
    "an-event-the-model-cannot-raise.md",
    "architecture/decisions/ADR-069-a-person-can-delegate-approvals-to-a-named-"
    "agent-for-a-stated-time-and-scope.md",
)


def _record() -> str:
    assert RECORD.is_file(), f"{RECORD.name} does not exist"
    return " ".join(RECORD.read_text(encoding="utf-8").split())


def test_decision_record_states_the_comment_only_and_path_rules():
    """Scenario id: `TRC-054` in hooks-comment-only-edits-and-prose/acceptance-criteria.md"""
    text = _record()

    # The headings every record has.
    for heading in ("## Decided by", "## Date", "## Supersedes", "## Decision",
                    "## Why", "## Evidence"):
        assert heading in text, heading
    # The definition per language and what counts as code.
    for word in ("Python", "YAML", "syntax tree", "events", "docstring",
                 "key order", "anchor", "pragma", "shebang", "hidden character"):
        assert word in text, word
    # Why the check fails closed.
    assert "judged as before" in text and "fails closed" in text
    # Why each exempt path class is not production code, and why the others are.
    assert "evals/*/seed/" in text and "never runs it in place" in text
    for path in ("examples/", "cli/vendor/", ".github/scripts/",
                 "src/examples/", "db/seed/"):
        assert path in text, path
    assert "only ratchets up" in text
    # Shell is not covered, and the condition for adding it back.
    assert "Shell is not covered" in text
    assert "12 files" in text and "fail closed" in text
    # The record has no Supersedes target: the earlier records stay.
    assert "ADR-068" not in text.split("## Supersedes", 1)[1].split("##", 1)[0]


def test_decision_record_leaves_the_earlier_records_unchanged():
    """Scenario id: `TRC-054` in hooks-comment-only-edits-and-prose/acceptance-criteria.md"""
    for name in EARLIER:
        assert (ROOT / name).is_file(), name
    changed = subprocess.run(
        ["git", "diff", "--name-only", "HEAD", "--", *EARLIER],
        cwd=str(ROOT), capture_output=True, text=True, timeout=30)
    assert changed.returncode == 0, changed.stderr
    assert changed.stdout.split() == [], (
        f"ADR-068 or ADR-069 was edited: {changed.stdout.split()}")
