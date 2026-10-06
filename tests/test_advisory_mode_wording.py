"""The config template says what advisory mode changes, and no more.

Advisory mode keeps `compass ci` and `compass check` from failing, so a team
can pilot Compass without blocking pull requests. The pre-tool hook does not
read the mode: it still refuses a code edit with no failing test on record,
because a failing test before code is a guardrail. The template `compass
init` writes said advisory mode meant "nothing blocks", which a person
piloting Compass would read as the hook standing aside too.

Scenario id: `TRC-001` (issue `advisory-mode-wording`).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"


def test_trc_001_the_template_says_the_hook_still_enforces(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    done = subprocess.run([sys.executable, str(CLI), "init"], cwd=tmp_path,
                          capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    text = (tmp_path / ".compass" / "config.yml").read_text(encoding="utf-8")
    comment = text.split("mode: enforced", 1)[0]
    assert "nothing blocks" not in comment
    assert "pre-tool hook" in comment and "still" in comment, comment
