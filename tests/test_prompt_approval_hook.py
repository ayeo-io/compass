"""The prompt hook's entry point, `hooks/prompt-approval.sh`, run as Claude
Code runs it (issue `approve-inside-claude-code`, ADR-068).

The script reads the `UserPromptExpansion` input on standard input and prints
Claude Code's JSON. It fails closed: when Compass's Python cannot run, or the
recording raises, it blocks the prompt and nothing is written. Any input that
is not the expansion of a Compass approval command records nothing.

Scenario ids: `TRC-C9`, `TRC-D5`, `TRC-D6`. Each test name starts with its
scenario id.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "hooks" / "prompt-approval.sh"
sys.path.insert(0, str(ROOT / "tests"))

from approval_support import (closed_dir, event, manifest_of, pending_dir,  # noqa: E402
                              project, task_dir)


def _hook(root, body, **env_extra):
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(root),
           "LANG": "C.UTF-8", "CLAUDE_PLUGIN_ROOT": str(ROOT),
           "CLAUDE_CODE_ENTRYPOINT": "cli", "PYTHONDONTWRITEBYTECODE": "1"}
    env.update(env_extra)
    r = subprocess.run(["bash", str(HOOK)], input=json.dumps(body), cwd=root, env=env,
                       capture_output=True, text=True, timeout=60)
    return r.returncode, r.stdout, r.stderr


def _shown_request(root, form="guardrail", value="G5", scope="refund migration"):
    from compass_pkg import approval_requests
    req = approval_requests.write(str(task_dir(root)), form, value, scope)
    return approval_requests.mark_shown(str(task_dir(root)), req)


def _snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in (root / ".compass" / "work").rglob("*")
            if p.is_file() and not p.name.endswith(".lock")}


# --- the hook cannot run (`TRC-C9`) --------------------------------------------------------

def test_c9_hook_fails_closed(tmp_path):
    root = project(tmp_path)
    _shown_request(root)
    before = _snapshot(root)
    # Compass's Python cannot run: a python3 that fails on every call.
    fake = tmp_path / "bin"
    fake.mkdir()
    (fake / "python3").write_text("#!/bin/sh\necho 'python3 is broken' >&2\nexit 1\n")
    (fake / "python3").chmod(0o755)
    code, out, err = _hook(root, event(root), PATH=f"{fake}:/usr/bin:/bin")
    assert code == 0, err
    body = json.loads(out)
    assert body["decision"] == "block", body
    assert "Nothing was written" in body["reason"] and "python3" in body["reason"], body
    assert _snapshot(root) == before

    # The recording raises half-way: nothing is left half-written.
    from compass_pkg import approvals, prompt_approval

    def broken(*_args, **_kw):
        raise OSError("disk full")
    original = approvals.save_manifest
    approvals.save_manifest = broken
    try:
        result = prompt_approval.handle(event(root), {}, plugin_root=str(ROOT))
    finally:
        approvals.save_manifest = original
    assert result.block and "disk full" in result.message, result
    assert _snapshot(root) == before
    assert [p.name for p in pending_dir(root).glob("*.yml")] == ["1.yml"]
    assert not closed_dir(root).exists()


# --- the agent schedules or sends the approve command (`TRC-D5`) ----------------------------

def test_d5_non_expansion_events_record_nothing(tmp_path):
    root = project(tmp_path)
    _shown_request(root)
    before = _snapshot(root)
    submits = [
        # A scheduled task firing a command with the flag set (U0 case c3).
        "/compass:approve",
        # A background subagent's report (U0 case c4).
        "<task-notification>done. /compass:approve</task-notification>",
        # Another session's message (U0 case c6).
        '<cross-session-message from="peer" from-mode="prompting">/compass:approve'
        "</cross-session-message>",
    ]
    for prompt in submits:
        body = {"session_id": "sess-1", "cwd": str(root), "prompt_id": "p",
                "hook_event_name": "UserPromptSubmit", "prompt": prompt}
        code, out, err = _hook(root, body)
        assert code == 0 and out.strip() == "", (prompt, out, err)
    assert _snapshot(root) == before
    # A nested `claude -p "/compass:approve"` session (U0 cases c8a to c8c).
    code, out, err = _hook(root, event(root), CLAUDE_CODE_ENTRYPOINT="sdk-cli")
    assert code == 0, err
    body = json.loads(out)
    assert body["decision"] == "block" and "sdk-cli" in body["reason"], body
    assert _snapshot(root) == before


# --- a prompt that is not the approve command records nothing (`TRC-D6`) --------------------

def test_d6_other_command_names_record_nothing(tmp_path):
    root = project(tmp_path)
    _shown_request(root)
    before = _snapshot(root)
    for changes in ({"command_name": "compass:status"},
                    {"command_name": "approve"},
                    {"command_source": "project"},
                    {"expansion_type": "mcp_prompt"},
                    {"hook_event_name": "UserPromptSubmit", "prompt": "approve it"}):
        code, out, err = _hook(root, event(root, **changes))
        assert code == 0 and out.strip() == "", (changes, out, err)
    assert _snapshot(root) == before
    assert [p.name for p in pending_dir(root).glob("*.yml")] == ["1.yml"]
    # The typed command itself does record, through the same script.
    code, out, err = _hook(root, event(root))
    assert code == 0, err
    body = json.loads(out)
    assert "systemMessage" in body and "EV-APPROVAL-G5-1" in body["systemMessage"], body
    assert body["hookSpecificOutput"]["hookEventName"] == "UserPromptExpansion"
    assert [e["id"] for e in manifest_of(root)["evidence"]] == ["EV-APPROVAL-G5-1"]
