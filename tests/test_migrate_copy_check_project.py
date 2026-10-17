"""Both copy check entry points pass the project root to their shared
judgement, for the issue `fix-copy-check-project`.

The copy check's two public entry points, `unrestorable_folders` (used by
`compass issue migrate --apply`) and `unrestorable_files` (used by
`compass policy migrate --words`), share one judgement. Each must pass the
project root to it, so a root whose real path is outside the project's
repository is refused ("outside") and one inside is judged file by file.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

from compass_pkg import migrate_copy_check as check  # noqa: E402


def _git(cwd, *args):
    env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull)
    env.pop("GIT_DIR", None)
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, env=env)


def _project(tmp_path):
    """A project in its own repository, with one committed and one uncommitted file."""
    project = tmp_path / "project"
    (project / ".compass" / "work" / "alpha").mkdir(parents=True)
    _git(project, "init", "-q")
    _git(project, "config", "user.email", "test@example.invalid")
    _git(project, "config", "user.name", "Test")
    (project / "compass.yml").write_text("committed: true\n")
    (project / ".compass" / "work" / "alpha" / "notes.md").write_text("committed\n")
    _git(project, "add", "-A")
    _git(project, "commit", "-q", "-m", "start")
    (project / "local.yml").write_text("uncommitted: true\n")
    return project


def test_unrestorable_files_judges_each_file_in_the_project(tmp_path, monkeypatch):
    monkeypatch.delenv("GIT_DIR", raising=False)
    project = _project(tmp_path)
    paths = [str(project / "compass.yml"), str(project / "local.yml")]
    found = check.unrestorable_files(str(project), paths)
    assert found.state == "judged", found
    assert found.unrestorable == [str(project / "local.yml")], found


def test_unrestorable_folders_judges_a_root_inside_the_repository(tmp_path, monkeypatch):
    monkeypatch.delenv("GIT_DIR", raising=False)
    project = _project(tmp_path)
    work = project / ".compass" / "work"
    found = check.unrestorable_folders(str(work), project=str(project))
    assert found.state == "judged", found
    assert found.unrestorable == [], found
    (work / "alpha" / "notes.md").write_text("changed\n")
    found = check.unrestorable_folders(str(work), project=str(project))
    assert found.unrestorable == ["alpha"], found


def test_unrestorable_folders_refuses_a_root_linked_outside(tmp_path, monkeypatch):
    monkeypatch.delenv("GIT_DIR", raising=False)
    project = _project(tmp_path)
    outside = tmp_path / "outside-docs"
    (outside / "2026-09-01-alpha").mkdir(parents=True)
    (outside / "2026-09-01-alpha" / "spec.md").write_text("only copy\n")
    (project / "docs").mkdir()
    os.symlink(outside, project / "docs" / "compass")
    found = check.unrestorable_folders(str(project / "docs" / "compass"), project=str(project))
    assert found.state == "outside", found
    assert found.unrestorable == ["2026-09-01-alpha"], found
