"""Delivery-approach selection: the deterministic core.

These tests prove that `compass approach evaluate` is a pure function: given
assessment values + the shipped routing-policy.yml, it produces the
documented delivery approach, fires the documented floors/caps, and permits
the documented parallelism.

The bulk of the proof is the YAML-driven parameterised test at the bottom -
each fixture in tests/fixtures/routes/ declares an input + expected output.
"""

# These tests assert the current stage keys. Older manifests still load
# through `normalize_spine` (ADR-006).
from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import load_route_fixtures


# --- happy-path: each fixture selects the documented delivery approach for
# representative assessment values --


def _reading_args(readings: dict) -> list[str]:
    """Translate an assessment dict into --assessment key=value CLI args."""
    args = []
    for k, v in readings.items():
        if isinstance(v, list):
            args.extend(["--assessment", f"{k}=" + ",".join(v)])
        else:
            args.extend(["--assessment", f"{k}={v}"])
    return args


def test_express_route_for_small_mapped_change(run_cli):
    """RP-SHAPE-003: small + contained + mapped == express."""
    r = run_cli("approach", "evaluate", "--json",
                *_reading_args({"risk": "contained",
                                "familiarity": "brownfield-mapped",
                                "size": "small",
                                "intent": "delivery"}))
    assert r.returncode == 0, r
    data = json.loads(r.stdout)
    assert data["delivery_approach"] == "quick-fix"
    assert data["candidate_route"] == "quick-fix"


def test_standard_route_for_default_shape(run_cli):
    """RP-SHAPE-005: size=standard == standard."""
    r = run_cli("approach", "evaluate", "--json",
                *_reading_args({"risk": "contained",
                                "familiarity": "brownfield-mapped",
                                "size": "standard",
                                "intent": "delivery"}))
    assert r.returncode == 0, r
    data = json.loads(r.stdout)
    assert data["delivery_approach"] == "regular"


def test_expedition_route_for_large_magnitude(run_cli):
    """RP-SHAPE-004: size=large == expedition."""
    r = run_cli("approach", "evaluate", "--json",
                *_reading_args({"risk": "contained",
                                "familiarity": "brownfield-mapped",
                                "size": "large",
                                "intent": "delivery"}))
    assert r.returncode == 0, r
    data = json.loads(r.stdout)
    assert data["delivery_approach"] == "full"
    # No policy bounds multiagent work: no number for it exists in
    # routing-policy.yml or .compass/config.yml, so only a cap makes one.
    assert data["subtask_ceiling"] is None


def test_hotfix_route_for_live_defect(run_cli):
    """RP-SHAPE-002: urgency=live-defect + small size == hotfix."""
    r = run_cli("approach", "evaluate", "--json",
                *_reading_args({"risk": "contained",
                                "familiarity": "brownfield-mapped",
                                "size": "small",
                                "intent": "delivery",
                                "urgency": "live-defect"}))
    assert r.returncode == 0, r
    data = json.loads(r.stdout)
    assert data["delivery_approach"] == "hotfix"


def test_spike_route_for_exploration_intent(run_cli):
    """RP-SHAPE-001: intent=exploration on safe surface == spike."""
    r = run_cli("approach", "evaluate", "--json",
                *_reading_args({"risk": "contained",
                                "familiarity": "brownfield-mapped",
                                "size": "small",
                                "intent": "exploration"}))
    assert r.returncode == 0, r
    data = json.loads(r.stdout)
    assert data["delivery_approach"] == "spike"
    assert data["subtask_ceiling"] == 1


# --- floors: a matching reading raises the route or forces a phase ---------


def test_floor_critical_blast_radius_forces_expedition(run_cli):
    """RP-FLOOR-001: risk=critical forces at least expedition."""
    r = run_cli("approach", "evaluate", "--json",
                *_reading_args({"risk": "critical",
                                "familiarity": "brownfield-mapped",
                                "size": "small",
                                "intent": "delivery"}))
    assert r.returncode == 0, r
    data = json.loads(r.stdout)
    assert data["delivery_approach"] == "full"
    fired = [f["id"] for f in data["policy_rules_fired"]]
    assert "RP-FLOOR-001" in fired
    # candidate was lighter; the floor raised it
    assert data["candidate_route"] != data["delivery_approach"]


