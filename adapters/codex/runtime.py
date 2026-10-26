#!/usr/bin/env python3
"""Codex's stage paths and hook payload boundary over the unchanged kit.

DEPENDENCY: Python 3.10+ standard library; shared hooks need Bash.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def patch_targets(command):
    """Read target headers, never evaluate the patch or infer policy from it."""
    lines = command.strip().splitlines()
    if not lines or lines[0] != "*** Begin Patch" or lines[-1] != "*** End Patch":
        raise ValueError("patch needs Begin Patch and End Patch markers")
    targets, moving = [], False
    for line in lines[1:-1]:
        if line in ("*** Begin Patch", "*** End Patch"):
            raise ValueError("nested patch markers")
        for action in ("Add File", "Update File", "Delete File", "Move to"):
            prefix = f"*** {action}: "
            if not line.startswith(prefix):
                continue
            target = line[len(prefix):]
            if not target or "\x00" in target or target != target.strip():
                raise ValueError("invalid patch target")
            if action == "Move to" and not moving:
                raise ValueError("Move to must follow Update File")
            targets.append(target)
            moving = action == "Update File"
            break
        else:
            if line.startswith("*** ") and line != "*** End of File":
                raise ValueError("unknown patch header")
    if not targets:
        raise ValueError("patch has no targets")
    return list(dict.fromkeys(targets))


#: The variables the shared hooks read: where to find programs, including the
#: settings a pyenv or asdf `python3` shim reads, the locale, the user's git
#: configuration, and the Compass and Claude settings. Any other variable, such
#: as a service's secret, is not passed.
HOOK_ENV_KEEP = ("PATH", "HOME", "USER", "LOGNAME", "SHELL", "TMPDIR", "LANG", "TZ", "TERM",
                 "COLUMNS", "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "GIT_DIR", "GIT_WORK_TREE",
                 "GIT_CEILING_DIRECTORIES", "GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM")
HOOK_ENV_KEEP_PREFIXES = ("LC_", "COMPASS_", "CLAUDE_", "PYENV_", "ASDF_")


def shared_hook(script, payload):
    env = {k: v for k, v in os.environ.items()
           if k in HOOK_ENV_KEEP or k.startswith(HOOK_ENV_KEEP_PREFIXES)}
    env["CLAUDE_PLUGIN_ROOT"] = str(ROOT)
    # The hook resolves the actual project from payload cwd and target paths.
    # Never carry a different runtime's project or plugin-data directory over.
    env.pop("CLAUDE_PROJECT_DIR", None)
    env.pop("CLAUDE_PLUGIN_DATA", None)
    return subprocess.run(["bash", str(ROOT / "hooks" / script)],
                          input=json.dumps(payload), text=True, capture_output=True,
                          cwd=payload["cwd"], env=env, timeout=20)


def run_hook(payload):
    event = payload.get("hook_event_name")
    if event in ("SessionStart", "Stop"):
        result = shared_hook("session-start.sh" if event == "SessionStart" else "stop.sh", payload)
        sys.stderr.write(result.stderr)
        if result.returncode:
            raise ValueError(f"shared {event} hook exited {result.returncode}")
        if event == "SessionStart" and result.stdout.strip():
            message = json.loads(result.stdout)
            output = message.setdefault("hookSpecificOutput", {})
            output["additionalContext"] = (output.get("additionalContext", "") +
                f"\nFramework root: {ROOT}\n" +
                (ROOT / "adapters/codex/INSTRUCTIONS.md").read_text(encoding="utf-8"))
            print(json.dumps(message))
        # Stop is advisory; its shared hook writes its advice to stderr.
        return 0
    if event not in ("PreToolUse", "PostToolUse"):
        return 0
    tool = payload.get("tool_name")
    if tool in ("Bash", "exec_command", "shell_command"):
        fields = payload.get("tool_input", {})
        payload = {**payload, "tool_name": "Bash", "tool_input": {
            "command": fields.get("cmd", fields.get("command"))}}
        if not isinstance(payload["tool_input"]["command"], str):
            raise ValueError("shell call needs a command")
    if tool == "apply_patch":
        command = payload.get("tool_input", {}).get("command")
        if not isinstance(command, str):
            raise ValueError("apply_patch needs tool_input.command")
        targets = patch_targets(command)
        calls = [{**payload, "tool_name": "Write", "tool_input": {
            "file_path": str(Path(payload["cwd"]) / target)}} for target in targets]
    else:
        calls = [payload]
    for call in calls:
        result = shared_hook("pre-tool.sh" if event == "PreToolUse" else "post-tool.sh", call)
        if event == "PreToolUse":
            sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
        if result.returncode:
            if result.returncode != 2:
                print(f"Compass Codex hook failed (exit {result.returncode}); call refused.",
                      file=sys.stderr)
            return 2
    return 0


def context():
    commands = {p.stem: str(p) for p in sorted((ROOT / "commands").glob("*.md"))}
    return {"root": str(ROOT), "contract": str(ROOT / "compass-contract.md"),
            "commands": commands, "roles": {
                "engineer": commands["assess"], "product-owner": commands["intent"],
                "designer": commands["design"], "product-marketer": commands["position"],
                "qa": commands["consult"]}}


def main():
    if sys.argv[1:] == ["context"]:
        print(json.dumps(context(), indent=2))
        return 0
    if sys.argv[1:] == ["hook"]:
        try:
            payload = json.load(sys.stdin)
            return run_hook(payload)
        except (ValueError, TypeError, AttributeError, KeyError, OSError,
                subprocess.SubprocessError) as exc:
            print(f"Compass Codex hook refused: {exc}", file=sys.stderr)
            return 2
    print("usage: runtime.py context|hook", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
