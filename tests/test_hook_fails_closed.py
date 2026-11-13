"""The pre-tool hook fails closed when it cannot read its own state.

`hooks/pre-tool.sh` enforces acceptance-before-code by reading the issue
manifest through `scripts/lib/compass-python.sh`. That helper used `exec`, which
replaces the calling shell - including the shell holding the call site's
`|| true`. So when the vendored PyYAML could not be resolved, the hook aborted
under `set -euo pipefail` with exit 3 and printed nothing, and because the
hook's contract is block = 2 and allow = 0, the runtime read exit 3 as a
non-blocking error and let the edit through.

Measured before the fix, same input, same issue:

    cli/vendor/yaml intact      -> exit 2, 1013 bytes of refusal on stderr
    cli/vendor/yaml moved away  -> exit 3, zero bytes on both streams

ADR-013 (vendored third-party code) covers the earlier form of this defect.

Removing `exec` alone is not enough. It restores the `|| true` and returns the
hook to failing *quietly*, which is where it was before and is still wrong. A
guardrail that cannot read its own state must fail closed and say why, which
is what these tests pin.

Scenario ids: see the issue's acceptance criteria.
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent

# The hook's I/O contract, stated in hooks/pre-tool.sh's own header.
BLOCK = 2
ALLOW = 0

EDIT_EVENT = json.dumps(
    {"tool_name": "Edit", "tool_input": {"file_path": "cli/compass_pkg/core.py"}}
)

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


@pytest.fixture
def project(tmp_path):
    """A copy of this repository with one active issue and no `.red` marker.

    Copied rather than cloned so the vendored tree can be broken without
    touching the working tree, and so the copy carries uncommitted work.
    """
    dest = tmp_path / "repo"
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
    # No `.red` marker: the hook must block an edit to production code.
    for marker in (".red", ".acceptance"):
        (work / marker).unlink(missing_ok=True)
    return dest


def _run_hook(project):
    result = subprocess.run(
        ["bash", str(project / "hooks" / "pre-tool.sh")],
        input=EDIT_EVENT, cwd=str(project),
        capture_output=True, text=True, timeout=120,
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(project)},
    )
    return result


def test_the_hook_blocks_when_it_can_read_the_spine(project):
    """The control. Without this, a broken-vendor test proves nothing."""
    result = _run_hook(project)
    assert result.returncode == BLOCK, (
        f"the hook did not block an edit to production code with no red on "
        f"record - so the broken-vendor case below has no baseline.\n"
        f"exit={result.returncode}\n{result.stdout}{result.stderr}"
    )


def test_the_hook_fails_closed_when_the_vendored_reader_cannot_start(project):
    """The defect: a broken vendor must not let the edit through."""
    shutil.rmtree(project / "cli" / "vendor")

    result = _run_hook(project)
    combined = result.stdout + result.stderr

    assert result.returncode != ALLOW, (
        f"the hook allowed an edit it could not check - the guardrail is off."
        f"\nexit={result.returncode}\n{combined}"
    )
    assert result.returncode == BLOCK, (
        f"the hook exited {result.returncode}, which is neither block ({BLOCK}) "
        f"nor allow ({ALLOW}). The runtime treats anything else as a "
        f"non-blocking error, so the edit proceeds.\n{combined}"
    )


def test_the_hook_says_why_it_could_not_check(project):
    """Failing closed in silence is only half the fix.

    The CLI already emits "this install is incomplete ... at <absolute path>".
    The hook discarded it. A person who hits this needs to be told what is
    wrong with their install, not left with an unexplained refusal.
    """
    shutil.rmtree(project / "cli" / "vendor")

    result = _run_hook(project)
    combined = result.stdout + result.stderr

    assert combined.strip(), (
        "the hook refused the edit and printed nothing at all"
    )
    assert "incomplete" in combined.lower() or "vendor" in combined.lower(), (
        f"the hook did not say that the install is what is wrong:\n{combined}"
    )


def test_the_guarded_surface_decision_fails_closed_too(project):
    """The second reader in the same hook, and the same failure shape.

    `is_enforced_path` checks a built-in production-code set first, then reads
    the project's own `enforcement.code_globs` from `.compass/config.yml`
    through the same helper. If that read cannot start, the project-declared
    globs silently vanish and the file is treated as unguarded.

    In this repository those globs are `hooks/*.sh` and `scripts/*.sh` - so a
    broken install stops guarding precisely the files whose breakage caused
    it. The built-in set still applies, which makes this narrower than the
    manifest read, not different in kind.
    """
    (project / ".compass" / "config.yml").write_text(
        "version: 1.0.0\nmode: enforced\n"
        "enforcement:\n  code_globs:\n    - \"scripts/*.sh\"\n",
        encoding="utf-8",
    )
    shutil.rmtree(project / "cli" / "vendor")

    result = subprocess.run(
        ["bash", str(project / "hooks" / "pre-tool.sh")],
        input=json.dumps({
            "tool_name": "Edit",
            "tool_input": {"file_path": "scripts/release.sh"},
        }),
        cwd=str(project), capture_output=True, text=True, timeout=120,
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(project)},
    )
    combined = result.stdout + result.stderr
    assert result.returncode != ALLOW, (
        f"a project-declared guarded path was allowed because the reader that "
        f"knows it is guarded could not start.\nexit={result.returncode}\n"
        f"{combined}"
    )
