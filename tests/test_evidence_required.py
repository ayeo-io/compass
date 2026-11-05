"""The evidence a change owes, computed from its assessment (`evidence_required`).

Assess selects the evidence, not an approach: `compass_pkg.evidence_required`
is a pure function of the assessment and the configuration in force. These
tests pin each row and each addition, the cases that leave out the tokens of
the four-layer acceptance strategy (`S17`), and the parity with 8.0.4: on every
assessment of the contract 1 grid and every subset of the `G5` labels, the
gates derived from the evidence equal the gates the 8.0.4 governance routes.

Issue: ayeo-io/compass-delivery#351 [Replace the approaches and eight stages
with one four-stage path].
"""
from __future__ import annotations

import copy

import pytest

import compat_baseline as cb
from compass_pkg import evidence_required as er
from compass_pkg.core import CompassError
from compass_pkg.routing import RoutingConflict, evaluate_route

EVERY_ISSUE = ["scenarios", "red-before-green", "suite-green",
               "correctness", "governance", "traceability"]
S17_ON = ["outer-loop", "isolation", "layering"]


def _assess(**over):
    out = {"risk": "contained", "familiarity": "brownfield-mapped", "size": "small",
           "goal": "delivery", "urgency": "none", "labels": []}
    out.update(over)
    return out


@pytest.fixture(scope="module")
def live():
    return cb.shipped_policy()


@pytest.fixture(scope="module")
def policy_8_0_4(tmp_path_factory):
    return cb.policy_8_0_4(tmp_path_factory.mktemp("policy-8-0-4"))


# --- the rows -------------------------------------------------------------------

def test_light_row_owes_the_every_issue_evidence_and_the_outer_loop(live):
    out = er.evaluate(_assess(), live)
    assert out["delivery_approach"] == er.APPROACH_DELIVERY == "delivery"
    assert out["evidence_required"] == EVERY_ISSUE + ["outer-loop"]
    assert out["gates"] == ["verify.correctness", "verify.governance",
                            "verify.traceability"]
    assert out["acceptance_routing"] == "existing-dsl"
    assert out["rules_fired"] == ["RP-EVID-LIGHT"]
    assert out["stages"] == er.PATH_STAGE_IDS == ("assess", "specify", "build", "ship")


def test_defect_row_adds_the_old_hotfix_evidence(live):
    out = er.evaluate(_assess(urgency="live-defect", size="atomic"), live)
    assert out["evidence_required"] == EVERY_ISSUE + [
        "regression", "security", "outer-loop", "isolation", "definition-of-done",
        "reproduce-first"]
    assert out["gates"] == ["verify.correctness", "verify.governance",
                            "verify.traceability", "verify.regression",
                            "verify.security"]
    assert out["acceptance_routing"] == "existing-dsl-isolation"
    assert out["rules_fired"] == ["RP-EVID-DEFECT"]


def test_standard_row_adds_regression_security_clarity_and_the_definition_of_done(live):
    out = er.evaluate(_assess(size="medium"), live)
    assert out["evidence_required"] == EVERY_ISSUE + [
        "regression", "security", "clarity"] + S17_ON + ["definition-of-done"]
    assert out["gates"] == ["verify.correctness", "verify.governance",
                            "verify.traceability", "verify.regression",
                            "verify.security", "verify.clarity"]
    assert out["acceptance_routing"] == "on"
    assert out["rules_fired"] == ["RP-EVID-STANDARD"]


@pytest.mark.parametrize("over", [
    {"size": "large"}, {"size": "product"}, {"risk": "cross-cutting"},
    {"urgency": "live-defect", "size": "medium"},
    {"urgency": "live-defect", "risk": "critical"},
    {"labels": ["auth"]}, {"urgency": "live-defect", "labels": ["payments"]},
])
def test_every_other_delivery_assessment_takes_the_standard_row(live, over):
    out = er.evaluate(_assess(**over), live)
    assert out["rules_fired"][0] == "RP-EVID-STANDARD"
    assert "reproduce-first" not in out["evidence_required"]


def test_exploration_takes_the_spike_row_and_owes_only_its_conclusion(live):
    out = er.evaluate(_assess(goal="exploration", risk="cross-cutting",
                              urgency="live-defect"), live)
    assert out["delivery_approach"] == "spike"
    assert out["evidence_required"] == []
    assert out["gates"] == ["spike.conclude"]
    assert out["acceptance_routing"] == "suspended"
    assert out["rules_fired"] == ["RP-EVID-SPIKE"]
    assert out["stages"] == er.SPIKE_STAGE_IDS == ("assess", "build", "ship")


