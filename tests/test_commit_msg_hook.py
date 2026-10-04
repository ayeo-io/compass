"""The commit-msg hook stops a rival product name before the push.

CI checks commit messages only after they are pushed (#366). The opt-in
hook in `scripts/git-hooks/` runs the same gate on the message before the
commit is made (#367). An invented product, "Zorblax Kit", stands in for a
real one.

Scenario id: CM-1 (issue `commit-msg-name-check`).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
HOOKS = ROOT / "scripts" / "git-hooks"
GATE = ROOT / "scripts" / "rival-name-gate.py"


@pytest.fixture
def repo(tmp_path):
    key = tmp_path / "key.yml"
    key.write_text(yaml.safe_dump({"rivals": {"R0": {
        "name": "Zorblax Kit", "aliases": [], "urls": []}}}), encoding="utf-8")
    hashes = tmp_path / "hashes.txt"
    subprocess.run([sys.executable, str(GATE), "--write-hashes", str(key),
                    "--hashes", str(hashes)], check=True)
    root = tmp_path / "repo"
    root.mkdir()
    for args in (["init", "-q"], ["config", "user.email", "t@example.invalid"],
                 ["config", "user.name", "t"],
                 ["config", "core.hooksPath", str(HOOKS)]):
        subprocess.run(["git", *args], cwd=str(root), check=True)
    (root / "a.txt").write_text("a\n", encoding="utf-8")
    subprocess.run(["git", "add", "a.txt"], cwd=str(root), check=True)
    env = {**os.environ, "RIVAL_NAME_HASHES": str(hashes)}
    return root, env


def _commit(root, env, message):
    return subprocess.run(["git", "commit", "-q", "-m", message], cwd=str(root),
                          env=env, capture_output=True, text=True)


def test_cm_1_a_message_naming_a_rival_is_refused(repo):
    root, env = repo
    result = _commit(root, env, "Compare with Zorblax Kit")
    assert result.returncode != 0, "the hook let a planted name through"
    output = (result.stdout + result.stderr).lower()
    assert "zorblax" not in output
    assert "rival product" in output
    log = subprocess.run(["git", "log", "--oneline"], cwd=str(root),
                         capture_output=True, text=True)
    assert log.stdout.strip() == ""


def test_cm_1_a_clean_message_commits(repo):
    root, env = repo
    result = _commit(root, env, "Compare with R0")
    assert result.returncode == 0, result.stdout + result.stderr


def test_cm_1_contributing_says_how_to_install_it():
    text = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    assert "git config core.hooksPath scripts/git-hooks" in text
