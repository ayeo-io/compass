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
    # ADR-099 cut the contract to one screen. It names the typed approval and the
    # delegation rule; `finish` writes the request, the assess command names the
    # request for the scenarios, and the reject command names `/compass:reject`.
    contract = _flat("compass-contract.md")
    for needle in ("Approve yourself only under a delegation naming you",
                   "ask them to type /compass:approve <n> and stop",
                   "Never create, extend or revoke a delegation"):
        assert needle in contract, needle
    assert "compass evidence request" in _flat("commands/assess.md")
    assert "/compass:reject" in _flat("commands/reject.md")
    guardrails = _flat("governance/guardrails.md")
    assert "delegat" in guardrails and "approval-withdrawal" in guardrails


def test_e4_contract_gives_the_delegated_approval_command():
    """The contract gives the command an agent runs to approve under a
    delegation naming it."""
    contract = _flat("compass-contract.md")
    assert "compass evidence approve --delegated --as" in contract
