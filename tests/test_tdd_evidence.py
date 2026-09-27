"""tdd-red / tdd-green: scenario binding, registry upsert, and the honesty
constraints (red is only recorded after a real failure; green only after a
real pass)."""
from __future__ import annotations

import json
import os
import shutil
import sys

import pytest

from conftest import write_red_record
import yaml

_BASH = shutil.which("bash")


def _baseline_body():
    return {
        "task": "tdd-task",
        "created": "2026-05-15",
        "assessment": {
            "risk": "contained",
            "familiarity": "brownfield-mapped",
            "size": "small",
            "intent": "delivery",
        },
        "delivery_approach": "express",
        "scenarios": [
            {"id": "SCN-001", "intent": "INT-1",
             "tests": ["tests/test_x.py::test_y"]},
        ],
        "evidence": [],
    }


# --- scenario binding rejects bogus ids ------------------------------------


def test_tdd_red_rejects_unknown_scenario(run_cli, make_task):
    make_task("tdd-bind", _baseline_body())
    r = run_cli("tdd-red", "--issue", "tdd-bind",
                "--scenario", "SCN-BOGUS",
                "--", "false")    # would have failed anyway
    assert r.returncode != 0, r
    combined = r.stdout + r.stderr
    assert "SCN-BOGUS" in combined, r


def test_tdd_green_rejects_unknown_scenario(run_cli, make_task):
    make_task("tdd-bind-g", _baseline_body())
    r = run_cli("tdd-green", "--issue", "tdd-bind-g",
                "--scenario", "SCN-BOGUS",
                "--", sys.executable, "-c", "import sys; sys.exit(0)")
    assert r.returncode != 0, r
    combined = r.stdout + r.stderr
    assert "SCN-BOGUS" in combined, r


# --- tdd-red honesty: a passing command cannot be recorded as red ---------



def _rec(task_dir, kind="green", scenario="SCN-001"):
    """The record a verb wrote, resolved by its binding.

    The binding decides the path: a run recorded `--scenario SCN-001` writes
    `<kind>-SCN-001.json`, not the shared `<kind>.json`. Before that rule, every
    scenario-bound run also overwrote the shared record - which is what
    destroyed a cited full-suite run on `zero-friction-install`.

    Reading through this helper rather than by convention keeps these tests
    about what they actually assert - coverage floors, micro-run settings,
    `--verified-by` - instead of about the evidence layout.
    """
    name = f"{kind}-{scenario}.json" if scenario else f"{kind}.json"
    return task_dir / "evidence" / name


def test_tdd_red_refuses_a_passing_command(run_cli, make_task):
    make_task("tdd-honest-red", _baseline_body())
    r = run_cli("tdd-red", "--issue", "tdd-honest-red",
                "--scenario", "SCN-001",
                "--", sys.executable, "-c", "import sys; sys.exit(0)")
    assert r.returncode != 0, r
    combined = r.stdout + r.stderr
    assert "PASSED" in combined or "red-before-green" in combined.lower(), r


def test_tdd_red_records_red_on_real_failure(run_cli, make_task, project):
    task_dir = make_task("tdd-real-red", _baseline_body())
    r = run_cli("tdd-red", "--issue", "tdd-real-red",
                "--scenario", "SCN-001",
                "--", sys.executable, "-c", "print('1 failed'); import sys; sys.exit(2)")
    assert r.returncode == 0, r
    # The record and the .red marker on disk. The record's path follows the
    # binding: this red was recorded --scenario SCN-001, so it is that
    # scenario's record and does not sit at the shared `red.json`. Before that
    # rule, every red overwrote the last one regardless of which scenario it
    # was evidence for (see tdd-green-unbound-record).
    assert _rec(task_dir, "red").is_file()
    assert not _rec(task_dir, "red", scenario=None).exists(), (
        "a scenario-bound red also wrote the unbound record")
    assert (task_dir / ".red").is_file()


# --- tdd-green honesty: a failing command cannot be recorded as green -----


