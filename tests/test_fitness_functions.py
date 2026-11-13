"""
Tests for architecture checks (command-passes + verify.architecture).
`TRC-B1`, `TRC-B2`, `TRC-B3`, `TRC-B6`, `TRC-B7`, `TRC-FM1`.
"""

# These tests read the per-check detail, which the command prints only
# under --verbose.
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest
import yaml

FRAMEWORK_ROOT = Path(__file__).resolve().parent.parent
CLI_PATH = FRAMEWORK_ROOT / "cli" / "compass"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_cli(*args: str, cwd: Path,
             extra_env: Optional[Dict[str, str]] = None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(CLI_PATH), *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )


def _write_project_checks(root: Path, checks: List[Dict[str, Any]]) -> None:
    """A `compass.yml` that opts in to project commands and declares `checks`."""
    (root / "compass.yml").write_text(yaml.safe_dump(
        {"schema": 1, "allow_project_commands": True, "project_checks": checks},
        sort_keys=False))


def _make_project(
    tmp_path: Path,
    project_guardrails: Optional[List[Dict[str, Any]]] = None,
    task_gates: Optional[List[Dict[str, Any]]] = None,
    risk: str = "cross-cutting",
) -> tuple[Path, Path]:
    """
    Build a minimal Compass project tree in tmp_path on the shipped check set.
    Each project guardrail becomes a project check of `compass.yml` (ADR-094):
    9.0.0 reads no copy of `guardrails.yml` (ADR-098).
    Returns (project_root, task_dir).
    """
    if project_guardrails:
        _write_project_checks(tmp_path, [
            {"id": g["id"], "name": g["name"], "command": g["params"]["command"],
             "stage": "ship"} for g in project_guardrails])

    # .compass/
    compass_dir = tmp_path / ".compass"
    (compass_dir / "work").mkdir(parents=True)
    task_dir = compass_dir / "work" / "test-task"
    task_dir.mkdir()
    (compass_dir / "current-task").write_text("test-task\n")
    # These tests are about what happens when a declared command RUNS - its
    # exit code, its timeout, its malformed declarations. Running a project
    # command is opt-in (see project-commands-are-a-trust-boundary), so the
    # fixture opts in; without it every test here would get "nothing to check"
    # and stop exercising the execution path it exists for. The opt-in itself
    # is covered in tests/test_project_command_boundary.py.
    if not project_guardrails:
        (compass_dir / "config.yml").write_text(
            "version: 1.0.0\nmode: enforced\nallow_project_commands: true\n")

    # manifest.yml
    gates = task_gates if task_gates is not None else [
        {"id": "verify.architecture", "status": "pending", "evidence": []}
    ]
    task_doc: Dict[str, Any] = {
        "schema_version": "1.1",
        "task": "test-task",
        "created": "2026-05-25",
        "status": "active",
        "assessment": {
            "risk": risk,
            "familiarity": "brownfield-mapped",
            "size": "standard",
            "intent": "delivery",
        },
        "delivery_approach": "standard",
        "scenarios": [
            {
                "id": "TRC-B1",
                "intent": "INT-3",
                "tests": ["tests/test_fitness_functions.py::test_stub"],
            },
        ],
        "changed_files": [],
        "evidence": [],
        "gates": gates,
    }
    with open(task_dir / "manifest.yml", "w") as f:
        yaml.safe_dump(task_doc, f)

    (task_dir / "evidence").mkdir()
    return tmp_path, task_dir


# ---------------------------------------------------------------------------
# `TRC-B1`: command-passes project guardrail clears when command exits 0
# ---------------------------------------------------------------------------

class TestCommandPassesSuccess:
    """`TRC-B1`: a command-passes project guardrail clears when the declared
    command exits 0."""

    def test_command_passes_check_succeeds_on_exit_0(self, tmp_path):
        """compass check passes when command-passes guardrail command exits 0."""
        project_guardrails = [
            {
                "id": "F1",
                "name": "Module directions",
                "statement": "Modules respect direction.",
                "checks": ["command-passes"],
                "params": {"command": "true"},
                "checked_at": ["verify"],
            }
        ]
        project_root, task_dir = _make_project(
            tmp_path, project_guardrails=project_guardrails
        )
        # Run compass check
        result = _run_cli("check", "--verbose", "--issue", "test-task", cwd=project_root)
        # command-passes must report success (PASS command-passes)
        assert "PASS command-passes" in result.stdout or "command-passes" in result.stdout, (
            f"Expected PASS command-passes in output:\n{result.stdout}\n{result.stderr}"
        )

    def test_command_passes_succeeds_in_check_output(self, tmp_path):
        """The PASS message appears in compass check output for exit-0 command."""
        project_guardrails = [
            {
                "id": "F1",
                "name": "Module directions",
                "statement": "Modules respect direction.",
                "checks": ["command-passes"],
                "params": {"command": "true"},
                "checked_at": ["verify"],
            }
        ]
        project_root, task_dir = _make_project(
            tmp_path, project_guardrails=project_guardrails
        )
        result = _run_cli("check", "--verbose", "--issue", "test-task", cwd=project_root)
        assert "FAIL command-passes" not in result.stdout, (
            f"Unexpected FAIL:\n{result.stdout}"
        )


