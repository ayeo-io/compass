"""The draft release notes for 7.0.0 name each removal, name only verbs that
exist and give the upgrade steps (issue `release-7-0-0-prep`).

Scenario ids: `TRC-029`, `TRC-030` and `TRC-031` in
release-7-0-0-prep/acceptance-criteria.md.

The draft is an untracked issue document, so the tests that read it skip in a
clean clone. The planted-draft test always runs, so the check can fail.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
DRAFT = ROOT / "docs" / "compass" / "2026-10-19-release-7-0-0-prep" / "release-notes.md"

PAIRS = [
    ("approach summary", "approach show"),
    ("issue set-status", "issue status set"),
    ("policy review-rules", "review-rule list"),
    ("issue dashboard", "issue render"),
    ("issue artifact", "issue artifact set"),
    ("migrate", "issue migrate"),
    ("issue subtask update", "issue subtask set"),
    ("run --stage build", "run --stage implement"),
]

needs_draft = pytest.mark.skipif(not DRAFT.is_file(), reason="the draft is not in this checkout")


def removals_missing(text):
    """The old spellings with no line that holds the old and the new spelling."""
    lines = text.splitlines()
    return [old for old, new in PAIRS
            if not any(f"`{old}`" in line and f"`{new}`" in line for line in lines)]


def named_verbs(text):
    """Each `compass <verb>` the text names in backticks: the words up to the
    first one that starts with `-` or `<`."""
    found = []
    for span in re.findall(r"`(compass [^`]+)`", text):
        words = []
        for word in span.split()[1:]:
            if word.startswith(("-", "<")):
                break
            words.append(word)
        if words and words not in found:
            found.append(words)
    return found


def upgrade_section(text):
    parts = text.split("\n## Upgrade\n", 1)
    return parts[1].split("\n## ", 1)[0] if len(parts) == 2 else ""


def upgrade_problems(text):
    body = re.sub(r"\s+", " ", upgrade_section(text))
    return [p for p in ("`.compass/work`", "`docs/compass`", "compass issue migrate",
                        "compass policy migrate --words") if p not in body]


@needs_draft
def test_the_draft_names_each_removed_spelling():
    """Scenario id: `TRC-029` in release-7-0-0-prep/acceptance-criteria.md."""
    assert removals_missing(DRAFT.read_text(encoding="utf-8")) == []


def test_a_planted_draft_missing_a_removal_is_reported():
    """Scenario id: `TRC-029` in release-7-0-0-prep/acceptance-criteria.md."""
    full = "\n".join(f"| `{old}` | `{new}` |" for old, new in PAIRS)
    assert removals_missing(full) == []
    without = "\n".join(line for line in full.splitlines() if "`issue subtask update`" not in line)
    assert removals_missing(without) == ["issue subtask update"]
    assert upgrade_problems("## Upgrade\n\nRun it.\n")
    assert named_verbs("run `compass issue migrate --apply` and `compass check`") == [
        ["issue", "migrate"], ["check"]]


def verbs_that_fail_help(verbs):
    env = dict(os.environ, COMPASS_OFFLINE="1")
    failed = []
    for words in verbs:
        result = subprocess.run([sys.executable, str(CLI), *words, "--help"], cwd=str(ROOT),
                                capture_output=True, text=True, env=env, timeout=60)
        if result.returncode != 0:
            failed.append(" ".join(words))
    return failed


@needs_draft
def test_every_verb_the_draft_names_runs_with_help():
    """Scenario id: `TRC-030` in release-7-0-0-prep/acceptance-criteria.md."""
    verbs = named_verbs(DRAFT.read_text(encoding="utf-8"))
    assert verbs
    assert verbs_that_fail_help(verbs) == []


def test_a_planted_unknown_verb_fails_help():
    """Scenario id: `TRC-030` in release-7-0-0-prep/acceptance-criteria.md."""
    verbs = named_verbs("run `compass issue migrate` then `compass issue nosuchverb`")
    assert verbs_that_fail_help(verbs) == ["issue nosuchverb"]


@needs_draft
def test_the_draft_gives_the_upgrade_steps():
    """Scenario id: `TRC-031` in release-7-0-0-prep/acceptance-criteria.md."""
    assert upgrade_problems(DRAFT.read_text(encoding="utf-8")) == []
