"""A `changed_files` path that no longer exists must fail
`changed-code-traces-to-scenario`, even when it maps to a scenario
(field report `R17`).

A path breaks when a project moves a spec from `docs/specs/backlog/` to
`docs/specs/implemented/` on ship, which is what that convention asks for -
so the trace breaks precisely when the project does the right thing, and
nothing was wrong except the record, which is the only thing a reader six
months out will have.

Scenarios: trace-rot-detection/acceptance-criteria.md (SCN-A1..F2).
"""

# These tests read `compass check`'s per-check detail, which it prints only
# under `--verbose`.
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"


def _git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True, check=False)


def _project(tmp_path, *, changed, status="active", correctness="pass",
             git=True):
    root = tmp_path / "proj"
    (root / "src").mkdir(parents=True)
    import shutil
    shutil.copytree(ROOT / "governance", root / "governance")
    (root / ".compass").mkdir()
    (root / ".compass" / "config.yml").write_text("version: 1.0.0\nmode: enforced\n")
    (root / ".compass" / "current-task").write_text("t\n")
    task_dir = root / ".compass" / "work" / "t"
    task_dir.mkdir(parents=True)
    (task_dir / "delivery-approach.md").write_text("# Route\n")

    task = {
        "schema_version": "1.1", "task": "t", "created": "2026-08-04",
        "status": status,
        "assessment": {"risk": "contained", "familiarity": "greenfield",
                     "size": "small", "intent": "delivery",
                     "urgency": "none", "role": "engineer", "labels": []},
        "delivery_approach": "standard", "topology": "solo", "policy_rules_fired": [],
        "stages": {},
        "evidence": [{"id": "EV-1", "type": "test-run", "path": "evidence/green.json"}],
        "gates": [{"id": "verify.correctness", "status": correctness,
                   "evidence": ["EV-1"] if correctness == "pass" else []}],
        "scenarios": [{"id": "SCN-1", "title": "t", "intent": "INT-1",
                       "tests": ["tests/test_thing.py"]}],
        "changed_files": changed,
        "claims": [], "follow_ups": [], "reassessments": [], "friction": [],
    }
    if status == "landed":
        task["land_timestamp"] = "2026-08-04T00:00:00Z"
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(task, sort_keys=False))
    (root / "tests").mkdir(exist_ok=True)
    (root / "tests" / "test_thing.py").write_text("def test_thing():\n    pass\n")
    (task_dir / "evidence").mkdir()
    (task_dir / "evidence" / "green.json").write_text(
        '{"command": "pytest", "exit_code": 0, "passed": true}')

    if git:
        _git(root.parent, "init", "-q", "-b", "main", str(root))
        _git(root, "config", "user.email", "t@example.com")
        _git(root, "config", "user.name", "T")
    return root


def _check(root):
    return subprocess.run(
        [sys.executable, str(CLI), "check", "--verbose", "--issue", "t"],
        cwd=str(root), capture_output=True, text=True, timeout=60,
    )


def _trace_line(out):
    for line in out.splitlines():
        if "changed-code-traces-to-scenario" in line:
            return line
    return ""


# ---------------------------------------------------------------------------
# Group A - a dead trace fails the issue claiming it
# ---------------------------------------------------------------------------

def test_scn_a1_missing_path_fails_a_task_claiming_correctness(tmp_path):
    root = _project(tmp_path, changed=[{"path": "src/moved.py",
                                        "scenarios": ["SCN-1"]}])
    result = _check(root)
    combined = result.stdout + result.stderr
    assert "FAIL changed-code-traces-to-scenario" in combined, (
        f"a dead trace passed:\n{combined}")
    assert "src/moved.py" in combined, combined
    assert result.returncode != 0, combined