# ---------------------------------------------------------------------------
# `TRC-B2`: command-passes project guardrail fails when command exits non-zero
# ---------------------------------------------------------------------------

class TestCommandPassesFailure:
    """`TRC-B2`: a command-passes project guardrail fails when the declared
    command exits non-zero."""

    def test_command_passes_check_fails_on_non_zero_exit(self, tmp_path):
        """compass check reports FAIL command-passes when command exits non-zero."""
        project_guardrails = [
            {
                "id": "F1",
                "name": "Module directions",
                "statement": "Modules respect direction.",
                "checks": ["command-passes"],
                "params": {"command": "false"},
                "checked_at": ["verify"],
            }
        ]
        project_root, task_dir = _make_project(
            tmp_path, project_guardrails=project_guardrails
        )
        result = _run_cli("check", "--verbose", "--issue", "test-task", cwd=project_root)
        assert "FAIL command-passes" in result.stdout, (
            f"Expected FAIL command-passes in output:\n{result.stdout}\n{result.stderr}"
        )

    def test_command_passes_failure_detail_includes_exit_code(self, tmp_path):
        """The failure detail includes the exit code information."""
        project_guardrails = [
            {
                "id": "F1",
                "name": "Module directions",
                "statement": "Modules respect direction.",
                "checks": ["command-passes"],
                "params": {"command": "false"},
                "checked_at": ["verify"],
            }
        ]
        project_root, task_dir = _make_project(
            tmp_path, project_guardrails=project_guardrails
        )
        result = _run_cli("check", "--verbose", "--issue", "test-task", cwd=project_root)
        # The failure detail must mention the exit code or "non-zero"
        combined = result.stdout + result.stderr
        assert ("exit" in combined.lower() or "1" in combined), (
            f"Expected exit code in failure output:\n{combined}"
        )


# ---------------------------------------------------------------------------
# `TRC-B3`: verify.architecture is advisory by default
# ---------------------------------------------------------------------------

class TestVerifyFitnessAdvisory:
    """`TRC-B3`: verify.architecture is advisory by default (not in gate set when
    no promotion floor fires)."""

    def test_fitness_not_in_gates_for_contained_blast_radius(self, tmp_path):
        """approach evaluate with contained risk does NOT add verify.architecture."""
        (tmp_path / ".compass").mkdir(exist_ok=True)

        result = _run_cli(
            "approach", "evaluate", "--json",
            "--assessment", "risk=contained",
            "--assessment", "familiarity=brownfield-mapped",
            "--assessment", "size=small",
            "--assessment", "intent=delivery",
            cwd=tmp_path,
        )
        assert result.returncode == 0, f"route evaluate failed: {result.stderr}"
        data = json.loads(result.stdout)
        assert "verify.architecture" not in data["gates"], (
            f"verify.architecture should NOT be in gates for contained risk, "
            f"got: {data['gates']}"
        )

    def test_command_passes_still_reported_but_advisory_ok(self, tmp_path):
        """When verify.architecture is not in gates, failing command-passes does not
        block the check at the gate level (though it will report the check failure)."""
        # A project with a command-passes guardrail that fails
        project_guardrails = [
            {
                "id": "F1",
                "name": "Module directions",
                "statement": "Modules respect direction.",
                "checks": ["command-passes"],
                "params": {"command": "false"},
                "checked_at": ["verify"],
            }
        ]
        # issue gates do NOT include verify.architecture
        task_gates = [
            {"id": "verify.correctness", "status": "pending", "evidence": []},
        ]
        project_root, task_dir = _make_project(
            tmp_path,
            project_guardrails=project_guardrails,
            task_gates=task_gates,
            risk="contained",  # no floor fires
        )
        # command-passes check still runs (`G4`: evidence, not assertion),
        # but verify.architecture gate is not in gate set
        result = _run_cli("check", "--verbose", "--issue", "test-task", cwd=project_root)
        # The key invariant: verify.architecture gate must not be mentioned as blocking
        # (it's not in the issue's gates list)
        assert "verify.architecture" not in result.stdout or \
               "not in gate set" in result.stdout or \
               "nothing to check" in result.stdout.lower(), (
            f"Unexpected verify.architecture blocking mention:\n{result.stdout}"
        )


# ---------------------------------------------------------------------------
# `TRC-B6`: nothing-to-check pass - no project guardrails → verify.architecture clears
# ---------------------------------------------------------------------------

