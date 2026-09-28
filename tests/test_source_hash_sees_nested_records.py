"""The source-tree hash sees files under a nested `.compass/`.

The hash leaves out the project's own `.compass/`, where Compass keeps its
records. A `.compass/` anywhere else - a worked example, a test fixture, an
eval seed - is part of the source tree, and an edit to it is a change. When
the hash left out every `.compass/` at any depth, such an edit looked like
no change: `compass acceptance record` refused a refactor, and a green after
the edit could count as a re-run without change.

Scenario ids: SHN-1 and SHN-2, for issue `source-hash-skips-nested-records`.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

from compass_pkg.tdd import _source_tree_hash  # noqa: E402


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    (project / "src").mkdir(parents=True)
    (project / "src" / "app.py").write_text("x = 1\n")
    nested = project / "examples" / "demo" / ".compass" / "work" / "fix"
    nested.mkdir(parents=True)
    (nested / "manifest.yml").write_text("issue: fix\n")
    own = project / ".compass" / "work" / "issue"
    own.mkdir(parents=True)
    (own / "manifest.yml").write_text("issue: issue\n")
    return project


def test_shn_1_an_edit_under_a_nested_compass_changes_the_hash(tmp_path):
    project = _project(tmp_path)
    before = _source_tree_hash(str(project))
    manifest = project / "examples" / "demo" / ".compass" / "work" / "fix" / "manifest.yml"
    manifest.write_text("issue: fix\nstatus: landed\n")
    assert _source_tree_hash(str(project)) != before


def test_shn_2_an_edit_under_the_project_root_compass_does_not(tmp_path):
    project = _project(tmp_path)
    before = _source_tree_hash(str(project))
    (project / ".compass" / "work" / "issue" / "manifest.yml").write_text(
        "issue: issue\nstatus: landed\n")
    assert _source_tree_hash(str(project)) == before


def test_shn_2_a_nested_git_directory_stays_out_of_the_hash(tmp_path):
    project = _project(tmp_path)
    git = project / "examples" / "demo" / ".git"
    git.mkdir()
    before = _source_tree_hash(str(project))
    (git / "config.json").write_text("{}\n")
    assert _source_tree_hash(str(project)) == before
