"""A session is told when another session moved the issue pointer.

Two interactive sessions share `.compass/current-task`. When one session
moves it, the other's edits were judged against an issue it was not working
on, with no word said. The pre-tool hook now records each Claude Code
session's issue by its session id, and refuses an edit once when the pointer
no longer names that session's issue. `compass issue use <slug>` confirms
which issue the session works on.

Scenario ids: CL-A to CL-D, in the acceptance criteria of the issue
`pointer-lease` (GitHub issue #314).
"""
from __future__ import annotations

import datetime
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from test_session_issue import _issue

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
PRE = ROOT / "hooks" / "pre-tool.sh"


@pytest.fixture
def project(tmp_path):
    """Two issues, `ex` and `why`, each with a red on record; the pointer
    names `ex`."""
    root = tmp_path / "proj"
    _issue(root, "ex", red=True)
    _issue(root, "why", red=True)
    (root / ".compass" / "current-task").write_text("ex\n")
    (root / "src").mkdir()
    return root


def _env(project, extra=None):
    env = {k: v for k, v in os.environ.items()
           if k not in ("COMPASS_ISSUE", "CLAUDE_CODE_SESSION_ID")}
    env["CLAUDE_PROJECT_DIR"] = str(project)
    env.update(extra or {})
    return env


def _edit(project, session, extra=None):
    payload = {"tool_name": "Edit",
               "tool_input": {"file_path": str(project / "src" / "app.py")}}
    if session is not None:
        payload["session_id"] = session
    return subprocess.run(["bash", str(PRE)], input=json.dumps(payload),
                          capture_output=True, text=True,
                          env=_env(project, extra), timeout=30)


def _use(project, session, slug):
    return subprocess.run([sys.executable, str(CLI), "issue", "use", slug],
                          cwd=project, capture_output=True, text=True,
                          env=_env(project, {"CLAUDE_CODE_SESSION_ID": session}),
                          timeout=60)


def _pointer(project):
    return (project / ".compass" / "current-task").read_text().strip()


# --- CL-A: a moved pointer is told ------------------------------------------------

def test_cl_a_an_edit_after_another_session_moved_the_pointer_is_refused(project):
    assert _edit(project, "session-a").returncode == 0
    assert _use(project, "session-b", "why").returncode == 0
    refused = _edit(project, "session-a")
    assert refused.returncode == 2, refused.stderr
    assert "pointer-moved" in refused.stderr
    assert "'ex'" in refused.stderr and "'why'" in refused.stderr
    assert "compass issue use" in refused.stderr


# --- CL-B: confirming ----------------------------------------------------------------

def test_cl_b_issue_use_confirms_either_issue(project):
    assert _edit(project, "session-a").returncode == 0
    assert _use(project, "session-b", "why").returncode == 0
    assert _edit(project, "session-a").returncode == 2
    assert _use(project, "session-a", "ex").returncode == 0
    assert _pointer(project) == "ex"
    assert _edit(project, "session-a").returncode == 0
    # Now session B's issue moved under it, and B is told in turn.
    assert _edit(project, "session-b").returncode == 2
    assert _use(project, "session-b", "ex").returncode == 0
    assert _edit(project, "session-b").returncode == 0


def test_cl_b_issue_use_refuses_an_issue_that_does_not_exist(project):
    result = _use(project, "session-a", "nope")
    assert result.returncode != 0
    assert _pointer(project) == "ex"


# --- CL-C: the session that moved it is not refused --------------------------------------

def test_cl_c_the_session_that_moved_the_pointer_edits_freely(project):
    assert _edit(project, "session-b").returncode == 0
    assert _use(project, "session-b", "why").returncode == 0
    assert _edit(project, "session-b").returncode == 0


def test_cl_c_quick_fix_start_records_the_new_issue_for_its_session(project):
    assert _edit(project, "session-c").returncode == 0
    started = subprocess.run(
        [sys.executable, str(CLI), "quick-fix", "start", "zed",
         "--risk", "trivial - one line", "--familiarity", "brownfield-mapped - known",
         "--size", "atomic - one line", "--intent", "INT-1",
         "--scenario-id", "Z-1", "--scenario", "Given a thing, then it works.",
         "--test", "tests/test_x.py"],
        cwd=project, capture_output=True, text=True,
        env=_env(project, {"CLAUDE_CODE_SESSION_ID": "session-c"}), timeout=60)
    assert started.returncode == 0, started.stdout + started.stderr
    assert _pointer(project) == "zed"
    # The new issue has no red yet, so the hook refuses for that reason,
    # never for a moved pointer.
    result = _edit(project, "session-c")
    assert "pointer-moved" not in result.stderr


