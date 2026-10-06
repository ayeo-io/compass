"""`compass init` - the verb that makes a directory a Compass project.

`compass init` creates `.compass/config.yml` and `.compass/work/` and is
safe to run twice. The five entry points call it.

Scenario ids: IOI-A1, IOI-A2 in
init-is-the-opt-in/acceptance-criteria.md
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CLI = REPO_ROOT / "cli" / "compass"


def _init(cwd, *extra, project_dir=None):
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    if project_dir:
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)
    return subprocess.run(
        [sys.executable, str(CLI), "init", *extra],
        cwd=str(cwd), capture_output=True, text=True, timeout=120, env=env)


def test_ioi_a1_the_init_verb_creates_a_project(tmp_path):
    root = (tmp_path / "fresh").resolve()
    root.mkdir()

    run = _init(root)
    out = run.stdout + run.stderr

    assert run.returncode == 0, f"compass init failed:\n{out}"
    assert (root / ".compass" / "config.yml").is_file(), (
        f"init did not write .compass/config.yml:\n{out}")
    assert (root / ".compass" / "work").is_dir(), (
        f"init did not create .compass/work/:\n{out}")
    assert str(root) in out or root.name in out, (
        "init did not name the directory it initialised - a command that "
        f"creates state in someone's repository says where:\n{out}")


def test_ioi_a1b_the_config_it_writes_is_readable(tmp_path):
    """A config the CLI cannot read afterwards is not an initialised project."""
    root = (tmp_path / "fresh").resolve()
    root.mkdir()
    _init(root)

    # `compass issue lint` resolves the project through .compass/, so a
    # readable config is the difference between "created a directory" and
    # "initialised a project".
    run = subprocess.run(
        [sys.executable, str(CLI), "flow"],
        cwd=str(root), capture_output=True, text=True, timeout=120)
    out = run.stdout + run.stderr
    assert "no .compass/ directory found" not in out, (
        f"the CLI still cannot see the project init just created:\n{out}")


def test_ioi_a2_init_is_safe_to_run_twice(tmp_path):
    """The property that lets every entry point call it without checking.

    If a second run overwrote config.yml, an entry point calling init
    unconditionally would silently discard the project's test command.
    """
    root = (tmp_path / "fresh").resolve()
    root.mkdir()
    _init(root)

    config = root / ".compass" / "config.yml"
    edited = config.read_text(encoding="utf-8") + "\n# edited by the project\n"
    config.write_text(edited, encoding="utf-8")
    issue = root / ".compass" / "work" / "an-issue"
    issue.mkdir(parents=True)
    (issue / "manifest.yml").write_text("schema_version: '2.0'\ntask: an-issue\n")

    run = _init(root)
    out = run.stdout + run.stderr

    assert run.returncode == 0, f"a second init failed:\n{out}"
    assert config.read_text(encoding="utf-8") == edited, (
        "init overwrote a config that was already there - every entry point "
        "calls this unconditionally, so a second run must not discard the "
        "project's own settings")
    assert (issue / "manifest.yml").is_file(), (
        "init removed or replaced existing work")
    assert "already" in out.lower(), (
        f"init did not report that the project was already initialised:\n{out}")


def test_ioi_a2b_the_json_result_says_which_happened(tmp_path):
    """A consumer must be able to tell creation from a no-op.

    A missing field shows the reader nothing instead of something false.
    """
    root = (tmp_path / "fresh").resolve()
    root.mkdir()

    first = json.loads(_init(root, "--json").stdout)
    second = json.loads(_init(root, "--json").stdout)

    assert "created" in first, (
        f"the first init's --json result has no `created` field: {first}")
    assert first["created"] is True, (
        f"the first init did not report creating the project: {first}")
    assert second.get("created") is False, (
        f"the second init did not report the project as already there: {second}")
    assert first.get("path"), f"--json carries no path: {first}"


def test_ioi_a1c_an_explicit_project_dir_is_where_it_initialises(tmp_path):
    """CLAUDE_PROJECT_DIR is the runtime saying where the project is."""
    root = (tmp_path / "stated").resolve()
    root.mkdir()
    elsewhere = (tmp_path / "elsewhere").resolve()
    elsewhere.mkdir()

    run = _init(elsewhere, project_dir=root)
    out = run.stdout + run.stderr

    assert run.returncode == 0, out
    assert (root / ".compass").is_dir(), (
        f"init ignored CLAUDE_PROJECT_DIR and initialised somewhere else:\n{out}")
    assert not (elsewhere / ".compass").exists(), (
        "init created a project in the working directory when it had been "
        "told where the project was")


def test_ioi_c2_init_creates_no_governance_directory(tmp_path):
    """Auto-initialisation creates project state only.

    Five commands call this on the user's behalf. Being initialised for you is
    small and reversible; having a governance/ directory copied into your
    repository because you ran /compass:intent is not, and it would arrive
    without the conversation that is the point of adopting it.
    """
    root = (tmp_path / "fresh").resolve()
    root.mkdir()

    _init(root)

    assert not (root / "governance").exists(), (
        "init copied governance/ into the project - that is the /compass:init "
        "slash command's job, after a conversation, not something five "
        "commands do on a user's behalf")
    entries = {p.name for p in (root / ".compass").iterdir()}
    # state.yml holds what init writes (ADR-043); config.yml is the hook's copy
    # of `initialised` until the hook reads state.yml.
    assert entries == {"config.yml", "state.yml", "work"}, (
        f"init created more than the project state it promises: {sorted(entries)}")


def test_ioi_b2_a_quiet_run_still_reports_creating_the_project(tmp_path):
    """--quiet carries errors and the decision hand-off only, and creating a
    directory in someone's repository is a decision, not progress chatter."""
    root = (tmp_path / "fresh").resolve()
    root.mkdir()

    run = _init(root, "--quiet")
    out = (run.stdout + run.stderr).strip()

    assert out, (
        "init created a project and said nothing under --quiet. Silent "
        "creation is how someone deletes .compass/ by hand or commits it "
        "without meaning to")


def test_ioi_d1_a_command_that_needs_an_issue_says_so(tmp_path):
    """Initialising a project does not create an issue.

    The failure this rules out is a confusing success: a user runs their first
    command, the project is initialised for them, and the next command they
    try reports something that does not name the real state.
    """
    root = (tmp_path / "fresh").resolve()
    root.mkdir()
    _init(root)

    run = subprocess.run(
        [sys.executable, str(CLI), "check"],
        cwd=str(root), capture_output=True, text=True, timeout=120)
    out = (run.stdout + run.stderr).lower()

    assert "no issue" in out, (
        "a freshly initialised project with no issue did not say so - a "
        f"reader cannot tell an empty project from a broken one:\n{out}")
    assert "no .compass/ directory found" not in out, (
        "the project init just created is not being seen")
