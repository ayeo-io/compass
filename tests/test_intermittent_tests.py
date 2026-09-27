"""Intermittent-test integrity.

Tests for `TRC-A1`, `TRC-A2`, `TRC-A3`, `TRC-A4`, `TRC-A5`, `TRC-A6`, `TRC-A7`,
`TRC-FM2`, `TRC-FM3`.
"""

# These tests read the per-check detail (name, PASS/FAIL, reason) that
# `compass check --verbose` prints.
from __future__ import annotations

import json
import sys
from pathlib import Path

from conftest import write_red_record

import pytest
import yaml

FRAMEWORK_ROOT = Path(__file__).resolve().parent.parent


# =============================================================================
# `TRC-A6` - strategies.md declares `S5` - "Intermittency is failure."
# =============================================================================

class TestS5InStrategiesMd:
    """`TRC-A6`: governance/strategies.md must declare `S5`."""

    def test_s5_exists_in_strategies_md(self):
        """`S5` must be present under ## Default method strategies."""
        strat_path = FRAMEWORK_ROOT / "governance" / "strategies.md"
        assert strat_path.is_file(), f"strategies.md not found at {strat_path}"
        text = strat_path.read_text(encoding="utf-8")
        assert "S5" in text, "S5 strategy id not found in strategies.md"

    def test_s5_is_named_intermittency_is_failure(self):
        """`S5` must be named 'Intermittency is failure.'"""
        strat_path = FRAMEWORK_ROOT / "governance" / "strategies.md"
        text = strat_path.read_text(encoding="utf-8")
        assert "Intermittency is failure" in text, (
            "S5 must be named 'Intermittency is failure.' in strategies.md"
        )

    def test_s5_mentions_rerun_to_green_as_signal_loss(self):
        """`S5` must say a rerun-to-green is the loss of the most useful signal."""
        strat_path = FRAMEWORK_ROOT / "governance" / "strategies.md"
        text = strat_path.read_text(encoding="utf-8")
        # `S5` must say: "a rerun-to-green is the loss of the most useful signal"
        assert "rerun" in text.lower(), (
            "S5 must mention rerun in the context of signal loss"
        )
        assert "signal" in text.lower(), (
            "S5 must mention signal loss"
        )

    def test_s5_is_in_default_method_strategies_section(self):
        """`S5` must appear under ## Default method strategies, after `S4`."""
        strat_path = FRAMEWORK_ROOT / "governance" / "strategies.md"
        text = strat_path.read_text(encoding="utf-8")
        # `S5` must come after `S4` in the default section
        s4_pos = text.find("(`S4`)")
        s5_pos = text.find("(`S5`)")
        assert s5_pos != -1, "the S5-tagged heading not found in strategies.md"
        assert s4_pos != -1, "the S4-tagged heading not found in strategies.md"
        assert s5_pos > s4_pos, "S5 must appear after S4 in strategies.md"
        # `S5` must appear before the project strategies section
        project_section_pos = text.find("## Project strategies")
        assert s5_pos < project_section_pos, (
            "S5 must appear in ## Default method strategies, before ## Project strategies"
        )


# =============================================================================
# `TRC-A1` - tdd-green records `attempts`:1 on a clean first pass
# =============================================================================

class TestTddGreenRecordsAttempts:
    """`TRC-A1`: tdd-green must record `attempts`:1 on a clean first pass."""

    def test_tdd_green_records_attempts_1_on_first_pass(self, run_cli, make_task, project):
        body = {
            "task": "attempts-test",
            "created": "2026-05-25",
            "assessment": {
                "risk": "contained",
                "familiarity": "brownfield-mapped",
                "size": "small",
                "intent": "delivery",
            },
            "delivery_approach": "express",
            "scenarios": [
                {"id": "SCN-001", "intent": "INT-1", "tests": []},
            ],
            "evidence": [],
        }
        task_dir = make_task("attempts-test", body)
        write_red_record(task_dir, "SCN-001")
        r = run_cli(
            "tdd-green", "--issue", "attempts-test",
            "--scenario", "SCN-001",
            "--", sys.executable, "-c", "import sys; sys.exit(0)",
        )
        assert r.returncode == 0, r
        # Read the written green.json
        green_file = task_dir / "evidence" / "green-SCN-001.json"
        assert green_file.is_file(), f"green evidence file not found: {green_file}"
        data = json.loads(green_file.read_text())
        assert data.get("attempts") == 1, (
            f"expected attempts:1 on first pass, got {data.get('attempts')!r}"
        )
        # rerun_without_change must NOT be true on a clean first pass
        assert not data.get("rerun_without_change"), (
            f"rerun_without_change should not be true on first pass: {data}"
        )

    def test_tdd_green_attempts_absent_on_unbound_run(self, run_cli, make_task, project):
        """Even without --scenario, `attempts`:1 must be recorded."""
        body = {
            "task": "attempts-unbound",
            "created": "2026-05-25",
            "assessment": {
                "risk": "contained",
                "familiarity": "brownfield-mapped",
                "size": "small",
                "intent": "delivery",
            },
            "delivery_approach": "express",
            "scenarios": [],
            "evidence": [],
        }
        make_task("attempts-unbound", body)
        r = run_cli(
            "tdd-green", "--issue", "attempts-unbound",
            "--", sys.executable, "-c", "import sys; sys.exit(0)",
        )
        assert r.returncode == 0, r
        green_file = project / ".compass" / "work" / "attempts-unbound" / "evidence" / "green.json"
        assert green_file.is_file()
        data = json.loads(green_file.read_text())
        assert data.get("attempts") == 1, (
            f"expected attempts:1 even without --scenario binding, got {data.get('attempts')!r}"
        )


