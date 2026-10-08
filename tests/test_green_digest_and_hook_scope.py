"""An edited green record is caught, a hook cannot widen a ship, and a
tracked file that matches `.gitignore` can ship.

A green record's `content_digest` was compared with the digest a gate
cited, never recomputed from the record, so an edit that left the field
alone passed. `ship-commit` checked its scope once, before the pre-commit
step, so a hook could stage a file outside it. And `changes_id` staged
with plain `git add`, which skips a tracked file that matches
`.gitignore`, so such a file never matched and could never ship.

Scenario ids: GDH-1 to GDH-4, in acceptance-criteria.md of issue
green-digest-and-hook-scope.
"""
from __future__ import annotations

import json
import sys

import yaml

from test_ship_commit_refuses_a_stale_green import (  # noqa: F401
    ROOT, SLUG, _cli, _fake_pre_commit, _git, _green, _hook, _ship, repo)

sys.path.insert(0, str(ROOT / "cli"))
from compass_pkg.evidence_identity import (  # noqa: E402
    _check_evidence_identity_matches)


def _manifest(repo):
    return yaml.safe_load(
        (repo / ".compass" / "work" / SLUG / "manifest.yml").read_text())


def test_gdh1_an_edited_green_record_fails_the_identity_check(repo):
    (repo / "src" / "new.py").write_text("y = 1\n")
    _green(repo)
    task_dir = repo / ".compass" / "work" / SLUG
    task = _manifest(repo)
    passed, _ = _check_evidence_identity_matches(task, str(task_dir))
    assert passed is True

    record_path = task_dir / "evidence" / "green.json"
    record = json.loads(record_path.read_text())
    record["log_excerpt"] = "edited after it was written"
    record_path.write_text(json.dumps(record))    # digest field left alone

    passed, detail = _check_evidence_identity_matches(task, str(task_dir))
    assert passed is False, detail
    assert "green.json" in detail


def test_gdh2_a_hook_cannot_stage_a_file_outside_the_scope(repo):
    (repo / "src" / "new.py").write_text("y = 1\n")
    _green(repo)
    _git(repo, "add", "src/new.py")
    _hook(repo, "printf 'x = 5\\n' > src/app.py\ngit add src/app.py\nexit 0\n")

    result = _cli(repo, "ship-commit", "--issue", SLUG, "-m", "land it")
    assert result.returncode != 0, result.stdout
    assert "src/app.py" in result.stdout + result.stderr
    # A git hook stages during the commit, so the commit may stand; the
    # issue must not be marked landed on it.
    assert _manifest(repo).get("status") != "landed"


def test_gdh3_a_tracked_file_that_matches_gitignore_can_ship(repo):
    (repo / ".gitignore").write_text("src/new.py\n")
    _git(repo, "add", ".gitignore")
    (repo / "src" / "new.py").write_text("y = 1\n")
    _git(repo, "add", "-f", "src/new.py")
    _git(repo, "commit", "-q", "-m", "tracked though ignored")
    (repo / "src" / "new.py").write_text("y = 2\n")
    _green(repo)
    _git(repo, "add", "-f", "src/new.py")

    result = _cli(repo, "ship-commit", "--issue", SLUG, "-m", "land it")
    assert result.returncode == 0, result.stdout + result.stderr


def test_gdh4_the_contract_and_the_refusal_say_the_right_thing():
    flat = " ".join((ROOT / "docs" / "safety-contract.md")
                    .read_text(encoding="utf-8").split()).lower()
    assert "an untracked file git ignores changes neither id" in flat
    source = (ROOT / "cli" / "compass_pkg" / "manifest.py").read_text(
        encoding="utf-8")
    assert "re-run `compass quick-fix " in source


