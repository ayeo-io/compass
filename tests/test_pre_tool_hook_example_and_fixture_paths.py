"""Eval fixture code is not production code, and nearby code still is.

`evals/<group>/<name>/seed/` holds input that the eval harness copies into a
sandbox and never runs in place, so an edit of it needs no failing test.
`examples/`, `cli/vendor/`, `.github/scripts/`, `evals/` outside `seed/`,
`src/examples/` and `db/seed/` stay guarded: `enforcement.code_globs` only
ratchets up (ADR-011), and each of them can run for a user or for the
project's own delivery.

The hook is run for real, with an assessed issue and no failing test on record.

Scenario ids: see hooks-comment-only-edits-and-prose/acceptance-criteria.md.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from test_session_issue import _issue

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "hooks" / "pre-tool.sh"


def _project(tmp_path):
    root = tmp_path / "proj"
    _issue(root, "issue-a", red=False)
    (root / ".compass" / "current-task").write_text("issue-a\n")
    return root


def _edit_code(root, rel):
    """An Edit that changes a line of code of `rel`. The file does not exist:
    these scenarios judge the path, and a code change is never a comment-only
    edit."""
    payload = {"tool_name": "Edit", "tool_input": {
        "file_path": str(root / rel), "old_string": "x = 1",
        "new_string": "x = 2"}}
    env = {k: v for k, v in os.environ.items()
           if k not in ("COMPASS_ISSUE", "CLAUDE_CODE_SESSION_ID")
           and not k.startswith("GIT_")}
    env["CLAUDE_PROJECT_DIR"] = str(root)
    return subprocess.run(["bash", str(HOOK)], input=json.dumps(payload),
                          capture_output=True, text=True, env=env,
                          cwd=str(root), timeout=60)


def _refused(result):
    assert result.returncode == 2, result.stderr
    assert result.stderr.rstrip().endswith("[no-red-on-record]"), result.stderr


def test_eval_fixture_file_needs_no_failing_test(tmp_path):
    """Scenario id: `TRC-023` in hooks-comment-only-edits-and-prose/acceptance-criteria.md"""
    root = _project(tmp_path)
    r = _edit_code(root, "evals/scenarios/example/seed/src/playlist.py")

    assert r.returncode == 0, r.stderr
    assert r.stderr == "", r.stderr


def test_path_that_leaves_the_fixture_folder_is_still_guarded(tmp_path):
    """Scenario id: `TRC-022` in hooks-comment-only-edits-and-prose/acceptance-criteria.md"""
    root = _project(tmp_path)
    r = _edit_code(root, "evals/scenarios/example/seed/../../../../cli/"
                         "compass_pkg/routing.py")

    _refused(r)


@pytest.mark.parametrize("rel", [
    "examples/bdd-adapters/pytest-bdd/src/reset_password.py",
    "cli/vendor/yaml/__init__.py",
    ".github/scripts/check_mutation_runner.py",
    "evals/judge.py",
    "src/examples/helpers.py",
    "db/seed/load.py",
])
def test_code_near_the_exempt_paths_is_still_guarded(tmp_path, rel):
    """Scenario id: `TRC-024` in hooks-comment-only-edits-and-prose/acceptance-criteria.md"""
    root = _project(tmp_path)

    _refused(_edit_code(root, rel))
