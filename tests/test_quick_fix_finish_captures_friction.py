"""A quick fix records the friction the CLI can derive, as ship does.

Ship step 6 runs the CLI's friction draft (recorded re-assessments,
absorbed scope without one). `quick-fix finish` landed a quick fix without
it, so 27 of the 28 issues landed on 5 and 6 October 2026 carried no
friction at all, and `compass retro --friction` read almost nothing. Finish
now runs the same draft; it stays advisory and never blocks.

Scenario id: QF-1 (issue `quick-fix-finish-captures-friction`).
"""
from __future__ import annotations

from test_quick_fix_verbs import (  # noqa: F401
    _finish, _manifest, _manifest_path, _ready_to_finish, _save_manifest, repo)

SLUG = "fix-greeting"


def test_qf_1_a_reassessed_quick_fix_records_the_derived_friction(repo):
    _ready_to_finish(repo, SLUG)
    manifest = _manifest(repo, SLUG)
    manifest["reassessments"] = [{"from_route": "quick-fix", "to_route": "quick-fix",
                                  "reason": "the fix touched a second file",
                                  "at": "2026-10-06T10:00:00+00:00"}]
    _save_manifest(repo, SLUG, manifest)
    result = _finish(repo, SLUG, "--no-commit")
    assert result.returncode == 0, result.stdout + result.stderr
    friction = _manifest(repo, SLUG).get("friction") or []
    assert any(e.get("source") == "derived" and "second file" in e.get("observation", "")
               for e in friction), friction
    assert "friction" in result.stdout, result.stdout


def test_qf_1_no_signal_writes_no_friction_and_prints_nothing_extra(repo):
    _ready_to_finish(repo, SLUG)
    result = _finish(repo, SLUG, "--no-commit")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "friction" not in _manifest(repo, SLUG)
    assert "friction" not in result.stdout, result.stdout