def test_tdd_green_refuses_a_failing_command(run_cli, make_task):
    # A red on record, so the run reaches the command-failure path rather than
    # being refused earlier for having no red to be the other half of.
    task_dir = make_task("tdd-honest-green", _baseline_body())
    write_red_record(task_dir, "SCN-001")
    r = run_cli("tdd-green", "--issue", "tdd-honest-green",
                "--scenario", "SCN-001",
                "--", sys.executable, "-c", "import sys; sys.exit(1)")
    assert r.returncode != 0, r
    combined = r.stdout + r.stderr
    assert "FAILED" in combined or "not green" in combined.lower(), r


# --- tdd-green upserts a test-run entry in manifest.yml's evidence registry ----


def test_tdd_green_upserts_test_run_in_registry(run_cli, make_task, project):
    task_dir = make_task("tdd-upsert", _baseline_body())
    write_red_record(task_dir, "SCN-001")
    r = run_cli("tdd-green", "--issue", "tdd-upsert",
                "--scenario", "SCN-001",
                "--", sys.executable, "-c", "import sys; sys.exit(0)")
    assert r.returncode == 0, r
    task = yaml.safe_load((task_dir / "manifest.yml").read_text())
    runs = [e for e in task["evidence"] if e["type"] == "test-run"]
    assert len(runs) == 1, f"expected one test-run entry, got {runs}"
    assert runs[0]["scenario"] == "SCN-001"
    assert runs[0]["path"].endswith(".json")


def test_tdd_green_upsert_is_idempotent_for_same_scenario(run_cli, make_task,
                                                          project):
    """Running tdd-green twice for the same scenario must UPDATE the
    existing entry, not append a new one."""
    task_dir = make_task("tdd-idem", _baseline_body())
    for _ in range(2):
        write_red_record(task_dir, "SCN-001")
        r = run_cli("tdd-green", "--issue", "tdd-idem",
                    "--scenario", "SCN-001",
                    "--", sys.executable, "-c", "import sys; sys.exit(0)")
        assert r.returncode == 0, r
    task = yaml.safe_load((task_dir / "manifest.yml").read_text())
    runs = [e for e in task["evidence"] if e["type"] == "test-run"]
    assert len(runs) == 1, f"expected one test-run entry after two runs, got {runs}"


def test_tdd_green_clears_red_marker(run_cli, make_task, project):
    task_dir = make_task("tdd-clear", _baseline_body())
    # leave a stale .red on disk first
    (task_dir / ".red").write_text("")
    write_red_record(task_dir, "SCN-001")
    r = run_cli("tdd-green", "--issue", "tdd-clear",
                "--scenario", "SCN-001",
                "--", sys.executable, "-c", "import sys; sys.exit(0)")
    assert r.returncode == 0, r
    assert not (task_dir / ".red").exists(), ".red marker should have been cleared"


# --- the check side: a bound test-run that does not resolve fails ---------


def test_check_suite_passed_fails_on_unresolvable_binding(run_cli, make_task):
    """A test-run entry whose `scenario` does not exist in scenarios must
    fail `_check_suite_passed`."""
    body = _baseline_body()
    body["evidence"].append({
        "id": "EV-T-X", "type": "test-run",
        "path": "evidence/green.json",
        "scenario": "SCN-NEVER",
    })
    body["scenarios"] = [{"id": "SCN-001", "intent": "INT-1",
                          "tests": ["tests/test_x.py::test_y"]}]
    body["changed_files"] = []
    body["gates"] = [{"id": "verify.correctness", "status": "pending"}]
    task_dir = make_task("bad-bind", body)
    ev = task_dir / "evidence"
    ev.mkdir(exist_ok=True)
    (ev / "green.json").write_text('{"exit_code": 0, "passed": true}')
    r = run_cli("check", "--issue", "bad-bind")
    assert r.returncode != 0, r
    assert "SCN-NEVER" in (r.stdout + r.stderr), r


