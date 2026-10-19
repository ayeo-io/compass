"""The 6.0.0 and 7.0.0 upgrade guides state what 7.0.0 removed and what stays
until 8.0.0 (issue `release-7-0-0-prep`).

Scenario ids: `TRC-025` to `TRC-028` in release-7-0-0-prep/acceptance-criteria.md.
Each check takes the text it reads, so a planted guide can show it fails.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"

# Each removed spelling and its new one, as a table row of the 7.0.0 guide.
ROWS = [
    ("approach summary", "approach show"),
    ("issue set-status", "issue status set"),
    ("policy review-rules", "review-rule list"),
    ("issue dashboard", "issue render"),
    ("issue artifact", "issue artifact set"),
    ("migrate", "issue migrate"),
    ("issue subtask update", "issue subtask set"),
    ("run --stage build", "run --stage implement"),
]
READERS = ("old words", "old approach names", "copied 5.x governance", ".compass/config.yml")


def read(name):
    return (ROOT / "docs" / name).read_text(encoding="utf-8")


def removed_sections(text):
    """The text under each `### What is removed` heading of the 7.0.0 guide."""
    parts = re.split(r"^### What is removed\n", text, flags=re.M)[1:]
    return [re.split(r"^#{2,3} ", part, maxsplit=1, flags=re.M)[0] for part in parts]


def missing_rows(text):
    body = "\n".join(removed_sections(text))
    return [old for old, new in ROWS
            if f"| `{old}` | `{new}`" not in body]


def kept_readers_problems(text):
    """The section before "Artifact status and decisions taken" must say the readers stay."""
    marker = "## Artifact status and decisions taken"
    if marker not in text:
        return ["the guide has no 'Artifact status and decisions taken' section"]
    before = re.sub(r"\s+", " ", text.split(marker, 1)[0])
    return [p for p in READERS + ("until 8.0.0",) if p not in before]


def guide_6_commands_problems(text):
    body = text.split("## Commands", 1)[1].split("\n## ", 1)[0]
    body = re.sub(r"\s+", " ", body)
    return [p for p in ("removed at 7.0.0", "docs/upgrade-7-0-0.md") if p not in body]


def guide_6_dates_problems(text):
    opening = text.split("\n## ", 1)[0]
    config_line = next(line for line in text.splitlines()
                       if line.startswith("- Configuration files"))
    return [name for name, part in (("opening paragraph", opening),
                                    ("configuration-files line", config_line))
            if "until 8.0.0" not in part or "until 7.0.0" in part]


def test_the_7_0_0_guide_lists_each_removed_spelling_with_its_new_one():
    """Scenario id: `TRC-025` in release-7-0-0-prep/acceptance-criteria.md."""
    text = read("upgrade-7-0-0.md")
    assert missing_rows(text) == []
    env = dict(os.environ, COMPASS_OFFLINE="1")
    for _, new in ROWS:
        words = []
        for word in new.split():
            if word.startswith("-"):
                break
            words.append(word)
        if new.startswith("run "):
            words = ["run"]       # `--stage implement` is a flag of `run`
        result = subprocess.run([sys.executable, str(CLI), *words, "--help"], cwd=str(ROOT),
                                capture_output=True, text=True, env=env, timeout=60)
        assert result.returncode == 0, (new, result.stderr)


def test_the_7_0_0_guide_says_the_readers_stay_until_8_0_0():
    """Scenario id: `TRC-026` in release-7-0-0-prep/acceptance-criteria.md."""
    assert kept_readers_problems(read("upgrade-7-0-0.md")) == []


def test_the_6_0_0_guide_says_the_aliases_were_removed_at_7_0_0():
    """Scenario id: `TRC-027` in release-7-0-0-prep/acceptance-criteria.md."""
    assert guide_6_commands_problems(read("upgrade-6-0-0.md")) == []


def test_the_6_0_0_guide_says_the_readers_stay_until_8_0_0():
    """Scenario id: `TRC-028` in release-7-0-0-prep/acceptance-criteria.md."""
    assert guide_6_dates_problems(read("upgrade-6-0-0.md")) == []


def test_a_planted_guide_with_a_gap_is_reported():
    """Each check reports a planted fault, so none of them passes on its own."""
    planted = ("# Upgrading\n\n## Artifact status and decisions taken\n\n### What is removed\n\n"
               "| `approach summary` | `approach show` |\n")
    assert "migrate" in missing_rows(planted)
    assert missing_rows("") == [old for old, _ in ROWS]
    assert kept_readers_problems(planted)
    assert kept_readers_problems("no sections")
    assert guide_6_commands_problems("## Commands\n\nThey keep working until 7.0.0.\n")
    assert guide_6_dates_problems(
        "This page says old forms are read until 7.0.0.\n\n## Words\n\n"
        "- Configuration files are read until 7.0.0.\n")