# =============================================================================
# `TRC-A2` - tdd-green records `attempts` > 1 and rerun_without_change
#           when no edits intervened
# =============================================================================

class TestTddGreenRerunDetection:
    """`TRC-A2`: On a second tdd-green invocation with no source change,
    `attempts` > 1 and rerun_without_change: true must be recorded."""

    def test_second_tdd_green_records_attempts_2_and_rerun_flag(
            self, run_cli, make_task, project):
        """Simulate: tdd-red, failing tdd-green, second passing tdd-green.
        The second green must record `attempts`:2 and rerun_without_change:true."""
        body = {
            "task": "rerun-test",
            "created": "2026-05-25",
            "assessment": {
                "risk": "contained",
                "familiarity": "brownfield-mapped",
                "size": "small",
                "intent": "delivery",
            },
            "delivery_approach": "express",
            "scenarios": [
                {"id": "SCN-001", "intent": "INT-1", "tests": []},
            ],
            "evidence": [],
        }
        task_dir = make_task("rerun-test", body)

        # Step 1: record a red
        r = run_cli(
            "tdd-red", "--issue", "rerun-test",
            "--scenario", "SCN-001",
            "--", sys.executable, "-c", "print('1 failed'); import sys; sys.exit(1)",
        )
        assert r.returncode == 0, r

        # A failing tdd-green errors without recording state, so this runs
        # two passing greens with no source change between them. The second
        # records `attempts`:2 and rerun_without_change:true.

        # First green (try 1):
        write_red_record(task_dir, "SCN-001")
        r = run_cli(
            "tdd-green", "--issue", "rerun-test",
            "--scenario", "SCN-001",
            "--", sys.executable, "-c", "import sys; sys.exit(0)",
        )
        assert r.returncode == 0, r
        green1 = task_dir / "evidence" / "green-SCN-001.json"
        data1 = json.loads(green1.read_text())
        assert data1.get("attempts") == 1

        # Second green with same source tree (no file changes):
        r = run_cli(
            "tdd-green", "--issue", "rerun-test",
            "--scenario", "SCN-001",
            "--", sys.executable, "-c", "import sys; sys.exit(0)",
        )
        assert r.returncode == 0, r
        data2 = json.loads(green1.read_text())
        assert data2.get("attempts") == 2, (
            f"expected attempts:2 on second run without source change, got {data2.get('attempts')!r}"
        )
        assert data2.get("rerun_without_change") is True, (
            f"expected rerun_without_change:true on second run, got {data2.get('rerun_without_change')!r}"
        )


# =============================================================================
# `TRC-A3` - `G4` fails when test-run shows rerun-to-green and no quarantine
# =============================================================================

