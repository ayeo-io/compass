"""`compass ship-commit` lands an issue whose declared file was deleted.

With nothing staged, ship-commit checks each declared changed file is clean
and in HEAD. A deliberate, committed deletion is in neither, so it refused
for ever. A declared path that is clean, absent from HEAD and absent from
disk is a committed deletion and counts as landed. A path never committed
and absent, or absent from HEAD but present on disk, still refuses.

Scenario id: IDR-5 (this repository's settings moved to compass.yml and
`.compass/config.yml` was deleted).
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

SLUG = "cdl"
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
    """A repository holding one source file, an issue declaring it, gates passed."""
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    (root / "src").mkdir()
    (root / "src" / "old.py").write_text("x = 1\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base")
    task = root / ".compass" / "work" / SLUG
    task.mkdir(parents=True)
    _write_manifest(root, ["src/old.py"])
    return root


def _write_manifest(root, paths):
    path = root / ".compass" / "work" / SLUG / "manifest.yml"
    path.write_text(yaml.safe_dump({
        "schema_version": "2.0", "issue": SLUG, "created": "2026-09-28",
        "status": "active", "evidence": [],
        "gates": [{"id": "verify.correctness", "status": "pass",
                   "evidence": []}],
        "changed_files": [{"path": p, "scenarios": ["S-1"]} for p in paths],
    }, sort_keys=False))


def _ship(root):
    return _cli(root, "ship-commit", "--issue", SLUG, "-m", "land it")


def test_idr5_a_committed_deletion_lands(repo):
    _git(repo, "rm", "-q", "src/old.py")
    _git(repo, "commit", "-q", "-m", "delete it")
    assert _git(repo, "status", "--porcelain", "--", "src/old.py") == ""

    result = _ship(repo)

    assert result.returncode == 0, result.stdout + result.stderr


def test_idr5_a_never_committed_absent_file_still_refuses(repo):
    _write_manifest(repo, ["src/old.py", "src/never.py"])

    result = _ship(repo)

    assert result.returncode != 0, result.stdout
    combined = result.stdout + result.stderr
    assert "src/never.py" in combined, combined


def test_idr5_an_untracked_file_on_disk_still_refuses(repo):
    (repo / "src" / "new.py").write_text("y = 1\n")
    _write_manifest(repo, ["src/old.py", "src/new.py"])

    result = _ship(repo)

    assert result.returncode != 0, result.stdout
    combined = result.stdout + result.stderr
    assert "src/new.py" in combined, combined
