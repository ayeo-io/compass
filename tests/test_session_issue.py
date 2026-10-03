"""A session's issue can come from `COMPASS_ISSUE`, ahead of the pointer.

`.compass/current-task` names the issue a person is working on. `compass run`
starts unattended sessions in the same project, and those sessions read the
same pointer, so the pre-tool hook judged an unattended session's edits by
the person's issue. `COMPASS_ISSUE` in a session's environment now names its
issue for the hooks and the CLI, and `compass run` sets it for every session
it starts.

Scenario ids: SI-A to SI-E, in the acceptance criteria of the issue
`run-session-issue`.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from conftest import write_red_record

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
PRE = ROOT / "hooks" / "pre-tool.sh"
POST = ROOT / "hooks" / "post-tool.sh"
STOP = ROOT / "hooks" / "stop.sh"


def _issue(root, slug, red):
    task = root / ".compass" / "work" / slug
    task.mkdir(parents=True)
    (task / "delivery-approach.md").write_text("# Route\n")
    (task / "manifest.yml").write_text(yaml.safe_dump({
        "schema_version": "2.0", "issue": slug, "created": "2026-10-03",
        "status": "active",
        "assessment": {"risk": "trivial", "familiarity": "brownfield-mapped",
                       "size": "atomic", "goal": "delivery", "role": "engineer",
                       "labels": []},
        "delivery_approach": "quick-fix",
        "stages": {"define": "light"},
        "scenarios": [{"id": "X-1", "title": "Given a thing, then it works.",
                       "intent": "INT-1", "tests": ["tests/test_x.py"]}],
    }, sort_keys=False))
    if red:
        write_red_record(task)
    return task


@pytest.fixture
def project(tmp_path):
    """Two issues: `ready` has a red on record, `bare` has none. The
    person's pointer names `bare`."""
    root = tmp_path / "proj"
    _issue(root, "ready", red=True)
    _issue(root, "bare", red=False)
    (root / ".compass" / "current-task").write_text("bare\n")
    (root / "src").mkdir()
    return root


def _env(project, issue=None):
    env = {k: v for k, v in os.environ.items() if k != "COMPASS_ISSUE"}
    env["CLAUDE_PROJECT_DIR"] = str(project)
    if issue is not None:
        env["COMPASS_ISSUE"] = issue
    return env


def _hook(hook, project, issue=None, target="src/app.py"):
    payload = {"tool_name": "Edit", "session_id": "s1",
               "tool_input": {"file_path": str(project / target)}}
    return subprocess.run(["bash", str(hook)], input=json.dumps(payload),
                          capture_output=True, text=True,
                          env=_env(project, issue), timeout=30)


def _cli(project, *args, issue=None):
    return subprocess.run([sys.executable, str(CLI), *args], cwd=project,
                          capture_output=True, text=True,
                          env=_env(project, issue), timeout=60)


# --- SI-A: the hook judges the session's issue ----------------------------------

def test_si_a_the_hook_judges_the_issue_the_variable_names(project):
    allowed = _hook(PRE, project, issue="ready")
    assert allowed.returncode == 0, allowed.stderr
    # The pointer's issue has no red; without the variable the edit is
    # refused, which shows the variable decided the first result.
    assert _hook(PRE, project).returncode == 2


def test_si_a_the_variable_blocks_when_its_issue_has_no_red(project):
    (project / ".compass" / "current-task").write_text("ready\n")
    blocked = _hook(PRE, project, issue="bare")
    assert blocked.returncode == 2, blocked.stderr
    assert _hook(PRE, project).returncode == 0


# --- SI-B: the CLI ------------------------------------------------------------------

def test_si_b_a_command_without_an_issue_uses_the_variable(project):
    result = _cli(project, "check", issue="ready")
    assert "'ready'" in result.stdout, result.stdout + result.stderr
    explicit = _cli(project, "check", "--issue", "bare", issue="ready")
    assert "'bare'" in explicit.stdout, explicit.stdout + explicit.stderr


# --- SI-C: a bad variable is refused, not ignored --------------------------------------