class TestNoTrustedRerunCheck:
    """`TRC-A3`, `TRC-A4`, `TRC-A5`, `TRC-FM3`: no-trusted-rerun CHECK_FN."""

    def _base_task_body(self):
        return {
            "task": "rerun-check",
            "created": "2026-05-25",
            "assessment": {
                "risk": "contained",
                "familiarity": "brownfield-mapped",
                "size": "small",
                "intent": "delivery",
            },
            "delivery_approach": "express",
            "scenarios": [
                {"id": "SCN-001", "intent": "INT-1", "tests": ["tests/t.py::t"]},
            ],
            "gates": [{"id": "verify.governance", "status": "pending"}],
            "evidence": [],
            "changed_files": [],
        }

    def test_g4_fails_when_rerun_without_change_and_no_quarantine(
            self, run_cli, make_task, project):
        """`TRC-A3`: a test-run with rerun_without_change:true and no quarantine
        must cause no-trusted-rerun check to fail."""
        body = self._base_task_body()
        body["task"] = "rerun-check-a3"
        body["scenarios"][0]["id"] = "SCN-A3"
        body["scenarios"][0]["tests"] = ["tests/t.py::test_a3"]
        body["evidence"] = [
            {
                "id": "EV-T-SCN-A3",
                "type": "test-run",
                "scenario": "SCN-A3",
                "path": "evidence/green-SCN-A3.json",
            }
        ]
        task_dir = make_task("rerun-check-a3", body)
        ev_dir = task_dir / "evidence"
        ev_dir.mkdir(exist_ok=True)
        # Write a green evidence file with rerun_without_change:true
        (ev_dir / "green-SCN-A3.json").write_text(json.dumps({
            "exit_code": 0,
            "passed": True,
            "attempts": 2,
            "rerun_without_change": True,
            "scenario": "SCN-A3",
        }))
        r = run_cli("check", "--verbose", "--issue", "rerun-check-a3")
        assert r.returncode != 0, (
            "compass check must fail when rerun_without_change:true and no quarantine"
        )
        combined = r.stdout + r.stderr
        assert "no-trusted-rerun" in combined, (
            f"Expected 'no-trusted-rerun' in output: {combined}"
        )

    def test_g4_passes_when_quarantined_test_links_tracking_task(
            self, run_cli, make_task, project):
        """`TRC-A4`: a quarantined test with a tracking issue must pass the check."""
        body = self._base_task_body()
        body["task"] = "rerun-check-a4"
        body["scenarios"][0]["id"] = "SCN-A4"
        body["scenarios"][0]["tests"] = ["tests/t.py::test_a4"]
        body["evidence"] = [
            {
                "id": "EV-T-SCN-A4",
                "type": "test-run",
                "scenario": "SCN-A4",
                "path": "evidence/green-SCN-A4.json",
            }
        ]
        task_dir = make_task("rerun-check-a4", body)
        ev_dir = task_dir / "evidence"
        ev_dir.mkdir(exist_ok=True)
        (ev_dir / "green-SCN-A4.json").write_text(json.dumps({
            "exit_code": 0,
            "passed": True,
            "attempts": 2,
            "rerun_without_change": True,
            "scenario": "SCN-A4",
            "test": "tests/t.py::test_a4",
        }))
        # Write a quarantine.yml with the test registered
        quarantine = {
            "version": "1.0.0",
            "quarantined": [
                {
                    "test": "tests/t.py::test_a4",
                    "tracking_task": "fix-flaky-a4",
                    "reason": "Race in setup",
                    "added": "2026-05-25",
                }
            ],
        }
        gov_dir = project / "governance"
        (gov_dir / "quarantine.yml").write_text(
            yaml.safe_dump(quarantine, default_flow_style=False)
        )
        r = run_cli("check", "--verbose", "--issue", "rerun-check-a4")
        # The no-trusted-rerun check must pass (quarantined with tracking issue)
        combined = r.stdout + r.stderr
        assert "no-trusted-rerun" not in combined.lower().replace("pass no-trusted-rerun", ""), (
            "no-trusted-rerun must not FAIL when test is quarantined with a tracking task"
        )
        # The check output must show PASS for no-trusted-rerun
        assert "PASS no-trusted-rerun" in combined, (
            f"Expected PASS for no-trusted-rerun when quarantined: {combined}"
        )

    def test_g4_passes_when_evidence_has_no_attempts_field(
            self, run_cli, make_task, project):
        """`TRC-A5`: old evidence without the `attempts` field must clear `G4` trivially."""
        body = self._base_task_body()
        body["task"] = "rerun-check-a5"
        body["scenarios"][0]["id"] = "SCN-A5"
        body["scenarios"][0]["tests"] = ["tests/t.py::test_a5"]
        body["evidence"] = [
            {
                "id": "EV-T-SCN-A5",
                "type": "test-run",
                "scenario": "SCN-A5",
                "path": "evidence/green-SCN-A5.json",
            }
        ]
        task_dir = make_task("rerun-check-a5", body)
        ev_dir = task_dir / "evidence"
        ev_dir.mkdir(exist_ok=True)
        # Old-style evidence: no `attempts`, no rerun_without_change
        (ev_dir / "green-SCN-A5.json").write_text(json.dumps({
            "exit_code": 0,
            "passed": True,
            "scenario": "SCN-A5",
        }))
        r = run_cli("check", "--verbose", "--issue", "rerun-check-a5")
        combined = r.stdout + r.stderr
        # no-trusted-rerun check must pass (no `attempts` to evaluate)
        assert "PASS no-trusted-rerun" in combined, (
            f"Expected PASS for no-trusted-rerun on old evidence: {combined}"
        )

    def test_no_trusted_rerun_fails_when_attempts_gt1_no_marker(
            self, run_cli, make_task, project):
        """`TRC-FM3`: `attempts`>1 without rerun_without_change fails the check."""
        body = self._base_task_body()
        body["task"] = "rerun-check-fm3"
        body["scenarios"][0]["id"] = "SCN-FM3"
        body["scenarios"][0]["tests"] = ["tests/t.py::test_fm3"]
        body["evidence"] = [
            {
                "id": "EV-T-SCN-FM3",
                "type": "test-run",
                "scenario": "SCN-FM3",
                "path": "evidence/green-SCN-FM3.json",
            }
        ]
        task_dir = make_task("rerun-check-fm3", body)
        ev_dir = task_dir / "evidence"
        ev_dir.mkdir(exist_ok=True)
        # Evidence with `attempts`:2 but NO rerun_without_change marker
        (ev_dir / "green-SCN-FM3.json").write_text(json.dumps({
            "exit_code": 0,
            "passed": True,
            "attempts": 2,
            # rerun_without_change absent - incomplete evidence
            "scenario": "SCN-FM3",
        }))
        r = run_cli("check", "--verbose", "--issue", "rerun-check-fm3")
        assert r.returncode != 0, (
            "check must fail when attempts>1 and rerun_without_change marker absent"
        )
        combined = r.stdout + r.stderr
        assert "no-trusted-rerun" in combined, (
            f"Expected no-trusted-rerun failure: {combined}"
        )


