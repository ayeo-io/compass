"""A refusal's advice works in the case it names.

The land-at-HEAD scope refusal told the user to take files out of a commit
that might be someone else's. The edited-green refusal said to re-record
the evidence, which on an unchanged tree is flagged as a rerun. The scope's
documents prefix repeated `issue_layout.docs_dir_for` and disagreed with it
when `created:` is missing. And `quick-fix finish` said nothing about a fix
the agent committed by hand and never traced.

Scenario ids: LRA-1 to LRA-4, in the delivery approach of issue
land-refusal-advice.
"""
from __future__ import annotations

import json
import sys

import yaml

from test_ship_commit_refuses_a_stale_green import (  # noqa: F401
    ROOT, SLUG, _cli, _git, _green, repo)

sys.path.insert(0, str(ROOT / "cli"))
from compass_pkg.evidence_identity import (  # noqa: E402
    _check_evidence_identity_matches)
from compass_pkg.manifest import _land_scope, _out_of_scope  # noqa: E402


def test_lra1_a_stray_commit_at_head_is_named_not_rewritten(repo):
    """Another person's commit on top of the fix is named, and the advice
    is to land from the issue's own commit, not to rewrite theirs."""
    (repo / "src" / "new.py").write_text("y = 1\n")
    _git(repo, "add", "src/new.py")
    _git(repo, "commit", "-q", "-m", "the fix")
    _green(repo)
    (repo / "src" / "app.py").write_text("x = 5\n")
    _git(repo, "commit", "-q", "-am", "someone else's change")
    theirs = _git(repo, "rev-parse", "--short", "HEAD")

    result = _cli(repo, "ship-commit", "--issue", SLUG, "-m", "land it")
    heard = result.stdout + result.stderr
    assert result.returncode != 0
    assert theirs in heard, heard
    assert "take them out of that commit" not in heard, heard


def test_lra2_restoring_an_edited_green_clears_the_refusal(repo):
    (repo / "src" / "new.py").write_text("y = 1\n")
    _green(repo)
    task_dir = repo / ".compass" / "work" / SLUG
    task = yaml.safe_load((task_dir / "manifest.yml").read_text())
    record = task_dir / "evidence" / "green.json"
    original = record.read_text()
    data = json.loads(original)
    data["log_excerpt"] = "edited"
    record.write_text(json.dumps(data))

    passed, detail = _check_evidence_identity_matches(task, str(task_dir))
    assert passed is False
    assert "restore" in detail.lower(), detail

    record.write_text(original)                    # the advice, followed
    passed, detail = _check_evidence_identity_matches(task, str(task_dir))
    assert passed is True, detail


def test_lra3_an_issue_with_no_created_date_owns_its_documents():
    task = {"changed_files": [{"path": "src/a.py"}]}
    owned, artifacts = _land_scope(task, "no-date")
    from compass_pkg.manifest import _docs_prefix
    prefix = _docs_prefix(task, "no-date")
    assert not _out_of_scope(["docs/compass/no-date/notes.md"], owned,
                             artifacts, prefix)


def test_lra4_finish_names_an_untraced_hand_committed_file(repo):
    """A fix committed by hand before finish is not traced by finish, but
    finish must say so rather than land it silently untraced."""
    from test_quick_fix_verbs import _ready_to_finish, _finish
    slug = "greet-hand"
    _ready_to_finish(repo, slug)
    (repo / "data" / "extra.txt").write_text("committed by hand\n")
    _git(repo, "add", "data/extra.txt")
    _git(repo, "commit", "-q", "-m", "part of the fix, by hand")

    finish = _finish(repo, slug)
    assert "data/extra.txt" in finish.stdout + finish.stderr
    assert "not traced" in (finish.stdout + finish.stderr).lower()
