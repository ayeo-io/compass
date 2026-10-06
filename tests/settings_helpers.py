"""Builders shared by the settings tests: a project for the hook, a git
repository for the multiagent scripts, and runners for each.

Not a test module: pytest does not collect it, so a test file can import it
without importing another file's tests.
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import yaml

import compat_hook as ch

GLOBS = "enforcement:\n  code_globs: ['packaging/**']\n"
OTHER_GLOBS = "enforcement:\n  code_globs: ['other/**']\n"
STATE = 'initialised:\n  by: "compass init"\n  at: "2026-09-05"\n'

#: Multiagent and project settings, with the issue-specific suffix `%s` in the
#: values so a test can tell which file a value came from.
SETTINGS = ("multiagent:\n  worktree_root: ../wt-%s\n  max_worktrees: %d\n"
            "project:\n  test_command: run-%s\n")


def make_project(base, *, compass_yml=None, old=None, state=None, issue=True,
                 work=True):
    """An opted-in project. `issue` adds an issue with no red on record, so a
    guarded path blocks on `no-red-on-record`."""
    project = Path(tempfile.mkdtemp(prefix="shkproj-", dir=base))
    if issue:
        ch._issue(project, config=None)
    else:
        (project / ".compass").mkdir()
        if work:
            (project / ".compass" / "work").mkdir()
    if compass_yml is not None:
        (project / "compass.yml").write_text(compass_yml)
    if old is not None:
        (project / ".compass" / "config.yml").write_text(old)
    if state is not None:
        (project / ".compass" / "state.yml").write_text(state)
    return project


def hook_edit(framework, base, project, path):
    """Run the hook on an edit of `path` and return (exit, code, stderr)."""
    outside = base / "outside"
    outside.mkdir(exist_ok=True)
    exit_code, code, _out, err = ch.run(
        framework, project, outside, "Edit",
        {"file_path": "{project}/" + path, "old_string": "a",
         "new_string": "b"}, base)
    return exit_code, code, err


def make_repo(base, **files):
    """A git repository with one issue and a one-subtask map. `files` maps
    `old` to `.compass/config.yml` and `compass` to `compass.yml`."""
    repo = Path(tempfile.mkdtemp(prefix="shkrepo-", dir=base))

    def git(*a):
        subprocess.run(["git", "-C", str(repo), *a], capture_output=True,
                       text=True, check=True)

    git("init", "-q", "-b", "main")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "T")
    work = repo / ".compass" / "work" / "s1"
    work.mkdir(parents=True)
    (repo / "README.md").write_text("# demo\n")
    for name, text in files.items():
        path = repo / (".compass/config.yml" if name == "old" else "compass.yml")
        path.write_text(text)
    (work / "manifest.yml").write_text(
        yaml.safe_dump({"issue": "s1", "assessment": {"risk": "contained"}}))
    (work / "delivery-approach.md").write_text("#\n")
    (work / "distribution-map.md").write_text(
        "# Map\n\n## 3. Mapping\n\n| Subtask | Owns | Scenarios | Branch name |\n"
        "|---|---|---|---|\n| subtask-1 | U1 | S1 | compass/s1/subtask-1 |\n")
    git("add", "-A")
    git("commit", "-q", "-m", "init")
    return repo


def run_script(framework, repo, script, *args):
    return subprocess.run(
        ["bash", str(framework / "scripts" / script), "s1", *args],
        cwd=str(repo), capture_output=True, text=True, timeout=120)
