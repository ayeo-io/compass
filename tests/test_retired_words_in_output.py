"""The CLI prints the current words where it printed retired ones.

ADR-044 retired the stage mode `full` (now `thorough`) and the stage name
`build` (now `implement`). These two outputs still printed the old words.

Scenarios: RWP-7 and RWP-8 of the issue `retired-words-in-prose-and-output`.
"""
from __future__ import annotations

import re


def test_rwp_7_a_forced_stage_names_thorough(run_cli):
    """RP-FLOOR-002 on unmapped ground. On the four-stage path (ADR-092) there are no
    stage modes, so the floor names the skill it needs and no forced stage."""
    r = run_cli("approach", "evaluate", "--verbose",
                "--assessment", "risk=cross-cutting",
                "--assessment", "familiarity=brownfield-unmapped",
                "--assessment", "size=medium",
                "--assessment", "goal=delivery")
    assert r.returncode == 0, r
    assert "(RP-FLOOR-002, floor)" in r.stdout, r.stdout
    # #360 merged the skill into `atdd`, which the check set names. The shared
    # project fixture no longer copies the frozen view, which still named
    # `behavior-mapping` (ADR-098), so the command reads the check set.
    assert "skill 'atdd' required" in r.stdout, r.stdout
    assert "forced to thorough" not in r.stdout, r.stdout
    assert "full-weight" not in r.stdout, r.stdout


def test_rwp_8_quick_fix_help_names_the_path(run_cli):
    """Since 9.0.0 `build` is a stage of the four-stage path (ADR-092), so the
    quick-fix line names the path, not the removed `implement` stage."""
    r = run_cli("--help")
    assert r.returncode == 0, r
    flat = " ".join(r.stdout.split())
    assert re.search(r"quick-fix start and finish a change of any size on the path", flat), (
        r.stdout)
    assert "implement and ship" not in flat, r.stdout