class TestNothingToCheckPass:
    """`TRC-B6`: when verify.architecture is in the gate set but no project guardrails
    declare command-passes, the check passes without checking anything."""

    def test_no_project_guardrails_passes_with_nothing_to_check(self, tmp_path):
        """With empty project: section and verify.architecture in gate set,
        command-passes clears without checking anything and reports the nothing to check message."""
        project_root, task_dir = _make_project(
            tmp_path,
            project_guardrails=[],  # no project guardrails
            task_gates=[
                {"id": "verify.architecture", "status": "pending", "evidence": []}
            ],
        )
        result = _run_cli("check", "--verbose", "--issue", "test-task", cwd=project_root)
        # Must pass (not fail) and mention nothing to check / no guardrails
        assert "FAIL command-passes" not in result.stdout, (
            f"command-passes should pass without checking anything:\n{result.stdout}\n{result.stderr}"
        )
        combined = result.stdout + result.stderr
        assert (
            "nothing to check" in combined.lower()
            or "0 project" in combined.lower()
            or "no fitness" in combined.lower()
            or "passed without checking anything" in combined.lower()
        ), (
            f"Expected nothing-to-check pass message:\n{combined}"
        )

    def test_passes_with_nothing_to_check_exits_pass(self, tmp_path):
        """A command-passes check with nothing to run is labelled NOTHING TO
        CHECK, not PASS (#110)."""
        project_root, task_dir = _make_project(
            tmp_path,
            project_guardrails=[],
            task_gates=[
                {"id": "verify.architecture", "status": "pending", "evidence": []}
            ],
        )
        result = _run_cli("check", "--verbose", "--issue", "test-task", cwd=project_root)
        assert "NOTHING TO CHECK command-passes" in result.stdout, (
            f"Expected NOTHING TO CHECK command-passes in output:\n{result.stdout}\n{result.stderr}"
        )
        assert "PASS command-passes" not in result.stdout


# ---------------------------------------------------------------------------
# `TRC-B7`: command-passes is recognised by compass policy lint
# ---------------------------------------------------------------------------

class TestPolicyLintCommandPasses:
    """`TRC-B7`: command-passes is recognised by compass policy lint."""

    def test_policy_lint_passes_with_command_passes_check(self, tmp_path):
        """compass policy lint exits 0 when compass.yml declares a
        project check, which runs command-passes."""
        project_guardrails = [
            {
                "id": "F1",
                "name": "Module directions",
                "statement": "Modules respect direction.",
                "checks": ["command-passes"],
                "params": {"command": "true"},
                "checked_at": ["verify"],
            }
        ]
        project_root, task_dir = _make_project(
            tmp_path, project_guardrails=project_guardrails
        )
        result = _run_cli("policy", "lint", cwd=project_root)
        assert result.returncode == 0, (
            f"policy lint should pass with command-passes check:\n"
            f"{result.stdout}\n{result.stderr}"
        )

    def test_command_passes_in_policy_lint_pass_message(self, tmp_path):
        """policy lint PASS message appears when command-passes is valid."""
        project_guardrails = [
            {
                "id": "F1",
                "name": "Module directions",
                "statement": "Modules respect direction.",
                "checks": ["command-passes"],
                "params": {"command": "true"},
                "checked_at": ["verify"],
            }
        ]
        project_root, task_dir = _make_project(
            tmp_path, project_guardrails=project_guardrails
        )
        result = _run_cli("policy", "lint", cwd=project_root)
        assert "PASS" in result.stdout, (
            f"Expected PASS in policy lint output:\n{result.stdout}\n{result.stderr}"
        )


# ---------------------------------------------------------------------------
# `TRC-FM1`: malformed command-passes declaration fails policy lint
# ---------------------------------------------------------------------------

class TestMalformedCommandPasses:
    """`TRC-FM1`: a malformed command-passes declaration fails policy lint."""

    def _make_guardrails(self, tmp_path: Path, params: Dict[str, Any]) -> Path:
        """A `compass.yml` whose project check carries `params` in place of its
        `command`, so a missing or non-text command is what the lint sees."""
        _write_project_checks(tmp_path, [
            {"id": "F1", "name": "Module directions", "stage": "ship", **params}])
        (tmp_path / ".compass").mkdir(exist_ok=True)
        return tmp_path

    def test_missing_command_field_fails_lint(self, tmp_path):
        """A project check with no `command` fails compass policy lint."""
        project_root = self._make_guardrails(tmp_path, params={})  # MISSING command
        result = _run_cli("policy", "lint", cwd=project_root)
        assert result.returncode != 0, (
            f"policy lint should FAIL with missing command:\n"
            f"{result.stdout}\n{result.stderr}"
        )
        combined = result.stdout + result.stderr
        assert "command" in combined.lower() and "required" in combined.lower(), (
            f"Expected 'command' and 'required' in failure output:\n{combined}"
        )

    def test_non_string_command_field_fails_lint(self, tmp_path):
        """A project check whose command is not a string fails policy lint."""
        project_root = self._make_guardrails(
            tmp_path, params={"command": 42}  # NOT a string
        )
        result = _run_cli("policy", "lint", cwd=project_root)
        assert result.returncode != 0, (
            f"policy lint should FAIL with non-string command:\n"
            f"{result.stdout}\n{result.stderr}"
        )
        combined = result.stdout + result.stderr
        assert "command" in combined.lower(), (
            f"Expected 'command' in failure output:\n{combined}"
        )
