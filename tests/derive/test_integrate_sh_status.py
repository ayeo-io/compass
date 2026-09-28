"""Tests for integrate.sh writing status: landed to manifest.yml (TRC-B11).

These tests check the YAML-write logic directly, and check that integrate.sh
contains the call to it.
"""
from __future__ import annotations

import os
import subprocess
import sys
import types
from pathlib import Path

import pytest
import yaml

FRAMEWORK_ROOT = Path(__file__).resolve().parent.parent.parent
CLI_PATH = FRAMEWORK_ROOT / "cli" / "compass"
INTEGRATE_SH = FRAMEWORK_ROOT / "scripts" / "integrate.sh"


def _load_compass_module():
    source = CLI_PATH.read_text(encoding="utf-8")
    mod = types.ModuleType("compass_cli")
    mod.__file__ = str(CLI_PATH)
    exec(compile(source, str(CLI_PATH), "exec"), mod.__dict__)
    return mod


# ---------------------------------------------------------------------------
# integrate.sh writes status: landed (`TRC-B11` part 2)
# ---------------------------------------------------------------------------

class TestIntegrateSh:
    """After the issue ships, manifest.yml has status: landed (`TRC-B11`).

    We test this in two layers:
    1. The derive_system_spec function correctly reads status: landed from
       manifest.yml (already covered in TestTrcB11 in test_derive_system_spec.py).
    2. scripts/integrate.sh writes status: landed to manifest.yml after
       combined regression passes.

    ADR-026 (`DPR-7`) moved the living-spec derivation off integrate.sh and
    onto `ship-commit`, the one step that lands every issue - solo or
    multiagent. The two tests that used to pin the old invocation, below,
    now pin its replacement: integrate.sh does not call the derivation, and
    ship-commit does, after it has marked the issue landed.
    """

    def test_integrate_sh_does_not_invoke_the_derivation(self):
        """integrate.sh must not call compass _derive-system-spec --internal -
        ADR-026 moved that call to ship-commit."""
        assert INTEGRATE_SH.is_file(), f"integrate.sh not found at {INTEGRATE_SH}"
        content = INTEGRATE_SH.read_text(encoding="utf-8")
        assert "_derive-system-spec" not in content, (
            "integrate.sh must not invoke compass _derive-system-spec "
            "--internal - ADR-026 moved the derivation to ship-commit"
        )

    def test_ship_commit_derives_after_marking_the_issue_landed(self):
        """ship-commit calls derive_system_spec, in the branch that has just
        marked the issue landed - never from integrate.sh (ADR-026).
        `tests/test_ship_commit_derives.py` proves this behaviourally: a
        gate that has not passed marks nothing landed and derives nothing."""
        manifest_src = (FRAMEWORK_ROOT / "cli" / "compass_pkg" / "manifest.py").read_text(
            encoding="utf-8")
        landed_marker = 'task["status"] = "landed"'
        derive_call = "_derive_and_commit_living_spec("
        assert landed_marker in manifest_src, (
            f"expected {landed_marker!r} in cli/compass_pkg/manifest.py"
        )
        assert "derive_system_spec" in manifest_src, (
            "compass ship-commit must call derive_system_spec after marking "
            "an issue landed (ADR-026)"
        )
        # The call site, not its definition or import, must sit inside the
        # branch that has just marked the issue landed.
        landed_pos = manifest_src.index(landed_marker)
        call_pos = manifest_src.index(derive_call, landed_pos)
        assert call_pos > landed_pos, (
            "ship-commit must call the derivation after marking the issue "
            "landed, not before"
        )

    def test_integrate_sh_writes_status_landed(self):
        """integrate.sh must write status: landed to the issue's manifest.yml."""
        assert INTEGRATE_SH.is_file(), f"integrate.sh not found at {INTEGRATE_SH}"
        content = INTEGRATE_SH.read_text(encoding="utf-8")
        assert "status: landed" in content or "status:landed" in content or \
               "landed" in content, (
            "integrate.sh must write status: landed to the task's manifest.yml"
        )

