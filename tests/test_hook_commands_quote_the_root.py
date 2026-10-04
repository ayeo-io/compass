"""Every Compass hook runs when the plugin's path contains a space.

Each hook command ran `${CLAUDE_PLUGIN_ROOT}/hooks/<name>.sh` unquoted, so a
plugin installed under a home folder such as `/Users/Jane Smith` split into
words and every hook failed: no pre-tool enforcement, no session-start
contract, and no error the user sees (#396).

Scenario id: HQ-1 (issue `quote-the-plugin-root-in-hooks`).
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _commands():
    hooks = json.loads((ROOT / "hooks" / "hooks.json").read_text())["hooks"]
    return [hook["command"] for groups in hooks.values()
            for group in groups for hook in group["hooks"]]


def test_hq_1_each_hook_command_runs_from_a_path_with_a_space(tmp_path):
    root = tmp_path / "plugin root"
    (root / "hooks").mkdir(parents=True)
    commands = _commands()
    assert len(commands) == 4
    for command in commands:
        name = command.rsplit("/", 1)[-1].strip('"')
        stub = root / "hooks" / name
        stub.write_text(f"#!/bin/sh\necho ran-{name}\n", encoding="utf-8")
        stub.chmod(0o755)
    for command in commands:
        name = command.rsplit("/", 1)[-1].strip('"')
        result = subprocess.run(
            ["bash", "-c", command], capture_output=True, text=True,
            env={**os.environ, "CLAUDE_PLUGIN_ROOT": str(root)})
        assert result.returncode == 0 and f"ran-{name}" in result.stdout, (
            command, result.stderr)
