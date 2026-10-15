"""`TRC-F1` - assessment remains mandatory, unchanged.

pre-tool.sh blocks an Edit on a production file when the current issue has no
delivery-approach.md (i.e. assessment did not complete).

The hook reads the hook context from stdin as JSON (Claude Code PreToolUse
format) and inspects the .compass/current-task pointer to find the issue
directory. If the issue directory lacks delivery-approach.md, it exits 2 and
writes a message to stderr naming the missing delivery-approach.md.

This test creates a synthetic Compass project in a tmp directory, sets up
.compass/current-task pointing at an issue without delivery-approach.md, then
invokes hooks/pre-tool.sh with the synthetic tool call JSON.

IMPORTANT NOTE on path design:
  hooks/pre-tool.sh exempts a target file whose basename or project-relative
  path matches an anchored test pattern (so you can always write the failing
  test before any red is on record). This means the target file's own
  basename and project-relative path must not contain the word "test" as a
  substring. We place the target at "src/app.py" to avoid this exemption.
  We also use tempfile.mkdtemp with a "compass-fixture-" prefix, as a
  matching convention - the project directory's own name is not part of
  the match.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from conftest import write_red_record



FRAMEWORK_ROOT = Path(__file__).resolve().parent.parent
HOOK_PATH = FRAMEWORK_ROOT / "hooks" / "pre-tool.sh"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_compass_project(root: Path, slug: str, *, with_route_md: bool) -> Path:
    """Scaffold a minimal Compass project under root.

    Returns the issue directory path.
    """
    compass_dir = root / ".compass"
    work_dir = compass_dir / "work"
    task_dir = work_dir / slug
    task_dir.mkdir(parents=True, exist_ok=True)

    # .compass/current-task points at our slug
    (compass_dir / "current-task").write_text(slug, encoding="utf-8")

    # Optionally create delivery-approach.md
    if with_route_md:
        (task_dir / "delivery-approach.md").write_text(
            "# Route\n\nroute: express\n", encoding="utf-8"
        )

    return task_dir


def _hook_env(project_dir: Path) -> dict:
    """Environment for the hook subprocess."""
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = str(project_dir)
    return env


def _tool_call_json(file_path: str, tool_name: str = "Edit") -> str:
    """Build a Claude Code PreToolUse JSON payload."""
    return json.dumps({
        "tool_name": tool_name,
        "tool_input": {
            "file_path": file_path,
        },
    })


def _fresh_project_dir() -> Path:
    """Return a new temp directory whose absolute path contains no 'test' substring.

    hooks/pre-tool.sh exempts a path matching an anchored test pattern - that
    is the exemption so engineers can always write the failing test.
    pytest's tmp_path fixture always includes the test function name in the
    path (e.g. ".../pytest-0/test_blocks_without_frame0/"), which contains
    "test". We therefore create our own directory whose path is clean.
    """
    d = tempfile.mkdtemp(prefix="compass-fix-")
    return Path(d)


# ---------------------------------------------------------------------------
# `TRC-F1`: hook blocks when delivery-approach.md is absent
# ---------------------------------------------------------------------------

def test_blocks_without_frame():
    """Assessment is still required - hook exits 2 and names missing
    delivery-approach.md.

    Given a fresh issue with no delivery-approach.md
    When any tool tries to Edit a file under the project source (a .py file)
    Then hooks/pre-tool.sh blocks the edit (exit code 2)
    And the block message names the missing delivery-approach.md
    """
    assert HOOK_PATH.is_file(), f"pre-tool.sh not found at {HOOK_PATH}"

    project = _fresh_project_dir()
    try:
        slug = "no-frame-slug"
        _make_compass_project(project, slug, with_route_md=False)

        # Target a recognised production file (.py extension).
        # "src/app.py" - no "test" component anywhere in the path.
        target = str(project / "src" / "app.py")
        assert "test" not in target.lower(), (
            f"Target path must not contain 'test': {target}"
        )
        payload = _tool_call_json(target, tool_name="Edit")

        result = subprocess.run(
            ["bash", str(HOOK_PATH)],
            input=payload,
            capture_output=True,
            text=True,
            env=_hook_env(project),
        )

        # Hook must block
        assert result.returncode == 2, (
            f"Expected exit 2 (block), got {result.returncode}.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        # Block message must name delivery-approach.md
        assert "delivery-approach.md" in result.stderr, (
            f"Expected 'delivery-approach.md' in stderr.\nstderr: {result.stderr}"
        )
    finally:
        shutil.rmtree(str(project), ignore_errors=True)


def test_allows_when_route_md_present_and_red_marker():
    """Hook allows the edit when delivery-approach.md exists and the .red
    marker is set.

    This is the complementary positive case - confirms the hook's basic
    allow-path still works after the F1 regression check.
    """
    assert HOOK_PATH.is_file(), f"pre-tool.sh not found at {HOOK_PATH}"

    project = _fresh_project_dir()
    try:
        slug = "framed-slug"
        task_dir = _make_compass_project(project, slug, with_route_md=True)

        # Drop the .red marker so the hook's green path is satisfied
        write_red_record(task_dir)

        target = str(project / "src" / "app.py")
        payload = _tool_call_json(target, tool_name="Edit")

        result = subprocess.run(
            ["bash", str(HOOK_PATH)],
            input=payload,
            capture_output=True,
            text=True,
            env=_hook_env(project),
        )

        assert result.returncode == 0, (
            f"Expected exit 0 (allow), got {result.returncode}.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    finally:
        shutil.rmtree(str(project), ignore_errors=True)


def test_hook_exits_zero_for_non_code_file():
    """Hook exempts non-production files (e.g. .md docs) from the check."""
    assert HOOK_PATH.is_file(), f"pre-tool.sh not found at {HOOK_PATH}"

    project = _fresh_project_dir()
    try:
        slug = "no-frame-slug"
        _make_compass_project(project, slug, with_route_md=False)

        # Markdown files are always exempt regardless of issue state
        target = str(project / "README.md")
        payload = _tool_call_json(target, tool_name="Edit")

        result = subprocess.run(
            ["bash", str(HOOK_PATH)],
            input=payload,
            capture_output=True,
            text=True,
            env=_hook_env(project),
        )

        assert result.returncode == 0, (
            f"Expected exit 0 (exempt), got {result.returncode}.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    finally:
        shutil.rmtree(str(project), ignore_errors=True)


# ---------------------------------------------------------------------------
# A red recorded with `tdd-red --verified-by` (`TRC-R8-1`, `TRC-R8-2` hook
# side). The hook gates on the .red marker; this widens HOW a red is
# recorded, not how the hook reads it. These guard the marker contract the
# verified-by red plugs into.
# ---------------------------------------------------------------------------

def test_no_red_blocks_wiring_change_baseline():
    """`TRC-R8-1` (baseline): with an assessed issue but no .red marker, the
    hook blocks a production edit - the gap a verified-by red exists to fill
    honestly."""
    project = _fresh_project_dir()
    try:
        _make_compass_project(project, "wire-slug", with_route_md=True)
        target = str(project / "src" / "app.py")
        result = subprocess.run(
            ["bash", str(HOOK_PATH)],
            input=_tool_call_json(target, tool_name="Edit"),
            capture_output=True, text=True, env=_hook_env(project),
        )
        assert result.returncode == 2, result.stderr
    finally:
        shutil.rmtree(project, ignore_errors=True)


def test_verified_by_red_allows_edit():
    """`TRC-R8`-2 (hook side): a recorded red (the .red marker a verified-by red
    drops) allows the production edit."""
    project = _fresh_project_dir()
    try:
        task_dir = _make_compass_project(project, "wire-ok", with_route_md=True)
        write_red_record(task_dir)   # a verified-by red drops this marker
        target = str(project / "src" / "app.py")
        result = subprocess.run(
            ["bash", str(HOOK_PATH)],
            input=_tool_call_json(target, tool_name="Edit"),
            capture_output=True, text=True, env=_hook_env(project),
        )
        assert result.returncode == 0, result.stderr
    finally:
        shutil.rmtree(project, ignore_errors=True)


# ---------------------------------------------------------------------------
# Issue `approve-inside-claude-code`: request files, delegation files and a
# delegated approval's caller (`TRC-D8`, `TRC-F10`, `TRC-F8`; ADR-068
# decision 10, ADR-069 decisions 4 and 8).
# ---------------------------------------------------------------------------

def _guard_run(project, tool, **fields):
    body = {"tool_name": tool, "session_id": "sess-guard",
            "tool_input": fields.pop("tool_input")}
    body.update(fields)
    return subprocess.run(["bash", str(HOOK_PATH)], input=json.dumps(body),
                          capture_output=True, text=True, env=_hook_env(project))


def _guarded_project():
    project = _fresh_project_dir()
    task_dir = _make_compass_project(project, "feature", with_route_md=True)
    write_red_record(task_dir)        # a red on record: only the new guards can refuse
    return project, task_dir


def test_d8_request_files_protected():
    project, task_dir = _guarded_project()
    try:
        request = task_dir / "approval-requests" / "pending" / "1.yml"
        request.parent.mkdir(parents=True)
        request.write_text("number: 1\n", encoding="utf-8")
        refused = [
            ("Edit", {"file_path": str(request)}),
            ("Write", {"file_path": str(task_dir / "approval-requests" / "closed" / "2.yml")}),
            ("Bash", {"command": f"sed -i '' 's/a/b/' {request}"}),
            ("Bash", {"command": "cat .compass/work/feature/approval-requests/pending/1.yml"}),
            ("Bash", {"command": "echo '{}' | hooks/prompt-approval.sh"}),
        ]
        for tool, tool_input in refused:
            r = _guard_run(project, tool, tool_input=tool_input)
            assert r.returncode == 2, (tool, tool_input, r.stderr)
            assert "[approval-request-protected]" in r.stderr, r.stderr
            assert "compass evidence request" in r.stderr, r.stderr
        for command in ("compass evidence request --guardrail G5 --scope 'refund'", "ls"):
            r = _guard_run(project, "Bash", tool_input={"command": command})
            assert r.returncode == 0, (command, r.stderr)
    finally:
        shutil.rmtree(project, ignore_errors=True)


def test_f10_delegation_files_protected():
    project, _ = _guarded_project()
    try:
        delegation = project / ".compass" / "delegations" / "DL-1.yml"
        delegation.parent.mkdir(parents=True)
        delegation.write_text("id: DL-1\n", encoding="utf-8")
        for tool, tool_input in (("Edit", {"file_path": str(delegation)}),
                                 ("Write", {"file_path": str(delegation.parent / "DL-2.yml")}),
                                 ("Bash", {"command": "rm .compass/delegations/DL-1.yml"})):
            r = _guard_run(project, tool, tool_input=tool_input)
            assert r.returncode == 2, (tool, tool_input, r.stderr)
            assert "[delegation-protected]" in r.stderr, r.stderr
    finally:
        shutil.rmtree(project, ignore_errors=True)


def test_f8_delegated_call_needs_matching_agent_type():
    project, _ = _guarded_project()
    approve = "compass evidence approve --check dod-reviewed --delegated --as {}"
    try:
        refused = [
            # The main agent: neither field.
            (approve.format("compass:architect"), {}),
            # Another plugin subagent.
            (approve.format("compass:architect"),
             {"agent_type": "compass:builder", "agent_id": "a1"}),
            # An agent id with no agent type, or an empty one, is not the main agent.
            (approve.format("main"), {"agent_id": "a2"}),
            (approve.format("main"), {"agent_id": "a3", "agent_type": ""}),
            # The name must match exactly, plugin prefix included.
            (approve.format("architect"),
             {"agent_type": "compass:architect", "agent_id": "a4"}),
            # A delegated call must say who it is.
            ("compass evidence approve --check dod-reviewed --delegated",
             {"agent_type": "compass:architect", "agent_id": "a5"}),
        ]
        for command, who in refused:
            r = _guard_run(project, "Bash", tool_input={"command": command}, **who)
            assert r.returncode == 2, (command, who, r.stderr)
            assert "[delegation-caller-mismatch]" in r.stderr, r.stderr
        allowed = [
            (approve.format("compass:architect"),
             {"agent_type": "compass:architect", "agent_id": "a6"}),
            (approve.format("main"), {}),
            # A session started with `--agent X` reports X and no agent id.
            (approve.format("compass:architect"), {"agent_type": "compass:architect"}),
        ]
        for command, who in allowed:
            r = _guard_run(project, "Bash", tool_input={"command": command}, **who)
            assert r.returncode == 0, (command, who, r.stderr)
    finally:
        shutil.rmtree(project, ignore_errors=True)


def test_f8_cli_refuses_an_agent_the_delegation_does_not_name(tmp_path):
    """The CLI half of `TRC-F8`: a call that reaches the CLI with another
    agent's name is refused because the delegation does not name it."""
    import datetime
    import sys
    sys.path.insert(0, str(FRAMEWORK_ROOT / "tests"))
    from approval_support import CHECK, SLUG, event, project, run, task_dir
    from compass_pkg import prompt_approval
    root = project(tmp_path)
    until = (datetime.datetime.now().astimezone() + datetime.timedelta(hours=2))
    done = prompt_approval.handle(
        event(root, command="compass:delegate",
              args=f"compass:architect until {until:%H:%M}"), {},
        plugin_root=str(FRAMEWORK_ROOT))
    assert not done.block, done
    before = (task_dir(root) / "manifest.yml").read_bytes()
    code, out, err = run(root, "evidence", "approve", "--issue", SLUG, "--check", CHECK,
                         "--scope", "x", "--delegated", "--as", "compass:builder")
    assert code != 0 and "no delegation in force names compass:builder" in out + err
    assert (task_dir(root) / "manifest.yml").read_bytes() == before
