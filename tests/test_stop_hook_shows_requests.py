"""The Stop hook shows the person each unshown approval request (issue
`approve-inside-claude-code`, ADR-068 decision 1).

A measurement on Claude Code 2.1.300 (ADR-068) showed that a Stop hook's `systemMessage` is
shown to the person under the reply, and that the model does not see it.

Scenario id: `TRC-B2`. The test name starts with it.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "hooks" / "stop.sh"
sys.path.insert(0, str(ROOT / "tests"))

from approval_support import SLUG, pending_dir, project, read_request, task_dir  # noqa: E402


def _stop(root):
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(root),
           "LANG": "C.UTF-8", "CLAUDE_PROJECT_DIR": str(root), "PYTHONDONTWRITEBYTECODE": "1"}
    body = {"session_id": "sess-1", "cwd": str(root), "hook_event_name": "Stop",
            "stop_hook_active": False}
    r = subprocess.run(["bash", str(HOOK)], input=json.dumps(body), cwd=root, env=env,
                       capture_output=True, text=True, timeout=60)
    return r.returncode, r.stdout, r.stderr


def _stop_from(project_dir, stdin, run_in):
    """Run the hook with `CLAUDE_PROJECT_DIR` set to `project_dir` (or unset
    when None), the given raw stdin, in the folder `run_in`."""
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(run_in),
           "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"}
    if project_dir is not None:
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)
    r = subprocess.run(["bash", str(HOOK)], input=stdin, cwd=run_in, env=env,
                       capture_output=True, text=True, timeout=60)
    return r.returncode, r.stdout, r.stderr


def _body(cwd):
    return json.dumps({"session_id": "sess-1", "cwd": cwd, "hook_event_name": "Stop",
                       "stop_hook_active": False})


# --- A session in a git worktree still shows the request (`TRC-001`) ------------------------

def test_trc_001_request_shown_when_project_dir_has_no_compass(tmp_path):
    from compass_pkg import approval_requests
    root = project(tmp_path / "real")
    empty = tmp_path / "empty"
    empty.mkdir()
    approval_requests.write(str(task_dir(root)), "guardrail", "G5", "refund table migration")
    code, out, err = _stop_from(empty, _body(str(root)), empty)
    assert code == 0, err
    assert "request 1" in json.loads(out)["systemMessage"], out
    req = read_request(pending_dir(root) / "1.yml")
    assert req["shown_at"] and req["shown_digest"] == approval_requests.digest(req)


def test_trc_001_request_shown_when_project_dir_is_another_compass_project(tmp_path):
    from compass_pkg import approval_requests
    root = project(tmp_path / "real")
    other = project(tmp_path / "other")
    approval_requests.write(str(task_dir(root)), "guardrail", "G5", "refund table migration")
    code, out, err = _stop_from(other, _body(str(root)), other)
    assert code == 0, err
    assert "request 1" in json.loads(out)["systemMessage"], out
    assert read_request(pending_dir(root) / "1.yml")["shown_at"]


def test_trc_001_cwd_in_a_subfolder_finds_the_project(tmp_path):
    from compass_pkg import approval_requests
    root = project(tmp_path / "real")
    empty = tmp_path / "empty"
    empty.mkdir()
    sub = root / "src" / "deep"
    sub.mkdir(parents=True)
    approval_requests.write(str(task_dir(root)), "guardrail", "G5", "refund table migration")
    code, out, err = _stop_from(empty, _body(str(sub)), empty)
    assert code == 0, err
    assert "request 1" in json.loads(out)["systemMessage"], out


def test_trc_001_no_compass_anywhere_prints_nothing(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    plain = tmp_path / "plain"
    plain.mkdir()
    code, out, err = _stop_from(empty, _body(str(plain)), empty)
    assert code == 0 and out == "", (out, err)


def test_trc_001_project_dir_itself_unchanged_when_cwd_differs(tmp_path):
    from compass_pkg import approval_requests
    root = project(tmp_path / "real")
    plain = tmp_path / "plain"
    plain.mkdir()
    approval_requests.write(str(task_dir(root)), "guardrail", "G5", "refund table migration")
    code, out, err = _stop_from(root, _body(str(plain)), root)
    assert code == 0, err
    assert "request 1" in json.loads(out)["systemMessage"], out


def test_trc_001_requests_of_both_roots_are_joined(tmp_path):
    from compass_pkg import approval_requests
    root = project(tmp_path / "real")
    other = project(tmp_path / "other")
    approval_requests.write(str(task_dir(root)), "guardrail", "G5", "from the worktree")
    approval_requests.write(str(task_dir(other)), "guardrail", "G5", "from the start folder")
    code, out, err = _stop_from(other, _body(str(root)), other)
    assert code == 0, err
    message = json.loads(out)["systemMessage"]
    assert "from the worktree" in message and "from the start folder" in message, message


def test_trc_001_malformed_stdin_changes_nothing(tmp_path):
    from compass_pkg import approval_requests
    root = project(tmp_path / "real")
    empty = tmp_path / "empty"
    empty.mkdir()
    approval_requests.write(str(task_dir(root)), "guardrail", "G5", "refund table migration")
    for stdin in ("not json", _body(7), json.dumps({"cwd": ["x"]}), json.dumps([1]), ""):
        code, out, err = _stop_from(empty, stdin, empty)
        assert code == 0 and out == "", (stdin, out, err)
    assert not read_request(pending_dir(root) / "1.yml").get("shown_at")
    # With the project as CLAUDE_PROJECT_DIR the bad stdin still shows it.
    code, out, err = _stop_from(root, "not json", root)
    assert code == 0 and "request 1" in json.loads(out)["systemMessage"], (out, err)


# --- Compass shows a pending request at the end of the turn (`TRC-B2`) ----------------------

def test_b2_stop_hook_shows_unshown_request(tmp_path):
    from compass_pkg import approval_requests
    root = project(tmp_path)
    approval_requests.write(str(task_dir(root)), "guardrail", "G5", "refund table migration")
    code, out, err = _stop(root)
    assert code == 0, err
    message = json.loads(out)["systemMessage"]
    for needle in ("request 1", "guardrail 5 sign-off", SLUG, "generation 1", "payments",
                   "migrations", "the agent's description: \"refund table migration\"",
                   "/compass:approve", "/compass:reject"):
        assert needle in message, (needle, message)
    req = read_request(pending_dir(root) / "1.yml")
    assert req["shown_at"] and req["shown_digest"] == approval_requests.digest(req)
    # Shown once: the next turn's end adds nothing for it.
    code, out, err = _stop(root)
    assert code == 0 and "request 1" not in out, out
    # A request of another issue is not shown in this session.
    other = root / ".compass" / "work" / "other"
    other.mkdir()
    (other / "manifest.yml").write_text((task_dir(root) / "manifest.yml").read_text())
    approval_requests.write(str(other), "guardrail", "G5", "elsewhere")
    code, out, err = _stop(root)
    assert "elsewhere" not in out, out
