#!/usr/bin/env python3
"""Install the Codex adapter in one project, preserving unrelated wiring.

DEPENDENCY: Python 3.10+ standard library. The kit stays in the source checkout.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
BEGIN = "<!-- compass:codex begin -->"
END = "<!-- compass:codex end -->"
EVENTS = ("SessionStart", "PreToolUse", "PostToolUse", "Stop")


def read(path):
    if path.is_symlink():
        raise ValueError(f"refusing managed file symlink: {path}")
    return path.read_bytes().decode("utf-8") if path.exists() else ""


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".compass-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(text)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def block():
    return (f"{BEGIN}\n"
            f"Before changing files, read `{ROOT / 'compass-contract.md'}` and "
            f"`{ROOT / 'adapters/codex/INSTRUCTIONS.md'}`.\n"
            "Use the $compass:compass skill for stages and roles. Keep issue state in this checkout.\n"
            f"{END}\n")


def hook_groups():
    command = f"python3 {shlex.quote(str(ROOT / 'adapters/codex/runtime.py'))} hook"
    return {event: {"matcher": ".*", "hooks": [
        {"type": "command", "command": command, "timeout": 30}]}
        for event in EVENTS}


def managed_span(text):
    if not text.count(BEGIN) and not text.count(END):
        return None
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        raise ValueError("AGENTS.md has ambiguous Compass markers")
    start, end = text.index(BEGIN), text.index(END) + len(END)
    if end < start:
        raise ValueError("AGENTS.md has reversed Compass markers")
    if text[end:end + 1] == "\n":
        end += 1
    return start, end


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def apply(project, uninstall=False):
    """Preflight every owned path before changing any project content."""
    project = project.resolve(strict=True)
    if not project.is_dir():
        raise ValueError("--project must name a directory")
    for rel in (".compass", ".codex", ".agents", ".agents/skills"):
        path = project / rel
        if path.is_symlink() or (path.exists() and not path.is_dir()):
            raise ValueError(f"refusing managed directory collision: {path}")
    receipt_path = project / ".compass/codex-install.json"
    receipt_text = read(receipt_path)
    receipt = json.loads(receipt_text) if receipt_text else None
    if receipt is not None and (not isinstance(receipt, dict) or receipt.get("schema") != 1
                                or not isinstance(receipt.get("groups"), dict)
                                or not isinstance(receipt.get("skill"), str)
                                or not isinstance(receipt.get("block_digest"), str)):
        raise ValueError("invalid Codex installation receipt")
    agents = project / "AGENTS.md"
    agents_existed = agents.exists()
    original_agents = read(agents)
    span = managed_span(original_agents)
    if span and (receipt is None or digest(original_agents[slice(*span)]) != receipt["block_digest"]):
        raise ValueError("Compass instructions changed or have no receipt; preserve them and resolve first")
    if receipt and span is None:
        raise ValueError("Compass instructions were removed; resolve the installation first")
    skill = project / ".agents/skills/compass"
    if skill.exists() or skill.is_symlink():
        if not receipt or not skill.is_symlink() or os.readlink(skill) != receipt["skill"]:
            raise ValueError(f"refusing to overwrite skill: {skill}")
    elif receipt:
        raise ValueError("Compass skill was removed; resolve the installation first")
    hooks_path = project / ".codex/hooks.json"
    hooks_existed = hooks_path.exists()
    hooks_text = read(hooks_path)
    hooks = json.loads(hooks_text) if hooks_text else {"hooks": {}}
    if not isinstance(hooks, dict) or not isinstance(hooks.get("hooks"), dict):
        raise ValueError("hooks.json must contain a hooks object")
    if any(not isinstance(groups, list) for groups in hooks["hooks"].values()):
        raise ValueError("each hooks.json event must contain a list")
    if receipt:
        if set(receipt["groups"]) != set(EVENTS):
            raise ValueError("invalid Codex hook receipt")
        for event, group in receipt["groups"].items():
            if hooks["hooks"].get(event, []).count(group) != 1:
                raise ValueError(f"Compass {event} hook changed; resolve it before reinstalling")
            hooks["hooks"][event].remove(group)
            if not hooks["hooks"][event]:
                del hooks["hooks"][event]
    if uninstall and receipt is None:
        return
    if span:
        start = span[0]
        prefix = receipt.get("prefix", "")
        if prefix and original_agents[:start].endswith(prefix):
            start -= len(prefix)
        new_agents = original_agents[:start] + original_agents[span[1]:]
    else:
        new_agents = original_agents
    groups = hook_groups()
    source_skill = str(ROOT / "adapters/codex/skills/compass")
    if not uninstall:
        # Own the leading newline too, so uninstall restores original bytes.
        prefix = "" if not new_agents or new_agents.endswith("\n") else "\n"
        own_block = block()
        new_agents += prefix + own_block
        for event, group in groups.items():
            hooks["hooks"].setdefault(event, []).append(group)
    # All collisions have been checked. Atomic replaces keep each file whole.
    if new_agents or not uninstall or not receipt.get("created_agents"):
        write(agents, new_agents)
    elif agents.exists():
        agents.unlink()
    if not uninstall or not receipt.get("created_hooks") or hooks != {"hooks": {}}:
        write(hooks_path, json.dumps(hooks, indent=2) + "\n")
    elif hooks_path.exists():
        hooks_path.unlink()
    if skill.is_symlink():
        skill.unlink()
    if uninstall:
        receipt_path.unlink()
        return
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.symlink_to(source_skill, target_is_directory=True)
    write(receipt_path, json.dumps({"schema": 1, "source": str(ROOT), "skill": source_skill,
          "block_digest": digest(own_block), "groups": groups,
          "prefix": prefix,
          "created_agents": receipt.get("created_agents") if receipt else not agents_existed,
          "created_hooks": receipt.get("created_hooks") if receipt else not hooks_existed}, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--uninstall", action="store_true")
    args = parser.parse_args()
    try:
        apply(args.project, args.uninstall)
    except (OSError, ValueError, TypeError) as exc:
        print(f"Compass Codex install: {exc}", file=sys.stderr)
        return 2
    print("Compass Codex wiring removed." if args.uninstall else
          "Compass Codex installed. Restart Codex; review and trust its hooks before use. "
          "Keep the source checkout in place; reinstall after moving or updating it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