# ===========================================================================
# Exit-code masking in piped test commands (`R2`, `TRC-R2-1`..`TRC-R2-5`)
# The masking path is caller-introduced: `bash -c '... | tail'` makes the
# shell return the final stage's exit code (tail = 0), masking an inner
# failure. The fix injects `set -o pipefail` into bash/zsh wrappers, warns on
# a pager/filter final stage, and cross-checks output for a fail-token.
# ===========================================================================


def _r2_body():
    body = _baseline_body()
    body["scenarios"] = [{"id": "SCN-001", "intent": "INT-1",
                          "tests": ["tests/test_x.py::test_y"]}]
    return body


def test_pipe_masking_records_false_green_baseline(run_cli, make_task):
    """`TRC-R2-1` (behaviour-mapping regression guard): a failing test piped to
    `tail` must NOT be recordable as a green. The masked inner failure is caught."""
    if not _BASH:
        pytest.skip("bash not available")
    task_dir = make_task("r2-mask", _r2_body())
    (task_dir / ".red").write_text("")
    write_red_record(task_dir, "SCN-001")
    r = run_cli("tdd-green", "--issue", "r2-mask", "--scenario", "SCN-001",
                "--", "bash", "-c", "exit 1 | tail -1")
    assert r.returncode != 0, r              # refused - not a false green
    assert (task_dir / ".red").exists(), r   # marker NOT cleared


def test_pipefail_propagates_masked_failure(run_cli, make_task):
    """With pipefail injected into the shell wrapper, the mid-pipeline
    failure propagates so tdd-green refuses and records no passing green (`TRC-R2-2`)."""
    if not _BASH:
        pytest.skip("bash not available")
    task_dir = make_task("r2-pf", _r2_body())
    (task_dir / ".red").write_text("")
    write_red_record(task_dir, "SCN-001")
    r = run_cli("tdd-green", "--issue", "r2-pf", "--scenario", "SCN-001",
                "--", "bash", "-c", "exit 1 | tail -1")
    assert r.returncode != 0, r
    assert "FAILED" in (r.stdout + r.stderr), r
    green = _rec(task_dir, "green")
    if green.exists():
        assert json.loads(green.read_text()).get("passed") is not True, r


def test_direct_argv_green_unchanged(run_cli, make_task):
    """An ordinary direct-argv passing command still records green
    (the hardening must not touch the default shell=False path) (`TRC-R2-3`)."""
    task_dir = make_task("r2-direct", _r2_body())
    (task_dir / ".red").write_text("")
    write_red_record(task_dir, "SCN-001")
    r = run_cli("tdd-green", "--issue", "r2-direct", "--scenario", "SCN-001",
                "--", sys.executable, "-c", "import sys; sys.exit(0)")
    assert r.returncode == 0, r
    green = json.loads((_rec(task_dir, "green")).read_text())
    assert green["passed"] is True, r
    assert not (task_dir / ".red").exists(), r


def test_pipe_filter_final_stage_warns(run_cli, make_task):
    """A top-level pipe ending in a pager/filter (tail) is flagged,
    even when the command happens to pass (`TRC-R2-4`)."""
    if not _BASH:
        pytest.skip("bash not available")
    task_dir = make_task("r2-warn", _r2_body())
    (task_dir / ".red").write_text("")
    write_red_record(task_dir, "SCN-001")
    r = run_cli("tdd-green", "--issue", "r2-warn", "--scenario", "SCN-001",
                "--", "bash", "-c", "echo hi | tail")
    combined = (r.stdout + r.stderr).lower()
    assert "pipe" in combined and "tail" in combined, r


def test_output_token_crosscheck_on_known_runner(run_cli, make_task):
    """A zero exit whose output carries a runner fail-token does not
    silently record a clean green (`TRC-R2-5`)."""
    if not _BASH:
        pytest.skip("bash not available")
    task_dir = make_task("r2-token", _r2_body())
    (task_dir / ".red").write_text("")
    write_red_record(task_dir, "SCN-001")
    r = run_cli("tdd-green", "--issue", "r2-token", "--scenario", "SCN-001",
                "--", "bash", "-c", "echo '1 failed in 0.10s'; exit 0")
    assert r.returncode != 0, r              # not a silent clean green
    assert "fail" in (r.stdout + r.stderr).lower(), r


