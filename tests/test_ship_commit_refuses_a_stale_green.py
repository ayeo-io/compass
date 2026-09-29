"""`compass ship-commit` refuses a stale green.

`ship-commit` commits whatever is staged, even when a file the issue changed
was edited after its newest green - so the landed files were not the tested
files, and only a later `compass check` noticed. Before it commits, it now
compares the newest bound record's `changes_id` with the same files now
(`binding.changes_paths`), refuses on a mismatch, and names the paths whose
content changed. An edit outside the issue's declared files and tests causes
no refusal.

Scenario ids: QFG-3 (the refusal), QFG-4 (the safety contract states the
limits a green record carries).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
sys.path.insert(0, str(ROOT / "cli"))

SLUG = "ssg"
GIT = ["git", "-c", "user.email=t@example.com", "-c", "user.name=t"]


def _git(root, *args):
    return subprocess.run([*GIT, *args], cwd=root, capture_output=True,
                          text=True, check=True).stdout.strip()


def _cli(root, *args):
    return subprocess.run([sys.executable, str(CLI), *args], cwd=root,
                          capture_output=True, text=True,
                          env={**os.environ, "CLAUDE_PROJECT_DIR": str(root)})


@pytest.fixture
def repo(tmp_path):
    """A git repository with a tracked, unclaimed file, and an issue that
    claims a new source file, gates already passed."""
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    (root / "src").mkdir()
    (root / "src" / "app.py").write_text("x = 1\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base")
    task = root / ".compass" / "work" / SLUG
    task.mkdir(parents=True)
    _write_manifest(root)
    return root


def _write_manifest(root, *, gates="pass"):
    path = root / ".compass" / "work" / SLUG / "manifest.yml"
    data = yaml.safe_load(path.read_text()) if path.exists() else {}
    data.update({"schema_version": "2.0", "issue": SLUG,
                 "created": "2026-09-28", "status": "active",
                 "gates": [{"id": "verify.correctness", "status": gates,
                            "evidence": []}],
                 "changed_files": [{"path": "src/new.py",
                                    "scenarios": ["S-1"]}]})
    data.setdefault("evidence", [])
    path.write_text(yaml.safe_dump(data, sort_keys=False))


def _green(root):
    result = _cli(root, "tdd-green", "--issue", SLUG, "--", sys.executable,
                  "-c", "pass")
    assert result.returncode == 0, result.stderr


def test_qfg3_a_changed_file_after_the_green_refuses(repo):
    """An edit to an issue file after its newest green stops the commit."""
    (repo / "src" / "new.py").write_text("y = 1\n")
    _green(repo)
    (repo / "src" / "new.py").write_text("y = 2\n")   # edited after the green
    _git(repo, "add", "src/new.py")
    head_before = _git(repo, "rev-parse", "HEAD")

    result = _cli(repo, "ship-commit", "--issue", SLUG, "-m", "land it")

    assert result.returncode != 0, result.stdout
    combined = result.stdout + result.stderr
    assert "src/new.py" in combined, combined
    assert "tdd-green" in combined, combined
    assert _git(repo, "rev-parse", "HEAD") == head_before, combined


def test_qfg3_an_edit_outside_the_issue_does_not_refuse(repo):
    """A file the issue did not claim can change freely; it is not compared."""
    (repo / "src" / "new.py").write_text("y = 1\n")
    _green(repo)
    (repo / "src" / "app.py").write_text("x = 2\n")   # unclaimed, unstaged
    _git(repo, "add", "src/new.py")

    result = _cli(repo, "ship-commit", "--issue", SLUG, "-m", "land it")

    assert result.returncode == 0, result.stdout + result.stderr


def test_qfg3_a_matching_green_commits(repo):
    """The control: nothing changed after the green, so the commit lands."""
    (repo / "src" / "new.py").write_text("y = 1\n")
    _green(repo)
    _git(repo, "add", "src/new.py")
    head_before = _git(repo, "rev-parse", "HEAD")

    result = _cli(repo, "ship-commit", "--issue", SLUG, "-m", "land it")

    assert result.returncode == 0, result.stdout + result.stderr
    assert _git(repo, "rev-parse", "HEAD") != head_before


def test_qfg3_a_landed_issue_does_not_block_a_later_ship(repo):
    """A landed issue's green was judged when it landed. A later edit to
    one of its files belongs to later work, which the pointer may still
    name, so it must not be refused as this issue's stale green."""
    (repo / "src" / "new.py").write_text("y = 1\n")
    _green(repo)
    path = repo / ".compass" / "work" / SLUG / "manifest.yml"
    data = yaml.safe_load(path.read_text())
    data["status"] = "landed"
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    (repo / "src" / "new.py").write_text("y = 3\n")   # later work
    _git(repo, "add", "src/new.py")
    head_before = _git(repo, "rev-parse", "HEAD")

    result = _cli(repo, "ship-commit", "--issue", SLUG, "-m", "later work")

    assert result.returncode == 0, result.stdout + result.stderr
    assert _git(repo, "rev-parse", "HEAD") != head_before


def test_qfg4_the_safety_contract_states_the_limits():
    text = " ".join((ROOT / "docs" / "safety-contract.md")
                    .read_text(encoding="utf-8").split())
    assert "runs no test" in text and "records a green" in text
    assert "not flagged as a rerun" in text and "changed_files" in text
