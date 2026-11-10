"""`quick-fix finish` leaves every path under `.compass/` out of the change.

`finish` reads the changed files from git (ADR-099) and never counts a path
under `.compass/` as part of the change. A tracked file inside it, such as
`.compass/config.yml`, stays changed in the tree and is not committed with the
fix, so ship does not refuse it as outside the issue's scope after the full
suite has run (#321). The issue's own folder is the record and is committed.

Scenario id: FT-1 (issue `finish-traces-compass-files`).
"""
from __future__ import annotations

from test_quick_fix_verbs import (_git, _land, _ready_to_finish,  # noqa: F401
                                  repo)


def test_ft_1_a_tracked_compass_file_stays_out_of_the_landing_commit(repo):
    config = repo / ".compass" / "config.yml"
    config.parent.mkdir(exist_ok=True)
    config.write_text("mode: enforced\n")
    _git(repo, "add", ".compass/config.yml")
    _git(repo, "commit", "-q", "-m", "config")
    _ready_to_finish(repo, "fix-greeting")
    config.write_text("mode: enforced\nproject: {}\n")
    result = _land(repo, "fix-greeting")
    assert result.returncode == 0, result.stdout + result.stderr
    committed = _git(repo, "show", "--name-only", "--format=", "HEAD")
    assert ".compass/config.yml" not in committed, committed
    assert "M .compass/config.yml" in _git(repo, "status", "--porcelain"), result.stdout
    # The record is committed with the fix (#356): the issue's own folder and
    # the ignore file that keeps its per-checkout files out. Nothing else.
    assert ".compass/work/" not in committed.replace(
        ".compass/work/fix-greeting/", "").replace(".compass/work/.gitignore", ""), committed


def test_ft_1_tracked_issue_state_stays_out(repo):
    """A project that uses Compass commits `.compass/work/`. Another issue's
    record there is tracked, but it is issue state, not this fix's change."""
    other = repo / ".compass" / "work" / "other-issue" / "devlog.md"
    other.parent.mkdir(parents=True)
    other.write_text("first\n")
    _git(repo, "add", ".compass/work/other-issue/devlog.md")
    _git(repo, "commit", "-q", "-m", "other issue")
    _ready_to_finish(repo, "fix-greeting")
    other.write_text("first\nsecond\n")
    result = _land(repo, "fix-greeting")
    assert result.returncode == 0, result.stdout + result.stderr
    committed = _git(repo, "show", "--name-only", "--format=", "HEAD")
    assert ".compass/work/other-issue/" not in committed, committed
