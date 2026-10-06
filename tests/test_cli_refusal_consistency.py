"""The CLI refuses consistently.

A refusal exits 2, says what is actually wrong, names the flag or argument
the person gave, goes to stderr, and shows paths from the project root. The
command corpus (contract 4) found eight places that broke one of these, and
a receipt that never showed the reasons a quick fix recorded.

Scenario id: `TRC-001` (issue `cli-refusal-consistency`).
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

import compat_commands  # noqa: E402


@pytest.fixture(scope="module")
def projects():
    return compat_commands.Projects(Path(tempfile.mkdtemp(prefix="compass-refusals-")))


def _run(projects, state, *argv):
    return projects.run({"project": state, "argv": list(argv)})


def test_trc_001_a_receipt_for_a_missing_issue_is_a_refusal(projects):
    out = _run(projects, "quick-fix-started", "issue", "receipt", "--issue", "nope")
    assert out.exit == 2, out
    assert "nope" in out.stderr and "/private/" not in out.stderr and "/tmp" not in out.stderr


def test_trc_001_an_ad_hoc_write_refuses_before_printing_a_result(projects):
    out = _run(projects, "initialised", "approach", "evaluate", "--write",
               "--assessment", "risk=trivial", "--assessment", "familiarity=brownfield-mapped",
               "--assessment", "size=atomic")
    assert out.exit == 2 and out.stdout.strip() == "", out
    assert "a issue" not in out.stderr and "an issue" in out.stderr, out.stderr


def test_trc_001_refresh_spec_outside_git_says_so(projects):
    out = _run(projects, "outside-git", "issue", "refresh-spec")
    assert out.exit == 2
    assert "not a git repository" in out.stderr, out.stderr


def test_trc_001_raised_by_names_the_argument_it_was_given(projects):
    out = _run(projects, "quick-fix-started", "issue", "raised-by", "nope", "--found-at", "review")
    assert out.exit == 2
    assert "--raised-by" not in out.stderr and "nope" in out.stderr, out.stderr


def test_trc_001_next_refuses_on_stderr_with_a_relative_path(projects):
    out = _run(projects, "regular-issue", "next")
    assert out.exit == 2 and out.stdout.strip() == "", out
    assert "delivery-approach.md" in out.stderr and "/private/" not in out.stderr, out.stderr


def test_trc_001_the_receipt_shows_the_reasons_a_quick_fix_recorded(projects):
    out = _run(projects, "quick-fix-started", "issue", "receipt")
    assert out.exit == 0, out
    assessment = out.stdout.split("Approach", 1)[0]
    assert "(no justification on file)" not in assessment, assessment


def test_trc_001_an_unknown_option_is_reported_against_its_verb(projects):
    out = _run(projects, "quick-fix-started", "check", "--frobnicate")
    assert out.exit == 2
    assert "usage: compass check" in out.stderr, out.stderr
    assert "unrecognized arguments: --frobnicate" in out.stderr


def test_trc_001_flow_outside_a_project_refuses_like_every_verb(projects):
    out = _run(projects, "empty", "flow")
    assert out.exit == 2, out
    assert ".compass" in out.stderr, out.stderr
