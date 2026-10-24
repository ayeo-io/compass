"""A person withdraws a guardrail 5 sign-off made under a delegation
(issue `approve-inside-claude-code`, ADR-069 decision 6).

`/compass:reject <record id> <reason>` on a delegated sign-off writes an
`approval-withdrawal` record. `human-approval-present` 1.2.0 skips a withdrawn
record while the issue is in flight; on a landed issue the floor of ADR-066
decision 5 still passes it, reported only. A waiver that names a withdrawn
approval fails.

Scenario ids: `TRC-F13`, `TRC-F15`. Each test name starts with its scenario id.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

from approval_support import OWNER, SLUG, event, manifest_of, project, run, task_dir  # noqa: E402
from test_delegation import ARCHITECT, _soon  # noqa: E402


def _type(root, args, command):
    from compass_pkg import prompt_approval
    return prompt_approval.handle(event(root, command=command, args=args), {},
                                  plugin_root=str(ROOT))


# --- the person overrules a delegated guardrail 5 sign-off (`TRC-F13`) ----------------------

def test_f13_withdrawal_fails_g5_in_flight(tmp_path):
    from compass_pkg import checks, waivers
    root = project(tmp_path)
    first = _type(root, f"--agent {ARCHITECT} --until {_soon()} --for g5", "compass:delegate")
    code = re.search(r"confirm (\S+)", first.message).group(1)
    assert not _type(root, f"confirm {code}", "compass:delegate").block
    done = run(root, "evidence", "approve", "--issue", SLUG, "--guardrail", "G5", "--scope",
               "the release tag", "--delegated", "--as", ARCHITECT)
    assert done[0] == 0, done
    ok, _ = checks._check_human_approval(manifest_of(root), str(task_dir(root)))
    assert ok
    result = _type(root, "EV-APPROVAL-G5-1 the tag was premature", "compass:reject")
    assert not result.block, result
    withdrawal = manifest_of(root)["evidence"][-1]
    assert withdrawal["type"] == "approval-withdrawal"
    assert withdrawal["withdraws"] == "EV-APPROVAL-G5-1"
    assert withdrawal["by"] == OWNER and withdrawal["at"] and withdrawal["via"] == "prompt"
    assert withdrawal["reason"] == "the tag was premature"
    assert withdrawal["issue"] == SLUG and withdrawal["generation"] == 1
    ok, detail = checks._check_human_approval(manifest_of(root), str(task_dir(root)))
    assert not ok and "withdrawn" in detail, detail
    assert "does not reverse" in result.message, result.message
    # A waiver that names the withdrawn approval fails.
    waiver = SimpleNamespace(id="W-1", body={"approved_by": "EV-APPROVAL-G5-1"},
                             catalogue="checks", entry="x")
    found = waivers.check_approval(waiver, [OWNER], manifest_of(root)["evidence"], None)
    assert found and "withdrawn" in str(found[0]), found


# --- a withdrawal never fails a landed issue (`TRC-F15`) -----------------------------------

def test_f15_landed_floor_holds():
    from compass_pkg import checks
    record = {"id": "EV-G5", "type": "human-approval", "guardrail": "G5",
              "decision": "approved", "approver": "jed72", "role": "owner",
              "scope": "the tag", "timestamp": "2026-10-15T22:00:00Z",
              "via": "delegation", "approved_by_agent": ARCHITECT, "delegation": "DL-1"}
    withdrawal = {"id": "EV-WITHDRAWAL-1", "type": "approval-withdrawal",
                  "withdraws": "EV-G5", "by": "jed72", "at": "2026-10-16T08:00:00Z",
                  "reason": "premature", "via": "prompt"}
    task = {"issue": "x", "assessment": {"labels": ["payments"]},
            "evidence": [record, withdrawal]}
    ok, detail = checks._check_human_approval(dict(task), "/nonexistent")
    assert not ok, detail
    landed = dict(task, status="done", close_reason="completed")
    ok, detail = checks._check_human_approval(landed, "/nonexistent")
    assert ok and "reported only" in detail, detail
