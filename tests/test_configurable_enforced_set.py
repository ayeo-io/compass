"""The guarded file set must be declared, not assumed (ADR-011).

The guarded set is project-configurable and only adds to the built-in
defaults, because a hard-coded set cannot predict which files a project
needs to guard. The hook blocked edits-without-a-red for `.py`, `.go` and -
surprisingly - `.github/workflows/compass.yml`, while letting
`docker-compose.yml`, `.gitignore` and `*.sha256` through, with no way for a
project to add its own files to the set.

ADR-011 reaches the same fix for a different reason: shell scripts are in
none of the lists, so this repository's own `hooks/` and `scripts/` are
unprotected by the mechanism they implement - and adding `.sh` to the
*default* would demand a failing test for every shell edit in every project
on upgrade.

So the set becomes project-configurable, ADDING to the built-in defaults.
Nothing removes framework enforcement: Compass's model is that project rules
ratchet up, and a key that exempted `*.py` would be a way to switch
enforcement off, presented as configuration.

Scenarios: configurable-enforced-set/acceptance-criteria.md
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "hooks" / "pre-tool.sh"


def _project(config=None, *, raw_config=None):
    """An initialised project with no red on record. Path contains no 'test'/'spec'."""
    root = Path(tempfile.mkdtemp(prefix="compass-fix-"))
    task_dir = root / ".compass" / "work" / "t"
    task_dir.mkdir(parents=True)
    (root / ".compass" / "current-task").write_text("t\n")
    (task_dir / "delivery-approach.md").write_text("# Route\n")
    (task_dir / "manifest.yml").write_text(yaml.safe_dump({
        "schema_version": "1.1", "task": "t", "created": "2026-08-06",
        "assessment": {"risk": "contained", "familiarity": "greenfield",
                     "size": "small", "intent": "delivery"},
        "delivery_approach": "standard", "stages": {"specify": "light"},
        "scenarios": [], "gates": [],
    }, sort_keys=False))
    body = raw_config if raw_config is not None else yaml.safe_dump(
        config or {"version": "1.0.0", "mode": "enforced"}, sort_keys=False)
    (root / ".compass" / "config.yml").write_text(body)
    return root


def _hook(root, target):
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = str(root)
    payload = {"tool_name": "Edit", "tool_input": {"file_path": str(root / target)}}
    return subprocess.run(["bash", str(HOOK)], input=json.dumps(payload),
                          capture_output=True, text=True, env=env, timeout=30)


CFG_SH = {"version": "1.0.0", "mode": "enforced",
          "enforcement": {"code_globs": ["*.sh"]}}


# ---------------------------------------------------------------------------
# Group A - configuring the set
# ---------------------------------------------------------------------------

def test_scn_a1_project_can_add_a_file_type():
    root = _project(CFG_SH)
    try:
        assert _hook(root, "deploy.sh").returncode == 2, (
            "a project declared .sh as production code and it was not enforced")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_scn_a2_path_shaped_glob():
    # `packaging/`, not `charts/` - the built-in set already covers chart and
    # manifest paths, so that would pass without any of this working.
    root = _project({"version": "1.0.0", "mode": "enforced",
                     "enforcement": {"code_globs": ["packaging/**"]}})
    try:
        assert _hook(root, "packaging/bundle.cfg").returncode == 2, (
            "a path-shaped glob did not match")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_scn_a3_no_config_unchanged():
    """The default behaviour must be bit-for-bit what it was."""
    root = _project()
    try:
        assert _hook(root, "src/app.py").returncode == 2, "python stopped being enforced"
        assert _hook(root, "notes.txt").returncode == 0, "a .txt started being enforced"
        assert _hook(root, "deploy.sh").returncode == 0, (
            "a project that configured nothing had .sh enforcement added to it")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_scn_a4_cannot_exempt_framework_types():
    """Project rules ratchet up. A key that exempted `*.py` would be a way
    to switch enforcement off, presented as configuration."""
    root = _project({"version": "1.0.0", "mode": "enforced",
                     "enforcement": {"code_globs": [], "exempt_globs": ["*.py"]}})
    try:
        assert _hook(root, "src/app.py").returncode == 2, (
            "a project exempted itself from framework enforcement")
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---------------------------------------------------------------------------
# Group B - legibility
# ---------------------------------------------------------------------------

def test_scn_b1_block_names_the_matching_glob():
    root = _project(CFG_SH)
    try:
        err = _hook(root, "deploy.sh").stderr
        assert "*.sh" in err, f"the matching glob was not named:\n{err}"
        assert "config" in err.lower(), (
            f"the message should say where the rule is declared:\n{err}")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_scn_b2_built_in_match_says_so():
    root = _project()
    try:
        err = _hook(root, "src/app.py").stderr
        assert "built-in" in err.lower(), (
            f"a built-in match should say so, so the rule is legible:\n{err}")
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---------------------------------------------------------------------------
# Group C - this repository
# ---------------------------------------------------------------------------

def test_scn_c1_this_repo_enforces_its_shell_scripts():
    """ADR-011's gap, closed where it applies: Compass's own hooks/ and scripts/
    are the enforcement mechanism, and were outside it."""
    cfg = yaml.safe_load((ROOT / "compass.yml").read_text())
    globs = ((cfg or {}).get("enforcement") or {}).get("code_globs") or []
    assert any(g.endswith(".sh") or "hooks/" in g or "scripts/" in g
               for g in globs), (
        f"this repo does not declare its shell scripts as production code: {globs}")


# ---------------------------------------------------------------------------
# Failure modes
# ---------------------------------------------------------------------------

def test_scn_f1_unreadable_config_does_not_block():
    root = _project(raw_config="enforcement: [this is not\n  valid: yaml\n")
    try:
        assert _hook(root, "notes.txt").returncode == 0, (
            "an unparseable config blocked an edit it had no rule about")
        assert _hook(root, "src/app.py").returncode == 2, (
            "an unparseable config disabled the built-in set")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_scn_f2_test_files_stay_exempt():
    """You have to be able to write the red, whatever the project declares."""
    root = _project(CFG_SH)
    try:
        assert _hook(root, "tests/test_helper.sh").returncode == 0, (
            "a project glob overrode the test-file exemption, so the red cannot "
            "be written")
    finally:
        shutil.rmtree(root, ignore_errors=True)
