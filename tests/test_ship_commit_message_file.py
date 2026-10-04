"""`compass ship-commit` takes its message from a file.

A long commit message is what `git commit -F` exists for, and ship-commit
took only `-m`. A shell fallback that routed around it printed "committed"
while HEAD had not moved, so the check ship-commit exists for was lost
(#120). `-F/--message-file` keeps long messages inside ship-commit.

Scenario id: SF-1 (issue `ship-commit-takes-a-message-file`).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

from test_quick_fix_verbs import _run, repo  # noqa: E402,F401

MESSAGE = "Add the greeting\n\nA body line with detail.\n\n| a | b |\n|---|---|\n"


def _head(root):
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=root,
                          capture_output=True, text=True).stdout.strip()


def _stage(root):
    (root / "greeting.txt").write_text("Hello\n")
    subprocess.run(["git", "add", "greeting.txt"], cwd=root, check=True)


def test_sf_1_ship_commit_takes_the_message_from_a_file(repo, tmp_path):
    _stage(repo)
    msg = tmp_path / "msg.txt"
    msg.write_text(MESSAGE, encoding="utf-8")
    before = _head(repo)
    result = _run(repo, "ship-commit", "-F", str(msg))
    assert result.returncode == 0, result.stderr
    assert _head(repo) != before
    body = subprocess.run(["git", "log", "-1", "--format=%B"], cwd=repo,
                          capture_output=True, text=True).stdout
    assert body.strip() == MESSAGE.strip()


def test_sf_1_both_or_neither_message_is_refused(repo, tmp_path):
    _stage(repo)
    msg = tmp_path / "msg.txt"
    msg.write_text(MESSAGE, encoding="utf-8")
    before = _head(repo)
    both = _run(repo, "ship-commit", "-m", "x", "-F", str(msg))
    neither = _run(repo, "ship-commit")
    assert both.returncode != 0 and neither.returncode != 0
    assert _head(repo) == before


def test_sf_1_a_missing_or_empty_file_is_refused(repo, tmp_path):
    _stage(repo)
    before = _head(repo)
    missing = _run(repo, "ship-commit", "-F", str(tmp_path / "nope.txt"))
    assert missing.returncode != 0 and "nope.txt" in missing.stderr
    empty = tmp_path / "empty.txt"
    empty.write_text("  \n", encoding="utf-8")
    blank = _run(repo, "ship-commit", "-F", str(empty))
    assert blank.returncode != 0
    assert _head(repo) == before