@pytest.mark.parametrize("over", [{"risk": "critical"}, {"labels": ["migrations"]}])
def test_exploration_on_a_surface_that_owes_a_sign_off_is_refused(live, over):
    # A spike ships nothing, so it must not touch the surface where a change owes
    # a person's sign-off. Re-assessing is a person's choice (`approaches/spike.md`).
    with pytest.raises(RoutingConflict, match="exploration cannot silently become delivery"):
        er.evaluate(_assess(goal="exploration", **over), live)


# --- the additions --------------------------------------------------------------

def test_cross_cutting_risk_adds_the_architecture_review(live):
    out = er.evaluate(_assess(risk="cross-cutting", size="medium"), live)
    assert "architecture" in out["evidence_required"]
    assert "verify.architecture" in out["gates"]
    assert "scenario-approval" not in out["evidence_required"]
    assert out["rules_fired"] == ["RP-EVID-STANDARD", "RP-REQUIRE-003"]


def test_critical_risk_adds_the_architecture_review_and_the_scenario_approval(live):
    out = er.evaluate(_assess(risk="critical", size="atomic"), live)
    assert out["evidence_required"] == EVERY_ISSUE + [
        "regression", "security", "clarity", "architecture"] + S17_ON + [
        "definition-of-done", "scenario-approval"]
    assert out["gates"][-1] == "verify.architecture"
    assert out["rules_fired"] == ["RP-EVID-STANDARD", "RP-REQUIRE-003", "RP-EVID-SIGNOFF"]


@pytest.mark.parametrize("label", er.G5_LABELS)
def test_a_g5_label_adds_architecture_scenario_approval_and_human_approval(live, label):
    out = er.evaluate(_assess(size="atomic", risk="trivial", labels=[label]), live)
    assert out["evidence_required"] == EVERY_ISSUE + [
        "regression", "security", "clarity", "architecture"] + S17_ON + [
        "definition-of-done", "scenario-approval", "human-approval"]
    assert out["rules_fired"] == ["RP-EVID-STANDARD", "RP-REQUIRE-004",
                                  "RP-EVID-SIGNOFF", "G5"]


def test_the_g5_labels_are_the_four_the_routing_rules_name(live):
    assert er.G5_LABELS == ("auth", "payments", "personal-data", "migrations")
    assert sorted(er.G5_LABELS) == cb.named_labels(live)


def test_a_label_outside_g5_adds_nothing(live):
    assert er.evaluate(_assess(labels=["docs"]), live) == er.evaluate(_assess(), live)


# --- the four-layer acceptance strategy -----------------------------------------

@pytest.mark.parametrize("row", [{}, {"urgency": "live-defect"}, {"size": "medium"}])
def test_the_strategy_turned_off_leaves_out_its_tokens_and_keeps_the_routing(live, row):
    on = er.evaluate(_assess(**row), live)
    off = er.evaluate(_assess(**row), live, acceptance_state="off")
    assert [t for t in on["evidence_required"] if t not in S17_ON] \
        == off["evidence_required"]
    assert not set(S17_ON) & set(off["evidence_required"])
    assert off["acceptance_routing"] == on["acceptance_routing"]
    assert off["acceptance_applies"] is False and on["acceptance_applies"] is True
    assert off["gates"] == on["gates"]


@pytest.mark.parametrize("kind", ["validation", "refactor"])
@pytest.mark.parametrize("row", [{}, {"urgency": "live-defect"}, {"size": "medium"}])
def test_an_expected_acceptance_of_validation_or_refactor_leaves_out_its_tokens(
        live, kind, row):
    on = er.evaluate(_assess(**row), live)
    out = er.evaluate(_assess(**row), live, expected_acceptance=kind)
    assert out["evidence_required"] == [t for t in on["evidence_required"]
                                        if t not in S17_ON]
    assert out["acceptance_applies"] is False


def test_an_unknown_strategy_state_or_acceptance_kind_is_refused(live):
    with pytest.raises(CompassError, match="acceptance_state"):
        er.evaluate(_assess(), live, acceptance_state="maybe")
    with pytest.raises(CompassError, match="expected_acceptance"):
        er.evaluate(_assess(), live, expected_acceptance="documentation")


# --- familiarity ----------------------------------------------------------------