@pytest.mark.parametrize("domain", ["auth", "payments", "personal-data", "migrations"])
def test_floor_g5_domains_force_expedition(run_cli, domain):
    """RP-FLOOR-003: touching any `G5` domain forces at least expedition."""
    r = run_cli("approach", "evaluate", "--json",
                *_reading_args({"risk": "contained",
                                "familiarity": "brownfield-mapped",
                                "size": "small",
                                "intent": "delivery",
                                "labels": [domain]}))
    assert r.returncode == 0, r
    data = json.loads(r.stdout)
    assert data["delivery_approach"] == "full", (
        f"touching {domain!r} should force expedition, got {data['delivery_approach']!r}"
    )
    fired = [f["id"] for f in data["policy_rules_fired"]]
    assert "RP-FLOOR-003" in fired


def test_floor_brownfield_unmapped_requires_specify(run_cli):
    """RP-FLOOR-002: brownfield-unmapped beyond a small, contained change
    forces the define stage to full and needs the behaviour-mapping skill."""
    r = run_cli("approach", "evaluate", "--json",
                *_reading_args({"risk": "contained",
                                "familiarity": "brownfield-unmapped",
                                "size": "standard",
                                "intent": "delivery"}))
    assert r.returncode == 0, r
    data = json.loads(r.stdout)
    fired = [f["id"] for f in data["policy_rules_fired"]]
    assert "RP-FLOOR-002" in fired
    assert data["stages"].get("define") == "full"
    assert "behaviour-mapping" in data["required_skills"]


# --- caps: critical risk caps worktrees to 1 -------------------------------


def test_cap_critical_caps_worktrees_to_one(run_cli):
    """RP-CAP-001: critical risk => max_worktrees=1, so the ceiling is 1."""
    r = run_cli("approach", "evaluate", "--json",
                *_reading_args({"risk": "critical",
                                "familiarity": "brownfield-mapped",
                                "size": "large",
                                "intent": "delivery"}))
    assert r.returncode == 0, r
    data = json.loads(r.stdout)
    assert data["delivery_approach"] == "full"   # floor pushed it
    assert data["max_worktrees"] == 1
    assert data["subtask_ceiling"] == 1
    fired_ids = [f["id"] for f in data["policy_rules_fired"]]
    assert "RP-CAP-001" in fired_ids


# --- candidate-vs-final is recorded in the output -------------------------


def test_candidate_and_final_route_both_recorded(run_cli):
    """The JSON output records both the composed candidate and the final
    route - the floor's effect must be visible, not hidden."""
    r = run_cli("approach", "evaluate", "--json",
                *_reading_args({"risk": "contained",
                                "familiarity": "brownfield-mapped",
                                "size": "small",
                                "intent": "delivery",
                                "labels": ["auth"]}))
    assert r.returncode == 0, r
    data = json.loads(r.stdout)
    assert data["candidate_route"] == "quick-fix"
    assert data["delivery_approach"] == "full"
    assert data["candidate_via"], "candidate_via must say WHY the candidate was picked"


# --- `TRC-F3`: regression baseline - adaptive routing is unchanged ----------


