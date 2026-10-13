"""`compass ship-commit --issue` lands at HEAD when the branch tip is a merge
or a commit that only re-derives the living spec.

With nothing staged, `ship-commit` lands at HEAD after judging what HEAD
added against the issue's declared scope. It compared HEAD with its first
parent only, so a tip that merged another branch listed everything that
branch brought, and a tip that only re-derived `docs/system-spec.md` listed
the living spec, which `ship-commit` writes itself. Both were refused.

The check now judges the issue's own commits along the first parent: a
living-spec-only commit is passed over, a merge of another branch counts
only what it changed against every parent (a conflict resolution), and the
walk stops at the issue's newest own commit, which is still judged in full.
An integration merge of a branch built on the tip is judged in full.

Scenario ids: `TRC-001` (the tip lands, and the issue's own commit is
still judged), `TRC-002` (an integration merge is judged in full).
"""
from __future__ import annotations

import yaml

from test_ship_commit_refuses_a_stale_green import (  # noqa: F401
    SLUG, _cli, _git, _green, repo)


def _manifest(root):
    path = root / ".compass" / "work" / SLUG / "manifest.yml"
    return yaml.safe_load(path.read_text())


def _issue_commit(root, extra=None):
    """Commit the issue's own work, green first, as the issue would."""
    (root / "src" / "new.py").write_text("y = 1\n")
    for rel, text in (extra or {}).items():
        (root / rel).write_text(text)
    _green(root)
    _git(root, "add", "-A", "src")
    _git(root, "commit", "-q", "-m", "the issue's work")


def _ship(root):
    return _cli(root, "ship-commit", "--issue", SLUG, "-m", "land it")


def _side_branch(root, files):
    """A branch from the base commit that changes `files`, outside the
    issue's scope."""
    base = _git(root, "rev-list", "--max-parents=0", "HEAD")
    _git(root, "branch", "side", base)
    current = _git(root, "rev-parse", "--abbrev-ref", "HEAD")
    _git(root, "checkout", "-q", "side")
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    _git(root, "add", "-A", *files)
    _git(root, "commit", "-q", "-m", "someone else's work")
    _git(root, "checkout", "-q", current)


def test_trc001_a_living_spec_commit_at_the_tip_lands(repo):
    """The tip re-derives docs/system-spec.md only: it lands at HEAD."""
    _issue_commit(repo)
    (repo / "docs").mkdir()
    (repo / "docs" / "system-spec.md").write_text("# System spec\n")
    _git(repo, "add", "docs/system-spec.md")
    _git(repo, "commit", "-q", "-m", "Re-derive the living spec")

    result = _ship(repo)

    assert result.returncode == 0, result.stdout + result.stderr
    assert _manifest(repo).get("land_commit")


def test_trc001_a_merge_of_another_branch_at_the_tip_lands(repo):
    """The tip merges a branch that changed paths outside the scope: what
    that branch brought is not the issue's, so it lands at HEAD."""
    _issue_commit(repo)
    _side_branch(repo, {"src/app.py": "x = 2\n", "lib/other.py": "z = 1\n"})
    _git(repo, "merge", "-q", "--no-ff", "-m", "Merge side", "side")

    result = _ship(repo)

    assert result.returncode == 0, result.stdout + result.stderr
    assert _manifest(repo).get("land_commit")


def test_trc001_a_merge_with_a_resolved_conflict_lands(repo):
    """The tip merges a branch after resolving a conflict in the issue's
    own file: the resolution is in scope, the rest the branch brought is
    not the issue's."""
    _issue_commit(repo)
    _side_branch(repo, {"src/new.py": "y = 9\n", "lib/other.py": "z = 1\n"})
    merge = __import__("subprocess").run(
        ["git", "-c", "user.email=t@example.com", "-c", "user.name=t",
         "merge", "--no-ff", "side"], cwd=repo, capture_output=True,
        text=True)
    assert merge.returncode != 0, "the fixture must conflict"
    (repo / "src" / "new.py").write_text("y = 10\n")
    _green(repo)
    _git(repo, "add", "src/new.py")
    _git(repo, "commit", "-q", "--no-edit")

    result = _ship(repo)

    assert result.returncode == 0, result.stdout + result.stderr
    assert _manifest(repo).get("land_commit")


def test_trc001_an_integration_merge_of_the_issue_lands(repo):
    """A multiagent integration merge brings the issue's own work from a
    subtask branch whose base is the first parent: it lands at HEAD, and
    the base commit below it is not judged as the issue's."""
    (repo / "src" / "app.py").write_text("x = 3\n")
    _git(repo, "commit", "-q", "-am", "unrelated work before the issue")
    _git(repo, "checkout", "-q", "-b", "subtask")
    (repo / "src" / "new.py").write_text("y = 1\n")
    _git(repo, "add", "src/new.py")
    _git(repo, "commit", "-q", "-m", "subtask work")
    _git(repo, "checkout", "-q", "-")
    _git(repo, "merge", "-q", "--no-ff", "-m", "Integrate subtask", "subtask")
    _green(repo)

    result = _ship(repo)

    assert result.returncode == 0, result.stdout + result.stderr


def test_trc002_an_integration_merge_with_a_stray_file_is_refused(repo):
    """An integration merge whose first parent is the base of the merged
    branch brings only that branch's work, which is the issue's: a stray
    file in it is still judged and refused."""
    _git(repo, "checkout", "-q", "-b", "subtask")
    (repo / "src" / "new.py").write_text("y = 1\n")
    (repo / "src" / "app.py").write_text("x = 8\n")
    _git(repo, "add", "src")
    _git(repo, "commit", "-q", "-m", "subtask work with a stray file")
    _git(repo, "checkout", "-q", "-")
    _git(repo, "merge", "-q", "--no-ff", "-m", "Integrate subtask", "subtask")
    _green(repo)

    result = _ship(repo)

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert "src/app.py" in combined, combined
    assert not _manifest(repo).get("land_commit")


def test_trc001_an_untraced_file_below_a_merge_is_still_refused(repo):
    """The issue's own first-parent commit changes an untraced file: a merge
    on top does not hide it."""
    _issue_commit(repo, extra={"src/app.py": "x = 7\n"})
    _side_branch(repo, {"lib/other.py": "z = 1\n"})
    _git(repo, "merge", "-q", "--no-ff", "-m", "Merge side", "side")

    result = _ship(repo)

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert "src/app.py" in combined, combined
    assert "lib/other.py" not in combined, combined
    assert not _manifest(repo).get("land_commit")


def test_trc001_an_untraced_file_below_a_spec_commit_is_still_refused(repo):
    """The issue's own commit changes an untraced file: a living-spec commit
    on top does not hide it."""
    _issue_commit(repo, extra={"src/app.py": "x = 7\n"})
    (repo / "docs").mkdir()
    (repo / "docs" / "system-spec.md").write_text("# System spec\n")
    _git(repo, "add", "docs/system-spec.md")
    _git(repo, "commit", "-q", "-m", "Re-derive the living spec")

    result = _ship(repo)

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert "src/app.py" in combined, combined
    assert not _manifest(repo).get("land_commit")
