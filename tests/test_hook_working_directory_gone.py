"""The pre-tool hook still judges a call when the session's directory is gone.

Claude Code lets a call run when the hook exits with anything other than 2.
`hooks/pre-tool.sh` read its working directory with `$(pwd)`; in a removed
directory that failed and ended the script with exit 1, so the edit ran with no
check. The hook now falls back to `CLAUDE_PROJECT_DIR`, or refuses with
`working-directory-gone` when it is unset and the call names a file inside a
Compass project.

Each test starts the hook from a directory that was removed after the shell
entered it. Bash prints its own `shell-init:` and `chdir:` lines on standard
error in that state; the tests drop them, so "prints nothing" means the hook
printed nothing of its own.

Scenario ids are in hook-exits-refuse-with-two/acceptance-criteria.md.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
BLOCK = 2
ALLOW = 0

# Starts a shell in a new directory, removes it, then runs the hook by
# absolute path. `"$1"` is the hook path.
REMOVED_DIR_WRAPPER = 'd="$(mktemp -d)" && cd "$d" && rmdir "$d" && bash "$1"'

SPINE = """schema_version: "2.0"
task: "guarded"
created: "2026-08-12"
status: active
assessment:
  risk: contained
  familiarity: greenfield
  size: small
  goal: delivery
  role: engineer
  labels: []
delivery_approach: quick-fix
topology: solo
policy_rules_fired: []
stages: {frame: full, specify: light, clarify: collapsed, plan: collapsed,
  distribute: skipped, build: full, verify: light, land: light}