# =============================================================================
# `TRC-A7` - quarantined test without tracking issue fails policy lint
# =============================================================================

class TestQuarantinePolicyLint:
    """`TRC-A7`: policy lint must reject quarantine entries without tracking_task."""

    def test_quarantine_entry_without_tracking_task_fails_policy_lint(
            self, run_cli, project):
        """A quarantine entry missing tracking_task must fail policy lint."""
        quarantine = {
            "version": "1.0.0",
            "quarantined": [
                {
                    "test": "tests/t.py::test_flaky",
                    # tracking_task intentionally absent
                    "reason": "Flaky due to network",
                    "added": "2026-05-25",
                }
            ],
        }
        gov_dir = project / "governance"
        (gov_dir / "quarantine.yml").write_text(
            yaml.safe_dump(quarantine, default_flow_style=False)
        )
        r = run_cli("policy", "lint")
        assert r.returncode != 0, (
            "policy lint must fail on quarantine entry missing tracking_task"
        )
        combined = r.stdout + r.stderr
        assert "tracking_task" in combined.lower() or "malformed" in combined.lower(), (
            f"Expected 'tracking_task' or 'malformed' in lint output: {combined}"
        )

    def test_valid_quarantine_entry_passes_policy_lint(self, run_cli, project):
        """A well-formed quarantine entry must pass policy lint."""
        quarantine = {
            "version": "1.0.0",
            "quarantined": [
                {
                    "test": "tests/t.py::test_flaky",
                    "tracking_task": "fix-flaky-test",
                    "reason": "Race condition in setup",
                    "added": "2026-05-25",
                }
            ],
        }
        gov_dir = project / "governance"
        (gov_dir / "quarantine.yml").write_text(
            yaml.safe_dump(quarantine, default_flow_style=False)
        )
        r = run_cli("policy", "lint")
        assert r.returncode == 0, (
            f"policy lint must pass on a well-formed quarantine entry: {r}"
        )

    def test_empty_quarantine_passes_policy_lint(self, run_cli, project):
        """An empty quarantine registry (shipped default) must pass policy lint."""
        quarantine = {
            "version": "1.0.0",
            "quarantined": [],
        }
        gov_dir = project / "governance"
        (gov_dir / "quarantine.yml").write_text(
            yaml.safe_dump(quarantine, default_flow_style=False)
        )
        r = run_cli("policy", "lint")
        assert r.returncode == 0, (
            f"policy lint must pass on empty quarantine: {r}"
        )


# =============================================================================
# `TRC-FM2` - `attempts` field with a non-positive value fails issue lint
# =============================================================================

