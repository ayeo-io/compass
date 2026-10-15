"""The guardrail 5 sign-off with no project configuration (GitHub issue #571,
folded into issue `approve-inside-claude-code`).

A project with no `compass.yml` checks runs the shipped default preset. Each
approval path writes a record that `human-approval-present` counts, and no
Compass message tells a person to edit `manifest.yml` by hand.

Scenario ids: `TRC-G1`, `TRC-G3`. Each test name starts with its scenario id.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

from test_approval_scoped_to_guardrail_5 import SLUG, _project, _run  # noqa: E402


# --- the fix text names the approval path (`TRC-G3`) --------------------------------------

def _in_order(text):
    first = text.index("/compass:approve")
    delegated = text.index("delegat", first)
    terminal = text.index("compass evidence approve --guardrail G5", delegated)
    return first < delegated < terminal


def test_g3_fix_text_names_approval_path(tmp_path):
    import json
    sys.path.insert(0, str(ROOT / "cli"))
    from compass_pkg import check_cmd
    root = _project(tmp_path)
    code, out, err = _run(root, "check", "--issue", SLUG, "--json")
    assert code != 0, out + err
    row = next(r for r in json.loads(out)["checks"] if r["name"] == "human-approval-present")
    assert row["status"] == "fail", row
    guidance = check_cmd.CHECK_GUIDANCE["human-approval-present"]
    for text in (row["detail"], guidance["do"], guidance["fix"]):
        assert _in_order(text), text
    for text in (row["detail"], *guidance.values()):
        lowered = text.lower()
        assert not ("manifest.yml" in lowered
                    and any(w in lowered for w in ("add ", "edit ", "append "))), text
