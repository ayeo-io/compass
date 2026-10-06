"""The derived living spec stays out of the way of pull requests.

Every landing re-derives `docs/system-spec.md` and its archive, so two open
pull requests each carry a derived copy and the second to merge conflicts on
both files, though nobody wrote a line of either. The derive also took every
issue landed in local records, so a branch could carry an issue that had
landed only on another branch.

The derive now keeps a landed issue only when the spec committed at HEAD
names it or its `land_commit` is reachable from HEAD, and `compass issue
refresh-spec` merges a base, takes the base's side of the two derived files,
re-derives and commits.

Scenario ids: LS-1 to LS-4 (issue `living-spec-conflicts`).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
sys.path.insert(0, str(ROOT / "cli"))

from compass_pkg import flow  # noqa: E402

GIT = ["git", "-c", "user.email=t@example.com", "-c", "user.name=t"]


def _git(root, *args):
    return subprocess.run([*GIT, *args], cwd=root, capture_output=True,
                          text=True, check=True).stdout.strip()


def _issue(root, slug, land_commit, title=None):
    work = root / ".compass" / "work" / slug
    work.mkdir(parents=True, exist_ok=True)
    (work / "manifest.yml").write_text(
        "schema_version: '2.0'\n"
        f"task: {slug}\n"
        "created: '2026-10-06'\n"
        "status: landed\n"
        f"land_commit: {land_commit}\n"
        f"land_timestamp: '2026-10-06T10:00:00+00:00'\n"
        "scenarios:\n"
        f"- id: TRC-{slug}\n"
        f"  title: {title or 'the behaviour of ' + slug}\n"
        f"  intent: INT-{slug}\n", encoding="utf-8")


def _repo(tmp_path):
    root = tmp_path / "proj"
    (root / ".compass").mkdir(parents=True)
    (root / ".compass" / "config.yml").write_text("version: 1.0.0\n")
    (root / ".gitignore").write_text(".compass/work/\n")
    (root / "README.md").write_text("base\n")
    _git(root, "init", "-q", "-b", "main")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base")
    return root


def _spec(root):
    """The current spec and its archive together: a superseded scenario
    moves to the archive and is still on record."""
    docs = root / "docs"
    return "".join((docs / name).read_text(encoding="utf-8")
                   for name in ("system-spec.md", "system-spec-archive.md")
                   if (docs / name).is_file())


def _commit_spec(root, message):
    _git(root, "add", "docs")
    _git(root, "commit", "-q", "-m", message)


# --- LS-1: only issues on this branch -------------------------------------------

def test_ls_1_an_issue_landed_on_another_branch_is_left_out(tmp_path):
    root = _repo(tmp_path)
    _git(root, "checkout", "-q", "-b", "other")
    (root / "other.txt").write_text("x\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "other work")
    elsewhere = _git(root, "rev-parse", "HEAD")
    _git(root, "checkout", "-q", "main")
    here = _git(root, "rev-parse", "HEAD")
    _issue(root, "on-this-branch", here)
    _issue(root, "on-another-branch", elsewhere)
    flow.derive_system_spec(str(root))
    spec = _spec(root)
    assert "on-this-branch" in spec
    assert "on-another-branch" not in spec


def test_ls_1_an_issue_the_committed_spec_names_is_kept(tmp_path):
    # A squash merge leaves the branch's land commit off main; main's
    # committed spec, re-derived at that landing, is what names the issue.
    root = _repo(tmp_path)
    _issue(root, "squashed", "0" * 40)
    (root / "docs").mkdir()
    (root / "docs" / "system-spec.md").write_text(
        "- **Source issue:** `squashed`\n", encoding="utf-8")
    _commit_spec(root, "main's spec, naming the squash-merged issue")
    flow.derive_system_spec(str(root))
    assert "TRC-squashed" in _spec(root)


def test_ls_1_outside_git_every_landed_issue_is_kept(tmp_path):
    root = tmp_path / "plain"
    (root / ".compass").mkdir(parents=True)
    (root / ".compass" / "config.yml").write_text("version: 1.0.0\n")
    _issue(root, "anything", "0" * 40)
    flow.derive_system_spec(str(root))
    assert "anything" in _spec(root)


# --- LS-2 and LS-3: compass issue refresh-spec ------------------------------------------

def _two_branches(tmp_path, extra_conflict=False):
    """main and a feature branch made from the same commit, each landing one
    issue and committing its own derived spec."""
    root = _repo(tmp_path)
    _git(root, "checkout", "-q", "-b", "feature")
    (root / "feature.txt").write_text("feature\n")
    if extra_conflict:
        (root / "README.md").write_text("feature edit\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "feature work")
    _issue(root, "feature-issue", _git(root, "rev-parse", "HEAD"))
    flow.derive_system_spec(str(root))
    _commit_spec(root, "spec after feature-issue")
    _git(root, "checkout", "-q", "main")
    (root / "main.txt").write_text("main\n")
    if extra_conflict:
        (root / "README.md").write_text("main edit\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "main work")
    _issue(root, "main-issue", _git(root, "rev-parse", "HEAD"))
    flow.derive_system_spec(str(root))
    _commit_spec(root, "spec after main-issue")
    _git(root, "checkout", "-q", "feature")
    return root


def _refresh(root, *args):
    # The command runs git itself; a CI runner has no committer identity.
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}
    return subprocess.run([sys.executable, str(CLI), "issue", "refresh-spec", *args],
                          cwd=root, capture_output=True, text=True, timeout=120, env=env)


def test_ls_2_refresh_merges_the_base_and_re_derives_both_issues(tmp_path):
    root = _two_branches(tmp_path)
    result = _refresh(root, "--base", "main")
    assert result.returncode == 0, result.stdout + result.stderr
    assert _git(root, "status", "--porcelain", "--untracked-files=no") == ""
    spec = _spec(root)
    assert "main-issue" in spec and "feature-issue" in spec, spec
    assert "<<<<<<<" not in spec


def test_ls_3_another_conflict_aborts_and_leaves_the_branch_as_it_was(tmp_path):
    root = _two_branches(tmp_path, extra_conflict=True)
    before = _git(root, "rev-parse", "HEAD")
    result = _refresh(root, "--base", "main")
    assert result.returncode != 0
    assert "README.md" in result.stderr, result.stderr
    assert _git(root, "rev-parse", "HEAD") == before
    assert not (root / ".git" / "MERGE_HEAD").exists()


# --- LS-4: the decision is recorded ----------------------------------------------

def test_ls_4_an_adr_records_the_selection_rule():
    found = [p for p in (ROOT / "architecture" / "decisions").glob("ADR-*.md")
             if "living spec" in p.read_text(encoding="utf-8").lower()
             and "reachable" in p.read_text(encoding="utf-8")
             and "ADR-008" in p.read_text(encoding="utf-8")]
    assert found, "no ADR records which landed issues the derive includes"


# --- review 1 ---------------------------------------------------------------------

def test_ls_1_a_spec_written_before_2_0_still_names_its_issues(tmp_path):
    # Specs up to v1.8.0 labelled the source with the retired word for an issue.
    root = _repo(tmp_path)
    _issue(root, "old-issue", "0" * 40)
    (root / "docs").mkdir()
    (root / "docs" / "system-spec.md").write_text(
        "- **Source " + "ta" + "sk:** `old-issue`\n", encoding="utf-8")
    _commit_spec(root, "a spec from before 2.0")
    flow.derive_system_spec(str(root))
    assert "TRC-old-issue" in _spec(root)


def test_ls_1_a_filtered_issue_is_not_reported_as_missing(tmp_path):
    import pytest
    from compass_pkg.core import CompassError
    root = _repo(tmp_path)
    _git(root, "checkout", "-q", "-b", "other")
    (root / "o.txt").write_text("o\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "o")
    elsewhere = _git(root, "rev-parse", "HEAD")
    _git(root, "checkout", "-q", "main")
    _issue(root, "on-another-branch", elsewhere)
    (root / "docs").mkdir()
    (root / "docs" / "system-spec.md").write_text(
        "- **Source issue:** `on-another-branch`\n", encoding="utf-8")
    try:
        flow.derive_system_spec(str(root))
    except CompassError as exc:
        assert "missing from" not in str(exc), exc


def test_ls_3_a_base_that_does_not_exist_is_named(tmp_path):
    root = _two_branches(tmp_path)
    result = _refresh(root, "--base", "origin/nowhere")
    assert result.returncode != 0
    assert "origin/nowhere" in result.stderr and "does not exist" in result.stderr, result.stderr


def test_ls_3_a_merge_already_in_progress_is_left_alone(tmp_path):
    root = _two_branches(tmp_path)
    subprocess.run([*GIT, "merge", "--no-commit", "--no-ff", "-s", "ours", "main"],
                   cwd=root, capture_output=True, check=True)
    result = _refresh(root, "--base", "main")
    assert result.returncode != 0
    assert "merge" in result.stderr and "in progress" in result.stderr, result.stderr
    assert (root / ".git" / "MERGE_HEAD").exists(), "the person's merge was aborted"


def test_ls_3_a_failed_commit_leaves_no_merge_half_done(tmp_path):
    root = _two_branches(tmp_path)
    hook = root / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\necho blocked by a hook >&2\nexit 1\n")
    hook.chmod(0o755)
    before = _git(root, "rev-parse", "HEAD")
    result = _refresh(root, "--base", "main")
    assert result.returncode != 0
    assert "blocked by a hook" in result.stderr, result.stderr
    assert not (root / ".git" / "MERGE_HEAD").exists()
    assert _git(root, "rev-parse", "HEAD") == before


def test_ls_1_a_record_with_no_land_commit_is_kept(tmp_path):
    # Records written before ship-commit recorded a land commit, or by hand,
    # cannot be judged by branch, so they are kept as before.
    root = _repo(tmp_path)
    work = root / ".compass" / "work" / "old-record"
    work.mkdir(parents=True)
    (work / "manifest.yml").write_text(
        "schema_version: '2.0'\ntask: old-record\nstatus: landed\n"
        "land_timestamp: '2026-10-01T00:00:00+00:00'\n"
        "scenarios:\n- id: TRC-old-record\n  title: an old behaviour\n"
        "  intent: INT-old\n", encoding="utf-8")
    flow.derive_system_spec(str(root))
    assert "TRC-old-record" in _spec(root)


def test_ls_2_an_up_to_date_branch_names_no_merge_in_its_commit(tmp_path):
    # Nothing was merged, so the commit must not say a merge happened.
    root = _repo(tmp_path)
    _issue(root, "here", _git(root, "rev-parse", "HEAD"))
    result = _refresh(root, "--base", "main")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "already up to date" in result.stdout
    message = _git(root, "log", "-1", "--format=%s")
    assert "merging" not in message, message
