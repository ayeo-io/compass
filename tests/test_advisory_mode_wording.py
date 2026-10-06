"""The settings reference says what advisory mode changes, and no more.

Advisory mode keeps `compass ci` and `compass check` from failing, so a team
can pilot Compass without blocking pull requests. The pre-tool hook does not
read the mode: it still refuses a code edit with no failing test on record,
because a failing test before code is a guardrail. The template `compass
init` wrote said advisory mode meant "nothing blocks", which a person
piloting Compass would read as the hook standing aside too.

The description moved from the init template to `docs/configuration.md` when
`compass init` stopped writing settings (ADR-043), so this test reads it
there.

Scenario id: `TRC-001` (issue `advisory-mode-wording`).
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _adoption_section():
    text = (ROOT / "docs" / "configuration.md").read_text(encoding="utf-8")
    assert "### `adoption`" in text, "docs/configuration.md has no adoption section"
    return text.split("### `adoption`", 1)[1].split("\n### ", 1)[0]


def test_trc_001_the_reference_says_the_hook_still_enforces():
    section = _adoption_section()
    assert "nothing blocks" not in section
    assert "`compass check` and `compass ci`" in section and "exit 0" in section
    assert "pre-tool hook" in section and "still" in section, section
