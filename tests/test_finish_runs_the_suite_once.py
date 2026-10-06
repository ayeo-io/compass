"""`compass quick-fix finish` runs the test command once.

Finish records a green for each scenario. It ran the command once per
scenario, so a quick fix with five scenarios and the full suite as its
command ran the suite five times. One passing run on one tree is evidence for
every scenario it covers, so the command now runs once and each scenario
still gets its own record.

Scenario id: `TRC-001` (issue `finish-runs-the-suite-once`).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

from test_quick_fix_verbs import (  # noqa: E402
    _base_greeting, _manifest, _run, _start, _write_greeting, repo,  # noqa: F401
)

TEST = "tests/test_greeting.py::test_greeting_says_hello"


def test_trc_001_finish_runs_the_command_once_for_two_scenarios(repo, tmp_path):
    _base_greeting(repo)
    assert _start(repo, "two-scenarios").returncode == 0
    added = _run(repo, "scenario", "add", "TRC-002", "--issue", "two-scenarios",
                 "--intent", "INT-1", "--test", TEST, "--quiet",
                 "--title", "Given the greeting, when it is read, then it is polite")
    assert added.returncode == 0, added.stderr
    for sid in ("TRC-001", "TRC-002"):
        red = _run(repo, "tdd-red", "--issue", "two-scenarios", "--scenario", sid,
                   "--", "python3", "-m", "pytest", "-q", TEST)
        assert red.returncode == 0, red.stderr
    _write_greeting(repo, "Hello, %s!")
    traced = _run(repo, "changed-file", "add", "data/greeting.txt", "--issue",
                  "two-scenarios", "--scenario", "TRC-001")
    assert traced.returncode == 0, traced.stderr

    # The command counts its own runs in a file outside the repository.
    count = tmp_path / "runs.txt"
    command = f"echo run >> {count} && python3 -m pytest -q {TEST}"
    done = _run(repo, "quick-fix", "finish", "--issue", "two-scenarios", "-m",
                "Say hello properly", "--no-commit", "--", "sh", "-c", command)
    assert done.returncode == 0, done.stdout + done.stderr

    assert count.read_text().splitlines() == ["run"], "the command ran more than once"
    greens = {e["scenario"] for e in _manifest(repo, "two-scenarios").get("evidence") or []
              if isinstance(e, dict) and e.get("type") == "test-run"}
    assert {"TRC-001", "TRC-002"} <= greens, greens
