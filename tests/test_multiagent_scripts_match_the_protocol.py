"""The multiagent scripts' comments and messages say what the protocol says.

Integration runs before `/compass:verify`, once per wave, and does not land
the issue: only `ship-commit` does (ADR-026). The session that owns the
issue orchestrates, whatever the number of subtasks. The scripts, and the
protocol's own landing command, must say the same.

Scenario ids: DSS-1 to DSS-4, in the delivery approach of issue
`multiagent-scripts-still-say-ship`.
"""
from __future__ import annotations

import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
MULTIAGENT = ROOT / "scripts" / "multiagent.sh"
INTEGRATE = ROOT / "scripts" / "integrate.sh"
PROTOCOL = ROOT / "docs" / "multiagent-protocol.md"
STALE = [r"LAND THE WORKTREES", r"ship-stage", r"lead builder", r"point of ship",
         r"before ship closes", r"land them with", r"ship integrates"]


def _git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args],
                          capture_output=True, text=True, check=True)


def _repo(tmp_path, map_rows):
    repo = tmp_path / "proj"
    task = repo / ".compass" / "work" / "demo"
    task.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "T")
    (repo / ".gitignore").write_text("/.compass/work/\n/.compass/current-task\n")
    (repo / ".compass" / "config.yml").write_text(
        "version: 1.0.0\nmode: enforced\nworktree_root: ../wt\nmax_worktrees: 4\n")
    (task / "manifest.yml").write_text(
        "task: demo\nassessment: {risk: contained}\nfired_guardrails: []\n")
    (task / "delivery-approach.md").write_text("# approach\n")
    (task / "distribution-map.md").write_text(
        "| Subtask | Owns work unit(s) | Owns scenario ids | Branch name | Wave |\n"
        "|---|---|---|---|---|\n" + map_rows)
    (repo / "app.py").write_text("x = 1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")
    return repo


def test_dss_1_no_script_says_integration_lands_or_happens_at_ship():
    found = []
    for script in (MULTIAGENT, INTEGRATE):
        for n, line in enumerate(script.read_text(encoding="utf-8").splitlines(), 1):
            for pattern in STALE:
                if re.search(pattern, line, re.IGNORECASE):
                    found.append(f"{script.name}:{n}: {line.strip()}")
    assert not found, "\n".join(found)


def test_dss_2_multiagent_names_the_order_of_waves_and_no_clean(tmp_path):
    repo = _repo(tmp_path, "| subtask-1 | U1 | S1 | compass/demo/subtask-1 | 1 |\n"
                           "| subtask-2 | U2 | S2 | compass/demo/subtask-2 | 2 |\n")
    result = subprocess.run(["bash", str(MULTIAGENT), "demo", "--dry-run"],
                            cwd=str(repo), capture_output=True, text=True, timeout=120)
    out = result.stdout
    assert result.returncode == 0, out + result.stderr
    assert "--no-clean" in out, out
    assert re.search(r"after this wave integrates", out, re.IGNORECASE), out


def test_dss_3_integrate_says_no_regression_ran_when_none_did(tmp_path):
    repo = _repo(tmp_path, "| subtask-1 | U1 | S1 | compass/demo/subtask-1 | 1 |\n")
    wt = tmp_path / "builder"
    _git(repo, "worktree", "add", "-q", "-b", "compass/demo/subtask-1", str(wt))
    (wt / "app.py").write_text("x = 2\n")
    _git(wt, "commit", "-qam", "work")
    result = subprocess.run(["bash", str(INTEGRATE), "demo", "--no-clean"],
                            cwd=str(repo), capture_output=True, text=True, timeout=120)
    out = result.stdout + result.stderr
    assert "merged cleanly" in out, out
    assert "regression above is green" not in out, out
    assert "no regression ran" in out.lower(), out


def test_dss_4_the_protocol_landing_command_runs_as_written():
    text = PROTOCOL.read_text(encoding="utf-8")
    block = text[text.index("## Landing"):]
    assert re.search(r"compass ship-commit --issue <slug> -m ", block), block[:400]
