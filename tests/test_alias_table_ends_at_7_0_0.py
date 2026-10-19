"""The alias table ends at 7.0.0 (release-7-0-0-prep, scenario group A).

The table in `cli/aliases.yml` holds no alias row and the two hint rows for
released verbs that 7.0.0 removed. The version check reports a planted row, so
the empty table is proved by a check that can fail.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))


def _table():
    from compass_pkg import aliases
    return aliases.load_table()


def test_the_alias_list_is_empty():
    """Scenario id: `TRC-001` in release-7-0-0-prep/acceptance-criteria.md"""
    assert _table()["aliases"] == []


def test_the_hint_rows_are_the_two_removed_released_verbs():
    """Scenario id: `TRC-002` in release-7-0-0-prep/acceptance-criteria.md"""
    hints = _table()["hints"]
    # Token lists, because a test file may not spell the removed verb as one phrase.
    assert sorted(row["old"] for row in hints) == [
        ["issue", "dashboard"], ["issue", "labels", "sync"]]
    for row in hints:
        assert row.get("released_in") and row.get("removed_in") == "7.0.0", row


def test_the_real_table_has_no_removal_problem_at_7_0_0():
    """Scenario id: `TRC-003` in release-7-0-0-prep/acceptance-criteria.md"""
    from compass_pkg import aliases
    assert aliases.removal_problems("7.0.0", _table()) == []


def test_a_planted_alias_row_is_reported():
    """Scenario id: `TRC-004` in release-7-0-0-prep/acceptance-criteria.md"""
    from compass_pkg import aliases
    planted = {"aliases": [{"old": ["frob", "nicate"], "new": ["frob", "set"],
                            "kind": "verb", "released_in": "v5.6.0"}],
               "hints": []}
    problems = aliases.removal_problems("7.0.0", planted)
    assert len(problems) == 1 and "frob nicate" in problems[0], problems
    # Before 7.0.0 the same row is allowed, so the check reads the version.
    assert aliases.removal_problems("6.9.9", planted) == []


def test_a_planted_hint_row_without_removed_in_is_reported():
    """Scenario id: `TRC-005` in release-7-0-0-prep/acceptance-criteria.md"""
    from compass_pkg import aliases
    planted = {"aliases": [], "hints": [{"old": ["frob", "nicate"],
                                         "new": ["frob", "set"]}]}
    problems = aliases.removal_problems("7.0.0", planted)
    assert len(problems) == 1 and "frob nicate" in problems[0], problems
