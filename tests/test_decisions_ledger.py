"""Settled decisions are immutable ledger entries, recorded by the person who
made them: the decisions-ledger issue, GitHub issue #254, and ADR-027.

Each test builds a throwaway git repository with a Compass project, and runs
`compass decision` and `compass ci` there.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"


def _git(root: Path, *args) -> str:
    r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def _compass(root: Path, *args):
    return subprocess.run([sys.executable, str(CLI), *args], cwd=root,
                          capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "Ada Person")
    (root / ".compass").mkdir()
    (root / "README.md").write_text("x\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base")
    return root


def _entries(root: Path) -> list:
    d = root / "governance" / "decisions"
    return sorted(d.glob("*.md")) if d.is_dir() else []


def test_record_writes_an_entry_with_decided_by_from_git(repo):
    """DL-A: the entry is dated today, named for its slug, and names the git
    user as the decider."""
    r = _compass(repo, "decision", "record", "keep-the-name")
    assert r.returncode == 0, r.stdout + r.stderr
    [entry] = _entries(repo)
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}-keep-the-name\.md", entry.name), entry.name
    text = entry.read_text()
    assert "Ada Person" in text
    for section in ("Decided by", "Date", "Supersedes", "Decision", "Why", "Evidence"):
        assert f"## {section}" in text, section


def test_compass_decided_by_wins_over_user_name(repo):
    """DL-A: `git config compass.decidedBy` names the decider when set, so a
    person can be recorded by a handle rather than their legal name."""
    _git(repo, "config", "compass.decidedBy", "ada-handle")
    assert _compass(repo, "decision", "record", "use-a-handle").returncode == 0
    text = _entries(repo)[0].read_text()
    assert "ada-handle" in text and "Ada Person" not in text


def test_record_offers_no_way_to_set_the_decider(repo):
    """DL-A: there is no option for `Decided by`; an option would be filled
    in by whoever runs the command."""
    r = _compass(repo, "decision", "record", "--help")
    assert r.returncode == 0 and "--supersedes" in r.stdout, r.stdout + r.stderr
    options = set(re.findall(r"(--[a-z][a-z-]*)", r.stdout))
    assert options == {"--supersedes", "--quiet", "--summary", "--verbose", "--json",
                       "--evidence-out", "--help"}, options


def test_record_refuses_an_existing_slug_and_a_bad_one(repo):
    """DL-A: one entry per slug; a slug is one lower-case hyphenated segment."""
    assert _compass(repo, "decision", "record", "once").returncode == 0
    again = _compass(repo, "decision", "record", "once")
    assert again.returncode != 0 and "once" in again.stdout + again.stderr
    for bad in ("../escape", "Has-Capitals", "two words"):
        assert _compass(repo, "decision", "record", bad).returncode != 0, bad
    assert len(_entries(repo)) == 1


def test_record_refuses_without_a_git_name(repo):
    """DL-A: no recorded decider, no entry."""
    _git(repo, "config", "--unset", "user.name")
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_SYSTEM"] = os.devnull
    r = subprocess.run([sys.executable, str(CLI), "decision", "record", "nameless"],
                       cwd=repo, capture_output=True, text=True, env=env)
    assert r.returncode != 0
    assert "git config" in r.stdout + r.stderr, r.stdout + r.stderr
    assert not _entries(repo)


def test_supersedes_names_an_existing_entry(repo):
    """DL-A: a change of mind is a new entry that names the old one."""
    assert _compass(repo, "decision", "record", "first-choice").returncode == 0
    missing = _compass(repo, "decision", "record", "second", "--supersedes", "no-such")
    assert missing.returncode != 0
    ok = _compass(repo, "decision", "record", "second-choice", "--supersedes", "first-choice")
    assert ok.returncode == 0, ok.stdout + ok.stderr
    newest = [e for e in _entries(repo) if "second-choice" in e.name][0]
    assert "first-choice" in newest.read_text()


def test_list_and_show(repo):
    """DL-B: list prints date, slug and the decision's first line; show
    prints the entry."""
    assert _compass(repo, "decision", "record", "listed").returncode == 0
    entry = _entries(repo)[0]
    entry.write_text(entry.read_text().replace(
        "## Decision\n", "## Decision\n\nThe listed choice stands.\n", 1))
    out = _compass(repo, "decision", "list").stdout
    assert "listed" in out and "The listed choice stands." in out, out
    shown = _compass(repo, "decision", "show", "listed")
    assert shown.returncode == 0 and "The listed choice stands." in shown.stdout


def _committed_entry(repo: Path) -> Path:
    assert _compass(repo, "decision", "record", "settled").returncode == 0
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "record")
    _git(repo, "tag", "base")
    return _entries(repo)[0]


def test_check_fails_on_an_edited_entry(repo):
    """DL-C: an entry that exists at the base ref may not change."""
    entry = _committed_entry(repo)
    entry.write_text(entry.read_text() + "\nedited\n")
    r = _compass(repo, "decision", "check", "--base", "base")
    assert r.returncode != 0 and entry.name in r.stdout + r.stderr


def test_check_fails_on_a_removed_entry(repo):
    """DL-C: removing an entry is a change too."""
    entry = _committed_entry(repo)
    entry.unlink()
    r = _compass(repo, "decision", "check", "--base", "base")
    assert r.returncode != 0 and entry.name in r.stdout + r.stderr


def test_check_passes_a_new_entry_and_refuses_a_bad_ref(repo):
    """DL-C: adding is allowed; an unknown ref fails loudly."""
    _committed_entry(repo)
    assert _compass(repo, "decision", "record", "added-later").returncode == 0
    assert _compass(repo, "decision", "check", "--base", "base").returncode == 0
    bad = _compass(repo, "decision", "check", "--base", "no-such-ref")
    assert bad.returncode != 0 and "no-such-ref" in bad.stdout + bad.stderr


def test_ci_runs_the_history_check_with_since(repo):
    """DL-D: compass ci --since runs the check; without it, ci says the
    check was skipped."""
    entry = _committed_entry(repo)
    plain = _compass(repo, "ci")
    assert "history check skipped" in plain.stdout.lower(), plain.stdout
    entry.write_text(entry.read_text() + "\nedited\n")
    since = _compass(repo, "ci", "--since", "base")
    assert since.returncode != 0 and entry.name in since.stdout, since.stdout


def test_reviewers_read_the_ledger():
    """DL-E: the reviewer and the governance-check skill read the ledger
    before recommending a reversal."""
    for rel in ("agents/reviewer.md", "skills/governance-check/SKILL.md"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "governance/decisions/" in text and "settled by" in text, rel


def test_the_verb_is_on_the_public_surface():
    """DL-F: the baseline and the README name the decision verb."""
    baseline = json.loads((ROOT / "tests" / "fixtures" / "cli-surface-baseline.json").read_text())
    assert "decision" in baseline["subcommands"]
    assert "compass decision" in (ROOT / "README.md").read_text(encoding="utf-8")


def test_the_ledger_holds_at_least_ten_entries():
    """DL-G: the first ten entries, each confirmed by the maintainer."""
    entries = sorted((ROOT / "governance" / "decisions").glob("*.md"))
    assert len(entries) >= 10, [e.name for e in entries]


def test_ci_compares_the_ledger_with_the_base_branch():
    """DL-D: on a pull request, CI runs compass ci --since the base branch,
    with full history, so an edited entry fails there."""
    text = (ROOT / ".github" / "workflows" / "compass.yml").read_text(encoding="utf-8")
    job = text[text.index("self-check"):text.index("bdd-adapter")]
    assert "fetch-depth: 0" in job
    assert 'compass ci --since "origin/$BASE_REF"' in job
    assert "BASE_REF: ${{ github.base_ref }}" in job


@pytest.fixture
def subdir_repo(tmp_path):
    """A git repository whose Compass project sits in app/, a layout Compass
    supports."""
    top = tmp_path / "top"
    root = top / "app"
    root.mkdir(parents=True)
    _git(top, "init", "-q")
    _git(top, "config", "user.email", "t@example.com")
    _git(top, "config", "user.name", "Ada Person")
    (root / ".compass").mkdir()
    (top / "README.md").write_text("x\n")
    _git(top, "add", "-A")
    _git(top, "commit", "-q", "-m", "base")
    return top, root


def test_check_in_a_subdirectory_project(subdir_repo):
    """DL-C: with the project in a subdirectory, an unchanged entry passes
    and an emptied one fails."""
    top, root = subdir_repo
    assert _compass(root, "decision", "record", "nested").returncode == 0
    _git(top, "add", "-A")
    _git(top, "commit", "-q", "-m", "record")
    _git(top, "tag", "base")
    clean = _compass(root, "decision", "check", "--base", "base")
    assert clean.returncode == 0, clean.stdout + clean.stderr
    entry = _entries(root)[0]
    entry.write_text("")
    emptied = _compass(root, "decision", "check", "--base", "base")
    assert emptied.returncode != 0 and entry.name in emptied.stdout + emptied.stderr


def test_check_ignores_line_ending_conversion(repo):
    """DL-C: an unchanged entry in a clone that converts line endings passes."""
    _committed_entry(repo)
    _git(repo, "config", "core.autocrlf", "true")
    entry = _entries(repo)[0]
    entry.write_bytes(entry.read_bytes().replace(b"\n", b"\r\n"))
    r = _compass(repo, "decision", "check", "--base", "base")
    assert r.returncode == 0, r.stdout + r.stderr


def test_plain_ci_keeps_exit_zero_with_an_edited_entry(repo):
    """DL-D: without --since, compass ci's exit code does not change."""
    entry = _committed_entry(repo)
    entry.write_text(entry.read_text() + "\nedited\n")
    assert _compass(repo, "ci").returncode == 0