def test_familiarity_never_changes_the_evidence(live):
    header, rows = cb.load_routing()
    seen = {}
    for row in rows:
        if row["kind"] != "grid":
            continue
        readings = _readings(row["assessment"])
        key = tuple(sorted((k, v) for k, v in readings.items()
                           if k not in ("familiarity", "labels")))
        try:
            out = er.evaluate(readings, live)
            got = (out["evidence_required"], out["gates"], out["acceptance_routing"])
        except RoutingConflict:
            got = "refused"
        seen.setdefault(key, set()).add(repr(got))
    assert seen and all(len(v) == 1 for v in seen.values())


def test_unmapped_ground_keeps_its_required_skill_and_its_advice(live):
    medium = er.evaluate(_assess(familiarity="brownfield-unmapped", size="medium"), live)
    assert medium["required_skills"] == ["behavior-mapping"]
    assert "RP-FLOOR-002" in medium["rules_fired"]
    small = er.evaluate(_assess(familiarity="brownfield-unmapped"), live)
    assert small["required_skills"] == []
    assert [s["id"] for s in small["applicable_strategies"]] == ["RP-ADV-002"]
    assert small["evidence_required"] == er.evaluate(_assess(), live)["evidence_required"]


# --- what the function reads of the configuration --------------------------------

def test_the_approaches_shapes_stage_modes_and_caps_are_never_read(live):
    stripped = copy.deepcopy(live)
    for key in ("route_shapes", "stage_mode_ranks", "autonomy_checkpoints"):
        stripped.pop(key, None)
    stripped["routing_strategies"].pop("default_shapes", None)
    stripped["routing_strategies"].pop("default_route", None)
    stripped["routing_guardrails"]["caps"] = [
        {"id": "X-CAP", "when": {}, "forbid_route": "regular", "max_worktrees": 0}]
    for fl in stripped["routing_guardrails"]["floors"]:
        fl.pop("force_minimum_route", None)
    header, rows = cb.load_routing()
    for row in rows[:200]:
        if row["kind"] != "grid":
            continue
        readings = _readings(row["assessment"])
        assert _result(readings, stripped) == _result(readings, live), readings


def test_the_rows_and_additions_owe_their_evidence_without_any_floor(live):
    """The additions are rows of this module, not of the configuration: a policy with
    no floors still owes the architecture review and the sign-offs."""
    bare = copy.deepcopy(live)
    bare["routing_guardrails"]["floors"] = []
    for over in ({"risk": "cross-cutting"}, {"risk": "critical"}, {"labels": ["auth"]}):
        assert er.evaluate(_assess(**over), bare)["evidence_required"] \
            == er.evaluate(_assess(**over), live)["evidence_required"], over


def test_a_floor_of_the_configuration_adds_its_gate(live):
    policy = copy.deepcopy(live)
    policy["routing_guardrails"]["floors"] += [
        {"id": "P-ONE", "when": {"size": "atomic"}, "add_gate": "verify.regression"},
        {"id": "P-TWO", "when": {"size": "atomic"}, "add_gate": "verify.claims"},
    ]
    out = er.evaluate(_assess(size="atomic"), policy)
    assert out["evidence_required"] == EVERY_ISSUE + ["regression", "outer-loop"]
    assert out["gates"] == ["verify.correctness", "verify.governance",
                            "verify.traceability", "verify.regression", "verify.claims"]
    assert out["rules_fired"] == ["RP-EVID-LIGHT", "P-ONE", "P-TWO"]
    # A spike takes no added gate, as in 8.x.
    spike = er.evaluate(_assess(size="atomic", goal="exploration"), policy)
    assert spike["gates"] == ["spike.conclude"]


def test_a_removed_gate_is_never_owed_and_its_rule_does_not_fire(policy_8_0_4):
    out = er.evaluate(_assess(risk="critical"), policy_8_0_4)
    assert "verify.analyze" not in out["gates"]
    assert "RP-REQUIRE-001" not in out["rules_fired"]


def test_an_assessment_outside_the_vocabulary_is_refused(live):
    with pytest.raises(CompassError, match="size"):
        er.evaluate(_assess(size="huge"), live)
    with pytest.raises(CompassError, match="risk"):
        er.evaluate({"familiarity": "greenfield", "size": "small"}, live)


def test_the_assessment_passed_in_is_not_changed(live):
    readings = _assess(labels=["auth"])
    before = copy.deepcopy(readings)
    er.evaluate(readings, live)
    assert readings == before


