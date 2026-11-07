"""The loop ceilings are policy rules, resolved by an issue's assessment.

The ceilings are rules in `governance/routing-policy.yml`. Before 9.0.0
`compass issue subtask` refused to open work past them and `compass check`
refused to land a run past them without a stop reason (LC-B to LC-F). 9.0.0
removed the subtask record and that check (ADR-090), and the tests of LC-B to
LC-F with them. The rules stay readable, and LC-A still holds.

Scenario ids: LC-A, in the acceptance criteria of the issue `loop-ceilings`
(GitHub issue #300).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
sys.path.insert(0, str(ROOT / "cli"))


def loop_ceilings(task):
    # Imported when called, so each test fails on its own behaviour while
    # the function is missing, not the whole file at collection.
    from compass_pkg.loop_ceilings import loop_ceilings as resolve
    return resolve(task)

SLUG = "multi"
GIT = ["git", "-c", "user.email=t@example.com", "-c", "user.name=t"]


def _git(root, *args):
    return subprocess.run([*GIT, *args], cwd=root, capture_output=True,
                          text=True, check=True).stdout.strip()


def _manifest(root, risk="cross-cutting", created="2026-10-03"):
    task = root / ".compass" / "work" / SLUG
    task.mkdir(parents=True, exist_ok=True)
    # A fresh manifest names no generation, so a stored one from an earlier
    # call would be refused as unreferenced: start the issue clean.
    shutil.rmtree(task / "generations", ignore_errors=True)
    (task / "manifest.yml").write_text(
        f"schema_version: '2.0'\nissue: {SLUG}\ncreated: '{created}'\n"
        f"status: active\nassessment: {{risk: {risk}, familiarity: "
        "brownfield-mapped, size: large, goal: delivery, role: engineer, "
        "labels: []}\n")
    evaluate = subprocess.run(
        [sys.executable, str(CLI), "approach", "evaluate", "--issue", SLUG,
         "--write"], cwd=root, capture_output=True, text=True)
    assert evaluate.returncode == 0, evaluate.stderr


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "src" / "app.py").write_text("x = 1\n")
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base")
    _manifest(root)
    return root


def _task(root):
    return yaml.safe_load((root / ".compass" / "work" / SLUG / "manifest.yml")
                          .read_text())


# --- LC-A: the ceilings are policy rules -------------------------------------

def test_lc_a_shipped_ceilings_resolve_by_risk(repo):
    old = os.getcwd()
    os.chdir(repo)
    try:
        wide = loop_ceilings(_task(repo))
        _manifest(repo, risk="contained")
        narrow = loop_ceilings(_task(repo))
    finally:
        os.chdir(old)
    assert wide["builder_attempts"] == (3, "RP-LOOP-001")
    assert wide["review_rounds"] == (3, "RP-LOOP-002")
    assert wide["replans"] == (2, "RP-LOOP-004")
    assert wide["repeated_error"] == (3, "RP-LOOP-005")
    # The lowest matching limit wins, so the contained rule lowers it.
    assert narrow["review_rounds"] == (2, "RP-LOOP-003")


def test_lc_a_a_policy_without_the_rules_gives_no_ceiling(repo):
    # 9.0.0 removed the drift report (ADR-098), which also named the missing
    # rules; the ceilings themselves are still absent.
    gov = repo / "governance"
    gov.mkdir()
    shutil.copy(ROOT / "governance" / "guardrails.yml", gov)
    policy = yaml.safe_load((ROOT / "governance" / "routing-policy.yml")
                            .read_text())
    del policy["routing_guardrails"]["loop_ceilings"]
    (gov / "routing-policy.yml").write_text(yaml.safe_dump(policy))
    old = os.getcwd()
    os.chdir(repo)
    try:
        assert loop_ceilings(_task(repo)) == {}
    finally:
        os.chdir(old)
