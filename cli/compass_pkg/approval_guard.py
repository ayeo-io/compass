# compass_pkg.approval_guard - the pre-tool checks on approval state
"""Decide whether the agent's tool call touches approval state it must not
(ADR-068 decision 10, ADR-069 decisions 4 and 8). `hooks/pre-tool.sh` calls
`check` with the hook input and blocks with the code it returns.

- **Request files.** Edit or Write on a file under an issue's
  `approval-requests/`, or a Bash command that names that folder or the
  prompt hook's entry point, gives `approval-request-protected`.
- **Delegation files.** Edit or Write under `.compass/delegations/`, or a
  Bash command that names that folder, gives `delegation-protected`.
- **The session transcript.** Claude Code writes a hook's block message to
  the session's transcript file (measured on Claude Code 2.1.301), and the
  block message is where the person sees the code that confirms a g5
  delegation. So Read or Grep on the transcript's folder, or a Bash command
  that names it or a `.claude*/projects` folder, gives
  `transcript-protected`.
- **A delegated approval's caller.** A Bash command that runs `compass
  evidence approve` with `--delegated` (or any flag that starts `--del`) must
  name the caller with `--as`, and the caller must be the agent Claude Code
  reports: `main` only when the input has neither `agent_type` nor
  `agent_id`, otherwise the exact `agent_type`, plugin prefix included. An
  `agent_id` with no or an empty `agent_type` is refused, because Claude
  Code's own internal agents report that shape (the host measurement on
  Claude Code 2.1.300, ADR-069). Anything else gives
  `delegation-caller-mismatch`.

The Bash checks match text, as the hook's other Bash checks do. They stop the
agent's ordinary use, not a deliberate workaround such as a variable that
assembles the path; the safety contract states that limit.
"""
# DEPENDENCY: standard library (os, re, shlex). Runs inside hooks/pre-tool.sh,
# so it keeps to syntax the hook's oldest supported python3 reads.
from __future__ import annotations

import os
import re
import shlex

REQUEST_FOLDER = "approval-requests"
HOOK_ENTRY = "prompt-approval.sh"
DELEGATION_FOLDER = ".compass/delegations"
EDIT_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")
READ_TOOLS = ("Read", "Grep")
#: A Claude Code configuration folder's transcripts, however it is spelled.
TRANSCRIPTS = re.compile(r"\.claude[\w.-]*/projects(?:/|\b)|CLAUDE_CONFIG_DIR")


def _path(text):
    return str(text or "").replace("\\", "/")


def caller(event):
    """The agent Claude Code reports for this call: `main`, its exact
    `agent_type`, or None when the input does not name one."""
    has_type = "agent_type" in event
    has_id = event.get("agent_id") not in (None, "")
    agent_type = event.get("agent_type")
    if not has_type and not has_id:
        return "main"
    if isinstance(agent_type, str) and agent_type.strip():
        return agent_type
    return None


def _words(command):
    try:
        return shlex.split(command)
    except ValueError:
        return command.split()


def _as_value(words):
    for i, word in enumerate(words):
        if word == "--as" and i + 1 < len(words):
            return words[i + 1]
        if word.startswith("--as="):
            return word[len("--as="):]
    return None


def _delegated_approve(words):
    """True for a command that runs `compass evidence approve` delegated."""
    runs = any(a == "evidence" and b == "approve" for a, b in zip(words, words[1:]))
    return runs and any(w.startswith("--del") for w in words)


def _transcript_folder(event):
    path = event.get("transcript_path")
    return os.path.dirname(_path(path)) if path else ""


def _names_transcript(text, folder):
    text = _path(text)
    return bool(TRANSCRIPTS.search(text)) or bool(folder and folder in text)


def check(event):
    """`(code, params)` for a call to refuse, else None."""
    tool = event.get("tool_name") or ""
    tool_input = event.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return None
    folder = _transcript_folder(event)
    if tool in READ_TOOLS:
        target = _path(tool_input.get("file_path") or tool_input.get("path"))
        if target and _names_transcript(target, folder):
            return "transcript-protected", {"target": target, "tool": tool}
        return None
    if tool in EDIT_TOOLS:
        target = _path(tool_input.get("file_path") or tool_input.get("path")
                       or tool_input.get("notebook_path"))
        if f"/{REQUEST_FOLDER}/" in target and ".compass/" in target:
            return "approval-request-protected", {"target": target, "tool": tool}
        if f"{DELEGATION_FOLDER}/" in target:
            return "delegation-protected", {"target": target, "tool": tool}
        if _names_transcript(target, folder):
            return "transcript-protected", {"target": target, "tool": tool}
        return None
    if tool != "Bash":
        return None
    command = str(tool_input.get("command") or "")
    if REQUEST_FOLDER in command or HOOK_ENTRY in command:
        return "approval-request-protected", {
            "target": "a command naming approval requests", "tool": tool}
    if DELEGATION_FOLDER in command:
        return "delegation-protected", {
            "target": "a command naming .compass/delegations", "tool": tool}
    if _names_transcript(command, folder):
        return "transcript-protected", {
            "target": "a command naming a session transcript", "tool": tool}
    words = _words(command)
    if _delegated_approve(words):
        named = _as_value(words)
        who = caller(event)
        if named is None or who is None or named != who:
            return "delegation-caller-mismatch", {
                "named": named or "no --as", "caller": who or "an agent with no agent type"}
    return None
