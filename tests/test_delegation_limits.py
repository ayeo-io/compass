"""Limits of a delegation that hold as the flag form and the common store arrive
(issue `delegation-everywhere`, group G).

Scenario ids: `TRC-072`, `TRC-074`, `TRC-076`, `TRC-077`, `TRC-099`. The first,
second, fourth and fifth pin behavior that holds before the flag form lands; their
fixtures write the files they need directly, so they run on the code as it was.
Each test name starts with its scenario id.
"""
from __future__ import annotations

import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

from approval_support import (event, manifest_of, project, run,  # noqa: E402
                              save_manifest)
from test_pre_tool_hook import (HOOK_PATH, _guarded_project,  # noqa: E402
                                _make_compass_project)
from conftest import write_red_record  # noqa: E402

# The delegation folder, built from pieces so that no line of this file names it whole.
STORE = ".compass/" + "delegations"


def _store(root):
    return root / ".compass" / "delegations"


def _write_dl(root, number, **fields):
    """A delegation file as `handle_delegate` writes it, put there directly."""
    body = {"id": f"DL-{number}", "agent": "compass:architect", "delegated_by": "jed72",
            "role": "owner", "approver_source": "owner",
            "created_at": "2026-10-23T08:00:00Z", "until": "2999-01-01T00:00:00Z",
            "issues": {"feature": 1}, "forms": ["checks", "documents", "checkpoints",
                                                "decisions"],
            "uses": 0, "created_via": "prompt", "session_id": "sess-1",
            "prompt_id": f"p-{number}", "nonce": "n" * 32}
    body.update(fields)
    folder = _store(root)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"DL-{number}.yml").write_text(yaml.safe_dump(body, sort_keys=False),
                                             encoding="utf-8")
    return body


def _bytes(root):
    folder = _store(root)
    return {p.name: p.read_bytes() for p in sorted(folder.rglob("*")) if p.is_file()}


def _type(root, args, command="compass:delegate", session="sess-1", **kw):
    from compass_pkg import prompt_approval
    return prompt_approval.handle(event(root, command=command, args=args, session=session,
                                        **kw), {}, plugin_root=str(ROOT))


# --- no CLI verb creates a delegation (TRC-072) --------------------------------------------

@pytest.mark.parametrize("command", [
    "delegate --agent main",
    "evidence delegate --agent main",
    "issue delegate --agent main",
    "delegate extend DL-1 --until 2027-01-01",
    "evidence delegate --extend DL-1",
    "revoke DL-1",
    "evidence revoke DL-1",
])
def test_TRC_072_no_cli_verb_creates_a_delegation(tmp_path, command):
    root = project(tmp_path)
    _write_dl(root, 1, until=None)
    before = _bytes(root)
    code, out, err = run(root, *command.split())
    assert code != 0, (command, out, err)
    assert _bytes(root) == before, command


# --- the agent's tools cannot reach the store from a worktree (TRC-074) --------------------

def _git(cwd, *argv):
    subprocess.run(["git", "-c", "user.email=t@example.com", "-c", "user.name=t", *argv],
                   cwd=cwd, check=True, capture_output=True, text=True)


@pytest.mark.parametrize("tool", ["Read", "Write", "Edit", "Bash"])
def test_TRC_074_the_agent_s_tools_cannot_reach_the_common_store_from_a_linked(tool):
    main, _ = _guarded_project()
    holder = Path(tempfile.mkdtemp(prefix="compass-fixture-")).resolve()
    try:
        main = main.resolve()
        (main / "compass.yml").write_text("schema: 1\n", encoding="utf-8")
        _git(main, "init", "-q")
        _git(main, "add", "compass.yml")
        _git(main, "commit", "-q", "-m", "x")
        work = holder / "w"
        _git(main, "worktree", "add", "-q", str(work))
        task = _make_compass_project(work, "feature", with_route_md=True)
        write_red_record(task)
        target = main / ".compass" / "delegations" / "DL-1.yml"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("id: DL-1\n", encoding="utf-8")
        tool_input = {"Read": {"file_path": str(target)},
                      "Write": {"file_path": str(target), "content": "x"},
                      "Edit": {"file_path": str(target), "old_string": "a",
                               "new_string": "b"},
                      "Bash": {"command": f"cat {target}"}}[tool]
        body = {"tool_name": tool, "session_id": "sess-guard", "tool_input": tool_input,
                "cwd": str(work)}
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(work))
        r = subprocess.run(["bash", str(HOOK_PATH)], input=json.dumps(body),
                           capture_output=True, text=True, env=env)
        assert r.returncode == 2 and "[delegation-protected]" in r.stderr, (
            tool, r.returncode, r.stderr)
        # Control: the same hook lets an ordinary file of the worktree through.
        ok = dict(body, tool_name="Read",
                  tool_input={"file_path": str(work / "src" / "app.py")})
        r = subprocess.run(["bash", str(HOOK_PATH)], input=json.dumps(ok),
                           capture_output=True, text=True, env=env)
        assert r.returncode == 0, r.stderr
    finally:
        shutil.rmtree(main, ignore_errors=True)
        shutil.rmtree(holder, ignore_errors=True)


