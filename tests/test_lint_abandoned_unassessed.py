"""`compass issue lint` does not demand an assessment an issue never had.

A queued issue that is abandoned before it is assessed never entered the
pipeline, which is why lint already excuses a queued one. Marking six such
issues abandoned made the release's `make ci` fail on each, for want of an
assessment nobody was meant to make.

Scenario id: LA-1 (issue `lint-excuses-unassessed-abandoned`).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

from test_quick_fix_verbs import _run, repo  # noqa: E402,F401


def _issue(root, slug, status):
    d = root / ".compass" / "work" / slug
    d.mkdir(parents=True)
    (d / "manifest.yml").write_text(
        f"schema_version: '2.0'\nissue: {slug}\ncreated: '2026-08-14'\n"
        f"status: {status}\nscenarios: []\n", encoding="utf-8")


def test_la_1_an_unassessed_abandoned_issue_passes_lint(repo):
    _issue(repo, "never-started", "abandoned")
    result = _run(repo, "issue", "lint", "--issue", "never-started")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "missing `assessment:`" not in result.stdout


def test_la_1_an_unassessed_active_issue_is_still_refused(repo):
    _issue(repo, "in-flight", "active")
    result = _run(repo, "issue", "lint", "--issue", "in-flight")
    assert result.returncode != 0
    assert "missing `assessment:`" in result.stdout + result.stderr
