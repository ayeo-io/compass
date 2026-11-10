"""The evidence a change owes, computed from its assessment (`evidence_required`).

Assess selects the evidence, not an approach: `compass_pkg.evidence_required`
is a pure function of the assessment and the configuration in force. These
tests pin the common row, each addition, the four-layer acceptance strategy
(`S17`), which is owed only where a project setting adds its tokens, and the
parity with 8.0.4: on every assessment of the contract 1 grid and every subset
of the `G5` labels, a refusal is a refusal on both sides, the gates are the
three every issue has, and the sign-offs owed are the ones 8.0.4 required.
Every delivery issue owes the same row (ADR-099 decision 4).

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

#: `request` (#356) is first in the manifest's order, so it starts every delivery list.
EVERY_ISSUE = ["request", "scenarios", "red-before-green", "suite-green",
               "correctness", "governance", "traceability"]
#: The ship approval every delivery row owes (#355). It is the last token in the
#: manifest's order, so it ends every delivery list.
SHIP = ["ship-approval"]
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

def test_the_common_row_owes_the_every_issue_evidence_and_nothing_more(live):
    out = er.evaluate(_assess(), live)
    assert out["delivery_approach"] == er.APPROACH_DELIVERY == "delivery"
    assert out["evidence_required"] == EVERY_ISSUE + SHIP
    assert out["gates"] == ["verify.correctness", "verify.governance",
                            "verify.traceability"]
    assert out["acceptance_routing"] == "guidance"
    assert out["acceptance_applies"] is False
    assert out["rules_fired"] == ["RP-EVID-COMMON"]
    assert out["stages"] == er.PATH_STAGE_IDS == ("assess", "specify", "build", "ship")


def test_a_live_defect_owes_the_common_evidence_and_no_reproduction_record(live):
    out = er.evaluate(_assess(urgency="live-defect", size="atomic"), live)
    assert out["evidence_required"] == EVERY_ISSUE + SHIP
    assert out["gates"] == ["verify.correctness", "verify.governance",
                            "verify.traceability"]
    assert out["acceptance_routing"] == "guidance"
    assert out["rules_fired"] == ["RP-EVID-COMMON"]


def test_a_project_rule_adds_the_old_hotfix_evidence_for_a_live_defect(live):
    policy = dict(live, require_evidence=[
        {"id": "RP-SETTING-HOTFIX", "when": {"urgency": "live-defect"},
         "add": ["regression", "security", "isolation", "definition-of-done",
                 "reproduce-first"]}])
    out = er.evaluate(_assess(urgency="live-defect", size="atomic"), policy)
    assert out["evidence_required"] == EVERY_ISSUE + [
        "regression", "security", "isolation", "definition-of-done",
        "reproduce-first"] + SHIP
    assert out["gates"] == ["verify.correctness", "verify.governance",
                            "verify.traceability", "verify.regression",
                            "verify.security"]
    assert out["acceptance_routing"] == "existing-dsl-isolation"
    assert out["rules_fired"] == ["RP-EVID-COMMON", "RP-SETTING-HOTFIX"]
    # Without the live defect the rule does not match.
    assert er.evaluate(_assess(size="atomic"), policy)["evidence_required"] \
        == EVERY_ISSUE + SHIP


@pytest.mark.parametrize("over", [
    {"size": "medium"}, {"size": "large"}, {"size": "product"},
    {"risk": "cross-cutting"}, {"urgency": "live-defect", "size": "medium"},
    {"familiarity": "greenfield"}, {"urgency": "live-defect", "risk": "cross-cutting"},
])
def test_no_size_risk_familiarity_or_urgency_adds_evidence(live, over):
    out = er.evaluate(_assess(**over), live)
    assert out["rules_fired"] == ["RP-EVID-COMMON"]
    assert out["evidence_required"] == EVERY_ISSUE + SHIP
    assert out["gates"] == ["verify.correctness", "verify.governance",
                            "verify.traceability"]
    assert out["acceptance_routing"] == "guidance"


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

def test_cross_cutting_risk_adds_no_review_and_no_approval(live):
    out = er.evaluate(_assess(risk="cross-cutting", size="medium"), live)
    assert "architecture" not in out["evidence_required"]
    assert "verify.architecture" not in out["gates"]
    assert "scenario-approval" not in out["evidence_required"]
    # The shipped floors that add the architecture gate are kept for 8.x only.
    assert out["rules_fired"] == ["RP-EVID-COMMON"]


def test_a_project_rule_adds_the_architecture_review_for_cross_cutting_risk(live):
    policy = dict(live, require_evidence=[
        {"id": "RP-SETTING-ARCH", "when": {"risk": ["cross-cutting", "critical"]},
         "add": ["architecture"]}])
    out = er.evaluate(_assess(risk="cross-cutting"), policy)
    assert out["evidence_required"] == EVERY_ISSUE + ["architecture"] + SHIP
    assert out["gates"][-1] == "verify.architecture"
    assert er.evaluate(_assess(), policy)["evidence_required"] == EVERY_ISSUE + SHIP


def test_critical_risk_adds_the_scenario_approval_and_no_sign_off(live):
    out = er.evaluate(_assess(risk="critical", size="atomic"), live)
    assert out["evidence_required"] == EVERY_ISSUE + ["scenario-approval"] + SHIP
    assert "human-approval" not in out["evidence_required"]
    assert out["gates"] == ["verify.correctness", "verify.governance",
                            "verify.traceability"]
    assert out["rules_fired"] == ["RP-EVID-COMMON", "RP-EVID-SIGNOFF"]


@pytest.mark.parametrize("label", er.G5_LABELS)
def test_a_g5_label_adds_scenario_approval_and_human_approval(live, label):
    out = er.evaluate(_assess(size="atomic", risk="trivial", labels=[label]), live)
    assert out["evidence_required"] == EVERY_ISSUE + [
        "scenario-approval", "human-approval"] + SHIP
    assert out["gates"] == ["verify.correctness", "verify.governance",
                            "verify.traceability"]
    assert out["rules_fired"] == ["RP-EVID-COMMON", "RP-EVID-SIGNOFF", "G5"]


def test_the_g5_labels_are_the_four_the_routing_rules_name(live):
    assert er.G5_LABELS == ("auth", "payments", "personal-data", "migrations")
    assert sorted(er.G5_LABELS) == cb.named_labels(live)


def test_a_label_outside_g5_adds_nothing(live):
    assert er.evaluate(_assess(labels=["docs"]), live) == er.evaluate(_assess(), live)


# --- the tighten-only settings the policy carries -------------------------------

def test_a_signoff_label_of_the_policy_owes_what_a_g5_label_owes(live):
    policy = dict(live, signoff_labels=["billing", "auth"])
    assert er.signoff_labels(policy) == er.G5_LABELS + ("billing",)
    added = er.evaluate(_assess(size="atomic", risk="trivial", labels=["billing"]), policy)
    shipped = er.evaluate(_assess(size="atomic", risk="trivial", labels=["auth"]), live)
    assert added == shipped
    with pytest.raises(RoutingConflict):
        er.evaluate(_assess(goal="exploration", labels=["billing"]), policy)


def test_the_policy_cannot_take_a_shipped_g5_label_away(live):
    policy = dict(live, signoff_labels=[])
    assert er.signoff_labels(policy) == er.G5_LABELS
    assert er.evaluate(_assess(labels=["auth"]), policy) == er.evaluate(
        _assess(labels=["auth"]), live)
    with pytest.raises(CompassError, match="signoff_labels"):
        er.evaluate(_assess(), dict(live, signoff_labels="billing"))


def test_required_evidence_of_the_policy_adds_its_tokens_where_it_matches(live):
    policy = dict(live, require_evidence=[
        {"id": "RP-SETTING-1", "when": {"risk": "contained"}, "add": ["security"]},
        {"id": "RP-SETTING-2", "when": {"size": "large"}, "add": ["clarity"]}])
    out = er.evaluate(_assess(), policy)
    assert out["evidence_required"] == EVERY_ISSUE + ["security"] + SHIP
    assert "verify.security" in out["gates"]
    assert out["rules_fired"] == ["RP-EVID-COMMON", "RP-SETTING-1"]
    assert er.evaluate(_assess(goal="exploration"), policy)["evidence_required"] == []
    with pytest.raises(CompassError, match="require_evidence"):
        er.evaluate(_assess(), dict(live, require_evidence=[{"id": "X", "add": ["nope"]}]))


# --- the four-layer acceptance strategy -----------------------------------------

ROWS_TO_TRY = [{}, {"urgency": "live-defect"}, {"size": "medium"}]


def _adds(*tokens):
    """The shipped configuration plus a project rule that adds `tokens`."""
    return lambda live: dict(live, require_evidence=[
        {"id": "RP-SETTING-S17", "when": {}, "add": list(tokens)}])


@pytest.mark.parametrize("row", ROWS_TO_TRY)
def test_the_strategy_is_guidance_and_owes_nothing_unless_a_setting_adds_a_token(live, row):
    out = er.evaluate(_assess(**row), live)
    assert not set(S17_ON) & set(out["evidence_required"])
    assert out["acceptance_routing"] == "guidance"
    assert out["acceptance_applies"] is False


@pytest.mark.parametrize("token, routing", [
    ("outer-loop", "existing-dsl"), ("isolation", "existing-dsl-isolation"),
    ("layering", "on")])
@pytest.mark.parametrize("row", ROWS_TO_TRY)
def test_a_setting_that_adds_a_strategy_token_owes_it_and_routes_the_strategy(
        live, row, token, routing):
    out = er.evaluate(_assess(**row), _adds(token)(live))
    assert token in out["evidence_required"]
    assert out["acceptance_routing"] == routing
    assert out["acceptance_applies"] is True
    assert out["gates"] == ["verify.correctness", "verify.governance",
                            "verify.traceability"]


@pytest.mark.parametrize("row", ROWS_TO_TRY)
def test_the_strategy_turned_off_keeps_the_routing_and_does_not_apply(live, row):
    policy = _adds("layering")(live)
    on = er.evaluate(_assess(**row), policy)
    off = er.evaluate(_assess(**row), policy, acceptance_state="off")
    assert off["acceptance_routing"] == on["acceptance_routing"] == "on"
    assert off["acceptance_applies"] is False and on["acceptance_applies"] is True
    assert off["gates"] == on["gates"]


@pytest.mark.parametrize("kind", ["validation", "refactor"])
@pytest.mark.parametrize("row", ROWS_TO_TRY)
def test_an_expected_acceptance_of_validation_or_refactor_does_not_apply_the_strategy(
        live, kind, row):
    policy = _adds("outer-loop")(live)
    assert er.evaluate(_assess(**row), policy)["acceptance_applies"] is True
    out = er.evaluate(_assess(**row), policy, expected_acceptance=kind)
    assert out["acceptance_applies"] is False
    assert out["acceptance_routing"] == "existing-dsl"
    assert er.evaluate(_assess(**row), live, expected_acceptance=kind)["evidence_required"] \
        == er.evaluate(_assess(**row), live)["evidence_required"]


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
    # #360 merged the skill into `atdd`, which the check set names.
    assert medium["required_skills"] == ["atdd"]
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
    assert out["evidence_required"] == EVERY_ISSUE + ["regression"] + SHIP
    assert out["gates"] == ["verify.correctness", "verify.governance",
                            "verify.traceability", "verify.regression", "verify.claims"]
    assert out["rules_fired"] == ["RP-EVID-COMMON", "P-ONE", "P-TWO"]
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

def _readings(assessment):
    """A contract 1 grid assessment in the words 9.0.0 reads, through the bridges of
    `compat_baseline.compact`: the size `standard` read as `medium` (`SIZE_NOW`), and
    the role left out. 7.0.0 retired role (ADR-070); the documents it brought in
    its place (`_role_as_documents`) went in 9.0.0 (ADR-091), so a 9.0.0 assessment
    names neither."""
    readings = {k: v for k, v in assessment.items() if k != "role"}
    readings["size"] = cb.SIZE_NOW.get(readings["size"], readings["size"])
    return readings


#: The three gates every delivery issue has, whatever its assessment.
THREE_GATES = ["verify.correctness", "verify.governance", "verify.traceability"]


def _result(readings, policy):
    try:
        out = er.evaluate(copy.deepcopy(readings), policy)
    except RoutingConflict:
        return "refused"
    return (sorted(out["gates"]), out["acceptance_routing"])


def _routed(readings, policy):
    """What the 8.0.4 copy routes: the gates and whether it owed a person's
    sign-off, or "refused"."""
    try:
        out = evaluate_route(copy.deepcopy(readings), policy)
    except RoutingConflict:
        return "refused"
    return sorted(out["gates"])


def _owed(readings, policy):
    """The sign-offs the evidence owes: `(scenario-approval, human-approval)`,
    or "refused"."""
    try:
        out = er.evaluate(copy.deepcopy(readings), policy)
    except RoutingConflict:
        return "refused"
    return ("scenario-approval" in out["evidence_required"],
            "human-approval" in out["evidence_required"])


def test_the_8_0_4_copy_routes_the_contract_1_baseline(policy_8_0_4):
    """The copy is the 8.x answer the parity test compares with: on every grid row
    and label subset it routes the 5.6.0 baseline after the bridges."""
    header, rows = cb.load_routing()
    assert cb.routing_differences(policy_8_0_4, header, rows, layered=True) == []


def _parity_differences(policy_8_0_4, live, first_only=False):
    """`(points, differences)` over every row of the contract 1 grid under every
    subset of the four `G5` labels. On each point:

    - a refusal on one side is a refusal on the other;
    - a spike has the one gate `spike.conclude` on both sides and owes no sign-off;
    - the evidence owes the three gates every issue has and no other, and the
      8.0.4 copy routed all three (ADR-099 decision 4: risk, size and urgency
      no longer add a review, so the 8.0.4 gates are a superset);
    - the evidence owes the scenario approval for critical risk or a `G5`
      label, and the `G5` sign-off for a `G5` label, as 8.x did."""
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
            owed = _owed(readings, live)
            if want == "refused" or got == "refused":
                bad = want != got or owed != "refused"
            elif got[0] == ["spike.conclude"]:
                bad = want != got[0] or owed != (False, False)
            else:
                signoff = (readings.get("risk") == "critical" or bool(labels), bool(labels))
                bad = (got[0] != THREE_GATES or not set(THREE_GATES) <= set(want)
                       or owed != signoff)
            if bad:
                differ.append(f"{readings}: 8.0.4 {want}, evidence {got}, owes {owed}")
                if first_only:
                    return points, differ
    return points, differ


def test_the_evidence_owes_what_8_0_4_required_of_a_person_on_every_grid_point(
        policy_8_0_4, live):
    """Parity: every row of the contract 1 grid (1,200 assessments) under every subset
    of the four `G5` labels (16), so 19,200 points. See `_parity_differences`."""
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
        rule, when, token = er.ADDITIONS[0]
        widened = (rule, {"risk": ["contained", "cross-cutting", "critical"]}, token)
        monkeypatch.setattr(er, "ADDITIONS", (widened,) + er.ADDITIONS[1:])
    _, differ = _parity_differences(policy_8_0_4, live, first_only=True)
    assert differ, f"planting a change in the {plant}s went unseen"
