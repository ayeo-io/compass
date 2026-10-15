"""The safety documents describe the approval paths (issue
`approve-inside-claude-code`, ADR-068, ADR-069).

Scenario id: `TRC-E4`. The test name starts with it.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _flat(path):
    return " ".join((ROOT / path).read_text(encoding="utf-8").replace("`", "").split())


# --- the safety documents describe the new path (`TRC-E4`) ----------------------------------

def test_e4_docs_name_prompt_path():
    for path in ("docs/safety-contract.md", "governance/guardrails.md", "compass-contract.md"):
        assert "/compass:approve" in _flat(path), path
    safety = _flat("docs/safety-contract.md")
    assert "a process running as the same operating system user can still write" in \
        safety.lower(), "the same-user limit"
    for needle in ("/compass:delegate", "approval-withdrawal", "nested claude -p"):
        assert needle in safety, needle
    contract = _flat("compass-contract.md")
    for needle in ("compass evidence approve --delegated --as", "compass evidence request",
                   "/compass:reject", "Never create, extend or revoke a delegation"):
        assert needle in contract, needle
    guardrails = _flat("governance/guardrails.md")
    assert "delegat" in guardrails and "approval-withdrawal" in guardrails
