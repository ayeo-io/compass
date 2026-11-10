"""Delivery-approach selection: the deterministic core.

These tests prove that the 8.x evaluator, `routing.evaluate_route`, is a pure
function: given assessment values + a routing policy, it produces the
documented delivery approach, fires the documented floors/caps, and permits
the documented parallelism.

The policy is the 8.0.4 governance copy (`compat_baseline.GOVERNANCE_8_0_4`),
the last release that routed delivery approaches. 9.0.0 replaces the
approaches with one path (ADR-092), so these tests do not read the live
default: a change to its approaches must not move a recorded route.

`compass approach evaluate` now prints the path for a delivery assessment and
keeps the approach only for a spike. The command reads the shipped check set:
9.0.0 reads no project copy of the governance files (ADR-098). So the tests of a delivery approach call
the evaluator in process, with the assessment read as the command reads it,
and each test that ran the command has a path twin at the bottom: the same
assessment through the command, and the evidence it owes now.

The bulk of the proof is the YAML-driven parameterised test - each fixture in
tests/fixtures/routes/ declares an input + expected output. The fixtures are
5.6.0-era baselines and are never re-captured.
"""

# These tests assert the current stage keys. Older manifests still load
# through `normalize_spine` (ADR-006).
from __future__ import annotations

import json
from pathlib import Path

import pytest

import compat_baseline as cb
from compass_pkg import evidence_required as er
from compass_pkg import routing
from compass_pkg.core import ASSESSMENT_KEY_MAP
from conftest import load_route_fixtures


# --- happy-path: each fixture selects the documented delivery approach for
# representative assessment values --


def _size_now(key: str, value):
    """A recorded 8.x size in the 9.0.0 word. The fixtures were written before
    `standard` became `medium`, and 9.0.0 reads no old word typed on the
    command line (ADR-098), so the test types the new one."""
    return cb.SIZE_NOW.get(value, value) if key == "size" else value


def _reading_args(readings: dict) -> list[str]:
    """Translate an assessment dict into --assessment key=value CLI args."""
    args = []
    for k, v in readings.items():
        if isinstance(v, list):
            args.extend(["--assessment", f"{k}=" + ",".join(v)])
        else:
            args.extend(["--assessment", f"{k}={_size_now(k, v)}"])
    return args


def _as_read(readings: dict) -> dict:
    """The assessment as `approach evaluate --assessment` reads it: the old key
    names mapped to the new ones, and a recorded old size in the new word."""
    out = {}
    for k, v in readings.items():
        k = ASSESSMENT_KEY_MAP.get(k, k)
        out[k] = list(v) if isinstance(v, list) else _size_now(k, v)
    return out


def _evaluate(readings: dict) -> dict:
    """What the 8.x evaluator gives for the assessment on the 8.0.4 copy: the
    result `approach evaluate --json` printed before the path (ADR-092)."""
    return routing.evaluate_route(_as_read(readings), cb.policy_8_0_4())


def _evaluate_cli(run_cli, readings: dict) -> dict:
    """The JSON `compass approach evaluate` prints for the assessment."""
    r = run_cli("approach", "evaluate", "--json", *_reading_args(readings))
    assert r.returncode == 0, r
    return json.loads(r.stdout)


def test_express_route_for_small_mapped_change():
    """RP-SHAPE-003: small + contained + mapped == express."""
    data = _evaluate({"risk": "contained",
                     "familiarity": "brownfield-mapped",
                     "size": "small",
                     "intent": "delivery"})
    assert data["delivery_approach"] == "quick-fix"
    assert data["candidate_route"] == "quick-fix"


def test_standard_route_for_default_shape():
    """RP-SHAPE-005: size=standard == standard."""
    data = _evaluate({"risk": "contained",
                     "familiarity": "brownfield-mapped",
                     "size": "standard",
                     "intent": "delivery"})
    assert data["delivery_approach"] == "regular"


def test_expedition_route_for_large_magnitude():
    """RP-SHAPE-004: size=large == expedition."""
    data = _evaluate({"risk": "contained",
                     "familiarity": "brownfield-mapped",
                     "size": "large",
                     "intent": "delivery"})
    assert data["delivery_approach"] == "full"
    # No policy bounds multiagent work: no number for it exists in
    # routing-policy.yml or .compass/config.yml, so only a cap makes one.
    assert data["subtask_ceiling"] is None


