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
    ROOT, SLUG, _cli, _git, _green, _hook, repo)

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
