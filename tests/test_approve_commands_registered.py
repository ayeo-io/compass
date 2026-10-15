"""The plugin registers the approval commands and the prompt hook (issue
`approve-inside-claude-code`, ADR-068 decision 2, ADR-069 decision 1).

U0 measured on Claude Code 2.1.300 that a scheduled task fires
`UserPromptExpansion` for a command without `disable-model-invocation: true`,
with the same fields as a typed one. So every command the hook serves sets the
flag, and the hook refuses a command whose file does not.

Scenario ids: `TRC-C10`, `TRC-D4`, `TRC-E2`, `TRC-F9`. Each test name starts
with its scenario id.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "cli"))

COMMANDS = ("approve", "reject", "delegate", "revoke")


def _front(name):
    text = (ROOT / "commands" / f"{name}.md").read_text(encoding="utf-8")
    match = re.match(r"---\n(.*?)\n---\n(.*)", text, re.S)
    assert match, name
    return yaml.safe_load(match.group(1)), match.group(2)


# --- the agent invokes the approve command itself (`TRC-D4`) --------------------------------

def test_d4_commands_disable_model_invocation(tmp_path):
    for name in COMMANDS:
        front, _ = _front(name)
        assert front.get("disable-model-invocation") is True, name
    # The hook refuses a command whose file does not set the flag.
    from approval_support import event, project
    from compass_pkg import prompt_approval
    root = project(tmp_path)
    plugin = tmp_path / "plugin" / "commands"
    plugin.mkdir(parents=True)
    for name in COMMANDS:
        (plugin / f"{name}.md").write_text(f"---\ndescription: {name}\n---\n\nBody.\n")
    for name in COMMANDS:
        result = prompt_approval.handle(event(root, command=f"compass:{name}"), {},
                                        plugin_root=str(plugin.parent))
        assert result.block and "disable-model-invocation" in result.message, (name, result)


# --- the model cannot create or extend a delegation (`TRC-F9`) -------------------------------

def test_f9_delegate_commands_not_model_invocable():
    for name in ("delegate", "revoke"):
        front, _ = _front(name)
        assert front.get("disable-model-invocation") is True, name


# --- the plugin registers the commands and the hook (`TRC-E2`) -------------------------------

def test_e2_hook_and_commands_registered():
    hooks = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]
    entries = hooks.get("UserPromptExpansion")
    assert entries and len(entries) == 1, entries
    matcher = entries[0]["matcher"]
    assert sorted(matcher.split("|")) == sorted(f"compass:{n}" for n in COMMANDS), matcher
    commands = [h["command"] for h in entries[0]["hooks"]]
    assert commands == ['"${CLAUDE_PLUGIN_ROOT}/hooks/prompt-approval.sh"'], commands
    assert (ROOT / "hooks" / "prompt-approval.sh").is_file()
    for entry in hooks.get("UserPromptSubmit") or []:
        for hook in entry.get("hooks") or []:
            assert "prompt-approval" not in hook.get("command", ""), hook
    for name in COMMANDS:
        assert (ROOT / "commands" / f"{name}.md").is_file(), name


# --- the command reaches the agent without a result (`TRC-C10`) ------------------------------

def test_c10_command_text_says_nothing_recorded():
    for name in ("approve", "reject"):
        _, body = _front(name)
        flat = " ".join(body.split())
        for needle in ("nothing was recorded", "compass evidence approve",
                       "never record", "Compass"):
            assert needle in flat, (name, needle)
