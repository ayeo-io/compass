"""Both instruction files tell an agent to name an issue by its GitHub number.

An internal row id means nothing to a person reading a report or a table, so
the rule must be where every runtime reads it: `AGENTS.md` for runtimes other
than Claude Code, and `CLAUDE.md` for Claude Code.

The quick fix that added the rule has one scenario, `TRC-001`, which this
file checks.
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _prose(path: Path) -> str:
    """File text with the hard wrapping collapsed, so a phrase can span lines."""
    return " ".join(path.read_text(encoding="utf-8").split())


@pytest.mark.parametrize("name", ["AGENTS.md", "CLAUDE.md"])
def test_trc_001_issue_reference_rule_is_in_the_instructions(name):
    """`TRC-001`: the file states the issue-number rule and its two formats."""
    prose = _prose(REPO_ROOT / name)
    for phrase in ("GitHub issue number", "`#N [title]`",
                   "`owner/repo#N [title]`", "row id"):
        assert phrase in prose, f"{name} does not state {phrase!r}"
