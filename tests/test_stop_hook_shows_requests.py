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
