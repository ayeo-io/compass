"""`compass ship-commit --issue` at the branch tip judges a hand edit of the
living spec in the issue's own commit.

`tip_scope.tip_own_paths` used to subtract the living-spec files from every
result. An issue's own commit that edited `docs/system-spec.md` by hand then
landed unreported, although the staged path refuses it. The living spec is
now left out only for a spec-only commit and for a conflict resolution.

Scenario id: `TRC-001`.
"""
from __future__ import annotations

import subprocess

from test_ship_commit_after_a_merge import (  # noqa: F401
    SLUG, _cli, _git, _green, _issue_commit, _manifest, _ship, _side_branch,
    repo)

SPEC = "docs/system-spec.md"


def _commit_spec(root, text, message):
    (root / "docs").mkdir(exist_ok=True)
    (root / SPEC).write_text(text)
    _git(root, "add", SPEC)
    _git(root, "commit", "-q", "-m", message)


def test_a_hand_edit_of_the_living_spec_in_the_issues_own_commit_is_refused(
        repo):
    """The issue's own commit changes src/new.py and the living spec: the
    spec is outside the issue's scope, so the landing is refused."""
    (repo / "src" / "new.py").write_text("y = 1\n")
    (repo / "docs").mkdir()
    (repo / SPEC).write_text("# System spec\n\nhand edit\n")
    _green(repo)
    _git(repo, "add", "src", SPEC)
    _git(repo, "commit", "-q", "-m", "the issue's work and a spec edit")

    result = _ship(repo)

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert SPEC in combined, combined
    assert not _manifest(repo).get("land_commit")


def test_a_hand_edit_below_a_merge_of_the_base_is_refused(repo):
    """A merge of the base on top does not hide the spec edit."""
    (repo / "src" / "new.py").write_text("y = 1\n")
    (repo / "docs").mkdir()
    (repo / SPEC).write_text("# System spec\n\nhand edit\n")
    _green(repo)
    _git(repo, "add", "src", SPEC)
    _git(repo, "commit", "-q", "-m", "the issue's work and a spec edit")
    _side_branch(repo, {"lib/other.py": "z = 1\n"})
    _git(repo, "merge", "-q", "--no-ff", "-m", "Merge side", "side")

    result = _ship(repo)

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert SPEC in combined, combined


def test_a_spec_only_commit_still_lands(repo):
    _issue_commit(repo)
    _commit_spec(repo, "# System spec\n", "Re-derive the living spec")

    result = _ship(repo)

    assert result.returncode == 0, result.stdout + result.stderr
    assert _manifest(repo).get("land_commit")


def test_a_conflict_resolution_of_the_living_spec_still_lands(repo):
    """The base and the issue's branch both changed the living spec; the
    merge resolves it. The resolution is derived output, not the issue's."""
    _issue_commit(repo)
    _side_branch(repo, {SPEC: "# System spec\n\nbase\n"})
    _commit_spec(repo, "# System spec\n\nbranch\n", "Re-derive the spec")
    merge = subprocess.run(
        ["git", "-c", "user.email=t@example.com", "-c", "user.name=t",
         "merge", "--no-ff", "side"], cwd=repo, capture_output=True,
        text=True)
    assert merge.returncode != 0, "the fixture must conflict"
    (repo / SPEC).write_text("# System spec\n\nresolved\n")
    _git(repo, "add", SPEC)
    _git(repo, "commit", "-q", "--no-edit")

    result = _ship(repo)

    assert result.returncode == 0, result.stdout + result.stderr
    assert _manifest(repo).get("land_commit")