# --- parity with 8.0.4 ------------------------------------------------------------

#: The routing of `S17` each 8.x approach names in the live default preset
#: (`governance/presets/default/approaches.yml`, `acceptance_strategy`). 8.0.4
#: itself named none, so every approach that ships read `on` there; the
#: routings come from 9.0.0, before the approaches were removed.
ROUTING_OF_APPROACH = {"quick-fix": "existing-dsl", "hotfix": "existing-dsl-isolation",
                       "regular": "on", "full": "on", "spike": "suspended"}


def _readings(assessment):
    """A contract 1 grid assessment in the words 9.0.0 reads, through the bridges of
    `compat_baseline.compact`: the size `standard` read as `medium` (`SIZE_NOW`), and
    the role left out. 7.0.0 retired role (ADR-070); the documents it brought in
    its place (`_role_as_documents`) went in 9.0.0 (ADR-091), so a 9.0.0 assessment
    names neither."""
    readings = {k: v for k, v in assessment.items() if k != "role"}
    readings["size"] = cb.SIZE_NOW.get(readings["size"], readings["size"])
    return readings


def _result(readings, policy):
    try:
        out = er.evaluate(copy.deepcopy(readings), policy)
    except RoutingConflict:
        return "refused"
    return (sorted(out["gates"]), out["acceptance_routing"])


def _routed(readings, policy):
    try:
        out = evaluate_route(copy.deepcopy(readings), policy)
    except RoutingConflict:
        return "refused"
    return (sorted(out["gates"]), ROUTING_OF_APPROACH[out["delivery_approach"]])


def test_the_8_0_4_copy_routes_the_contract_1_baseline(policy_8_0_4):
    """The copy is the 8.x answer the parity test compares with: on every grid row
    and label subset it routes the 5.6.0 baseline after the bridges."""
    header, rows = cb.load_routing()
    assert cb.routing_differences(policy_8_0_4, header, rows, layered=True) == []


def _parity_differences(policy_8_0_4, live, first_only=False):
    """`(points, differences)` over every row of the contract 1 grid under every
    subset of the four `G5` labels."""
    header, rows = cb.load_routing()
    grid = [row["assessment"] for row in rows if row["kind"] == "grid"]
    subsets = list(cb.label_subsets(header["labels"]))
    assert len(grid) == 1200 and len(subsets) == 16
    differ, points = [], 0
    for assessment in grid:
        for labels in subsets:
            readings = dict(_readings(assessment), labels=labels)
            points += 1
            want = _routed(readings, policy_8_0_4)
            got = _result(readings, live)
            if got != want:
                differ.append(f"{readings}: 8.0.4 {want}, evidence {got}")
                if first_only:
                    return points, differ
    return points, differ


def test_the_evidence_owes_the_gates_8_0_4_routed_on_every_grid_point(policy_8_0_4, live):
    """Parity: every row of the contract 1 grid (1,200 assessments) under every subset
    of the four `G5` labels (16), so 19,200 points. On each, the gates derived from
    `evidence_required` equal the gates the 8.0.4 copy routes, and the `S17` routing
    equals the routing of the approach 8.0.4 chose. A refusal on one side must be a
    refusal on the other."""
    points, differ = _parity_differences(policy_8_0_4, live)
    assert points == 19200
    assert differ == [], f"{len(differ)} of {points} points differ:\n" + "\n".join(differ[:40])


@pytest.mark.parametrize("plant", ["row", "addition"])
def test_the_parity_test_sees_one_changed_row_or_addition(policy_8_0_4, live,
                                                          monkeypatch, plant):
    if plant == "row":
        rows = list(er.ROWS)
        rule, when, tokens, routing = rows[1]
        rows[1] = (rule, when, tokens + ("regression",), routing)
        monkeypatch.setattr(er, "ROWS", tuple(rows))
    else:
        # Taking an addition out is not seen: the configuration's own floors
        # `RP-REQUIRE-003` and `RP-REQUIRE-004` add the same gate. Widening one is.
        rule, when, token = er.ADDITIONS[0]
        widened = (rule, {"risk": ["contained", "cross-cutting", "critical"]}, token)
        monkeypatch.setattr(er, "ADDITIONS", (widened,) + er.ADDITIONS[1:])
    _, differ = _parity_differences(policy_8_0_4, live, first_only=True)
    assert differ, f"planting a change in the {plant}s went unseen"
