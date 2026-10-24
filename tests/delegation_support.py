"""Fixtures for the tests of issue `delegation-everywhere` that need git
worktrees: a repository with a main checkout and linked worktrees, each a
Compass project, built in a temporary folder.

`repo(tmp_path)` copies the template project into a new git repository.
`add_worktree` makes a linked worktree. `add_issue` writes an issue folder
into a project folder. The helpers never touch the real project's `.compass/`.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

from approval_support import event, project  # noqa: E402


def git(cwd, *argv):
    subprocess.run(["git", "-c", "user.email=t@example.com", "-c", "user.name=t", *argv],
                   cwd=cwd, check=True, capture_output=True, text=True)


def repo(tmp_path, sub=None):
    """A git repository whose main checkout holds the template project, at the
    repository's top or in the folder `sub`. Returns the repository's top."""
    seed = project(tmp_path / "seed")
    top = tmp_path / "top"
    here = top / sub if sub else top
    shutil.copytree(seed, here)
    git(top, "init", "-q")
    git(top, "add", str((here / "compass.yml").relative_to(top)))
    git(top, "commit", "-q", "-m", "x")
    return top


def project_of(top, sub=None):
    return top / sub if sub else top


def add_worktree(top, name, sub=None):
    """A linked worktree named `name`, beside the main checkout. Returns its
    top folder; its project folder is `project_of(path, sub)`."""
    path = top.parent / name
    git(top, "worktree", "add", "-q", str(path))
    return path


def add_issue(project_dir, slug, generation=1, current=False):
    """An issue folder with a manifest at the given generation."""
    task = Path(project_dir) / ".compass" / "work" / slug
    task.mkdir(parents=True, exist_ok=True)
    body = {"schema_version": "2.0", "issue": slug, "created": "2026-10-15",
            "status": "active", "generation": generation, "evidence": []}
    (task / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False),
                                       encoding="utf-8")
    if current:
        (Path(project_dir) / ".compass" / "current-task").write_text(slug + "\n",
                                                                     encoding="utf-8")
    return task


def type_(root, args, command="compass:delegate", session="sess-1", env=None, **kw):
    """Type a command in a session whose folder is `root`."""
    from compass_pkg import prompt_approval
    return prompt_approval.handle(event(root, command=command, args=args, session=session,
                                        **kw), dict(env or {}), plugin_root=str(ROOT))


def delegations(project_dir):
    folder = Path(project_dir) / ".compass" / "delegations"
    return {p.stem: yaml.safe_load(p.read_text(encoding="utf-8"))
            for p in sorted(folder.glob("DL-*.yml"))} if folder.is_dir() else {}


def set_owner(project_dir, owner):
    path = Path(project_dir) / "compass.yml"
    body = yaml.safe_load(path.read_text(encoding="utf-8"))
    body["owner"] = owner
    path.write_text(yaml.safe_dump(body), encoding="utf-8")
