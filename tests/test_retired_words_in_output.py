"""The CLI prints the current words where it printed retired ones.

ADR-044 retired the stage mode `full` (now `thorough`) and the stage name
`build` (now `implement`). These two outputs still printed the old words.

Scenarios: RWP-7 and RWP-8 of the issue `retired-words-in-prose-and-output`.
"""
from __future__ import annotations

import re


def test_rwp_7_a_forced_stage_names_thorough(run_cli):
    """RP-FLOOR-002 forces the define stage on unmapped ground."""
    r = run_cli("approach", "evaluate", "--verbose",
                "--assessment", "risk=cross-cutting",
                "--assessment", "familiarity=brownfield-unmapped",
                "--assessment", "size=medium",
                "--assessment", "goal=delivery")
    assert r.returncode == 0, r
    assert "stage 'define' forced to thorough" in r.stdout, r.stdout
    assert "full-weight" not in r.stdout, r.stdout


def test_rwp_8_quick_fix_help_names_implement(run_cli):
    r = run_cli("--help")
    assert r.returncode == 0, r
    flat = " ".join(r.stdout.split())
    assert re.search(r"quick-fix assess, implement and ship a quick fix", flat), (
        r.stdout)
    assert "build and ship" not in flat, r.stdout
