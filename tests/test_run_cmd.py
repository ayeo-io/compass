"""What an unattended `compass run` session is told.

Scenario id: CHS-14 (issue `contract-handoff-and-staging-rules`).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

from compass_pkg import run_cmd  # noqa: E402


def test_prompt_has_approval_sentence():
    prompt = run_cmd._prompt("implement", "some-issue")
    assert ("If a step needs a person's approval, record nothing, end with "
            "the exact command they must run, and stop.") in prompt
