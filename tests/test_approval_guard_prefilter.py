"""The shell prefilter of the approval guard (issue
`approval-guard-ifs-as-and-delegation-globs`).

The hook starts python3 for the guard only when a call can need it. A glob
character after `.compass/` or after `deleg` in a Bash command can reach the
delegation files, so it must start the guard. An ordinary call must not, or
every shell command would pay for a python3 start.

The test runs a copy of the hook in which the guard module raises. The hook
refuses a call whose guard cannot run (`reader-failed`), so a refusal shows
that the call started the guard and a pass shows that it did not.

Scenario id: `TRC-013` in approval-guard-ifs-as-and-delegation-globs/acceptance-criteria.md
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

from test_pre_tool_hook import HOOK_PATH, _guarded_project  # noqa: E402

# Each command holds a glob character after `.compass/` or `deleg`.
STARTS_GUARD = (
    "cat .compass/deleg*/*",
    "cat .comp*/deleg*/*",
    "ls .compass/work/*",
    "cat .compass/deleg?tions/DL-1.yml",
    "cat .compass/[d]eleg*/*",
    "ls .compass/d*",
    # Letter case is ignored, as macOS opens a path in any case.
    "cat .Compass/Deleg*/*",
)

# None of these can reach the delegation folder through a glob.
STARTS_NO_GUARD = (
    "ls src/*.py",
    "cat docs/*.md",
    "git status",
    "grep -rn approve src",
    "ls",
)


def _broken_copy(tmp_path):
    """A copy of the plugin whose guard module cannot be imported."""
    keep = shutil.ignore_patterns("__pycache__", "*.pyc")
    copy = tmp_path / "plugin"
    for folder in ("hooks", "scripts/lib", "cli"):
        shutil.copytree(ROOT / folder, copy / folder, ignore=keep)
    guard = copy / "cli" / "compass_pkg" / "approval_guard.py"
    guard.write_text("raise RuntimeError('the guard cannot run')\n", encoding="utf-8")
    return copy / "hooks" / "pre-tool.sh"


def _run(hook, project, command):
    body = {"tool_name": "Bash", "session_id": "sess-prefilter",
            "tool_input": {"command": command}, "cwd": str(project)}
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(project), PYTHONDONTWRITEBYTECODE="1")
    started = time.monotonic()
    result = subprocess.run(["bash", str(hook)], input=json.dumps(body),
                            capture_output=True, text=True, env=env)
    return result, time.monotonic() - started


def test_trc_013_prefilter_starts_guard_only_where_needed(tmp_path):
    """Scenario id: `TRC-013` in approval-guard-ifs-as-and-delegation-globs/acceptance-criteria.md"""
    project, _ = _guarded_project()
    try:
        broken = _broken_copy(tmp_path)

        for command in STARTS_GUARD:
            r, _ = _run(broken, project, command)
            assert r.returncode == 2 and "[reader-failed]" in r.stderr, (
                command, r.returncode, r.stderr)

        for command in STARTS_NO_GUARD:
            r, took = _run(broken, project, command)
            assert r.returncode == 0, (command, r.returncode, r.stderr)
            assert took < 2.0, (command, took)

        # Control on the intact hook: the broken copy does not pass the first
        # set merely because every call is refused.
        for command in STARTS_NO_GUARD:
            r, _ = _run(HOOK_PATH, project, command)
            assert r.returncode == 0, (command, r.returncode, r.stderr)
        r, _ = _run(HOOK_PATH, project, "cat .compass/delegations/DL-1.yml")
        assert r.returncode == 2 and "[delegation-protected]" in r.stderr, r.stderr
        # The glob form reaches the same folder and the guard must refuse it
        # with the same code.
        r, _ = _run(HOOK_PATH, project, "cat .compass/deleg*/*")
        assert r.returncode == 2 and "[delegation-protected]" in r.stderr, (
            r.returncode, r.stderr)
    finally:
        shutil.rmtree(project, ignore_errors=True)