class TestTaskLintAttemptsValidation:
    """`TRC-FM2`: issue lint must reject `attempts` <= 0 on test-run evidence entries."""

    def test_task_lint_fails_on_attempts_zero(self, run_cli, make_task, project):
        """`attempts`:0 in a test-run evidence entry must fail issue lint."""
        body = {
            "task": "attempts-lint",
            "created": "2026-05-25",
            "assessment": {
                "risk": "contained",
                "familiarity": "brownfield-mapped",
                "size": "small",
                "intent": "delivery",
            },
            "evidence": [
                {
                    "id": "EV-T-SCN-001",
                    "type": "test-run",
                    "path": "evidence/green.json",
                    "attempts": 0,  # invalid: must be >= 1
                }
            ],
        }
        make_task("attempts-lint", body)
        r = run_cli("issue", "lint", "--issue", "attempts-lint")
        assert r.returncode != 0, (
            "task lint must fail when test-run evidence has attempts:0"
        )
        combined = r.stdout + r.stderr
        assert "attempts" in combined.lower(), (
            f"Expected 'attempts' in lint output: {combined}"
        )

    def test_task_lint_fails_on_attempts_negative(self, run_cli, make_task, project):
        """`attempts`:-1 in a test-run evidence entry must fail issue lint."""
        body = {
            "task": "attempts-lint-neg",
            "created": "2026-05-25",
            "assessment": {
                "risk": "contained",
                "familiarity": "brownfield-mapped",
                "size": "small",
                "intent": "delivery",
            },
            "evidence": [
                {
                    "id": "EV-T-SCN-001",
                    "type": "test-run",
                    "path": "evidence/green.json",
                    "attempts": -1,  # invalid
                }
            ],
        }
        make_task("attempts-lint-neg", body)
        r = run_cli("issue", "lint", "--issue", "attempts-lint-neg")
        assert r.returncode != 0, (
            "task lint must fail when test-run evidence has negative attempts"
        )

    def test_task_lint_passes_on_attempts_1(self, run_cli, make_task, project):
        """`attempts`:1 in a test-run evidence entry must pass issue lint."""
        body = {
            "task": "attempts-lint-ok",
            "created": "2026-05-25",
            "assessment": {
                "risk": "contained",
                "familiarity": "brownfield-mapped",
                "size": "small",
                "intent": "delivery",
            },
            "evidence": [
                {
                    "id": "EV-T-SCN-001",
                    "type": "test-run",
                    "path": "evidence/green.json",
                    "attempts": 1,  # valid
                }
            ],
        }
        make_task("attempts-lint-ok", body)
        r = run_cli("issue", "lint", "--issue", "attempts-lint-ok")
        assert r.returncode == 0, (
            f"task lint must pass when test-run evidence has attempts:1: {r}"
        )

    def test_task_lint_passes_on_evidence_without_attempts(
            self, run_cli, make_task, project):
        """Old evidence without `attempts` field must pass issue lint (TRC-A5 / backward compat)."""
        body = {
            "task": "attempts-lint-absent",
            "created": "2026-05-25",
            "assessment": {
                "risk": "contained",
                "familiarity": "brownfield-mapped",
                "size": "small",
                "intent": "delivery",
            },
            "evidence": [
                {
                    "id": "EV-T-SCN-001",
                    "type": "test-run",
                    "path": "evidence/green.json",
                    # no `attempts` field - old evidence
                }
            ],
        }
        make_task("attempts-lint-absent", body)
        r = run_cli("issue", "lint", "--issue", "attempts-lint-absent")
        assert r.returncode == 0, (
            f"task lint must pass on old evidence without attempts field: {r}"
        )


# =============================================================================
# `TRC-A1` (supplementary) - guardrails.yml has no-trusted-rerun registered
# =============================================================================

class TestNoTrustedRerunInGuardrailsYml:
    """no-trusted-rerun must be in guardrails.yml checks and in `G4`."""

    def test_no_trusted_rerun_check_registered(self):
        gr_path = FRAMEWORK_ROOT / "governance" / "guardrails.yml"
        gr = yaml.safe_load(gr_path.read_text())
        assert "no-trusted-rerun" in (gr.get("checks") or {}), (
            "guardrails.yml `checks:` must declare 'no-trusted-rerun'"
        )

    def test_no_trusted_rerun_attached_to_g4(self):
        gr_path = FRAMEWORK_ROOT / "governance" / "guardrails.yml"
        gr = yaml.safe_load(gr_path.read_text())
        defaults = gr.get("defaults") or []
        g4 = next((g for g in defaults if g.get("id") == "G4"), None)
        assert g4 is not None, "G4 not found in guardrails.yml defaults"
        assert "no-trusted-rerun" in g4.get("checks", []), (
            "no-trusted-rerun must be listed in G4.checks"
        )

    def test_policy_lint_still_passes_after_adding_check(self, run_cli):
        r = run_cli("policy", "lint")
        assert r.returncode == 0, (
            f"policy lint must pass after adding no-trusted-rerun: {r}"
        )
