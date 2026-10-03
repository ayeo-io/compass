"""A review fix to a landed issue rebinds its landing.

`ship-commit` records `land_commit` as the commit that landed the issue. A
fix made during the pull request's review then changes the issue's own files
after that commit: a green re-recorded on the fixed files fails
`evidence-matches-tree`, and a green not re-recorded covers none of the fix
(issue #337). The way through already exists: with nothing staged,
`compass ship-commit --issue <slug>` lands the issue at HEAD once its
newest green names HEAD's files. The check's advice now says so.

Scenario id: RB-1 (issue `review-fix-rebinds-land-commit`).
"""
from __future__ import annotations

import yaml

from test_quick_fix_verbs import (GREET_CMD, _finish, _git, _ready_to_finish,  # noqa: F401
                                  _run, repo)


def _land(repo):
    _ready_to_finish(repo, "fix-greeting")
    result = _finish(repo, "fix-greeting")
    assert result.returncode == 0, result.stdout + result.stderr


def _review_fix(repo):
    # Still passes the test, but changes the issue's own file.
    (repo / "data" / "greeting.txt").write_text("Hello, %s!\n\n")
    _git(repo, "add", "data/greeting.txt")
    _git(repo, "commit", "-q", "-m", "review fix")


def _land_commit(repo):
    manifest = repo / ".compass" / "work" / "fix-greeting" / "manifest.yml"
    return yaml.safe_load(manifest.read_text())["land_commit"]


def test_rb_1_a_new_green_and_ship_commit_rebind_the_landing(repo):
    _land(repo)
    before = _land_commit(repo)
    _review_fix(repo)
    green = _run(repo, "tdd-green", "--issue", "fix-greeting", "--scenario",
                 "TRC-001", *GREET_CMD)
    assert green.returncode == 0, green.stdout + green.stderr
    ship = _run(repo, "ship-commit", "--issue", "fix-greeting", "-m", "Rebind after the review fix")
    assert ship.returncode == 0, ship.stdout + ship.stderr
    after = _land_commit(repo)
    assert after != before
    fix = _git(repo, "rev-parse", "HEAD~1").strip()
    assert after in (fix, _git(repo, "rev-parse", "HEAD").strip()), after
    check = _run(repo, "check", "--issue", "fix-greeting")
    assert "FAIL evidence-matches-tree" not in check.stdout, check.stdout


def test_rb_1_without_a_new_green_the_rebind_is_refused(repo):
    _land(repo)
    before = _land_commit(repo)
    _review_fix(repo)
    ship = _run(repo, "ship-commit", "--issue", "fix-greeting", "-m", "Rebind after the review fix")
    assert ship.returncode != 0, ship.stdout + ship.stderr
    assert _land_commit(repo) == before


def test_rb_1_the_check_names_the_rebind_for_a_landed_issue():
    from compass_pkg.check_cmd import CHECK_GUIDANCE
    advice = CHECK_GUIDANCE["evidence-matches-tree"]["fix"]
    assert "ship-commit --issue" in advice, advice