@pytest.mark.parametrize("bad", ["missing", "../ready", "a/b"])
def test_si_c_a_bad_variable_is_refused_without_falling_back(project, bad):
    (project / ".compass" / "current-task").write_text("ready\n")
    hook = _hook(PRE, project, issue=bad)
    assert hook.returncode == 2, hook.stderr
    assert "COMPASS_ISSUE" in hook.stderr
    cli = _cli(project, "check", issue=bad)
    assert cli.returncode != 0
    assert "COMPASS_ISSUE" in cli.stderr


# --- SI-D: compass run sets it -----------------------------------------------------------

_STUB = r'''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
Path(os.environ["STUB_SEEN"]).write_text(os.environ.get("COMPASS_ISSUE", "<unset>"))
print(json.dumps({"type": "result", "subtype": "success", "is_error": False,
                  "session_id": "s1", "total_cost_usd": 0.0}))
'''


def test_si_d_compass_run_names_its_issue_in_every_session(project, tmp_path):
    stub = tmp_path / "claude"
    stub.write_text(_STUB)
    stub.chmod(0o755)
    env = _env(project)
    env["STUB_SEEN"] = str(tmp_path / "seen")
    result = subprocess.run(
        [sys.executable, str(CLI), "run", "ready", "--stage", "verify",
         "--stop-file", str(tmp_path / "STOP"), "--claude", str(stub),
         "--max-cycles", "1"],
        cwd=project, capture_output=True, text=True, env=env, timeout=60)
    assert result.returncode in (0, 4), result.stderr
    assert (tmp_path / "seen").read_text() == "ready"
    assert (project / ".compass" / "current-task").read_text() == "bare\n"


# --- SI-E: every reader agrees ------------------------------------------------------------

def test_si_e_the_post_tool_hook_logs_to_the_variables_issue(project):
    (project / "src" / "app.py").write_text("x = 1\n")
    work = project / ".compass" / "work"
    # The hook appends to a devlog that exists; it never creates one.
    for slug in ("ready", "bare"):
        (work / slug / "devlog.md").write_text("# Devlog\n")
    _hook(POST, project, issue="ready")
    assert "edit: src/app.py" in (work / "ready" / "devlog.md").read_text()
    assert (work / "bare" / "devlog.md").read_text() == "# Devlog\n"


def test_si_e_the_stop_hook_checks_the_variable_not_the_pointer(project):
    (project / ".compass" / "current-task").write_text("gone\n")
    result = subprocess.run(["bash", str(STOP)], input="{}", capture_output=True,
                            text=True, env=_env(project, "ready"), timeout=30)
    assert "points at 'gone'" not in result.stdout + result.stderr


def test_si_e_the_receipt_and_status_line_read_the_variable(project):
    receipt = _cli(project, "issue", "receipt", issue="ready")
    assert "ready" in receipt.stdout, receipt.stdout + receipt.stderr
    sys.path.insert(0, str(ROOT / "cli"))
    from compass_pkg import statusline
    old = os.environ.get("COMPASS_ISSUE")
    os.environ["COMPASS_ISSUE"] = "ready"
    try:
        line = statusline.render(str(project))
    finally:
        if old is None:
            os.environ.pop("COMPASS_ISSUE", None)
        else:
            os.environ["COMPASS_ISSUE"] = old
    assert "ready" in line and "bare" not in line


# --- found in review: the suite inside an unattended session ----------------------

def test_si_d_the_suite_passes_inside_a_session_that_sets_the_variable():
    """`compass run` sets the variable for its sessions, and those sessions
    run this suite. The tests build their own projects, so the session's
    issue must not reach them."""
    env = {**os.environ, "COMPASS_ISSUE": "an-issue-this-suite-never-builds"}
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
         "tests/test_hook_enforces_g2.py", "tests/test_hook_failure_matrix.py"],
        cwd=ROOT, capture_output=True, text=True, env=env, timeout=600)
    assert result.returncode == 0, result.stdout[-2000:]


def test_si_c_the_hooks_and_the_cli_read_a_padded_value_alike(project):
    for value in (" ", "ready "):
        assert _hook(PRE, project, issue=value).returncode == 2, repr(value)
        cli = _cli(project, "check", issue=value)
        assert cli.returncode != 0 and "COMPASS_ISSUE" in cli.stderr, repr(value)
