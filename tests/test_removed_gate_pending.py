"""A pending removed gate does not stop the checks that wait for every gate (ADR-091).

9.0.0 removed the `verify.analyze` gate. An issue made before then can still list
it as pending, and such an issue can land, because a removed gate owes nothing.
So every reader that asks "has every gate passed?" must leave it out too. If one
does not, the issue lands and that reader's check never runs:

- `ship-commit` does not compare the staged files with the newest green;
- `evidence-matches-tree` reads a stale green as a note;
- `compass next` names the verify stage when no gate is left to clear.

Each reader asks `gate_status.all_gates_passed`.

Issue: ayeo-io/compass-delivery#353.
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

import compass_pkg  # noqa: E402,F401  (the bundled PyYAML first)

SLUG = "bound"
GIT = ["git", "-c", "user.email=t@example.com", "-c", "user.name=t"]

PASSED_AND_ANALYZE_PENDING = [
    {"id": "verify.correctness", "status": "pass", "evidence": []},
    {"id": "verify.analyze", "status": "pending", "evidence": []},
]


def test_a_pending_removed_gate_leaves_every_gate_passed():
    from compass_pkg.gate_status import all_gates_passed
    assert all_gates_passed({"gates": PASSED_AND_ANALYZE_PENDING}) is True


def test_a_pending_live_gate_is_not_every_gate_passed():
    from compass_pkg.gate_status import all_gates_passed
    gates = PASSED_AND_ANALYZE_PENDING + [{"id": "verify.security", "status": "pending"}]
    assert all_gates_passed({"gates": gates}) is False


def test_no_gate_is_not_every_gate_passed():
    from compass_pkg.gate_status import all_gates_passed
    assert all_gates_passed({"gates": []}) is False
    assert all_gates_passed({}) is False


def test_compass_next_reaches_ship_past_a_pending_removed_gate():
    from compass_pkg import next_cmd
    task = {"stages": {"verify": "thorough", "ship": "thorough"},
            "gates": PASSED_AND_ANALYZE_PENDING}
    assert "verify" in next_cmd._stages_on_record(task, None)


def _git(root, *args):
    return subprocess.run([*GIT, *args], cwd=root, capture_output=True,
                          text=True, check=True).stdout.strip()


def _cli(root, *args):
    return subprocess.run([sys.executable, str(CLI), *args], cwd=root,
                          capture_output=True, text=True,
                          env={**os.environ, "CLAUDE_PROJECT_DIR": str(root)})


@pytest.fixture
def repo(tmp_path):
    """A git repository and an issue whose live gates have passed, with the
    removed `verify.analyze` gate still pending, and a green on record."""
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    (root / "src").mkdir()
    (root / "src" / "app.py").write_text("x = 1\n")
    (root / ".gitignore").write_text("/.compass/work/\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base")
    task = root / ".compass" / "work" / SLUG
    task.mkdir(parents=True)
    (task / "manifest.yml").write_text(yaml.safe_dump({
        "schema_version": "2.0", "issue": SLUG, "created": "2026-09-25",
        "status": "active", "gates": PASSED_AND_ANALYZE_PENDING, "evidence": [],
        "changed_files": [{"path": "src/new.py", "scenarios": ["S-1"]}]},
        sort_keys=False))
    (root / "src" / "new.py").write_text("y = 2\n")
    green = _cli(root, "tdd-green", "--issue", SLUG, "--", sys.executable, "-c", "pass")
    assert green.returncode == 0, green.stderr
    (root / "src" / "new.py").write_text("y = 3\n")   # changed after the green
    return root


def test_evidence_matches_tree_fails_a_stale_green(repo):
    from compass_pkg.binding import _check_evidence_matches_tree
    task_dir = repo / ".compass" / "work" / SLUG
    task = yaml.safe_load((task_dir / "manifest.yml").read_text())
    ok, why = _check_evidence_matches_tree(task, str(task_dir))
    assert ok is False, why
    assert "stale" in why


def test_ship_commit_refuses_a_stale_green(repo):
    _git(repo, "add", "src/new.py")
    result = _cli(repo, "ship-commit", "--issue", SLUG, "-m", "land it")
    assert result.returncode != 0, result.stdout
    assert "changed after" in result.stderr, result.stderr