# --- a wrong, late or other session's code writes nothing (TRC-076) ------------------------

@pytest.mark.parametrize("who,wrong_code,minutes", [
    ("sess-1", True, 2),
    ("sess-1", False, 11),
    ("sess-2", False, 2),
])
def test_TRC_076_a_wrong_late_or_other_session_s_confirmation_code_writes_no_delegation(
        tmp_path, monkeypatch, who, wrong_code, minutes):
    from compass_pkg import delegations
    root = project(tmp_path)
    first = _type(root, "--for g5", prompt_id="p-first")
    assert first.block, first
    code = re.search(r"/compass:delegate confirm (\S+)", first.message).group(1)
    typed = "0000-0000-0000-0000" if wrong_code else code
    later = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=minutes)
    monkeypatch.setattr(delegations, "_now", lambda: later)
    answer = _type(root, f"confirm {typed}", session=who, prompt_id="p-second")
    assert answer.block, answer
    assert not list(_store(root).glob("DL-*.yml"))


# --- revoke from a session in any worktree (TRC-078) ---------------------------------------

def test_TRC_078_compass_revoke_dl_n_ends_one_of_several_from_a_session_in(tmp_path):
    from delegation_support import add_issue, add_worktree, repo, set_owner
    from delegation_support import type_ as type_in
    top = repo(tmp_path)
    work = add_worktree(top, "w")
    add_issue(work, "wt-issue", current=True)
    set_owner(work, "pat")
    _write_dl(top, 1, until=None, format=2)
    _write_dl(top, 2, until=None, format=2)
    result = type_in(work, "DL-1", command="compass:revoke", session="sess-w")
    assert not result.block, result
    found = {p.stem: yaml.safe_load(p.read_text(encoding="utf-8"))
             for p in sorted(_store(top).glob("DL-*.yml"))}
    assert found["DL-1"]["revoked_by"] == "jed72" and found["DL-1"]["revoked_at"]
    assert not found["DL-2"].get("revoked_at")


# --- a typed command is answered once (TRC-077) --------------------------------------------

def test_TRC_077_a_typed_compass_delegate_is_answered_once(tmp_path):
    root = project(tmp_path)
    _write_dl(root, 1, prompt_id="P")
    before = _bytes(root)
    answer = _type(root, "", prompt_id="P")
    assert answer.block and "already answered (DL-1)" in answer.message, answer
    assert sorted(p.name for p in _store(root).glob("DL-*.yml")) == ["DL-1.yml"]
    assert {k: v for k, v in _bytes(root).items() if k.startswith("DL-")} == {
        k: v for k, v in before.items() if k.startswith("DL-")}


# --- a delegated checkpoint or decisions approval stays (TRC-099) --------------------------

@pytest.mark.parametrize("record", [
    {"id": "EV-CP-1", "type": "checkpoint-approval", "checkpoint": "plan"},
    {"id": "EV-DEC-1", "type": "artifact-approval", "decisions": True},
])
def test_TRC_099_a_delegated_checkpoint_or_decisions_approval_cannot_be_overruled_with_compass_reject(
        tmp_path, record):
    root = project(tmp_path)
    body = manifest_of(root)
    body["evidence"].append(dict(record, via="delegation", delegation="DL-1",
                                 approved_by_agent="compass:architect"))
    save_manifest(root, body)
    count = len(manifest_of(root)["evidence"])
    answer = _type(root, f"{record['id']} wrong call", command="compass:reject")
    assert answer.block and "compass issue decision set" in answer.message, answer
    assert len(manifest_of(root)["evidence"]) == count