# ===========================================================================
# Coverage-floor neutralisation on TDD micro-runs (`R7`, `TRC-R7-1`..`R7-5`)
# A project --cov-fail-under floor must not turn a passing single-file micro-run
# into a refused green. tdd-red/green inject --cov-fail-under=0 for recognised
# pytest invocations (absent an explicit one) and honour a test_micro_command setting.
# ===========================================================================


def test_coverage_floor_refuses_micro_run_baseline(run_cli, make_task):
    """`TRC-R7-1` (regression guard): a recognised pytest micro-run is neutralised
    so a project coverage floor cannot refuse a passing targeted test.

    Narrowed deliberately: the neutralising flag is injected only where
    pytest-cov can actually load. `--cov-fail-under` is a pytest-cov flag, not a
    pytest one, so injecting it into a project that disables plugin autoload
    made pytest exit 4 - a usage error, with no test run at all - and
    `compass tdd-red` then recorded that as a failing test. The guarantee this
    test protects is unharmed by the narrowing: where pytest-cov cannot load
    there is no coverage floor to refuse anything. See `TRC-G1`..`TRC-G3` in
    executable-bdd-and-richer-plans/acceptance-criteria.md.
    """
    import importlib.util
    cov_loadable = (not os.environ.get("PYTEST_DISABLE_PLUGIN_AUTOLOAD")
                    and importlib.util.find_spec("pytest_cov") is not None)

    task_dir = make_task("r7-base", _r2_body())
    (task_dir / ".red").write_text("")
    write_red_record(task_dir, "SCN-001")
    r = run_cli("tdd-green", "--issue", "r7-base", "--scenario", "SCN-001",
                "--", sys.executable, "-m", "pytest", "--version")
    assert r.returncode == 0, r
    green = json.loads((_rec(task_dir, "green")).read_text())

    if cov_loadable:
        assert "--cov-fail-under=0" in green["command"], r
    else:
        assert "--cov-fail-under" not in green["command"], (
            "injected a pytest-cov flag where pytest-cov cannot load; the "
            "runner would reject it and no test would run:\n%r" % r)


def test_micro_run_neutralises_coverage_floor(run_cli, make_task):
    """A passing pytest micro-run records green with the floor neutralised (`TRC-R7-2`)."""
    task_dir = make_task("r7-neut", _r2_body())
    (task_dir / ".red").write_text("")
    write_red_record(task_dir, "SCN-001")
    r = run_cli("tdd-green", "--issue", "r7-neut", "--scenario", "SCN-001",
                "--", sys.executable, "-m", "pytest", "--version")
    assert r.returncode == 0, r
    assert json.loads((_rec(task_dir, "green")).read_text())["passed"] is True


def test_full_suite_coverage_gate_unaffected(run_cli, make_task):
    """An explicit --cov-fail-under is preserved (not clobbered to 0) -
    the full-suite gate's floor is respected (`TRC-R7-3`)."""
    task_dir = make_task("r7-full", _r2_body())
    (task_dir / ".red").write_text("")
    write_red_record(task_dir, "SCN-001")
    r = run_cli("tdd-green", "--issue", "r7-full", "--scenario", "SCN-001",
                "--", sys.executable, "-m", "pytest", "--version", "--cov-fail-under=85")
    assert r.returncode == 0, r
    cmd = json.loads((_rec(task_dir, "green")).read_text())["command"]
    assert "--cov-fail-under=85" in cmd and "--cov-fail-under=0" not in cmd, r


def test_non_pytest_micro_run_untouched(run_cli, make_task):
    """A non-pytest command gets no coverage injection (`TRC-R7-4`)."""
    task_dir = make_task("r7-nonpy", _r2_body())
    (task_dir / ".red").write_text("")
    write_red_record(task_dir, "SCN-001")
    r = run_cli("tdd-green", "--issue", "r7-nonpy", "--scenario", "SCN-001",
                "--", sys.executable, "-c", "import sys; sys.exit(0)")
    assert r.returncode == 0, r
    assert "--cov-fail-under" not in json.loads(
        (_rec(task_dir, "green")).read_text())["command"], r


