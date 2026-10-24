"""The pre-tool hook declares a time limit, and the safety contract says what it covers.

The hook scans a Bash command in shell. A scan that runs past the host's time
limit used to let the call run on most Claude Code versions. `hooks/hooks.json`
now sets `timeout` and `onFailure` on the pre-tool entry, and
`docs/safety-contract.md` states the limit and the versions it holds on.

Scenario id: `TRC-013` in pre-tool-hook-time-bounded/acceptance-criteria.md
Scenario id: `TRC-014` in pre-tool-hook-time-bounded/acceptance-criteria.md
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# The entries of the five other events, written out so that a change to one of
# them fails this test (the file is read as it stood before the keys were added).
_OTHER_EVENTS = {
    # The Bash matcher and the two events after it let post-tool.sh delete the
    # call ticket of a delegated approval when its call ends (issue
    # `delegation-everywhere`).
    "PostToolUse": [
        {
            "matcher": "Edit|Write|Bash",
            "hooks": [
                {
                    "type": "command",
                    "command": "\"${CLAUDE_PLUGIN_ROOT}/hooks/post-tool.sh\"",
                }
            ],
        }
    ],
    "PostToolUseFailure": [
        {
            "matcher": "Bash",
            "hooks": [
                {
                    "type": "command",
                    "command": "\"${CLAUDE_PLUGIN_ROOT}/hooks/post-tool.sh\"",
                }
            ],
        }
    ],
    "PermissionDenied": [
        {
            "matcher": "Bash",
            "hooks": [
                {
                    "type": "command",
                    "command": "\"${CLAUDE_PLUGIN_ROOT}/hooks/post-tool.sh\"",
                }
            ],
        }
    ],
    "Stop": [
        {
            "hooks": [
                {
                    "type": "command",
                    "command": "\"${CLAUDE_PLUGIN_ROOT}/hooks/stop.sh\"",
                }
            ],
        }
    ],
    "SessionStart": [
        {
            "matcher": "startup|clear|compact",
            "hooks": [
                {
                    "type": "command",
                    "command": "\"${CLAUDE_PLUGIN_ROOT}/hooks/session-start.sh\"",
                }
            ],
        }
    ],
    "UserPromptExpansion": [
        {
            "matcher": "compass:approve|compass:reject|compass:delegate|compass:revoke",
            "hooks": [
                {
                    "type": "command",
                    "command": "\"${CLAUDE_PLUGIN_ROOT}/hooks/prompt-approval.sh\"",
                }
            ],
        }
    ],
    "UserPromptSubmit": [
        {
            "hooks": [
                {
                    "type": "command",
                    "command": "\"${CLAUDE_PLUGIN_ROOT}/hooks/approval-summary.sh\"",
                }
            ],
        }
    ],
}


def test_the_pre_tool_entry_declares_a_time_limit_and_blocks_on_failure():
    """Scenario id: `TRC-013` in pre-tool-hook-time-bounded/acceptance-criteria.md"""
    hooks = json.loads((ROOT / "hooks" / "hooks.json").read_text())["hooks"]

    groups = hooks["PreToolUse"]
    assert len(groups) == 1
    assert groups[0]["matcher"] == "Edit|Write|Bash|Read|Grep"
    assert len(groups[0]["hooks"]) == 1
    entry = groups[0]["hooks"][0]
    assert entry == {
        "type": "command",
        "command": "\"${CLAUDE_PLUGIN_ROOT}/hooks/pre-tool.sh\"",
        "timeout": 15,
        "onFailure": "block",
    }
    assert entry["timeout"] == 15 and not isinstance(entry["timeout"], bool)

    others = {event: groups for event, groups in hooks.items() if event != "PreToolUse"}
    assert others == _OTHER_EVENTS


def test_the_safety_contract_states_the_limit_and_the_minimum_version():
    """Scenario id: `TRC-014` in pre-tool-hook-time-bounded/acceptance-criteria.md"""
    text = " ".join((ROOT / "docs" / "safety-contract.md").read_text().split())

    assert "98304 bytes" in text
    assert "Claude Code 2.1.295" in text
    # The length limit does not depend on the host version.
    assert "on every version of Claude Code" in text
    assert "On an older version the length limit still refuses" in text
    assert "can let the call run" in text
    # The page must not claim that every timeout fails closed.
    assert "not every timeout" in text.lower()
    assert not re.search(r"(?<!not )every timeout (?:fails closed|blocks)", text, re.I)
