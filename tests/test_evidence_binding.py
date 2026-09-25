"""A test record names the tree it ran on, and a stale one stops counting.

A green record proved a command passed once. It did not prove the present tree
was the tested tree: code could change after the green and the record still
cleared `suite-passed`. Every red, green and acceptance record now carries
two ids. `tree_id` is the git tree id of the tracked files on disk plus the
issue's own untracked changed files, leaving out `.compass/` and
`docs/compass/`, which a record cannot affect. `changes_id` is a tree of the
issue's changed files alone. `evidence-matches-tree` compares the newest
record's `tree_id` with the tree now, and fails once the issue is ready to
ship. For a landed issue it compares `changes_id` with the same files in the
commit `ship-commit` recorded, which is what `compass ci` runs; HEAD moving on
after the land does not matter.

The fixture ignores `/.compass/work/`, as this repository does; one test
tracks it instead, as a project may.

Scenario ids: EVB-1 to EVB-7, in the acceptance criteria of the issue
`evidence-binding`.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
sys.path.insert(0, str(ROOT / "cli"))

from compass_pkg.check_results import NOTHING_TO_CHECK  # noqa: E402

SLUG = "bound"
GIT = ["git", "-c", "user.email=t@example.com", "-c", "user.name=t"]


def _git(root, *args):
    return subprocess.run([*GIT, *args], cwd=root, capture_output=True,
                          text=True, check=True).stdout.strip()


def _cli(root, *args):
    return subprocess.run([sys.executable, str(CLI), *args], cwd=root,
                          capture_output=True, text=True,
                          env={**os.environ, "CLAUDE_PROJECT_DIR": str(root)})


@pytest.fixture
def repo(tmp_path):
    """A git repository with one committed source file, an ignored path, and
    an issue whose gates can be set by the test."""
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    # `compass ship-commit` runs its own `git commit`, which the -c flags in
    # GIT do not reach. A CI runner has no global identity, so the repository
    # must carry one.
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    (root / "src").mkdir()
    (root / "src" / "app.py").write_text("x = 1\n")
    (root / ".gitignore").write_text("/.compass/work/\nprivate/\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base")
    task = root / ".compass" / "work" / SLUG
    task.mkdir(parents=True)
    _write_manifest(root, gates="pass")
    return root


def _write_manifest(root, *, gates, status="active", extra=None):
    path = root / ".compass" / "work" / SLUG / "manifest.yml"
    data = yaml.safe_load(path.read_text()) if path.exists() else {}
    data.update({"schema_version": "2.0", "issue": SLUG,
                 "created": "2026-09-25", "status": status,
                 "gates": [{"id": "verify.correctness", "status": gates,
                            "evidence": []}],
                 "changed_files": data.get("changed_files") or [
                     {"path": "src/new.py", "scenarios": ["S-1"]}]})
    data.setdefault("evidence", [])
    data.update(extra or {})
    path.write_text(yaml.safe_dump(data, sort_keys=False))


def _green(root):
    result = _cli(root, "tdd-green", "--issue", SLUG, "--", sys.executable,
                  "-c", "pass")
    assert result.returncode == 0, result.stderr


def _check(root):
    from compass_pkg.binding import _check_evidence_matches_tree
    task_dir = root / ".compass" / "work" / SLUG
    task = yaml.safe_load((task_dir / "manifest.yml").read_text())
    return _check_evidence_matches_tree(task, str(task_dir))


def _record(root, name="green"):
    return json.loads((root / ".compass" / "work" / SLUG / "evidence" /
                       f"{name}.json").read_text())


def test_evb_1_a_green_names_the_tree_it_ran_on(repo):
    (repo / "src" / "new.py").write_text("y = 2\n")   # claimed, untracked
    (repo / "notes.txt").write_text("not claimed\n")  # untracked, unclaimed
    _green(repo)
    _git(repo, "add", "src/new.py")
    expected = _git(repo, "write-tree")
    assert _record(repo).get("tree_id") == expected
    assert _record(repo).get("changes_id")


def test_evb_1_a_red_and_an_acceptance_name_their_tree(repo):
    red = _cli(repo, "tdd-red", "--issue", SLUG, "--", sys.executable, "-c",
               "import sys; sys.exit(1)")
    assert red.returncode == 0, red.stderr
    assert _record(repo, "red").get("tree_id")
    start = _cli(repo, "acceptance", "start", "--issue", SLUG, "--kind",
                 "validation", "--", sys.executable, "-c", "pass")
    assert start.returncode == 0, start.stderr
    done = _cli(repo, "acceptance", "record", "--issue", SLUG, "--",
                sys.executable, "-c", "pass")
    assert done.returncode == 0, done.stderr
    assert _record(repo, "acceptance").get("tree_id")


def test_evb_1_outside_git_a_record_carries_no_tree(tmp_path):
    task = tmp_path / ".compass" / "work" / SLUG
    task.mkdir(parents=True)
    (task / "manifest.yml").write_text(
        f"schema_version: '2.0'\nissue: {SLUG}\ncreated: '2026-09-25'\n"
        "status: active\nevidence: []\n")
    _green(tmp_path)
    assert "tree_id" not in _record(tmp_path)


def test_evb_2_a_green_for_a_changed_tree_fails_at_ship(repo):
    _green(repo)
    (repo / "src" / "app.py").write_text("x = 2\n")   # tracked, unclaimed
    ok, why = _check(repo)
    assert ok is False, why
    assert "stale" in why and "re-run" in why


def test_evb_2_the_check_is_registered(repo):
    _green(repo)
    result = _cli(repo, "check", "--issue", SLUG, "--json")
    assert "evidence-matches-tree" in result.stdout


def test_evb_3_before_ship_a_stale_green_is_a_note(repo):
    _write_manifest(repo, gates="pending")
    _green(repo)
    (repo / "src" / "app.py").write_text("x = 2\n")
    ok, why = _check(repo)
    assert ok is True, why
    assert "stale" in why


def test_evb_4_an_ignored_or_unclaimed_edit_does_not_make_a_green_stale(repo):
    _green(repo)
    (repo / "private").mkdir()
    (repo / "private" / "note.md").write_text("private\n")
    (repo / "scratch.txt").write_text("unclaimed\n")
    ok, why = _check(repo)
    assert ok is True, why
    assert "stale" not in why


def test_evb_5_a_landed_issue_is_checked_against_its_land_commit(repo):
    (repo / "src" / "new.py").write_text("y = 2\n")
    _green(repo)
    _git(repo, "add", "src/new.py")
    _git(repo, "commit", "-q", "-m", "land")
    land = _git(repo, "rev-parse", "HEAD")
    _write_manifest(repo, gates="pass", status="landed",
                    extra={"land_commit": land})
    ok, why = _check(repo)
    assert ok is True, why
    # HEAD moving on after the land does not matter.
    (repo / "src" / "later.py").write_text("z = 3\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "later work")
    ok, why = _check(repo)
    assert ok is True, why
    # A land commit whose changed files are not the tested ones does.
    (repo / "src" / "new.py").write_text("y = 3\n")
    _git(repo, "add", "src/new.py")
    _git(repo, "commit", "-q", "-m", "a different land")
    _write_manifest(repo, gates="pass", status="landed",
                    extra={"land_commit": _git(repo, "rev-parse", "HEAD")})
    ok, why = _check(repo)
    assert ok is False, why
    assert "landed" in why


def test_evb_5_ship_commit_records_the_commit_it_made(repo):
    # HEAD is no longer the land commit once a spec commit follows it -
    # `land_commit` is, so read the commit ship-commit made by that field,
    # not by assuming it is HEAD.
    head_before = _git(repo, "rev-parse", "HEAD")
    (repo / "src" / "new.py").write_text("y = 2\n")
    _git(repo, "add", "src/new.py")
    result = _cli(repo, "ship-commit", "--issue", SLUG, "-m", "land it")
    assert result.returncode == 0, result.stderr
    manifest = yaml.safe_load((repo / ".compass" / "work" / SLUG /
                               "manifest.yml").read_text())
    land_commit = manifest.get("land_commit")
    assert land_commit and land_commit != head_before
    assert _git(repo, "log", "-1", "--format=%s", land_commit) == "land it"


def test_evb_6_records_without_a_tree_are_not_judged(repo):
    ev = repo / ".compass" / "work" / SLUG / "evidence"
    ev.mkdir()
    (ev / "green.json").write_text(json.dumps(
        {"exit_code": 0, "passed": True, "timestamp": "2026-09-25T00:00:00"}))
    _write_manifest(repo, gates="pass", extra={"evidence": [
        {"id": "EV-T", "type": "test-run", "path": "evidence/green.json"}]})
    ok, _ = _check(repo)
    assert ok is NOTHING_TO_CHECK


def test_evb_6_a_landed_issue_with_no_land_commit_is_not_judged(repo):
    _green(repo)
    _write_manifest(repo, gates="pass", status="landed")
    ok, why = _check(repo)
    assert ok is NOTHING_TO_CHECK, why


def test_evb_7_the_safety_contract_states_the_boundary():
    text = " ".join((ROOT / "docs" / "safety-contract.md")
                    .read_text(encoding="utf-8").split())
    assert "tree_id" in text
    assert "does not prove" in text and "trusted runner" in text


def test_evb_2_a_tracked_compass_work_does_not_make_every_green_stale(repo):
    """A project may commit `.compass/work/`. tdd-green writes the manifest
    after it names the tree, so the tree must leave `.compass/` out."""
    (repo / ".gitignore").write_text("private/\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "track the work directory")
    _green(repo)
    ok, why = _check(repo)
    assert ok is True and "stale" not in why, why


def test_evb_5_artifacts_in_the_land_commit_do_not_fail_the_landed_check(repo):
    (repo / ".gitignore").write_text("private/\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "track the work directory")
    (repo / "src" / "new.py").write_text("y = 2\n")
    _green(repo)
    (repo / "notes.md").write_text("an unrelated uncommitted edit\n")
    result = _cli(repo, "ship-commit", "--issue", SLUG, "-m", "land it",
                  "src/new.py", ".compass/work")
    assert result.returncode == 0, result.stderr
    ok, why = _check(repo)
    assert ok is True, why


@pytest.mark.parametrize("value", ["0" * 40, "HEAD", "--all", "not-a-commit"])
def test_evb_6_a_land_commit_that_is_not_a_commit_id_fails(repo, value):
    _green(repo)
    _write_manifest(repo, gates="pass", status="landed",
                    extra={"land_commit": value})
    ok, why = _check(repo)
    assert ok is False, why
    assert "land_commit" in why


def test_evb_6_a_land_commit_missing_from_the_clone_is_not_judged(repo):
    _green(repo)
    _write_manifest(repo, gates="pass", status="landed",
                    extra={"land_commit": "ab" * 20})
    ok, why = _check(repo)
    assert ok is NOTHING_TO_CHECK, why

