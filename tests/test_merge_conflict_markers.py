"""No merge conflict marker is left in a tracked source file.

Moved from the tests of the preset interfaces, whose other cases (the
classification of a git parent chain, the map form of `extends:` and the
reserved `preset:` key) went with the configuration layers in 9.0.0 (ADR-094).

Scenario id: `PI-6`.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_pi_6_no_merge_conflict_marker_is_left_in_the_tracked_sources():
    files = subprocess.run(["git", "ls-files", "cli", "docs", "schemas", "tests"], cwd=ROOT,
                           capture_output=True, text=True).stdout.split()
    left = []
    for name in files:
        path = ROOT / name
        if path.suffix not in (".py", ".md", ".yml", ".json") or not path.is_file():
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.startswith(("<<<<<<< ", ">>>>>>>> ")) or line == "=======":
                left.append(f"{name}:{number}")
    assert left == []
