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


# --- the terminal fallback keeps working (`TRC-E1`) ---------------------------------------

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


# --- the agent writes an approval into the manifest by hand (`TRC-D3`) --------------------

def test_d3_hand_written_record_named(tmp_path):
    from test_approval_scoped_to_guardrail_5 import G5, _run, SLUG
    cases = [
        ({}, "written without a Compass command"),
        ({"via": "terminal"}, "via a terminal"),
        ({"via": "prompt", "host": "claude-code", "session_id": "s1", "prompt_id": "p1",
          "request": 1, "nonce": "n1"}, "via a typed prompt"),
    ]
    for number, (extra, words) in enumerate(cases):
        record = dict(G5, **extra)
        root = _project(tmp_path / f"case-{number}", [record])
        _, row = _check_row(root)
        assert row["status"] == "pass", row
        assert words in row["detail"], (words, row)
        code, out, err = _run(root, "issue", "receipt", "--issue", SLUG)
        assert code == 0, out + err
        lines = out.splitlines()
        at = [i for i, one in enumerate(lines) if "EV-G5" in one and "human-approval" in one]
        assert at and words == lines[at[0] + 1].strip(), (words, out)