def test_hotfix_route_for_live_defect():
    """RP-SHAPE-002: urgency=live-defect + small size == hotfix."""
    data = _evaluate({"risk": "contained",
                     "familiarity": "brownfield-mapped",
                     "size": "small",
                     "intent": "delivery",
                     "urgency": "live-defect"})
    assert data["delivery_approach"] == "hotfix"


def test_spike_route_for_exploration_intent(run_cli):
    """RP-SHAPE-001: intent=exploration on safe surface == spike. A spike keeps
    its approach on the path, so the command still prints it. Like a path issue
    it has no subtask ceiling (ADR-092 decision 11)."""
    data = _evaluate_cli(run_cli, {"risk": "contained",
                                   "familiarity": "brownfield-mapped",
                                   "size": "small",
                                   "intent": "exploration"})
    assert data["delivery_approach"] == "spike"
    assert "subtask_ceiling" not in data and "max_worktrees" not in data


# --- floors: a matching reading raises the route or forces a phase ---------


def test_floor_critical_blast_radius_forces_expedition():
    """RP-FLOOR-001: risk=critical forces at least expedition."""
    data = _evaluate({"risk": "critical",
                     "familiarity": "brownfield-mapped",
                     "size": "small",
                     "intent": "delivery"})
    assert data["delivery_approach"] == "full"
    fired = [f["id"] for f in data["policy_rules_fired"]]
    assert "RP-FLOOR-001" in fired
    # candidate was lighter; the floor raised it
    assert data["candidate_route"] != data["delivery_approach"]


@pytest.mark.parametrize("domain", ["auth", "payments", "personal-data", "migrations"])
def test_floor_g5_domains_force_expedition(domain):
    """RP-FLOOR-003: touching any `G5` domain forces at least expedition."""
    data = _evaluate({"risk": "contained",
                     "familiarity": "brownfield-mapped",
                     "size": "small",
                     "intent": "delivery",
                     "labels": [domain]})
    assert data["delivery_approach"] == "full", (
        f"touching {domain!r} should force expedition, got {data['delivery_approach']!r}"
    )
    fired = [f["id"] for f in data["policy_rules_fired"]]
    assert "RP-FLOOR-003" in fired


def test_floor_brownfield_unmapped_requires_specify():
    """RP-FLOOR-002: brownfield-unmapped beyond a small, contained change
    forces the define stage to full and needs the behavior-mapping skill."""
    data = _evaluate({"risk": "contained",
                     "familiarity": "brownfield-unmapped",
                     "size": "medium",
                     "intent": "delivery"})
    fired = [f["id"] for f in data["policy_rules_fired"]]
    assert "RP-FLOOR-002" in fired
    assert data["stages"].get("define") == "thorough"
    assert "behavior-mapping" in data["required_skills"]


# --- caps: critical risk caps worktrees to 1 -------------------------------


def test_cap_critical_caps_worktrees_to_one():
    """RP-CAP-001: critical risk => max_worktrees=1, so the ceiling is 1."""
    data = _evaluate({"risk": "critical",
                     "familiarity": "brownfield-mapped",
                     "size": "large",
                     "intent": "delivery"})
    assert data["delivery_approach"] == "full"   # floor pushed it
    assert data["max_worktrees"] == 1
    assert data["subtask_ceiling"] == 1
    fired_ids = [f["id"] for f in data["policy_rules_fired"]]
    assert "RP-CAP-001" in fired_ids


# --- candidate-vs-final is recorded in the output -------------------------


def test_candidate_and_final_route_both_recorded():
    """The JSON output records both the composed candidate and the final
    route - the floor's effect must be visible, not hidden."""
    data = _evaluate({"risk": "contained",
                     "familiarity": "brownfield-mapped",
                     "size": "small",
                     "intent": "delivery",
                     "labels": ["auth"]})
    assert data["candidate_route"] == "quick-fix"
    assert data["delivery_approach"] == "full"
    assert data["candidate_via"], "candidate_via must say WHY the candidate was picked"


# --- `TRC-F3`: regression baseline - adaptive routing is unchanged ----------