def test_cl_c_the_assess_and_resume_instructions_set_the_pointer_by_issue_use():
    for rel in ("approaches/assess-procedure.md", "commands/resume.md", "agents/router.md"):
        text = (ROOT / rel).read_text()
        assert "compass issue use" in text, rel


# --- CL-D: where the lease steps aside --------------------------------------------------------

def test_cl_d_the_session_issue_variable_disables_the_lease(project):
    assert _edit(project, "session-a").returncode == 0
    assert _use(project, "session-b", "why").returncode == 0
    result = _edit(project, "session-a", {"COMPASS_ISSUE": "ex"})
    assert result.returncode == 0, result.stderr


def test_cl_d_no_session_id_and_a_stale_record_refuse_nothing(project):
    assert _edit(project, None).returncode == 0
    assert _edit(project, "session-a").returncode == 0
    table = project / ".compass" / "sessions.json"
    data = json.loads(table.read_text())
    old = (datetime.datetime.now(datetime.timezone.utc)
           - datetime.timedelta(hours=13)).isoformat(timespec="seconds")
    data["session-a"]["at"] = old
    table.write_text(json.dumps(data))
    assert _use(project, "session-b", "why").returncode == 0
    assert _edit(project, "session-a").returncode == 0


def test_cl_d_a_lease_check_that_crashes_refuses_the_edit(project):
    """Hooks fail closed: a lease check that cannot run refuses, naming
    what failed, rather than letting the edit through unchecked."""
    (project / ".compass" / "sessions.json").mkdir()
    result = _edit(project, "session-a")
    assert result.returncode == 2, result.stderr
    assert "reader-failed" in result.stderr and "session" in result.stderr


# --- the session table kept tidy (issue #318) ----------------------------------

def test_st2_concurrent_records_are_all_kept(project):
    sys.path.insert(0, str(ROOT / "cli"))
    from concurrent.futures import ProcessPoolExecutor
    compass_dir = str(project / ".compass")
    with ProcessPoolExecutor(max_workers=8) as pool:
        list(pool.map(_record_one, [(compass_dir, f"s{i}") for i in range(40)]))
    table = json.loads((project / ".compass" / "sessions.json").read_text())
    assert len(table) == 40


def _record_one(args):
    sys.path.insert(0, str(ROOT / "cli"))
    from compass_pkg.session_lease import record
    record(args[0], args[1], "ex")


def test_st2_stale_records_are_dropped_when_the_table_is_written(project):
    assert _edit(project, "old-session").returncode == 0
    table = project / ".compass" / "sessions.json"
    data = json.loads(table.read_text())
    data["old-session"]["at"] = (datetime.datetime.now(datetime.timezone.utc)
                                 - datetime.timedelta(hours=13)).isoformat(timespec="seconds")
    table.write_text(json.dumps(data))
    assert _edit(project, "new-session").returncode == 0
    assert "old-session" not in json.loads(table.read_text())


def test_st2_the_table_is_ignored_by_git_in_any_project(project):
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    assert _edit(project, "session-a").returncode == 0
    ignored = subprocess.run(["git", "check-ignore", "-q", ".compass/sessions.json"],
                             cwd=project)
    assert ignored.returncode == 0


def test_st2_a_pointer_moved_refusal_counts_against_the_sessions_issue(project):
    assert _edit(project, "session-a").returncode == 0
    assert _use(project, "session-b", "why").returncode == 0
    assert _edit(project, "session-a").returncode == 2
    log = (project / ".compass" / "interruptions.log").read_text().splitlines()
    assert log and log[-1].split("\t")[1] == "ex", log


def test_st2_a_planted_record_cannot_point_outside_the_work_folder(project):
    """A record's issue name comes from a file; it is joined onto the work
    folder only when it is one path segment."""
    assert _edit(project, "session-a").returncode == 0
    table = project / ".compass" / "sessions.json"
    data = json.loads(table.read_text())
    data["session-a"]["issue"] = "../side"
    table.write_text(json.dumps(data))
    (project / ".compass" / "side").mkdir()
    result = _edit(project, "session-a")
    assert result.returncode == 2, result.stderr
    log = (project / ".compass" / "interruptions.log").read_text().splitlines()
    assert log[-1].split("\t")[1] == "ex", log