def test_existing_combinations_unchanged(run_cli):
    """`TRC-F3`: The five reference delivery approaches still compose the same
    way.

    Loads tests/fixtures/route-baseline.yml (captured at HEAD fb092c0 before
    the cross-task-architectural-integrity work started) and asserts that for
    each assessment combination, `compass approach evaluate --json` still
    produces:
      - the same delivery-approach name (expected_route)
      - the same permitted parallelism (expected_subtask_ceiling)
      - the same per-phase weights (expected_phases)
      - the same gate set (expected_gates)

    A mismatch is a real regression: routing has drifted from the baseline.
    If that happens, this test must STOP and report - do not patch the
    fixture to make a regression pass.
    """
    import yaml

    baseline_path = (
        Path(__file__).resolve().parent / "fixtures" / "route-baseline.yml"
    )
    assert baseline_path.is_file(), f"Baseline fixture not found: {baseline_path}"

    baseline = yaml.safe_load(baseline_path.read_text(encoding="utf-8"))
    assert baseline, "Baseline fixture is empty - cannot verify routing"

    failures = []

    for entry in baseline:
        name = entry.get("name", "?")
        readings = entry["assessment"]
        expected_route = entry["expected_route"]
        # The baseline records an orchestration shape. `compass approach
        # evaluate` now emits a subtask ceiling, so the baseline values were
        # translated (solo=1, solo-or-pair=2, swarm=8).
        expected_ceiling = entry["expected_subtask_ceiling"]
        expected_phases = entry["expected_phases"]
        expected_gates = set(entry["expected_gates"])

        r = run_cli("approach", "evaluate", "--json", *_reading_args(readings))

        if r.returncode != 0:
            failures.append(
                f"[{name}] compass approach evaluate failed (exit {r.returncode}):\n"
                f"  stderr: {r.stderr}"
            )
            continue

        data = json.loads(r.stdout)

        actual_route = data.get("delivery_approach")
        actual_ceiling = data.get("subtask_ceiling")
        actual_phases = data.get("stages", {})
        actual_gates = set(data.get("gates", []))

        if actual_route != expected_route:
            failures.append(
                f"[{name}] ROUTE DRIFT: expected '{expected_route}', "
                f"got '{actual_route}'"
            )
        if expected_ceiling != actual_ceiling:
            failures.append(
                f"[{name}] PARALLELISM DRIFT: expected ceiling {expected_ceiling} "
                f"(substring), got '{actual_topology}'"
            )
        if actual_phases != expected_phases:
            failures.append(
                f"[{name}] PHASE DRIFT:\n"
                f"  expected: {expected_phases}\n"
                f"  actual  : {actual_phases}"
            )
        if actual_gates != expected_gates:
            failures.append(
                f"[{name}] GATE DRIFT:\n"
                f"  expected: {sorted(expected_gates)}\n"
                f"  actual  : {sorted(actual_gates)}"
            )

    assert not failures, (
        "Adaptive routing has drifted from the baseline - these are REAL "
        "REGRESSIONS, not test-logic errors:\n\n" + "\n\n".join(failures)
    )


# --- the YAML fixtures: one parameterised test for the whole set ----------


@pytest.mark.parametrize("fixture", load_route_fixtures(),
                         ids=lambda f: f["__file__"])
def test_route_fixture(run_cli, fixture):
    """One row per YAML in tests/fixtures/routes/. Each declares assessment
    values plus the expected delivery approach, floor, or conflict; the
    CLI's --json output must match."""
    args = _reading_args(fixture["assessment"])
    r = run_cli("approach", "evaluate", "--json", *args)
    expected = fixture["expected"]
    if expected.get("conflict"):
        assert r.returncode != 0, f"expected a conflict, got success:\n{r}"
        msg = expected.get("conflict_message_contains")
        if msg:
            assert msg.lower() in (r.stdout + r.stderr).lower(), r
        return
    assert r.returncode == 0, r
    data = json.loads(r.stdout)
    if "candidate_route" in expected:
        assert data["candidate_route"] == expected["candidate_route"]
    if "route" in expected:
        assert data["delivery_approach"] == expected["delivery_approach"]
    fired = [f["id"] for f in data.get("policy_rules_fired", [])]
    for fid in expected.get("fired_guardrail_ids", []):
        assert fid in fired, f"expected {fid!r} fired, got {fired!r}"
    if "subtask_ceiling" in expected:
        assert expected["subtask_ceiling"] == data["subtask_ceiling"], (
            f"permitted-parallelism mismatch: {data['subtask_ceiling']!r} vs "
            f"{expected['subtask_ceiling']!r}"
        )
    if "has_gate" in expected:
        assert expected["has_gate"] in data["gates"], (
            f"missing gate {expected['has_gate']!r} in {data['gates']!r}"
        )