class TestStatusLandedWrite:
    """Unit tests for writing status: landed to manifest.yml."""

    def test_task_yml_with_status_landed_validates(self, tmp_path):
        """A manifest.yml with status: landed passes the schema check."""
        task_dir = tmp_path / ".compass" / "work" / "test-land"
        task_dir.mkdir(parents=True, exist_ok=True)

        task = {
            "schema_version": "1.1",
            "task": "test-land",
            "created": "2026-05-25",
            "status": "landed",
            "land_timestamp": "2026-05-25T10:00:00+00:00",
            "assessment": {
                "risk": "contained",
                "familiarity": "greenfield",
                "size": "small",
            },
            "scenarios": [],
            "changed_files": [],
            "gates": [],
            "evidence": [],
            "claims": [],
            "follow_ups": [],
            "reassessments": [],
        }
        (task_dir / "manifest.yml").write_text(
            yaml.safe_dump(task, sort_keys=False), encoding="utf-8"
        )

        # Should lint clean
        import shutil
        gov_src = FRAMEWORK_ROOT / "governance"
        gov_dst = tmp_path / "governance"
        gov_dst.mkdir(exist_ok=True)
        for name in ("routing-policy.yml", "guardrails.yml"):
            shutil.copyfile(gov_src / name, gov_dst / name)

        (tmp_path / ".compass" / "current-task").write_text(
            "test-land", encoding="utf-8"
        )

        result = subprocess.run(
            [sys.executable, str(CLI_PATH), "issue", "lint", "--issue", "test-land"],
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, (
            f"manifest.yml with status: landed should lint clean: "
            f"{result.stdout}\n{result.stderr}"
        )

    def test_task_yml_status_active_validates(self, tmp_path):
        """A manifest.yml with status: active passes the schema check."""
        task_dir = tmp_path / ".compass" / "work" / "test-active"
        task_dir.mkdir(parents=True, exist_ok=True)

        task = {
            "schema_version": "1.1",
            "task": "test-active",
            "created": "2026-05-25",
            "status": "active",
            "assessment": {
                "risk": "contained",
                "familiarity": "greenfield",
                "size": "small",
            },
            "scenarios": [],
            "changed_files": [],
            "gates": [],
            "evidence": [],
            "claims": [],
            "follow_ups": [],
            "reassessments": [],
        }
        (task_dir / "manifest.yml").write_text(
            yaml.safe_dump(task, sort_keys=False), encoding="utf-8"
        )

        import shutil
        gov_src = FRAMEWORK_ROOT / "governance"
        gov_dst = tmp_path / "governance"
        gov_dst.mkdir(exist_ok=True)
        for name in ("routing-policy.yml", "guardrails.yml"):
            shutil.copyfile(gov_src / name, gov_dst / name)

        (tmp_path / ".compass" / "current-task").write_text(
            "test-active", encoding="utf-8"
        )

        result = subprocess.run(
            [sys.executable, str(CLI_PATH), "issue", "lint", "--issue", "test-active"],
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, (
            f"manifest.yml with status: active should lint clean: "
            f"{result.stdout}\n{result.stderr}"
        )

    def test_task_yml_invalid_status_rejected(self, tmp_path):
        """A manifest.yml with an invalid status value fails JSON schema validation."""
        # Only matters if jsonschema is installed
        try:
            import jsonschema
        except ImportError:
            pytest.skip("jsonschema not installed - schema validation not available")

        task_dir = tmp_path / ".compass" / "work" / "test-bad-status"
        task_dir.mkdir(parents=True, exist_ok=True)

        task = {
            "schema_version": "1.1",
            "task": "test-bad-status",
            "created": "2026-05-25",
            "status": "invalid-status",  # not in enum [active, landed]
            "assessment": {
                "risk": "contained",
                "familiarity": "greenfield",
                "size": "small",
            },
        }
        (task_dir / "manifest.yml").write_text(
            yaml.safe_dump(task, sort_keys=False), encoding="utf-8"
        )

        import shutil
        gov_src = FRAMEWORK_ROOT / "governance"
        gov_dst = tmp_path / "governance"
        gov_dst.mkdir(exist_ok=True)
        for name in ("routing-policy.yml", "guardrails.yml"):
            shutil.copyfile(gov_src / name, gov_dst / name)

        (tmp_path / ".compass" / "current-task").write_text(
            "test-bad-status", encoding="utf-8"
        )

        result = subprocess.run(
            [sys.executable, str(CLI_PATH), "issue", "lint", "--issue", "test-bad-status"],
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode != 0, (
            "manifest.yml with status: invalid-status should fail lint"
        )