def test_existing_combinations_unchanged():
    """`TRC-F3`: The five reference delivery approaches still compose the same
    way.

    Loads tests/fixtures/route-baseline.yml (captured at HEAD fb092c0 before
    the cross-task-architectural-integrity work started) and asserts that for
    each assessment combination, the 8.x evaluator on the 8.0.4 copy still
    produces:
      - the same delivery-approach name (expected_route)
      - the same permitted parallelism (expected_subtask_ceiling)
      - the same per-phase weights (expected_phases)
      - the same gate set (expected_gates)

    A mismatch is a real regression: routing has drifted from the baseline.
    If that happens, this test must STOP and report - do not patch the
    fixture to make a regression pass.
    """
    baseline = _baseline()
    failures = []

    for entry in baseline:
        name = entry.get("name", "?")
        readings = entry["assessment"]
        expected_route = entry["expected_route"]
        # The baseline records an orchestration shape. The evaluator now
        # emits a subtask ceiling, so the baseline values were translated
        # (solo=1, solo-or-pair=2, swarm=8).
        expected_ceiling = entry["expected_subtask_ceiling"]
        expected_phases = entry["expected_phases"]
        expected_gates = set(entry["expected_gates"])

        try:
            data = _evaluate(readings)
        except routing.CompassError as exc:
            failures.append(f"[{name}] the evaluator refused: {exc}")
            continue

        actual_route = data.get("delivery_approach")
        actual_ceiling = data.get("subtask_ceiling")
        # The baseline predates the rename of the depth words and is not
        # rewritten: the stage weights are compared in the words it recorded.
        actual_phases = {s: cb.DEPTH_WAS.get(m, m)
                         for s, m in data.get("stages", {}).items()}
        actual_gates = set(data.get("gates", []))

        if actual_route != expected_route:
            failures.append(
                f"[{name}] ROUTE DRIFT: expected '{expected_route}', "
                f"got '{actual_route}'"
            )
        if expected_ceiling != actual_ceiling:
            failures.append(
                f"[{name}] PARALLELISM DRIFT: expected ceiling {expected_ceiling}, "
                f"got {actual_ceiling!r}"
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


def _baseline():
    import yaml

    baseline_path = (
        Path(__file__).resolve().parent / "fixtures" / "route-baseline.yml"
    )
    assert baseline_path.is_file(), f"Baseline fixture not found: {baseline_path}"
    baseline = yaml.safe_load(baseline_path.read_text(encoding="utf-8"))
    assert baseline, "Baseline fixture is empty - cannot verify routing"
    return baseline


# --- the YAML fixtures: one parameterised test for the whole set ----------


@pytest.mark.parametrize("fixture", load_route_fixtures(),
                         ids=lambda f: f["__file__"])
def test_route_fixture(run_cli, fixture):
    """One row per YAML in tests/fixtures/routes/. Each declares assessment
    values plus the expected delivery approach, floor, or conflict; the 8.x
    evaluator's result on the 8.0.4 copy must match. A conflict is refused by
    the command as well, since the path refuses it too."""
    expected = fixture["expected"]
    if expected.get("conflict"):
        with pytest.raises(routing.RoutingConflict) as refused:
            _evaluate(fixture["assessment"])
        r = run_cli("approach", "evaluate", "--json",
                    *_reading_args(fixture["assessment"]))
        assert r.returncode != 0, f"expected a conflict, got success:\n{r}"
        msg = expected.get("conflict_message_contains")
        if msg:
            assert msg.lower() in str(refused.value).lower(), refused.value
            assert msg.lower() in (r.stdout + r.stderr).lower(), r
        return
    data = _evaluate(fixture["assessment"])
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


# --- path twins: the same assessments through the command now --------------
#
# Each test above that ran `compass approach evaluate` has its twin here. A
# delivery assessment prints `delivery` and the evidence it owes; the 8.x keys
# of the approach (`stages`, `subtask_ceiling`, `max_worktrees`) are gone.

#: The evidence of the acceptance strategy `S17` (`governance/strategies.md`).
#: It is owed only where a project setting adds it (ADR-099 decision 9).
S17_EVIDENCE = ("outer-loop", "isolation", "layering")

#: What every delivery issue owes between the request link and the ship approval
#: (ADR-099 decision 4). Size, risk, familiarity and urgency add nothing.
COMMON = ["scenarios", "red-before-green", "suite-green", "correctness",
          "governance", "traceability"]
SMALL = {"risk": "contained", "familiarity": "brownfield-mapped",
         "size": "small", "intent": "delivery"}
COMMON_RULE = ["RP-EVID-COMMON"]

PATH_TWINS = {
    # twin of test_express_route_for_small_mapped_change
    "small-mapped": (SMALL, COMMON, COMMON_RULE),
    # twin of test_standard_route_for_default_shape
    "standard": (dict(SMALL, size="standard"), COMMON, COMMON_RULE),
    # twin of test_expedition_route_for_large_magnitude
    "large": (dict(SMALL, size="large"), COMMON, COMMON_RULE),
    # twin of test_hotfix_route_for_live_defect
    "live-defect": (dict(SMALL, urgency="live-defect"), COMMON, COMMON_RULE),
    # twin of test_floor_critical_blast_radius_forces_expedition
    "critical": (dict(SMALL, risk="critical"), COMMON + ["scenario-approval"],
                 COMMON_RULE + ["RP-EVID-SIGNOFF"]),
    # twin of test_cap_critical_caps_worktrees_to_one
    "critical-large": (dict(SMALL, risk="critical", size="large"),
                       COMMON + ["scenario-approval"], COMMON_RULE + ["RP-EVID-SIGNOFF"]),
    # twin of test_floor_brownfield_unmapped_requires_specify
    "brownfield-unmapped": (dict(SMALL, familiarity="brownfield-unmapped",
                                 size="medium"),
                            COMMON, COMMON_RULE + ["RP-FLOOR-002"]),
}
# twins of test_floor_g5_domains_force_expedition and
# test_candidate_and_final_route_both_recorded: a `G5` label owes two sign-offs.
for _domain in ("auth", "payments", "personal-data", "migrations"):
    PATH_TWINS[f"g5-{_domain}"] = (
        dict(SMALL, labels=[_domain]),
        COMMON + ["scenario-approval", "human-approval"],
        COMMON_RULE + ["RP-EVID-SIGNOFF", "G5"])


@pytest.mark.parametrize("name", sorted(PATH_TWINS))
def test_the_command_prints_the_path_for_a_delivery_assessment(run_cli, name):
    readings, owed, fired = PATH_TWINS[name]
    data = _evaluate_cli(run_cli, readings)
    assert data["delivery_approach"] == "delivery"
    # Every delivery row also owes the request link, first in the manifest's order
    # (#356), and the ship approval, last (#355). The records of `S17` are owed
    # only where a project setting adds them, and these projects have none.
    assert not [t for t in data["evidence_required"] if t in S17_EVIDENCE]
    assert data["evidence_required"] == ["request"] + owed + ["ship-approval"]
    assert [f["id"] for f in data["policy_rules_fired"]] == fired
    # The gates are derived from the evidence (ADR-092).
    path = er.evaluate(_as_read(readings), cb.policy_8_0_4())
    assert data["gates"] == path["gates"]
    for key in ("stages", "subtask_ceiling", "max_worktrees"):
        assert key not in data, f"the path does not print {key!r}"
    if name == "brownfield-unmapped":
        # #360 merged the skill into `atdd`, which the check set names.
        assert "atdd" in data["required_skills"]


def test_the_command_prints_the_path_for_each_baseline_combination(run_cli):
    """Twin of test_existing_combinations_unchanged: the command prints
    `delivery` for each delivery row of the baseline, and a spike row as the
    8.x evaluator routes it over the check set the command reads."""
    shipped = cb.shipped_policy()
    for entry in _baseline():
        old = _evaluate(entry["assessment"])
        data = _evaluate_cli(run_cli, entry["assessment"])
        if old["delivery_approach"] == "spike":
            live = routing.evaluate_route(_as_read(entry["assessment"]), shipped)
            assert data["delivery_approach"] == "spike", entry["name"]
            assert data["gates"] == old["gates"] == live["gates"], entry["name"]
            assert data["stages"] == live["stages"], entry["name"]
        else:
            assert data["delivery_approach"] == "delivery", entry["name"]
            assert data["evidence_required"], entry["name"]


@pytest.mark.parametrize("fixture", [f for f in load_route_fixtures()
                                     if not f["expected"].get("conflict")],
                         ids=lambda f: f["__file__"])
def test_the_command_prints_the_path_for_each_route_fixture(run_cli, fixture):
    """Twin of test_route_fixture for the fixtures that are not a conflict."""
    data = _evaluate_cli(run_cli, fixture["assessment"])
    if fixture["expected"]["delivery_approach"] == "spike":
        assert data["delivery_approach"] == "spike"
        assert fixture["expected"]["has_gate"] in data["gates"]
    else:
        assert data["delivery_approach"] == "delivery"
        assert "evidence_required" in data
        assert "subtask_ceiling" not in data
