"""An approval record names how it was made (issue `approve-inside-claude-code`).

A record gains `via`: `prompt` when the Claude Code hook wrote it from a typed
`/compass:approve`, `terminal` when a person ran `compass evidence approve` at
a terminal, and `delegation` when an agent recorded it under a delegation. No
verdict reads `via`; the detail of `human-approval-present` and the receipt
name it, and a record with no `via` still counts (ADR-006, ADR-068 decision 7).

Scenario ids: `TRC-E1`, `TRC-D3`. Each test name starts with its scenario id.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

from test_approval_scoped_to_guardrail_5 import (  # noqa: E402
    DOD, NO_SUBJECT, _approve, _check_row, _manifest, _project)


# --- TRC-E1: the terminal fallback keeps working ------------------------------------------

def test_e1_terminal_record_holds_via(tmp_path):
    root = _project(tmp_path / "terminal", [DOD])
    code, out, err = _approve(root, "--guardrail", "G5", "--approver", "jed72",
                              "--role", "owner", "--scope", "refund migration")
    assert code == 0, out + err
    record = _manifest(root)["evidence"][-1]
    assert record["id"] == "EV-APPROVAL-G5-1"
    assert record["via"] == "terminal"
    assert record["approver"] == "jed72" and record["guardrail"] == "G5"
    _, row = _check_row(root)
    assert row["status"] == "pass", row

    # An earlier record with no `via` key is still counted.
    earlier = _project(tmp_path / "earlier", [NO_SUBJECT])
    assert "via" not in _manifest(earlier)["evidence"][-1]
    _, row = _check_row(earlier)
    assert row["status"] == "pass", row