def test_scn_a2_rename_hint_names_the_new_path(tmp_path):
    root = _project(tmp_path, changed=[{"path": "src/old.py",
                                        "scenarios": ["SCN-1"]}])
    (root / "src" / "old.py").write_text("x = 1\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "add old")
    _git(root, "mv", "src/old.py", "src/new.py")
    _git(root, "commit", "-q", "-m", "rename")

    result = _check(root)
    combined = result.stdout + result.stderr
    assert "FAIL changed-code-traces-to-scenario" in combined, combined
    assert "src/new.py" in combined, (
        f"git knows the rename; the message should offer it:\n{combined}"
    )


def test_scn_a3_pending_gates_are_not_failed_on_a_missing_path(tmp_path):
    root = _project(tmp_path, changed=[{"path": "src/not-yet.py",
                                        "scenarios": ["SCN-1"]}],
                    correctness="pending")
    result = _check(root)
    assert "FAIL changed-code-traces-to-scenario" not in result.stdout, (
        "a task that has not claimed correctness was failed on a missing path:\n"
        + result.stdout
    )


# ---------------------------------------------------------------------------
# Group B - history is reported, not re-litigated
# ---------------------------------------------------------------------------

def test_scn_b1_landed_task_is_reported_not_failed(tmp_path):
    root = _project(tmp_path, changed=[{"path": "src/gone.py",
                                        "scenarios": ["SCN-1"]}],
                    status="landed")
    result = _check(root)
    line = _trace_line(result.stdout)
    assert "FAIL changed-code-traces-to-scenario" not in result.stdout, (
        f"re-validated a landed task's historical record:\n{result.stdout}"
    )
    assert "no longer exist" in line or "1" in line, (
        f"the rot must still be said out loud on a landed task:\n{line!r}"
    )


def test_scn_b2_a_clean_task_says_the_paths_were_confirmed(tmp_path):
    root = _project(tmp_path, changed=[{"path": "src/here.py",
                                        "scenarios": ["SCN-1"]}])
    (root / "src" / "here.py").write_text("x = 1\n")
    result = _check(root)
    line = _trace_line(result.stdout)
    assert "PASS" in line, f"{result.stdout}"
    assert "present" in line or "exist" in line, (
        f"a pass should say the paths were confirmed present, not merely "
        f"traced:\n{line!r}"
    )


# ---------------------------------------------------------------------------
# Group C - the framework does not grow a new guardrail for this
# ---------------------------------------------------------------------------

def test_scn_c1_no_new_check_name_in_governance():
    """ADR-002: growth is by artifacts, not by new checks. This behaviour rides
    on the existing check rather than adding one."""
    from tests.test_stream_c_no_new_checks_or_gates import BASELINE_CHECKS
    from check_set_files import view as shipped_view
    doc = shipped_view("guardrails.yml")
    names = set()
    for g in doc.get("guardrails", {}).get("framework", []):
        names.update(g.get("checks") or [])
    assert names <= set(BASELINE_CHECKS), (
        f"new check name(s) added: {sorted(names - set(BASELINE_CHECKS))}"
    )


# ---------------------------------------------------------------------------
# Failure modes
# ---------------------------------------------------------------------------

def test_scn_f1_a_deliberately_deleted_file_is_not_trace_rot(tmp_path):
    """Removing dead code is a legitimate change, and the file it removes is
    legitimately absent. Git knows the difference between deleted and moved."""
    root = _project(tmp_path, changed=[{"path": "src/dead.py",
                                        "scenarios": ["SCN-1"]}])
    (root / "src" / "dead.py").write_text("unused = 1\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "add dead code")
    _git(root, "rm", "-q", "src/dead.py")
    _git(root, "commit", "-q", "-m", "remove dead code")

    result = _check(root)
    assert "FAIL changed-code-traces-to-scenario" not in result.stdout, (
        f"a deliberately deleted file was reported as trace rot:\n{result.stdout}"
    )


def test_scn_f2_outside_git_the_check_still_fails_without_the_hint(tmp_path):
    root = _project(tmp_path, changed=[{"path": "src/moved.py",
                                        "scenarios": ["SCN-1"]}], git=False)
    result = _check(root)
    combined = result.stdout + result.stderr
    assert "Traceback" not in combined, f"errored outside git:\n{combined}"
    assert "FAIL changed-code-traces-to-scenario" in combined, (
        f"missing path passed outside git:\n{combined}")
    assert "src/moved.py" in combined, combined
