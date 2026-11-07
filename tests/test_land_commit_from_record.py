"""The land commit of a committed record is read from git (#356).

When the issue record ships in the code commit, the manifest holds
`landed_with_record: true` and no `land_commit`. `landing.land_commit` then
returns the newest commit that added the manifest's current `land_timestamp`
line. After a squash merge that is the squash commit on the default branch.

Each test builds a real git repository in a temporary folder. No test
reaches the network: the shallow clone clones a local path.
"""
from __future__ import annotations

import pathlib
import subprocess

import yaml

from compass_pkg import binding, landing
from compass_pkg.check_results import NOTHING_TO_CHECK

GIT = ["git", "-c", "user.email=t@example.com", "-c", "user.name=t",
       "-c", "commit.gpgsign=false", "-c", "init.defaultBranch=main"]
ISSUE = pathlib.Path(".compass/work/fix-it")
STAMP = "2026-11-07T10:00:00+00:00"
EXAMPLE = (pathlib.Path(__file__).resolve().parent.parent / "examples" / "quick-fix-typo"
           / ".compass" / "work" / "fix-timeout-error-message")


def _git(root, *args):
    return subprocess.run([*GIT, *args], cwd=root, capture_output=True,
                          text=True, check=True).stdout.strip()


def _commit(root, name, message=None):
    (root / name).write_text(name + "\n")
    _git(root, "add", name)
    _git(root, "commit", "-q", "-m", message or name)
    return _git(root, "rev-parse", "HEAD")


def _repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _commit(root, "README.md", "base")
    (root / ISSUE).mkdir(parents=True)
    return root


def _manifest(stamp=STAMP, with_record=True, completed=True):
    data = {"issue": "fix-it", "status": "done" if completed else "backlog"}
    if completed:
        data["close_reason"] = "completed"
        data["land_timestamp"] = stamp
    if with_record:
        data["landed_with_record"] = True
    return data


def _land(root, data, code="fix.py"):
    """Commit the code and the record together, as committed mode does."""
    (root / ISSUE / "manifest.yml").write_text(yaml.safe_dump(data, sort_keys=False))
    (root / code).write_text(code + "\n")
    _git(root, "add", str(ISSUE / "manifest.yml"), code)
    _git(root, "commit", "-q", "-m", "land " + code)
    return _git(root, "rev-parse", "HEAD")


def _derived(root, data=None):
    task_dir = root / ISSUE
    task = data if data is not None else yaml.safe_load(
        (task_dir / "manifest.yml").read_text())
    return landing.land_commit(task, str(task_dir))


def test_a_stored_land_commit_wins(tmp_path):
    root = _repo(tmp_path)
    _land(root, _manifest())
    stored = "a" * 40
    assert _derived(root, dict(_manifest(), land_commit=stored)) == stored


def test_the_commit_that_added_the_line_is_the_land_commit(tmp_path):
    root = _repo(tmp_path)
    landed = _land(root, _manifest())
    _commit(root, "later.txt")
    assert _derived(root) == landed


def test_after_a_squash_merge_it_is_the_squash_commit(tmp_path):
    root = _repo(tmp_path)
    _git(root, "checkout", "-q", "-b", "work")
    on_branch = _land(root, _manifest())
    _git(root, "checkout", "-q", "main")
    _commit(root, "other.txt")
    _git(root, "merge", "--squash", "-q", "work")
    _git(root, "commit", "-q", "-m", "squash work")
    squash = _git(root, "rev-parse", "HEAD")
    assert _derived(root) == squash
    assert squash != on_branch
    _git(root, "checkout", "-q", "work")
    assert _derived(root) == on_branch


def test_after_a_rebase_it_is_the_rebased_commit(tmp_path):
    root = _repo(tmp_path)
    _git(root, "checkout", "-q", "-b", "work")
    on_branch = _land(root, _manifest())
    _git(root, "checkout", "-q", "main")
    _commit(root, "other.txt")
    _git(root, "checkout", "-q", "work")
    _git(root, "rebase", "-q", "main")
    rebased = _git(root, "rev-parse", "HEAD")
    _git(root, "checkout", "-q", "main")
    _git(root, "merge", "--ff-only", "-q", "work")
    assert _derived(root) == rebased
    assert rebased != on_branch


def test_after_a_merge_commit_it_is_the_branch_commit(tmp_path):
    root = _repo(tmp_path)
    _git(root, "checkout", "-q", "-b", "work")
    on_branch = _land(root, _manifest())
    _git(root, "checkout", "-q", "main")
    _commit(root, "other.txt")
    _git(root, "merge", "--no-ff", "-q", "-m", "merge work", "work")
    assert _git(root, "rev-parse", "HEAD") != on_branch
    assert _derived(root) == on_branch


def test_a_second_landing_moves_the_land_commit(tmp_path):
    root = _repo(tmp_path)
    first = _land(root, _manifest())
    second = _land(root, _manifest(stamp="2026-11-08T09:30:00+00:00"), code="review_fix.py")
    assert second != first
    assert _derived(root) == second


def test_a_shallow_clone_without_the_landing_gives_none(tmp_path):
    root = _repo(tmp_path)
    _land(root, _manifest())
    _commit(root, "later.txt")
    clone = tmp_path / "clone"
    _git(tmp_path, "clone", "-q", "--depth", "1", "file://" + str(root), str(clone))
    assert _derived(clone) is None


def test_a_manifest_without_the_key_is_not_derived(tmp_path):
    root = _repo(tmp_path)
    _land(root, _manifest(with_record=False))
    assert _derived(root) is None


def test_an_issue_not_completed_is_not_derived(tmp_path):
    root = _repo(tmp_path)
    _land(root, _manifest())
    assert _derived(root, _manifest(completed=False)) is None


def test_outside_a_git_repository_it_gives_none(tmp_path):
    task_dir = tmp_path / "issue"
    task_dir.mkdir()
    assert landing.land_commit(_manifest(), str(task_dir)) is None


def test_the_tracked_example_keeps_its_verdict():
    """The one tracked landed manifest has no `land_commit` and no
    `landed_with_record`, so `evidence-matches-tree` still declines on it."""
    task = yaml.safe_load((EXAMPLE / "manifest.yml").read_text())
    assert "landed_with_record" not in task
    assert landing.land_commit(task, str(EXAMPLE)) is None
    verdict, detail = binding._check_landed(task, str(EXAMPLE), str(EXAMPLE), "x", {})
    assert verdict == NOTHING_TO_CHECK
    assert detail.startswith("landed with no land_commit recorded")


def test_the_binding_check_reads_the_derived_commit(tmp_path):
    root = _repo(tmp_path)
    landed = _land(root, _manifest())
    verdict, detail = binding._check_landed(_manifest(), str(root / ISSUE), str(root),
                                            "evidence/green.json", {"changes_id": "0" * 40})
    # The record names other files than the land commit holds, and the
    # failure names the commit read from git.
    assert verdict is False
    assert landed[:12] in detail
