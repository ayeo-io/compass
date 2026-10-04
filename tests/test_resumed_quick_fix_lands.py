"""A resumed quick fix lands in one command.

Sessions resuming a quick fix another session had started made 30 and 37
tool calls against 6 and 12 without a framework: about eight were `--help`
calls looking for the landing verbs, and the rest passed each gate by hand,
because nothing told them `quick-fix finish` lands a resumed quick fix
(#386).

Scenario id: RQ-1 (issue `resumed-quick-fix-lands-in-one-command`).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from test_quick_fix_verbs import (  # noqa: F401
    _finish, _manifest, _ready_to_finish, repo)

ROOT = Path(__file__).resolve().parent.parent


def test_rq_1_the_resume_command_names_the_landing_command():
    text = " ".join((ROOT / "commands" / "resume.md").read_text().split())
    assert "compass quick-fix finish" in text
    assert "compass tdd-red" in text
    assert "do not pass the gates by hand" in text.lower()


def test_rq_1_finish_lands_a_quick_fix_with_no_start_record(repo):
    _ready_to_finish(repo, "fix")
    record = subprocess.run(
        ["git", "rev-parse", "--git-path", "compass/start-state/fix.json"],
        cwd=str(repo), capture_output=True, text=True, check=True).stdout.strip()
    (repo / record).unlink()        # another session started it
    result = _finish(repo, "fix")
    assert result.returncode == 0, result.stdout + result.stderr
    assert _manifest(repo, "fix")["status"] == "landed"
