"""Local git repositories that stand in for a remote parent (issue `git-parents`).

Tests build a repository under a temporary folder and point
`COMPASS_PARENT_REMOTE_BASE` at its parent, so no test reaches the network.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import yaml

REAL_GIT = "/usr/bin:/bin:/opt/homebrew/bin:/usr/local/bin"

# A parent that sets one top-level value, so a merged field has a source to show.
PARENT_DOC = {"schema": 1, "owner": "platform-team"}


def _git(cwd, *argv):
    env = {"PATH": os.environ.get("PATH", REAL_GIT), "HOME": str(cwd),
           "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
           "GIT_AUTHOR_DATE": "2026-10-01T00:00:00Z",
           "GIT_COMMITTER_DATE": "2026-10-01T00:00:00Z"}
    done = subprocess.run(["git", *argv], cwd=cwd, env=env, capture_output=True,
                          text=True, timeout=60)
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


def make_remote(base, owner="acme", repo="bank", files=None, symlink=None):
    """A local repository at `<base>/<owner>/<repo>.git` and the sha of its one
    commit. `files` maps a path to text; the default is a valid parent."""
    path = Path(base) / owner / f"{repo}.git"
    path.mkdir(parents=True)
    _git(path, "init", "--quiet", "-b", "main")
    _git(path, "config", "uploadpack.allowAnySHA1InWant", "true")
    _git(path, "config", "uploadpack.allowFilter", "true")
    files = {"compass.yml": yaml.safe_dump(PARENT_DOC)} if files is None else files
    for name, text in files.items():
        (path / name).parent.mkdir(parents=True, exist_ok=True)
        (path / name).write_text(text, encoding="utf-8")
    if symlink:
        os.symlink(symlink[1], path / symlink[0])
    _git(path, "add", "-A")
    _git(path, "commit", "--quiet", "-m", "parent")
    return _git(path, "rev-parse", "HEAD")


def fake_git(tmp_path):
    """A `git` that logs its arguments and fails. Returns `(bin dir, log)`."""
    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir()
    log = tmp_path / "git-calls.log"
    script = bin_dir / "git"
    script.write_text(f"#!/bin/sh\necho \"$@\" >> {log}\nexit 1\n", encoding="utf-8")
    script.chmod(0o755)
    return bin_dir, log


def team_parent(tmp_path, parent_doc, project_root):
    """Publish `parent_doc` as the git parent `acme/team`, make the project at
    `project_root` extend it, and fetch it into the project's cache with
    `compass policy lint`. Later commands read the cached parent without the
    mirror. Returns the `extends:` reference.

    A test that changes a legacy stage (such as plan), an approach, the caps
    rules or a `dor-*` check uses it: since 9.0.0 a project layer's change to one
    of them is left out (ADR-092), and a git parent's change is still merged."""
    base = Path(tmp_path) / "remotes"
    sha = make_remote(base, repo="team", files={"compass.yml": yaml.safe_dump(parent_doc)})
    ref = f"github:acme/team@1.0.0#{sha}"
    path = Path(project_root) / "compass.yml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else {"schema": 1}
    path.write_text(yaml.safe_dump(dict(doc, extends=ref)), encoding="utf-8")
    cli = Path(__file__).resolve().parent.parent / "cli" / "compass"
    env = {"PATH": os.environ.get("PATH", REAL_GIT), "HOME": str(project_root),
           "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "NO_COLOR": "1",
           "PYTHONDONTWRITEBYTECODE": "1", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
           "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1",
           "COMPASS_PARENT_REMOTE_BASE": str(base)}
    done = subprocess.run([sys.executable, str(cli), "policy", "lint"], cwd=project_root,
                          env=env, capture_output=True, text=True, timeout=180)
    assert done.returncode == 0, done.stdout + done.stderr
    return ref


ISSUE = {
    "schema_version": "2.0", "issue": "feature", "created": "2026-10-08", "status": "active",
    "assessment": {"risk": "contained", "familiarity": "brownfield-mapped",
                   "size": "medium", "goal": "delivery", "role": "engineer",
                   "labels": []},
    "evidence": [],
}
OUTCOME = {
    "delivery_approach": "regular",
    "stages": {"assess": "thorough", "implement": "thorough"},
    "gates": [{"id": "verify.correctness", "status": "pending", "evidence": []}],
    "checkpoints": [], "policy_rules_fired": [], "subtask_ceiling": 1, "artifacts": [],
}


def issue_project(tmp_path, extends):
    """A project whose `compass.yml` extends `extends`, with one open issue.
    Returns `(project root, issue folder)`."""
    root = Path(tmp_path) / "project"
    task_dir = root / ".compass" / "work" / "feature"
    task_dir.mkdir(parents=True)
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(ISSUE, sort_keys=False),
                                           encoding="utf-8")
    set_extends(root, extends)
    return root, task_dir


def set_extends(root, extends):
    (Path(root) / "compass.yml").write_text(
        yaml.safe_dump({"schema": 1, "extends": extends}), encoding="utf-8")


def commit(task_dir, **changes):
    """Store the configuration the issue resolves to now, as `approach evaluate
    --write` does, and return the result."""
    from compass_pkg import effective
    manifest = yaml.safe_load((Path(task_dir) / "manifest.yml").read_text(encoding="utf-8"))
    manifest.update(OUTCOME)
    manifest.update(changes)
    return effective.commit_generation(str(task_dir), manifest)