def test_gdh2_shipping_again_does_not_land_a_widened_commit(repo):
    """After ship-commit refused to mark a hook-widened commit landed, a
    second run finds nothing staged and lands at HEAD. It must judge what
    HEAD added, not mark the issue landed on it."""
    (repo / "src" / "new.py").write_text("y = 1\n")
    _green(repo)
    _git(repo, "add", "src/new.py")
    _hook(repo, "printf 'x = 5\\n' > src/app.py\ngit add src/app.py\nexit 0\n")
    first = _cli(repo, "ship-commit", "--issue", SLUG, "-m", "land it")
    assert first.returncode != 0

    second = _cli(repo, "ship-commit", "--issue", SLUG, "-m", "land it")
    assert second.returncode != 0, second.stdout
    assert "src/app.py" in second.stdout + second.stderr
    assert _manifest(repo).get("status") != "landed"


def test_gdh2_a_pre_commit_step_that_stages_a_stray_file_stops_the_commit(
        repo, tmp_path):
    """The pre-commit framework runs before git commit, so a file it stages
    outside the scope is caught before anything is committed."""
    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir()
    fake = bin_dir / "pre-commit"
    fake.write_text("#!/bin/sh\nprintf 'x = 5\\n' > src/app.py\n"
                    "git add src/app.py\nexit 0\n")
    fake.chmod(0o755)
    (repo / ".pre-commit-config.yaml").write_text("repos: []\n")
    _git(repo, "add", ".pre-commit-config.yaml")
    _git(repo, "commit", "-q", "-m", "hooks")
    env = {**__import__("os").environ, "CLAUDE_PROJECT_DIR": str(repo),
           "PATH": f"{bin_dir}{__import__('os').pathsep}"
                   f"{__import__('os').environ['PATH']}"}
    (repo / "src" / "new.py").write_text("y = 1\n")
    _green(repo)
    _git(repo, "add", "src/new.py")
    head_before = _git(repo, "rev-parse", "HEAD")

    result = _ship(repo, env, "--issue", SLUG, "-m", "land it")
    assert result.returncode != 0, result.stdout
    assert "src/app.py" in result.stdout + result.stderr
    assert _git(repo, "rev-parse", "HEAD") == head_before


def test_gdh2_a_land_at_head_takes_declared_tests_and_the_issue_documents(repo):
    """The issue owns its declared test files and its documents as well as
    its changed files: a commit holding them lands at HEAD."""
    path = repo / ".compass" / "work" / SLUG / "manifest.yml"
    data = yaml.safe_load(path.read_text())
    data["scenarios"] = [{"id": "S-1", "title": "t", "intent": "INT-1",
                          "tests": ["tests/test_new.py::test_it"]}]
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    (repo / "src" / "new.py").write_text("y = 1\n")
    (repo / "tests").mkdir()
    (repo / "tests" / "test_new.py").write_text("def test_it():\n    pass\n")
    docs = repo / "docs" / "compass" / f"2026-09-28-{SLUG}"
    docs.mkdir(parents=True)
    (docs / "notes.md").write_text("the issue's own document\n")
    _git(repo, "add", "src/new.py", "tests/test_new.py", str(docs))
    _git(repo, "commit", "-q", "-m", "the fix, committed by hand")
    _green(repo)

    result = _cli(repo, "ship-commit", "--issue", SLUG, "-m", "land it")
    assert result.returncode == 0, result.stdout + result.stderr
    assert _manifest(repo).get("status") == "done"
    assert _manifest(repo).get("close_reason") == "completed"


def test_gdh2_an_issue_with_no_changed_files_is_not_scope_checked(repo):
    """ADR-006: an issue that has not said what it changes has no scope to
    check against, even when its scenarios declare tests."""
    path = repo / ".compass" / "work" / SLUG / "manifest.yml"
    data = yaml.safe_load(path.read_text())
    data["changed_files"] = []
    data["scenarios"] = [{"id": "S-1", "title": "t", "intent": "INT-1",
                          "tests": ["tests/test_new.py::test_it"]}]
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    (repo / "src" / "new.py").write_text("y = 1\n")
    _git(repo, "add", "src/new.py")

    result = _cli(repo, "ship-commit", "--issue", SLUG, "-m", "land it")
    assert result.returncode == 0, result.stdout + result.stderr
