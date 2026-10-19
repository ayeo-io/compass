"""The decision record that moves the legacy readers from 7.0.0 to 8.0.0
(issue `release-7-0-0-prep`).

Scenario ids: `TRC-012`, `TRC-013` and `TRC-014` in
release-7-0-0-prep/acceptance-criteria.md.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

from compass_pkg import decisions  # noqa: E402

LEDGER = ROOT / "governance" / "decisions"
NEW = LEDGER / "2026-10-19-legacy-readers-readable-until-8-0-0.md"
THREE = {
    "2026-10-06-old-route-names-readable-until-7-0-0",
    "2026-10-06-legacy-governance-readable-until-7-0-0",
    "2026-10-06-the-approach-catalogue-is-approaches",
}


def _section(text, name):
    part = text.split(f"## {name}", 1)[1]
    return part.split("\n## ", 1)[0]


def supersedes(text):
    """The entries named in a record's Supersedes section."""
    return set(re.findall(r"(\d{4}-\d{2}-\d{2}-[a-z0-9-]+)\.md", _section(text, "Supersedes")))


def test_the_new_entry_supersedes_exactly_three_entries():
    """Scenario id: `TRC-012` in release-7-0-0-prep/acceptance-criteria.md."""
    assert supersedes(NEW.read_text(encoding="utf-8")) == THREE


def test_the_decision_names_8_0_0_and_each_reader():
    """Scenario id: `TRC-013` in release-7-0-0-prep/acceptance-criteria.md."""
    decision = _section(NEW.read_text(encoding="utf-8"), "Decision")
    for phrase in ("8.0.0", "old words", "old approach names", "copied 5.x governance",
                   "generated governance views", ".compass/config.yml"):
        assert phrase in decision, phrase


def test_the_settled_list_shows_the_new_entry_and_not_the_three():
    """Scenario id: `TRC-014` in release-7-0-0-prep/acceptance-criteria.md."""
    lines = decisions.settled(str(ROOT), limit=100)
    new_slug = "legacy-readers-readable-until-8-0-0"
    assert sum(1 for line in lines if line.startswith(new_slug + ":")) == 1
    for name in THREE:
        slug = name[len("2026-10-06-"):]
        assert not any(line.startswith(slug + ":") for line in lines), slug