evidence: []
gates: []
scenarios: []
changed_files: []
claims: []
follow_ups: []
reassessments: []
friction: []
"""


@pytest.fixture(scope="module")
def project(tmp_path_factory):
    """A copy of this repository with one active issue and no `.red` marker."""
    dest = tmp_path_factory.mktemp("wdg") / "repo"
    shutil.copytree(
        ROOT, dest,
        ignore=shutil.ignore_patterns(
            ".git", "__pycache__", ".pytest_cache", "dist", "node_modules"),
        symlinks=True,
    )
    work = dest / ".compass" / "work" / "guarded"
    work.mkdir(parents=True, exist_ok=True)
    (work / "manifest.yml").write_text(SPINE, encoding="utf-8")
    (work / "delivery-approach.md").write_text(
        "# Delivery approach - guarded\n", encoding="utf-8")
    (dest / ".compass" / "current-task").write_text("guarded\n", encoding="utf-8")
    (dest / ".compass" / "config.yml").write_text(
        "version: 1.0.0\nmode: enforced\n", encoding="utf-8")
    for marker in (".red", ".acceptance"):
        (work / marker).unlink(missing_ok=True)
    return dest


def _event(tool, **tool_input):
    return json.dumps({"tool_name": tool, "tool_input": tool_input})


_SHIM_DIR = []


@pytest.fixture(scope="module", autouse=True)
def python_that_needs_a_directory(tmp_path_factory):
    """Put a `python3` first on PATH that fails in a removed directory.

    A pyenv shim does this on some machines and a plain interpreter does not,
    so without it the tests would not show whether the hook gives its readers
    a directory that exists.
    """
    shim_dir = tmp_path_factory.mktemp("shim")
    shim = shim_dir / "python3"
    shim.write_text(
        "#!/bin/sh\n"
        "pwd >/dev/null 2>&1 || { echo 'cannot change working directory' >&2;"
        " exit 1; }\n"
        f'exec "{sys.executable}" "$@"\n', encoding="utf-8")
    shim.chmod(0o755)
    _SHIM_DIR[:] = [str(shim_dir)]
    yield
    _SHIM_DIR[:] = []


def _env(project_dir):
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}
    if _SHIM_DIR:
        env["PATH"] = _SHIM_DIR[0] + os.pathsep + env.get("PATH", "")
    if project_dir is not None:
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)
    return env


def _own_lines(stderr):
    """Standard error without the lines bash prints for the removed directory."""
    return "\n".join(
        line for line in stderr.splitlines()
        if not line.startswith(("shell-init:", "chdir:"))
    )


def _run(hook_root, event, project_dir, removed):
    hook = str(hook_root / "hooks" / "pre-tool.sh")
    if removed:
        cmd = ["bash", "-c", REMOVED_DIR_WRAPPER, "wrapper", hook]
        cwd = None
    else:
        cmd = ["bash", hook]
        cwd = str(hook_root)
    return subprocess.run(
        cmd, input=event, cwd=cwd, capture_output=True, text=True,
        timeout=120, env=_env(project_dir),
    )


def _code(stderr):
    found = re.findall(r"\[([a-z0-9-]+)\]\s*$", _own_lines(stderr).strip())
    return found[-1] if found else None


def test_wdg_1_removed_directory_with_project_variable_refuses_as_usual(project):
    """Scenario id: `TRC-001` in hook-exits-refuse-with-two/acceptance-criteria.md"""
    event = _event("Edit", file_path=str(project / "cli" / "compass_pkg" / "core.py"))
    normal = _run(project, event, project, removed=False)
    assert normal.returncode == BLOCK and _code(normal.stderr), normal.stderr

    gone = _run(project, event, project, removed=True)
    assert gone.returncode == BLOCK, (gone.returncode, gone.stderr)
    assert _code(gone.stderr) == _code(normal.stderr), gone.stderr


def test_wdg_2_removed_directory_with_project_variable_allows_as_usual(project):
    """Scenario id: `TRC-002` in hook-exits-refuse-with-two/acceptance-criteria.md"""
    event = _event("Edit", file_path=str(project / "docs" / "notes.md"))
    normal = _run(project, event, project, removed=False)
    assert normal.returncode == ALLOW, normal.stderr

    gone = _run(project, event, project, removed=True)
    assert gone.returncode == ALLOW, (gone.returncode, gone.stderr)
    assert _own_lines(gone.stderr).strip() == ""


def test_wdg_3_no_project_variable_and_a_project_path_refuses_with_the_new_code(project):
    """Scenario id: `TRC-003` in hook-exits-refuse-with-two/acceptance-criteria.md"""
    event = _event("Edit", file_path=str(project / "cli" / "compass_pkg" / "core.py"))
    gone = _run(project, event, None, removed=True)
    assert gone.returncode == BLOCK, (gone.returncode, gone.stderr)
    assert _code(gone.stderr) == "working-directory-gone", gone.stderr


def test_wdg_4_no_project_in_view_is_allowed(project):
    """Scenario id: `TRC-004` in hook-exits-refuse-with-two/acceptance-criteria.md"""
    gone = _run(project, _event("Bash", command="ls"), None, removed=True)
    assert gone.returncode == ALLOW, (gone.returncode, gone.stderr)
    assert _own_lines(gone.stderr).strip() == ""


def test_wdg_5_repository_that_never_opted_in_is_allowed(project, tmp_path):
    """Scenario id: `TRC-005` in hook-exits-refuse-with-two/acceptance-criteria.md"""
    plain = tmp_path / "plain"
    (plain / "src").mkdir(parents=True)
    event = _event("Edit", file_path=str(plain / "src" / "app.py"))
    gone = _run(project, event, plain, removed=True)
    assert gone.returncode == ALLOW, (gone.returncode, gone.stderr)
    assert _own_lines(gone.stderr).strip() == ""


SAFETY_CONTRACT = ROOT / "docs" / "safety-contract.md"
SECTION_HEADING = (
    "### The pre-tool hook refuses on a removed working directory, "
    "and three exits still let a call through"
)


def _section():
    text = SAFETY_CONTRACT.read_text(encoding="utf-8")
    assert SECTION_HEADING in text, "the contract has no section on the exits"
    body = text.split(SECTION_HEADING, 1)[1]
    section = re.split(r"\n#{2,3} ", body, maxsplit=1)[0]
    # One line, so a phrase is found wherever the document wraps it.
    return " ".join(section.split())


def test_wdg_6_contract_states_the_remaining_exits():
    """Scenario id: `TRC-008` in hook-exits-refuse-with-two/acceptance-criteria.md"""
    section = _section()
    lowered = section.lower()
    for phrase in ("own folder", "helper script", "time-out"):
        assert phrase in lowered, phrase
    assert "unreadable, or fails when it runs" in section
    assert "standard error is closed" not in lowered
    assert "exits 127" in section
    assert "declared limit" in section


def test_wdg_7_contract_states_the_removed_directory_rules():
    """Scenario id: `TRC-009` in hook-exits-refuse-with-two/acceptance-criteria.md"""
    section = _section()
    assert "CLAUDE_PROJECT_DIR" in section
    assert "working-directory-gone" in section
    assert "allows" in section and "no project" in section


def test_wdg_8_contract_gives_the_reason_for_no_catch_all():
    """Scenario id: `TRC-010` in hook-exits-refuse-with-two/acceptance-criteria.md"""
    section = _section()
    assert "3.2.57" in section
    assert "unbound" in section
    assert "status 0" in section


def test_wdg_10_pwd_naming_a_missing_directory_counts_as_gone(project):
    """`pwd` can succeed in a removed directory on some platforms.

    The stub prints a path that does not exist, as a stale `pwd` would. Only
    the `[ -d "$SESSION_DIR" ]` clause in the hook notices.
    """
    # Stale only in the session's directory, so the hook's other uses of
    # `pwd` (finding its own folder) still work.
    stub = (
        'pwd() { if [ "$PWD" = "$STUB_CWD" ]; then echo /no/such/directory; '
        'else builtin pwd; fi; }; export -f pwd; exec bash "$1"')
    hook = str(project / "hooks" / "pre-tool.sh")
    event = _event("Edit", file_path=str(project / "cli" / "compass_pkg" / "core.py"))
    gone = subprocess.run(
        ["bash", "-c", stub, "wrapper", hook], input=event, cwd=str(project),
        capture_output=True, text=True, timeout=120,
        env={**_env(None), "STUB_CWD": str(project)})
    assert gone.returncode == BLOCK, (gone.returncode, gone.stderr)
    assert "[working-directory-gone]" in gone.stderr, gone.stderr


def test_wdg_9_existing_directory_is_judged_as_before(project):
    """Scenario id: `TRC-011` in hook-exits-refuse-with-two/acceptance-criteria.md

    Pins behaviour that exists before the change, so it passes before and
    after; it cannot be red on the real hook.
    """
    refused = _run(
        project,
        _event("Edit", file_path=str(project / "cli" / "compass_pkg" / "core.py")),
        project, removed=False)
    assert refused.returncode == BLOCK
    lines = refused.stderr.strip().splitlines()
    assert len(lines) == 3, refused.stderr
    assert lines[0].startswith("Blocked") and lines[1].startswith("Why")
    assert lines[2].startswith("Fix") and lines[2].endswith("]")

    allowed = _run(
        project, _event("Edit", file_path=str(project / "docs" / "notes.md")),
        project, removed=False)
    assert allowed.returncode == ALLOW
    assert allowed.stderr.strip() == ""
