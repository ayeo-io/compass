"""An open issue keeps the git parent it ran against (issue `git-parents`).

A generation stores the parent's ref and sha in `versions.yml` and the merged
configuration in `resolved.yml`. Moving the pin in `compass.yml` changes
nothing for an issue that already has a generation, and a reader of that
generation never fetches.

Scenario id: `GP-13`. Each test name starts with its scenario id.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))
from parent_fixtures import commit, issue_project, make_remote, set_extends  # noqa: E402


def _parent(owner):
    return yaml.safe_dump({"schema": 1, "owner": owner})


def _two_commits(base):
    """One repository with two commits, and the sha of each."""
    from parent_fixtures import _git
    first = make_remote(base, files={"compass.yml": _parent("team-a")})
    repo = Path(base) / "acme" / "bank.git"
    (repo / "compass.yml").write_text(_parent("team-b"), encoding="utf-8")
    _git(repo, "commit", "--quiet", "-am", "second")
    return first, _git(repo, "rev-parse", "HEAD")


def _pinned(sha):
    return f"github:acme/bank@1.2.0#{sha}"


def test_gp_13_a_moved_pin_does_not_change_an_issue_with_a_generation(tmp_path, monkeypatch):
    from compass_pkg import effective, parents
    base = tmp_path / "remotes"
    first, second = _two_commits(base)
    root, task_dir = issue_project(tmp_path, _pinned(first))
    monkeypatch.setenv("COMPASS_PARENT_REMOTE_BASE", str(base))
    monkeypatch.chdir(root)
    assert commit(task_dir).committed
    set_extends(root, _pinned(second))

    def forbidden(*args, **kwargs):
        raise AssertionError("reading a stored generation ran git")

    monkeypatch.setattr(parents, "_git", forbidden)
    view = effective.effective_for(str(task_dir))
    assert (view.source, view.generation) == ("generation", 1)
    assert view.versions["parents"][-1]["sha"] == first
    assert (view.resolved.get("capabilities") is not None) and not (
        root / ".compass" / "cache" / "parents" / second).exists()


def test_gp_13_the_next_generation_takes_the_new_pin(tmp_path, monkeypatch):
    base = tmp_path / "remotes"
    first, second = _two_commits(base)
    root, task_dir = issue_project(tmp_path, _pinned(first))
    monkeypatch.setenv("COMPASS_PARENT_REMOTE_BASE", str(base))
    monkeypatch.chdir(root)
    assert commit(task_dir).committed
    set_extends(root, _pinned(second))
    assert commit(task_dir, delivery_approach="full").committed
    shas = [yaml.safe_load((task_dir / "generations" / str(n) / "versions.yml")
                           .read_text(encoding="utf-8"))["parents"][-1]["sha"]
            for n in (1, 2)]
    assert shas == [first, second]