def test_test_micro_command_knob_precedence(run_cli, make_task, project):
    """With no -- command, tdd-green uses project.test_micro_command (`TRC-R7-5`)."""
    task_dir = make_task("r7-knob", _r2_body())
    (task_dir / ".red").write_text("")
    (project / ".compass" / "config.yml").write_text(
        "version: 1.0.0\nmode: enforced\nproject:\n  test_micro_command: \"true\"\n")
    write_red_record(task_dir, "SCN-001")
    r = run_cli("tdd-green", "--issue", "r7-knob", "--scenario", "SCN-001")
    assert r.returncode == 0, r
    assert json.loads((_rec(task_dir, "green")).read_text())["command"] == "true", r


# ===========================================================================
# First-class `--verified-by` red (`R8`, `TRC-R8-2`..`R8-6`; `R8-1` hook part in test_pre_tool_hook)
# ===========================================================================


def test_verified_by_typecheck_records_red(run_cli, make_task):
    """A red checked by typecheck records the guard with its kind (`TRC-R8-2`)."""
    task_dir = make_task("r8-vb", _r2_body())
    r = run_cli("tdd-red", "--issue", "r8-vb", "--scenario", "SCN-001",
                "--verified-by", "typecheck", "--", "bash", "-c", "echo '1 error'; exit 1")
    assert r.returncode == 0, r
    red = json.loads((_rec(task_dir, "red")).read_text())
    assert red.get("verified_by") == "typecheck", r
    assert (task_dir / ".red").exists(), r


def test_verified_by_guard_bound_to_scenario_at_verify(run_cli, make_task):
    """The green carries the `--verified-by` kind forward and binds the
    guard to the scenario in the registry (`TRC-R8-3`)."""
    task_dir = make_task("r8-bind", _r2_body())
    (task_dir / ".red").write_text("")
    write_red_record(task_dir, "SCN-001")
    r = run_cli("tdd-green", "--issue", "r8-bind", "--scenario", "SCN-001",
                "--verified-by", "typecheck", "--", "true")
    assert r.returncode == 0, r
    green = json.loads((_rec(task_dir, "green")).read_text())
    assert green.get("verified_by") == "typecheck", r
    task = yaml.safe_load((task_dir / "manifest.yml").read_text())
    assert any(e.get("type") == "test-run" and e.get("scenario") == "SCN-001"
               for e in task["evidence"]), r


def test_passing_command_without_verified_by_rejected(run_cli, make_task):
    """No smuggling - a passing command with no --verified-by records no red (`TRC-R8-4`)."""
    task_dir = make_task("r8-nosmug", _r2_body())
    r = run_cli("tdd-red", "--issue", "r8-nosmug", "--scenario", "SCN-001",
                "--", "true")
    assert r.returncode != 0, r
    assert "PASSED" in (r.stdout + r.stderr), r
    assert not (task_dir / ".red").exists(), r


def test_verified_by_rejects_unknown_kind(run_cli, make_task):
    """An unrecognised `--verified-by` kind is refused with the allowed set (`TRC-R8-5`)."""
    task_dir = make_task("r8-kind", _r2_body())
    r = run_cli("tdd-red", "--issue", "r8-kind", "--scenario", "SCN-001",
                "--verified-by", "handwave", "--", "bash", "-c", "exit 1")
    assert r.returncode != 0, r
    combined = r.stdout + r.stderr
    assert "handwave" in combined and "typecheck" in combined, r
    assert not (task_dir / ".red").exists(), r


def test_verified_by_guard_must_fail_first(run_cli, make_task):
    """A `--verified-by` red still needs the guard to genuinely fail (`TRC-R8-6`)."""
    task_dir = make_task("r8-mustfail", _r2_body())
    r = run_cli("tdd-red", "--issue", "r8-mustfail", "--scenario", "SCN-001",
                "--verified-by", "regression", "--", "true")
    assert r.returncode != 0, r
    assert not (task_dir / ".red").exists(), r
