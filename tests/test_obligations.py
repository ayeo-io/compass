"""What a resolved configuration owes an assessment: the obligations function,
the evaluator adapter and the issue-layer evaluation order.

`obligations.py` turns the merged catalogues into the input today's evaluator
takes, runs the evaluator and returns the facts the classifier will compare.
Nothing reads it yet, so these tests also replay it against today's behaviour:
the routing grid of the compatibility baseline and the archive sample's
recorded verdicts. A replay that cannot fail proves nothing, so each one is
run over a planted fault as well.

Scenario ids: `OB-1` to `OB-8` (issue `obligations`).
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

from compass_pkg.core import CompassError  # noqa: E402
from compass_pkg.routing import evaluate_route  # noqa: E402

READINGS = {"risk": "contained", "familiarity": "greenfield", "size": "small",
            "labels": []}


def _policy(stages, floors=None, ranks=None, extra_shapes=None):
    """The smallest legacy-shaped policy the evaluator accepts: one approach
    and the floors given."""
    policy = {
        "routing_strategies": {"default_route": "regular"},
        "routing_guardrails": {"floors": floors or []},
        "route_shapes": {"regular": {"weight": 2, "stages": stages, "gates": [],
                                     "artifacts": {}, "subtask_ceiling": 1}},
    }
    policy["route_shapes"].update(extra_shapes or {})
    if ranks is not None:
        policy["stage_mode_ranks"] = ranks
    return policy


def _floor(*stages):
    return [{"id": "F-1", "when": {"risk": "contained"}, "never_skip": list(stages)}]


# --- OB-2: the evaluator lifts by rank when it is given ranks --------------------

RANKS = {"refine": {"skipped": 0, "collapsed": 1, "light": 2, "full": 3,
                    "thorough": 4, "draft": 0},
         "implement": {"full": 3}}


def test_ob_2_a_floor_lifts_a_mode_whose_rank_is_below_full():
    policy = _policy({"refine": "draft", "implement": "full"}, _floor("refine"),
                     RANKS)
    # `draft` is not in the fixed set, so only the rank can lift it.
    assert evaluate_route(READINGS, policy)["stages"]["refine"] == "full"


def test_ob_2_a_floor_leaves_a_mode_of_rank_full_or_above_alone():
    for mode in ("full", "thorough"):
        policy = _policy({"refine": mode, "implement": "full"}, _floor("refine"),
                         RANKS)
        assert evaluate_route(READINGS, policy)["stages"]["refine"] == mode


def test_ob_2_a_floor_leaves_a_mode_with_no_rank_alone():
    policy = _policy({"refine": "expedited", "implement": "full"}, _floor("refine"),
                     RANKS)
    assert evaluate_route(READINGS, policy)["stages"]["refine"] == "expedited"


def test_ob_2_a_stage_the_floor_does_not_name_is_not_lifted():
    policy = _policy({"refine": "draft", "implement": "full"}, _floor("implement"),
                     RANKS)
    assert evaluate_route(READINGS, policy)["stages"]["refine"] == "draft"


def test_ob_2_a_policy_with_no_ranks_lifts_exactly_the_fixed_set():
    for mode, lifted in (("collapsed", True), ("skipped", True), ("light", True),
                         ("full", False), ("draft", False), ("expedited", False)):
        policy = _policy({"refine": mode}, _floor("refine"))
        got = evaluate_route(READINGS, policy)["stages"]["refine"]
        assert got == ("full" if lifted else mode), mode


def test_ob_2_a_stage_with_no_full_rank_is_not_lifted_by_rank():
    # Without a rank for `full` there is nothing to be below.
    policy = _policy({"refine": "draft"}, _floor("refine"),
                     {"refine": {"draft": 0}})
    assert evaluate_route(READINGS, policy)["stages"]["refine"] == "draft"


# --- the shipped preset as a resolved configuration ------------------------------

def _preset_config():
    """The committed preset files merged as one parent layer: what a loader
    will hand the obligations function once one exists."""
    import yaml
    from compass_pkg import catalogue_spec, merge
    preset = ROOT / "governance" / "presets" / "default"
    parts = []
    for name in catalogue_spec.CATALOGUES:
        part = yaml.safe_load((preset / f"{name}.yml").read_text(encoding="utf-8"))
        parts.append({k: v for k, v in part.items() if k != "schema"})
    config, _ = merge.apply({}, {"schema": 1, **merge.combine(parts)}, "parent",
                            "default")
    return config


@pytest.fixture(scope="module")
def preset_config():
    return _preset_config()


def _respelled(result):
    """A routing result with the two values the catalogues spell differently
    written their way: a document is its id (no `.md`), and a stage is its
    current name. The legacy files keep the older spelling (`intent.md`,
    `land`), and `governance/legacy-views.yml` records where."""
    from compass_pkg import core
    renames = core._stage_key_renames()
    out = copy.deepcopy(result)
    if "required_artifacts" in out:
        out["required_artifacts"] = [a[:-3] if a.endswith(".md") else a
                                     for a in out["required_artifacts"]]
    for blocked in out.get("blocked_phases") or []:
        blocked["phase"] = renames.get(blocked["phase"], blocked["phase"])
    return out


def _replay(adapted, header, rows, first_only=False):
    """Where the adapted policy routes differently from the baseline, in the
    catalogues' spelling. Grid and archive rows compare with the recorded
    result. A label row records only a digest of the legacy spelling, so it
    compares with today's policy through the same respelling."""
    from compat_baseline import compact, digest, label_subsets, shipped_policy
    found, today = [], None
    for row in rows:
        if row["kind"] in ("grid", "archive"):
            if compact(row["assessment"], adapted) != _respelled(row["result"]):
                found.append(f"{row['kind']} {row['assessment']}")
        elif row["kind"] == "label-digests":
            today = today or shipped_policy()
            for subset in label_subsets(header["labels"]):
                readings = dict(row["assessment"], labels=subset)
                if (digest(_respelled(compact(readings, adapted)))
                        != digest(_respelled(compact(readings, today)))):
                    found.append(f"labels {subset} on {row['assessment']}")
                    break
        if found and first_only:
            break
    return found


@pytest.fixture(scope="module")
def baseline():
    from compat_baseline import load_routing
    return load_routing()


def _differences_between(today, adapted, assessments, first_only=False):
    """Where two policies route differently over the same assessments."""
    from compat_baseline import compact
    found = []
    for readings in assessments:
        a, b = compact(readings, today), compact(readings, adapted)
        if a != b:
            found.append((readings, a, b))
            if first_only:
                break
    return found


# --- OB-1: the adapted preset routes the compatibility grid as today's policy ----

def test_ob_1_the_adapted_preset_routes_the_whole_baseline_as_before(preset_config,
                                                                    baseline):
    from compass_pkg import obligations
    header, rows = baseline
    adapted = obligations.policy_adapter(preset_config)
    differences = _replay(adapted, header, rows)
    assert differences == [], "\n".join(differences[:10])


def test_ob_1_the_only_spelling_the_replay_changes_is_the_two_the_catalogues_respell(
        preset_config, baseline):
    """Without the respelling, the adapted preset differs from the baseline in
    `required_artifacts` and `blocked_phases` and in nothing else, and each
    differing value is the baseline's value in the catalogues' spelling."""
    from compass_pkg import obligations
    from compat_baseline import compact
    _, rows = baseline
    adapted = obligations.policy_adapter(preset_config)
    fields = set()
    for row in rows:
        if row["kind"] not in ("grid", "archive"):
            continue
        now = compact(row["assessment"], adapted)
        old = row["result"]
        for key in set(now) | set(old):
            if now.get(key) != old.get(key):
                fields.add(key)
        assert now == _respelled(old), row["assessment"]
    assert fields == {"required_artifacts", "blocked_phases"}


def test_ob_1_a_gate_dropped_from_the_preset_breaks_the_replay(preset_config, baseline):
    from compass_pkg import obligations
    header, rows = baseline
    config = copy.deepcopy(preset_config)
    regular = config["approaches"]["regular"]
    regular["gates"] = [g for g in regular["gates"] if g != "verify.regression"]
    adapted = obligations.policy_adapter(config)
    assert _replay(adapted, header, rows, first_only=True), \
        "a dropped gate went unseen"


def test_ob_1_a_floor_dropped_from_the_preset_breaks_the_replay(preset_config, baseline):
    from compass_pkg import obligations
    header, rows = baseline
    config = copy.deepcopy(preset_config)
    del config["rules"]["floors"]["rules"]["RP-FLOOR-001"]
    adapted = obligations.policy_adapter(config)
    assert _replay(adapted, header, rows, first_only=True)


def test_ob_1_a_change_only_a_label_reaches_breaks_the_replay(preset_config, baseline):
    from compass_pkg import obligations
    header, rows = baseline
    config = copy.deepcopy(preset_config)
    config["rules"]["floors"]["rules"]["RP-FLOOR-003"]["when"] = {
        "labels_any": ["nothing-matches"]}
    adapted = obligations.policy_adapter(config)
    # No grid row carries a label, so only the label rows can see it.
    assert [d for d in _replay(adapted, header, rows, first_only=True)
            if d.startswith("labels")]


def test_ob_1_the_generated_fallback_shape_goes_back_to_the_default_route(preset_config):
    strategies = _api("policy_adapter")(preset_config)["routing_strategies"]
    assert strategies["default_route"] == "regular"
    assert "RP-SHAPE-FALLBACK" not in [r["id"] for r in strategies["default_shapes"]]
    assert [r["id"] for r in strategies["default_shapes"]] == [
        f"RP-SHAPE-00{i}" for i in range(1, 6)]


def test_ob_1_the_ranks_reach_the_evaluator(preset_config):
    from compass_pkg import obligations
    ranks = obligations.policy_adapter(preset_config)["stage_mode_ranks"]
    assert ranks["ship"] == {"light": 2, "full": 3, "full-plus-backfill": 4}
    assert "reproduce-first" not in ranks["define"]
    assert ranks["define"]["full"] == 3


def test_ob_1_a_planted_rank_on_a_mode_a_floor_reaches_breaks_the_replay(
        preset_config, baseline):
    from compass_pkg import obligations
    header, rows = baseline
    config = copy.deepcopy(preset_config)
    # `reproduce-first` carries no rank, and floor RP-FLOOR-002 names `define`.
    config["stages"]["define"]["modes"]["reproduce-first"] = {"rank": 2}
    adapted = obligations.policy_adapter(config)
    assert _replay(adapted, header, rows), \
        "a planted rank on a lifted stage went unseen"


def test_ob_1_a_planted_rank_on_expedited_is_seen_when_a_floor_names_implement(
        preset_config):
    """Today's policy has no floor on `implement`, so a rank on `expedited`
    cannot show in the baseline. With one such floor added to both paths, it
    does."""
    from compass_pkg import obligations
    from compat_baseline import shipped_policy
    today = shipped_policy()
    today["routing_guardrails"]["floors"].append(
        {"id": "RP-PLANT", "when": {"urgency": "live-defect"},
         "require_phase": "implement"})
    config = copy.deepcopy(preset_config)
    config["rules"]["floors"]["rules"]["RP-PLANT"] = {
        "order": 99, "when": {"urgency": "live-defect"},
        "then": {"require_phase": "implement"}}
    config["rules"]["floors"]["hit"]["require_phase"] = "collect"
    hotfixes = [{"risk": "contained", "familiarity": "greenfield", "size": "small",
                 "goal": "delivery", "urgency": "live-defect", "role": "engineer",
                 "labels": []}]
    assert _differences_between(today, obligations.policy_adapter(config),
                                hotfixes) == []
    config["stages"]["implement"]["modes"]["expedited"] = {"rank": 2}
    assert _differences_between(today, obligations.policy_adapter(config),
                                hotfixes, first_only=True), \
        "a planted rank on expedited went unseen"


# --- helpers for the obligations function ----------------------------------------

def _api(name):
    from compass_pkg import obligations
    assert hasattr(obligations, name), f"obligations.{name} is not defined yet"
    return getattr(obligations, name)


def _assessment(**kw):
    base = {"risk": "contained", "familiarity": "brownfield-mapped",
            "size": "standard", "goal": "delivery", "urgency": "none",
            "role": "engineer", "labels": []}
    base.update(kw)
    return base


def _layer(config, doc, kind="project"):
    from compass_pkg import merge
    return merge.apply(config, doc, kind, f"test-{kind}")[0]


def _with_entry_lists(config):
    """The preset plus what a project can add: a human check, a judged check,
    an entry list and an exit list, and a gate that holds one of them."""
    return _layer(config, {
        "schema": 1,
        "checks": {
            "design-reviewed": {
                "statement": "A person read the design.", "kind": "human",
                "severity": "blocking", "on_skipped": "fail",
                "approvers": ["lead"], "inputs": ["technical-design"]},
            "plain-english": {
                "statement": "The text reads plainly.", "kind": "judged",
                "severity": "advisory", "on_skipped": "pass",
                "reviewers": ["editor", "peer"], "accepts": ["manual-review"]},
        },
        "stages": {"plan": {"set": {"entry": ["design-reviewed"],
                                    "exit": ["plain-english"]}}},
        "gates": {"verify.clarity": {"set": {"checks": ["plain-english"]}}},
    })


# --- OB-3: the facts, and the table that names them ------------------------------

def test_ob_3_every_compared_field_is_a_fact_or_a_lock_footprint():
    from compass_pkg.catalogue_spec import OBLIGATION_FIELDS
    produced = _api("FACT_FOR_FIELD")
    footprints = _api("FOOTPRINT_ONLY")
    assert set(produced) | set(footprints) == set(OBLIGATION_FIELDS)
    assert not set(produced) & set(footprints)
    facts = {f.name for f in __import__("dataclasses").fields(_api("Obligations"))}
    assert set(produced.values()) <= facts, set(produced.values()) - facts


def test_ob_3_the_facts_equal_the_evaluators_answers(preset_config):
    obligations = _api("obligations")
    adapted = _api("policy_adapter")(preset_config)
    cases = [
        _assessment(),
        _assessment(risk="critical", size="large", labels=["auth", "migrations"]),
        _assessment(size="atomic", risk="trivial", urgency="live-defect"),
        _assessment(role="product-marketer"),
        _assessment(role="product-owner", familiarity="brownfield-unmapped"),
        _assessment(goal="exploration", size="small", risk="trivial"),
    ]
    for case in cases:
        got = obligations(preset_config, case)
        assert not isinstance(got, _api("Refused")), (case, got)
        by_level = {level: evaluate_route(copy.deepcopy(case), adapted, autonomy=level)
                    for level in ("controlled", "balanced", "autonomous")}
        r = by_level["balanced"]
        assert got.approach == r["delivery_approach"]
        assert got.stage_mode == r["stages"]
        review = {g for g, body in preset_config["gates"].items()
                  if body["kind"] == "review"}
        assert set(got.gate_set) & review == set(r["gates"]), case
        assert got.artifacts_owed == {a["kind"]: a["depth"] for a in r["artifacts"]}
        assert list(got.required_skills) == sorted(r["required_skills"])
        assert set(got.blocked_stages) == {b["phase"] for b in r["blocked_phases"]}
        assert got.checkpoints == {lv: tuple(x["checkpoints"])
                                   for lv, x in by_level.items()}
        assert got.ceilings["subtask_ceiling"] == r["subtask_ceiling"]
        assert got.ceilings["max_worktrees"] == r["max_worktrees"]


def test_ob_3_a_critical_change_owes_what_the_policy_says(preset_config):
    got = _api("obligations")(preset_config, _assessment(risk="critical"))
    assert got.approach == "full"
    assert got.stage_mode["refine"] == "full"
    assert {"verify.analyze", "verify.architecture"} <= set(got.gate_set)
    assert got.ceilings["max_worktrees"] == 1
    assert got.ceilings["subtask_ceiling"] == 1


def test_ob_3_the_guardrails_are_in_the_gate_set(preset_config):
    got = _api("obligations")(preset_config, _assessment())
    assert {"G1", "G2", "G3", "G4"} <= set(got.gate_set)
    assert "G5" not in got.gate_set          # no label, risk below critical
    assert "S1" not in got.gate_set          # a spike guardrail
    assert got.gate_checks["G2"] == ("scenario-has-id-and-intent",)
    assert got.gate_accepts["verify.correctness"] == ("test-run",)


def test_ob_3_the_human_signoff_gate_applies_to_a_domain_label(preset_config):
    got = _api("obligations")(preset_config, _assessment(labels=["payments"]))
    assert "G5" in got.gate_set
    assert "human-approval-present" in got.checks


def test_ob_3_a_spike_owes_only_its_own_guardrails(preset_config):
    got = _api("obligations")(
        preset_config, _assessment(goal="exploration", size="small", risk="trivial"))
    assert got.approach == "spike"
    assert "S1" in got.gate_set and "G1" not in got.gate_set
    assert got.artifacts_owed == {}


def test_ob_3_loop_ceilings_equal_the_lowest_matching_limit(preset_config):
    """The same answer `loop_ceilings.loop_ceilings` gives from the policy
    file, at every assessment of the grid."""
    from compass_pkg.loop_ceilings import loop_ceilings
    obligations = _api("obligations")
    from compat_baseline import grid, shipped_policy
    vocabulary = shipped_policy()["assessment_vocabulary"]
    names = ("builder_attempts", "review_rounds", "replans", "repeated_error",
             "run_cycles", "run_minutes", "run_cost_usd")
    seen = set()
    for readings in grid(vocabulary):
        got = obligations(preset_config, readings)
        if isinstance(got, _api("Refused")):
            continue
        expected = {n: lim for n, (lim, _) in
                    loop_ceilings({"assessment": readings}).items()}
        actual = {n: got.ceilings[n] for n in names if got.ceilings.get(n) is not None}
        assert actual == expected, readings
        seen.add(tuple(sorted(expected.items())))
    assert len(seen) > 1, "the ceilings never varied, so the replay saw one case"


def test_ob_3_entry_exit_gate_and_check_facts(preset_config):
    config = _with_entry_lists(preset_config)
    got = _api("obligations")(config, _assessment())
    assert got.entry["plan"] == ("design-reviewed",)
    assert got.exit["plan"] == ("plain-english",)
    assert got.entry["define"] == () and got.exit["define"] == ()
    assert got.gate_checks["verify.clarity"] == ("plain-english",)
    human = got.checks["design-reviewed"]
    assert human == {"kind": "human", "impl": None, "params": {}, "accepts": [],
                     "reviewers": [], "approvers": ["lead"],
                     "inputs": ["technical-design"], "severity": "blocking",
                     "on_skipped": "fail", "statement": "A person read the design."}
    judged = got.checks["plain-english"]
    assert judged["reviewers"] == ["editor", "peer"]
    assert judged["accepts"] == ["manual-review"]
    assert judged["statement"] == "The text reads plainly."
    assert "statement" not in got.checks["suite-passed"]


def _with_artifact_links(config):
    config = _with_entry_lists(config)
    return _layer(config, {"schema": 1, "artifacts": {"technical-design": {"set": {
        "depends_on": ["acceptance-criteria"], "checks": ["design-reviewed"]}}}})


def test_ob_3_the_artifact_catalogue_adds_its_links_as_facts(preset_config):
    from compass_pkg.catalogue_spec import OBLIGATION_FIELDS
    assert OBLIGATION_FIELDS["artifacts.depends_on"] == "obligation-set"
    assert OBLIGATION_FIELDS["artifacts.checks"] == "obligation-set"
    assert _api("FACT_FOR_FIELD")["artifacts.depends_on"] == "artifact_depends_on"
    assert _api("FACT_FOR_FIELD")["artifacts.checks"] == "artifact_checks"
    config = _with_artifact_links(preset_config)
    got = _api("obligations")(config, _assessment())
    assert got.artifact_depends_on["technical-design"] == ("acceptance-criteria",)
    assert got.artifact_checks["technical-design"] == ("design-reviewed",)
    assert got.artifact_checks["acceptance-criteria"] == ()
    assert set(got.artifact_checks) == set(got.artifacts_owed)


def test_ob_3_detaching_a_check_from_an_artifact_shows(preset_config):
    obligations = _api("obligations")
    config = _with_artifact_links(preset_config)
    detached = _layer(config, {"schema": 1, "artifacts": {"technical-design": {
        "set": {"checks": []}}}})
    before = obligations(config, _assessment()).compared()
    after = obligations(detached, _assessment()).compared()
    assert before["artifact_checks"] != after["artifact_checks"]
    # The check is no longer listed anywhere, since nothing else names it.
    assert "design-reviewed" in before["checks"]


def test_ob_3_the_checks_an_artifact_adds_are_listed(preset_config):
    """A check only an artifact names is still a check the configuration owes."""
    config = _layer(preset_config, {"schema": 1, "checks": {"artifact-only": {
        "statement": "x", "kind": "human", "severity": "blocking",
        "on_skipped": "fail"}}, "artifacts": {"technical-design": {
            "set": {"checks": ["artifact-only"]}}}})
    got = _api("obligations")(config, _assessment())
    assert "artifact-only" in got.checks
    assert all("artifact-only" not in ids for ids in got.gate_checks.values())
    assert all("artifact-only" not in ids for ids in got.entry.values())


def test_ob_3_required_artifacts_equal_the_evaluators_answer(preset_config):
    adapted = _api("policy_adapter")(preset_config)
    for role, expected in (("product-owner", ("intent",)),
                           ("product-marketer", ("launch-readiness",)),
                           ("engineer", ())):
        case = _assessment(role=role)
        got = _api("obligations")(preset_config, case)
        legacy = evaluate_route(case, adapted)["required_artifacts"]
        assert got.required_artifacts == tuple(sorted(
            a[:-3] if a.endswith(".md") else a for a in legacy)) == expected


def test_ob_3_a_legacy_document_name_with_a_suffix_is_its_id(preset_config):
    config = copy.deepcopy(preset_config)
    config["rules"]["role_rules"]["rules"]["RP-ROLE-002"]["then"][
        "require_artifact"] = "intent.md"
    got = _api("obligations")(config, _assessment(role="product-owner"))
    assert got.required_artifacts == ("intent",)


def test_ob_3_the_replays_spelling_follows_cores_tables_and_the_adapters_rule(
        monkeypatch):
    from compass_pkg import core, legacy_adapter, obligations
    table = core._stage_key_renames()
    assert table, "core holds no retired stage name"
    for old, new in table.items():
        assert _respelled({"blocked_phases": [{"phase": old}]})[
            "blocked_phases"][0]["phase"] == new
    # A name added to core's table is read through at once: the replay holds no copy.
    monkeypatch.setattr(core, "_stage_key_renames",
                        lambda: dict(table, **{"zz-retired": "zz-current"}))
    assert _respelled({"blocked_phases": [{"phase": "zz-retired"}]})[
        "blocked_phases"][0]["phase"] == "zz-current"
    for name in ("intent.md", "intent", "a.md.md", "md", ""):
        assert _respelled({"required_artifacts": [name]})["required_artifacts"][0] \
            == obligations._artifact_id(name) == legacy_adapter._artifact_id(name)


def test_ob_3_the_same_refusal_from_two_layerings_has_the_same_reason(preset_config):
    obligations = _api("obligations")
    other = _layer(preset_config, {"schema": 1, "checks": {"extra": {
        "statement": "x", "kind": "human", "severity": "advisory",
        "on_skipped": "pass"}}}, "parent")
    other = _layer(other, {"schema": 1, "checks": {"extra2": {
        "statement": "y", "kind": "human", "severity": "advisory",
        "on_skipped": "pass"}}}, "project")
    case = _assessment(goal="exploration", risk="critical")
    one, two = obligations(preset_config, case), obligations(other, case)
    assert isinstance(one, _api("Refused")) and one.reason == two.reason
    for word in ("test-parent", "test-project", ".yml", "/"):
        assert word not in one.reason.replace("and/or", "")


def test_ob_3_compared_leaves_out_the_outcomes(preset_config):
    got = _api("obligations")(preset_config, _assessment(risk="critical"))
    compared = got.compared()
    assert "approach" not in compared and "rules_fired" not in compared
    assert set(compared) == set(_api("FACT_FOR_FIELD").values())


# --- OB-4: a refusal is an outcome ------------------------------------------------

def test_ob_4_a_spike_that_a_floor_would_deliver_is_refused(preset_config):
    refused = _api("Refused")
    got = _api("obligations")(
        preset_config, _assessment(goal="exploration", risk="critical"))
    assert isinstance(got, refused)
    assert got.reason.startswith("routing conflict - exploration cannot silently "
                                 "become delivery.")
    # Today's evaluator says the same through the same input.
    adapted = _api("policy_adapter")(preset_config)
    with pytest.raises(CompassError) as exc:
        evaluate_route(_assessment(goal="exploration", risk="critical"), adapted)
    assert got.reason == str(exc.value)


def test_ob_4_a_forbidden_approach_is_refused(preset_config):
    config = _layer(preset_config, {"schema": 1, "rules": {"caps": {"set": {"rules": {
        "set": {"RP-PLANT-CAP": {"order": 9, "when": {"risk": "cross-cutting"},
                                 "then": {"forbid_approach": "regular"}}}}}}}})
    got = _api("obligations")(config, _assessment(risk="cross-cutting"))
    assert isinstance(got, _api("Refused"))
    assert "is forbidden by a cap" in got.reason
    assert not isinstance(_api("obligations")(config, _assessment(risk="contained")),
                          _api("Refused"))


def test_ob_4_two_refusals_with_one_reason_are_equal(preset_config):
    obligations = _api("obligations")
    one = obligations(preset_config, _assessment(goal="exploration", risk="critical"))
    two = obligations(preset_config, _assessment(goal="exploration", risk="critical",
                                                 labels=["auth"]))
    other = _api("Refused")("another reason")
    assert one == _api("Refused")(one.reason)
    assert one != other and two != other


def test_ob_4_the_refused_points_of_the_grid_are_the_baseline_errors(preset_config,
                                                                    baseline):
    obligations = _api("obligations")
    _, rows = baseline
    grid_rows = [r for r in rows if r["kind"] == "grid"]
    errors = {json_key(r["assessment"]): r["result"]["error"]
              for r in grid_rows if "error" in r["result"]}
    assert errors, "the baseline has no refusal, so there is nothing to count"
    refused = {}
    for row in grid_rows:
        got = obligations(preset_config, row["assessment"])
        if isinstance(got, _api("Refused")):
            refused[json_key(row["assessment"])] = got.reason
    assert refused == errors


def json_key(assessment):
    import json
    return json.dumps(assessment, sort_keys=True)


def test_ob_4_a_fault_in_the_configuration_is_not_a_refusal(preset_config):
    config = copy.deepcopy(preset_config)
    config["stages"]["plan"]["entry"] = ["no-such-check"]
    with pytest.raises(CompassError, match="no-such-check"):
        _api("obligations")(config, _assessment())
    config = copy.deepcopy(preset_config)
    config["approaches"]["regular"]["extends"] = "full"
    config["approaches"]["full"]["extends"] = "regular"
    with pytest.raises(CompassError, match="cycle"):
        _api("obligations")(config, _assessment())


# --- OB-6: which checks and gates are in force ------------------------------------

def _checks_config(preset_config):
    return _layer(preset_config, {
        "schema": 1,
        "checks": {
            "needs-switch": {"statement": "x", "kind": "deterministic",
                             "impl": "suite-passed", "severity": "blocking",
                             "on_skipped": "fail",
                             "requires": ["entry-exit-evaluation"]},
            "only-critical": {"statement": "x", "kind": "deterministic",
                              "impl": "suite-passed", "severity": "blocking",
                              "on_skipped": "fail", "when": {"risk": "critical"}},
            "threshold": {"statement": "x", "kind": "deterministic",
                          "impl": "suite-passed", "severity": "blocking",
                          "on_skipped": "fail",
                          "blocking_when": {"risk": {"at_least": "cross-cutting"}}},
        },
        "stages": {"plan": {"set": {"entry": ["needs-switch", "only-critical",
                                              "threshold"]}}},
    })


def test_ob_6_a_check_that_requires_a_switch_is_active_only_with_it(preset_config):
    config = _checks_config(preset_config)
    obligations = _api("obligations")
    assert "needs-switch" not in obligations(config, _assessment()).entry["plan"]
    on = obligations(config, _assessment(), capabilities=("entry-exit-evaluation",))
    assert "needs-switch" in on.entry["plan"] and "needs-switch" in on.checks


def test_ob_6_a_check_with_a_when_is_active_only_where_it_matches(preset_config):
    config = _checks_config(preset_config)
    obligations = _api("obligations")
    assert "only-critical" not in obligations(config, _assessment()).entry["plan"]
    critical = obligations(config, _assessment(risk="critical"))
    assert "only-critical" in critical.entry["plan"]


def test_ob_6_severity_is_advisory_where_blocking_when_does_not_match(preset_config):
    config = _checks_config(preset_config)
    obligations = _api("obligations")
    low = obligations(config, _assessment(risk="contained"))
    high = obligations(config, _assessment(risk="cross-cutting"))
    assert low.checks["threshold"]["severity"] == "advisory"
    assert high.checks["threshold"]["severity"] == "blocking"


def test_ob_6_a_check_that_blocks_for_some_assessments_only_shows_it(preset_config):
    """`scenarios-are-executable` blocks from cross-cutting risk upwards, as
    `compass check` reads it today."""
    obligations = _api("obligations")
    low = obligations(preset_config, _assessment(risk="contained"))
    high = obligations(preset_config, _assessment(risk="cross-cutting"))
    assert low.checks["scenarios-are-executable"]["severity"] == "advisory"
    assert high.checks["scenarios-are-executable"]["severity"] == "blocking"


def test_ob_6_a_guardrail_gate_follows_applies_to_and_when(preset_config):
    obligations = _api("obligations")
    delivery = obligations(preset_config, _assessment())
    spike = obligations(preset_config, _assessment(goal="exploration", risk="trivial",
                                                   size="small"))
    assert "G1" in delivery.gate_set and "S1" not in delivery.gate_set
    assert "S1" in spike.gate_set and "G1" not in spike.gate_set
    assert "G5" not in delivery.gate_set
    assert "G5" in obligations(preset_config, _assessment(risk="critical")).gate_set


def test_ob_6_statement_is_compared_for_human_and_judged_checks_only(preset_config):
    config = _with_entry_lists(preset_config)
    got = _api("obligations")(config, _assessment())
    assert "statement" in got.checks["design-reviewed"]
    assert "statement" in got.checks["plain-english"]
    assert "statement" not in got.checks["suite-passed"]


# --- OB-5: the issue layer ---------------------------------------------------------

def _issue(config, **doc):
    """`(config with the issue layer merged, the layer document)`: the stage
    modes travel in the merged catalogues, the approach and the ceilings in
    the document, which the merge cannot carry."""
    stages = {s: {"set": {"mode": m}} for s, m in doc.pop("modes", {}).items()}
    layer = dict(doc, **({"stages": stages} if stages else {}))
    return _layer(config, {"schema": 1, **{k: v for k, v in layer.items()
                                           if k == "stages"}}, "issue"), layer


def _owed(config, assessment, layer=None, **kw):
    return _api("obligations")(config, assessment, issue=layer, **kw)


SMALL = dict(size="small", risk="trivial")


def test_ob_5_the_issue_names_the_candidate(preset_config):
    config, layer = _issue(preset_config, approach="regular")
    assert _owed(preset_config, _assessment(**SMALL)).approach == "quick-fix"
    got = _owed(config, _assessment(**SMALL), layer)
    assert got.approach == "regular"
    assert got.stage_mode["plan"] == "full"


def test_ob_5_without_an_issue_approach_the_first_matching_shape_is_the_candidate(
        preset_config):
    config, layer = _issue(preset_config, modes={"refine": "light"})
    assert _owed(config, _assessment(**SMALL), layer).approach == "quick-fix"


def test_ob_5_the_issue_changes_a_base_mode(preset_config):
    config, layer = _issue(preset_config, modes={"refine": "light"})
    got = _owed(config, _assessment(**SMALL), layer)
    assert got.stage_mode["refine"] == "light"       # quick-fix has `collapsed`
    assert got.stage_mode["plan"] == "collapsed"     # the rest is untouched


def test_ob_5_a_floor_lifts_a_mode_the_issue_lowered(preset_config):
    """RP-FLOOR-002 names `define` for unmapped ground, so a lowered `define`
    is lifted back. The issue needs no waiver there: it has no effect."""
    config, layer = _issue(preset_config, modes={"define": "collapsed"})
    unmapped = _assessment(familiarity="brownfield-unmapped")
    assert _owed(config, unmapped, layer).stage_mode["define"] == "full"
    assert _owed(config, _assessment(), layer).stage_mode["define"] == "collapsed"


def test_ob_5_a_floor_that_names_another_stage_leaves_the_override_standing(
        preset_config):
    config, layer = _issue(preset_config, modes={"refine": "skipped"})
    unmapped = _assessment(familiarity="brownfield-unmapped")
    assert _owed(config, unmapped, layer).stage_mode["refine"] == "skipped"


def test_ob_5_an_override_on_an_approach_a_floor_replaced_is_ignored(preset_config):
    """Critical risk raises the approach to `full`, which has its own base
    modes. The override was on the candidate's, so it is reported and dropped."""
    config, layer = _issue(preset_config, modes={"breakdown": "skipped"})
    got = _owed(config, _assessment(risk="critical"), layer)
    assert got.approach == "full"
    assert got.stage_mode["breakdown"] == "multiagent"
    assert got.ignored_overrides == {"breakdown": "skipped"}
    assert _owed(config, _assessment(), layer).ignored_overrides == {}


def test_ob_5_an_issue_can_set_a_stage_of_the_approach_it_names(preset_config):
    config, layer = _issue(preset_config, modes={"breakdown": "skipped"},
                           approach="spike")
    got = _owed(config, _assessment(goal="exploration", **SMALL), layer)
    assert got.stage_mode["breakdown"] == "skipped"        # the spike has it


def test_ob_5_an_issue_spike_that_a_floor_would_deliver_is_refused(preset_config):
    config, layer = _issue(preset_config, approach="spike")
    got = _owed(config, _assessment(risk="critical"), layer)
    assert isinstance(got, _api("Refused"))


def test_ob_5_an_issue_can_lower_the_subtask_ceiling_and_never_raise_it(preset_config):
    """Floors and caps win over the issue layer, so the issue's value is a
    minimum with the approach's own ceiling, as a loop ceiling is."""
    config, layer = _issue(preset_config, ceilings={"subtask_ceiling": 4})
    assert _owed(config, _assessment(), layer).ceilings["subtask_ceiling"] == 2
    assert _owed(config, _assessment(**SMALL), layer).ceilings["subtask_ceiling"] == 1
    assert _owed(config, _assessment(risk="critical"), layer) \
        .ceilings["subtask_ceiling"] == 1               # RP-CAP-001
    # `full` has no ceiling at all, so the issue's value is the only one.
    assert _owed(config, _assessment(size="large"), layer) \
        .ceilings["subtask_ceiling"] == 4
    config, layer = _issue(preset_config, ceilings={"subtask_ceiling": 1})
    assert _owed(config, _assessment(), layer).ceilings["subtask_ceiling"] == 1


def test_ob_5_the_evaluator_lowers_a_subtask_ceiling_for_an_issue_and_never_raises_it():
    policy = _policy({"refine": "light"})
    assert evaluate_route(READINGS, policy, issue={"subtask_ceiling": 5}
                          )["subtask_ceiling"] == 1
    policy["route_shapes"]["regular"]["subtask_ceiling"] = 3
    assert evaluate_route(READINGS, policy, issue={"subtask_ceiling": 2}
                          )["subtask_ceiling"] == 2
    policy["route_shapes"]["regular"]["subtask_ceiling"] = None
    assert evaluate_route(READINGS, policy, issue={"subtask_ceiling": 2}
                          )["subtask_ceiling"] == 2


def test_ob_5_an_issue_can_lower_a_loop_ceiling_and_not_raise_it(preset_config):
    lower, layer = _issue(preset_config, ceilings={"review_rounds": 1})
    assert _owed(lower, _assessment(), layer).ceilings["review_rounds"] == 1
    higher, layer = _issue(preset_config, ceilings={"review_rounds": 9})
    # RP-LOOP-002 sets 3, and RP-LOOP-003 lowers it to 2 below cross-cutting.
    assert _owed(higher, _assessment(risk="cross-cutting"), layer) \
        .ceilings["review_rounds"] == 3
    assert _owed(higher, _assessment(), layer).ceilings["review_rounds"] == 2


def test_ob_5_an_empty_issue_layer_changes_nothing(preset_config):
    assessment = _assessment(risk="critical", labels=["auth"])
    assert _owed(preset_config, assessment, {}) == _owed(preset_config, assessment)


def test_ob_5_a_fault_in_the_issue_layer_raises(preset_config):
    config, layer = _issue(preset_config, modes={"refine": "no-such-mode"})
    with pytest.raises(CompassError, match="no-such-mode"):
        _owed(config, _assessment(), layer)
    config, layer = _issue(preset_config, approach="no-such-approach")
    with pytest.raises(CompassError, match="no-such-approach"):
        _owed(config, _assessment(), layer)
    config, layer = _issue(preset_config, ceilings={"no_such_ceiling": 2})
    with pytest.raises(CompassError, match="no_such_ceiling"):
        _owed(config, _assessment(), layer)
    config, layer = _issue(preset_config, ceilings={"review_rounds": 0})
    with pytest.raises(CompassError, match="review_rounds"):
        _owed(config, _assessment(), layer)


def _fault(call):
    """The message of the `CompassError` the call raises. Any other outcome,
    including another kind of error, fails the test."""
    try:
        call()
    except Exception as exc:                     # noqa: BLE001
        assert isinstance(exc, CompassError), f"{type(exc).__name__}: {exc}"
        return str(exc)
    raise AssertionError("no error was raised")


def test_ob_5_a_malformed_issue_layer_raises_a_compass_error(preset_config):
    for layer in ({"ceilings": [1]}, {"ceilings": "3"}, "full", ["approach"],
                  {"approach": ["regular"]}, {"stages": 3}):
        _fault(lambda layer=layer: _owed(preset_config, _assessment(), layer))


def test_ob_5_an_issue_key_nobody_defines_is_refused_by_name(preset_config):
    assert "route" in _fault(lambda: _owed(preset_config, _assessment(),
                                           {"route": "full"}))


def test_ob_5_an_issue_may_carry_the_keys_the_catalogue_spec_allows(preset_config):
    from compass_pkg.catalogue_spec import ISSUE_KEYS
    assert "route" not in ISSUE_KEYS
    got = _owed(preset_config, _assessment(), {"autonomy": "controlled"})
    assert got == _owed(preset_config, _assessment())


def test_ob_5_an_old_approach_name_is_read_as_the_current_one(preset_config):
    from compass_pkg.core import canonical_shape
    assert canonical_shape("feature") == "regular"
    config, layer = _issue(preset_config, approach="feature")
    assert _owed(config, _assessment(**SMALL), layer).approach == "regular"


def test_ob_5_an_approach_nobody_defines_raises_even_where_a_floor_would_hide_it(
        preset_config):
    """At critical risk the evaluator alone raises the unknown approach to
    `full` and answers; the faulty layer must still be reported."""
    config, layer = _issue(preset_config, approach="ghost")
    assert "ghost" in _fault(lambda: _owed(config, _assessment(risk="critical"), layer))
    assert evaluate_route(_assessment(risk="critical"),
                          _api("policy_adapter")(config),
                          issue={"approach": "ghost"})["delivery_approach"] == "full"


def test_ob_5_an_issue_autonomy_changes_no_fact(preset_config):
    """The caller applies it: checkpoints come back for every value asked for."""
    plain = _owed(preset_config, _assessment())
    for level in ("controlled", "balanced", "autonomous"):
        assert _owed(preset_config, _assessment(), {"autonomy": level}) == plain
    assert set(plain.checkpoints) == {"controlled", "balanced", "autonomous"}


def test_ob_5_a_mode_ranked_equal_to_full_is_not_lifted():
    ranks = {"refine": {"full": 3, "equal": 3, "light": 2}}
    policy = _policy({"refine": "equal"}, _floor("refine"), ranks)
    assert evaluate_route(READINGS, policy)["stages"]["refine"] == "equal"


def test_ob_5_a_skipped_stage_still_lists_its_active_checks(preset_config):
    config = _layer(_with_entry_lists(preset_config), {
        "schema": 1, "stages": {"refine": {"set": {"entry": ["design-reviewed"]}}}})
    config, layer = _issue(config, modes={"refine": "skipped"})
    got = _owed(config, _assessment(), layer)
    assert got.stage_mode["refine"] == "skipped"
    assert got.entry["refine"] == ("design-reviewed",)
    assert "design-reviewed" in got.checks


def test_ob_5_a_retired_stage_name_in_a_policy_is_read_as_the_current_one(
        preset_config):
    config = copy.deepcopy(preset_config)
    config["rules"]["role_rules"]["rules"]["RP-ROLE-001"]["then"]["block_phase"] = "land"
    got = _owed(config, _assessment(role="product-marketer"))
    assert got.blocked_stages == ("ship",)


def test_ob_5_the_evaluator_reports_what_it_applied_and_ignored():
    policy = _policy({"refine": "light", "implement": "full"}, _floor("refine"))
    out = evaluate_route(READINGS, policy, issue={
        "stage_modes": {"implement": "expedited", "ship": "light"}})
    assert out["stages"]["implement"] == "expedited"
    assert out["issue_overrides"] == {"applied": {"implement": "expedited"},
                                      "ignored": {"ship": "light"}}
    # A call with no issue input has no such key, as before.
    assert "issue_overrides" not in evaluate_route(READINGS, policy)


# --- OB-7: on_skipped against today's verdicts -------------------------------------

def _recorded_verdicts():
    import json

    from compat_baseline import ARCHIVE
    return json.loads(ARCHIVE.read_text(encoding="utf-8"))["issues"]


def _replay_on_skipped(config, recorded):
    """`(issue, check, today, obligation path)` for each check that stood
    down in the archive sample where the obligation path says something else.
    A check that stood down reported `nothing-to-check`; the path says what
    `on_skipped` makes of that."""
    skipped_verdict = _api("skipped_verdict")
    found = []
    for slug, result in sorted(recorded.items()):
        for name, status in sorted(result["verdicts"].items()):
            check = (config.get("checks") or {}).get(name)
            if status == "nothing-to-check" and check is not None:
                if skipped_verdict(check) != status:
                    found.append((slug, name, status, skipped_verdict(check)))
    return found


def test_ob_7_skipped_verdict_says_what_on_skipped_means(preset_config):
    skipped_verdict = _api("skipped_verdict")
    assert skipped_verdict({"on_skipped": "pass"}) == "pass"
    assert skipped_verdict({"on_skipped": "not-applicable"}) == "nothing-to-check"
    assert skipped_verdict({"on_skipped": "fail"}) == "fail"
    with pytest.raises(CompassError, match="on_skipped"):
        skipped_verdict({"on_skipped": "maybe"})


def test_ob_7_the_sample_has_every_check_that_declines(preset_config):
    """The replay is only as strong as what the sample exercises: every check
    the preset marks `not-applicable` must have stood down at least once."""
    recorded = _recorded_verdicts()
    stood_down = {name for r in recorded.values()
                  for name, status in r["verdicts"].items()
                  if status == "nothing-to-check"}
    from compass_pkg.legacy_views import has_implementation
    # `compass check` runs only checks with an implementation; the human Ready
    # checks never run on the sample, so they cannot stand down there.
    declining = {n for n, c in preset_config["checks"].items()
                 if c["on_skipped"] == "not-applicable" and has_implementation(c)}
    assert declining <= stood_down, declining - stood_down


def test_ob_7_the_only_differences_on_the_sample_are_the_landed_by_relaxations(
        preset_config):
    from archive import sample_root
    import yaml
    from compass_pkg.landed_by import LANDED_BY_RELAXES
    recorded = _recorded_verdicts()
    found = _replay_on_skipped(preset_config, recorded)
    assert found, "the replay found nothing to compare"
    work = sample_root() / ".compass" / "work"
    pointed = {slug for slug in recorded
               if yaml.safe_load((work / slug / "manifest.yml").read_text(
                   encoding="utf-8")).get("landed_by")}
    assert pointed, "no sampled issue carries a landed_by pointer"
    assert {name for _, name, _, _ in found} == {
        "scenarios-have-tests", "suite-passed", "scenario-has-id-and-intent",
        "gate-evidence-present"}
    assert len(found) == 16
    assert {(slug, name) for slug, name, _, _ in found} == {
        (slug, name) for slug in pointed for name in LANDED_BY_RELAXES
        if recorded[slug]["verdicts"].get(name) == "nothing-to-check"}
    # Today's `compass check` stands these four checks down because of the
    # pointer; the preset says `fail` for a check with nothing to check.
    assert {today for _, _, today, _ in found} == {"nothing-to-check"}
    assert {path for _, _, _, path in found} == {"fail"}


def _empty_issue_verdicts():
    """What each registered check says of an issue with nothing in it."""
    import os
    import tempfile

    import yaml
    from compass_pkg import check_registry
    from check_corpus_runner import verdict
    root = Path(tempfile.mkdtemp())
    task_dir = root / ".compass" / "work" / "empty"
    (task_dir / "evidence").mkdir(parents=True)
    manifest = {"schema_version": "2.0", "issue": "empty", "task": "empty",
                "status": "active", "delivery_approach": "quick-fix",
                "assessment": {"risk": "contained", "familiarity": "greenfield",
                               "size": "small", "goal": "delivery",
                               "role": "engineer", "labels": []},
                "gates": [], "scenarios": [], "changed_files": [], "evidence": [],
                "claims": []}
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
    here = os.getcwd()
    os.chdir(root)
    try:
        return {name: verdict(entry.fn(manifest, str(task_dir)))
                for name, entry in check_registry.REGISTRY.items()}
    finally:
        os.chdir(here)


# Checks an empty issue passes without declining. Their `on_skipped` is `fail`,
# the strictest value, and it can never apply while they never report
# nothing-to-check. A check that starts to decline is reported here and keeps
# `fail`. That an empty issue passes them is a defect in the checks, not in the
# preset, and is filed apart from this issue.
PASS_WHEN_EMPTY = {"backfills-paid", "changed-code-traces-to-scenario",
                "consistency-check-passes", "dod-evidence-typed",
                "no-trusted-rerun", "spike-no-production-changes"}


def test_ob_7_on_an_empty_issue_each_check_says_what_on_skipped_says(preset_config):
    from compass_pkg.legacy_views import has_implementation
    skipped_verdict = _api("skipped_verdict")
    today = _empty_issue_verdicts()
    # Only a check with an implementation runs on an empty issue; the human
    # Ready and Done checks have none, and their capability is off.
    checks = {name: check for name, check in preset_config["checks"].items()
              if has_implementation(check)}
    assert set(today) == set(checks)
    for name, status in today.items():
        path = skipped_verdict(checks[name])
        if status == "nothing-to-check":
            assert path == "nothing-to-check", name
        elif name in PASS_WHEN_EMPTY:
            assert status == "pass" and path == "fail", name
        else:
            assert path == status, name
    declined = {n for n, s in today.items() if s == "nothing-to-check"}
    assert declined == {n for n, c in checks.items()
                        if c["on_skipped"] == "not-applicable"}


def test_ob_7_a_planted_on_skipped_breaks_the_replays(preset_config):
    # A check that declines, marked as one that fails.
    config = copy.deepcopy(preset_config)
    config["checks"]["scenarios-are-executable"]["on_skipped"] = "fail"
    assert ("scenarios-are-executable" in
            {name for _, name, _, _ in _replay_on_skipped(config, _recorded_verdicts())})
    # A check that does not decline, marked as one that does.
    config = copy.deepcopy(preset_config)
    config["checks"]["suite-passed"]["on_skipped"] = "not-applicable"
    today, skipped_verdict = _empty_issue_verdicts(), _api("skipped_verdict")
    assert today["suite-passed"] != "nothing-to-check"
    assert skipped_verdict(config["checks"]["suite-passed"]) == "nothing-to-check"


# --- OB-8: nothing else changes -----------------------------------------------------

EVALUATOR_KEYS = {
    "renamed_routes", "candidate_route", "candidate_via", "delivery_approach",
    "policy_rules_fired", "stages", "gates", "artifacts", "subtask_ceiling",
    "required_artifacts", "required_skills", "blocked_phases", "max_worktrees",
    "applicable_strategies", "checkpoints"}


def test_ob_8_the_evaluator_called_as_before_returns_the_same_keys():
    from compat_baseline import shipped_policy
    out = evaluate_route(_assessment(), shipped_policy())
    assert set(out) == EVALUATOR_KEYS
    assert set(evaluate_route(_assessment(), shipped_policy(), "controlled")) \
        == EVALUATOR_KEYS


def test_ob_8_an_empty_issue_input_is_no_issue_input():
    from compat_baseline import shipped_policy
    assert evaluate_route(_assessment(), shipped_policy(), issue={}) \
        == evaluate_route(_assessment(), shipped_policy())


def test_ob_8_the_command_answers_as_before(tmp_path):
    import json
    import subprocess
    out = subprocess.run(
        [sys.executable, str(ROOT / "cli" / "compass"), "approach", "evaluate",
         "--json", "--assessment", "risk=trivial", "--assessment",
         "familiarity=greenfield", "--assessment", "size=small"],
        cwd=tmp_path, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    answer = json.loads(out.stdout)
    assert answer["delivery_approach"] == "quick-fix"
    assert "issue_overrides" not in answer


def _obligations_importers(paths):
    """The files among `paths` that import `obligations` in any form: `from
    compass_pkg import obligations`, with other names or in a parenthesised list,
    `from compass_pkg.obligations import x`, and `import compass_pkg.obligations`."""
    import ast
    found = []
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.ImportFrom):
                if node.module == "compass_pkg":
                    names = [a.name for a in node.names]
                elif node.module == "compass_pkg.obligations":
                    names = ["obligations"]
            elif isinstance(node, ast.Import):
                names = [a.name.rsplit(".", 1)[-1] for a in node.names
                         if a.name.startswith("compass_pkg.")]
            if "obligations" in names:
                found.append(path)
                break
    return found


def test_ob_8_only_classify_effective_and_the_replay_read_the_new_path():
    """Amended 2026-10-07 (ADR-037): `effective` may import `obligations` as
    well as `classify`; the readers go through the effective view. The replay
    (policy diff) runs the same function to list what a change moves."""
    paths = [p for p in sorted((ROOT / "cli").rglob("*.py"))
             if p.name != "obligations.py" and "vendor" not in p.parts]
    users = [str(p.relative_to(ROOT)) for p in _obligations_importers(paths)]
    assert users == ["cli/compass_pkg/classify.py", "cli/compass_pkg/effective.py",
                     "cli/compass_pkg/replay.py"]
    assert "obligations" not in (ROOT / "cli" / "compass").read_text(encoding="utf-8")


def test_ob_8_the_import_rule_sees_every_import_form(tmp_path):
    forms = {
        "a.py": "from compass_pkg import obligations\n",
        "b.py": "from compass_pkg import (\n    layers,\n    obligations,\n)\n",
        "c.py": "import compass_pkg.obligations as o\n",
        "d.py": "def f():\n    from compass_pkg.obligations import obligations\n",
    }
    for name, text in forms.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    (tmp_path / "e.py").write_text("from compass_pkg import layers\n", encoding="utf-8")
    seen = sorted(p.name for p in _obligations_importers(sorted(tmp_path.glob("*.py"))))
    assert seen == ["a.py", "b.py", "c.py", "d.py"]


def test_ob_8_a_third_importer_fails_the_rule(tmp_path):
    planted = tmp_path / "reader.py"
    planted.write_text("from compass_pkg import (\n    obligations,\n)\n", encoding="utf-8")
    paths = [p for p in sorted((ROOT / "cli").rglob("*.py"))
             if p.name != "obligations.py" and "vendor" not in p.parts] + [planted]
    users = [p.name for p in _obligations_importers(paths)]
    assert users != ["classify.py", "effective.py"]
    assert users[-1] == "reader.py"


def test_ob_8_the_effect_names_are_the_inverse_of_the_adapters():
    from compass_pkg import legacy_adapter, obligations
    assert obligations._LEGACY_EFFECT == {
        new: old for old, new in legacy_adapter.RENAMED_EFFECTS.items()}


def test_ob_8_the_module_declares_its_dependencies_and_stays_small():
    path = ROOT / "cli" / "compass_pkg" / "obligations.py"
    text = path.read_text(encoding="utf-8")
    assert "# DEPENDENCY:" in text
    assert len(text.splitlines()) < 600          # the target the design sets
    core = (ROOT / "cli" / "compass_pkg" / "core.py").read_text(encoding="utf-8")
    assert len(core.splitlines()) <= 1200


def test_ob_4_an_assessment_outside_the_vocabulary_raises_and_is_not_a_refusal(
        preset_config):
    """The evaluator also raises for a misread assessment. That is a fault in
    the caller's input, and two faults with one message must not compare as
    equal outcomes."""
    with pytest.raises(CompassError, match="is not in the vocabulary"):
        _api("obligations")(preset_config, _assessment(risk="huge"))
    with pytest.raises(CompassError, match="missing required reading"):
        _api("obligations")(preset_config, {"risk": "contained"})


def test_ob_4_an_approach_with_no_entry_raises_and_is_not_a_refusal(preset_config):
    config = copy.deepcopy(preset_config)
    config["rules"]["default_shapes"]["rules"]["RP-SHAPE-005"]["then"][
        "lean_toward"] = "ghost"
    with pytest.raises(CompassError, match="ghost"):
        _api("obligations")(config, _assessment())


def test_ob_4_the_evaluators_two_conflicts_are_the_ones_that_refuse():
    from compass_pkg import routing
    conflict = getattr(routing, "RoutingConflict", None)
    assert conflict is not None and issubclass(conflict, CompassError)


def test_ob_6_a_capability_nobody_defines_raises(preset_config):
    """A misspelt switch would turn nothing on and nobody would be told, so a
    switch the catalogue spec does not name is a fault, whether it is passed
    in or a check needs it."""
    with pytest.raises(CompassError, match="entry-exit-evalution"):
        _api("obligations")(preset_config, _assessment(),
                            capabilities=("entry-exit-evalution",))
    config = _layer(preset_config, {"schema": 1, "checks": {"typo": {
        "statement": "x", "kind": "deterministic", "impl": "suite-passed",
        "severity": "blocking", "on_skipped": "fail",
        "requires": ["artifact-freshnes"]}},
        "stages": {"plan": {"set": {"entry": ["typo"]}}}})
    with pytest.raises(CompassError, match="artifact-freshnes"):
        _api("obligations")(config, _assessment())


def test_ob_8_the_owning_docs_name_the_module_and_the_evaluator_input():
    readme = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    rows = [line for line in readme.splitlines()
            if line.startswith("|") and "cli/compass_pkg/obligations.py" in line]
    assert len(rows) == 1, "docs/README.md needs one owning-doc row for obligations.py"
    owner = rows[0].split("|")[2].strip().strip("`")
    assert (ROOT / owner).is_file(), owner
    policy = (ROOT / "governance" / "routing-policy.md").read_text(encoding="utf-8")
    for word in ("cli/compass_pkg/obligations.py", "stage_mode_ranks", "RoutingConflict"):
        assert word in policy, f"routing-policy.md does not mention {word}"


# --- the evaluator reads the configuration's orders; guards for what it cannot read ---

def _reordered(config):
    """`size` reordered, with a floor that reads it through `at_least`."""
    config = copy.deepcopy(config)
    config["dimensions"]["size"]["values"] = ["atomic", "small", "large", "standard",
                                              "product"]
    config["rules"]["floors"]["rules"]["RP-PLANT-ORDER"] = {
        "order": 90, "when": {"size": {"at_least": "large"}},
        "then": {"force_minimum_approach": "full"}}
    return config


def test_ob_1_the_evaluator_reads_the_configurations_dimension_orders(preset_config):
    config = _reordered(preset_config)
    case = _assessment(size="standard")
    adapted = _api("policy_adapter")(config)
    assert adapted["dimension_orders"]["size"] == ["atomic", "small", "large",
                                                   "standard", "product"]
    # In the configured order `standard` reaches `large`, so the floor fires.
    assert _api("obligations")(config, case).approach == "full"
    assert evaluate_route(case, adapted)["delivery_approach"] == "full"
    # Without the key the evaluator reads the shipped order, and does not.
    without = {k: v for k, v in adapted.items() if k != "dimension_orders"}
    assert evaluate_route(case, without)["delivery_approach"] == "regular"


def test_ob_1_a_blocking_when_reads_the_configurations_orders(preset_config):
    # Every clause reads one order; a check's blocking_when reading the
    # shipped order while the rest read the configured one would split them.
    config = _reordered(preset_config)
    config["checks"]["suite-passed"]["blocking_when"] = {"size": {"at_least": "large"}}
    got = _api("obligations")(config, _assessment(size="standard"))
    assert got.checks["suite-passed"]["severity"] == "blocking"


def test_ob_1_the_shipped_orders_are_what_the_evaluator_assumed(preset_config):
    from compass_pkg.catalogue_spec import SHIPPED_ORDERS
    adapted = _api("policy_adapter")(preset_config)
    assert {k: tuple(v) for k, v in adapted["dimension_orders"].items()} \
        == dict(SHIPPED_ORDERS)


def test_ob_1_a_declared_hit_policy_other_than_the_built_in_one_raises(preset_config):
    policy = _api("policy_adapter")
    config = copy.deepcopy(preset_config)
    config["rules"]["floors"]["hit"]["force_minimum_approach"] = "min"
    message = _fault(lambda: policy(config))
    assert "floors" in message and "force_minimum_approach" in message
    config = copy.deepcopy(preset_config)
    config["rules"]["loop_ceilings"]["hit"]["limit"] = "max"
    message = _fault(lambda: policy(config))
    assert "loop_ceilings" in message and "limit" in message
    config = copy.deepcopy(preset_config)
    config["rules"]["floors"]["hit"]["add_gate"] = "first"
    assert "add_gate" in _fault(lambda: policy(config))
    assert _fault(lambda: _api("obligations")(config, _assessment()))


def test_ob_1_the_built_in_hit_policies_are_the_adapters(preset_config):
    from compass_pkg import legacy_adapter
    built_in = _api("BUILT_IN_HIT")
    assert built_in == legacy_adapter.EFFECT_HITS
    assert _api("DEFAULT_HIT") == "collect"
    for rule_set in preset_config["rules"].values():
        for effect, declared in rule_set["hit"].items():
            assert declared == built_in.get(effect, "collect"), effect


def test_ob_1_an_approach_the_evaluator_does_not_know_raises_and_is_not_refused(
        preset_config):
    config = copy.deepcopy(preset_config)
    config["approaches"]["sixth"] = copy.deepcopy(config["approaches"]["regular"])
    config["approaches"]["sixth"]["weight"] = 9
    assert "sixth" in _fault(lambda: _api("obligations")(config, _assessment()))
    assert "sixth" in _fault(lambda: _api("policy_adapter")(config))


def test_ob_1_a_changed_ships_on_a_shipped_approach_raises(preset_config):
    for name, ships in (("regular", False), ("spike", True)):
        config = copy.deepcopy(preset_config)
        config["approaches"][name]["ships"] = ships
        message = _fault(lambda: _api("obligations")(config, _assessment()))
        assert name in message and "ships" in message


def test_ob_1_the_five_approaches_are_the_ones_the_policy_ships(preset_config):
    assert set(_api("EVALUATOR_APPROACHES")) == set(preset_config["approaches"])


def test_ob_8_no_planning_id_that_a_reader_cannot_open_is_cited():
    """The shipped files of this increment cite decisions and ADRs a reader can
    open, never an id from a planning document that is not in the repository."""
    import re
    private = re.compile(r"(?<![A-Za-z0-9-])(D-\d+|CF-\d+|X-\d+|Q-\d+|PC-\d+|R-7|S1\.\d+)\b")
    for rel in ("cli/compass_pkg/obligations.py", "cli/compass_pkg/routing.py",
                "governance/routing-policy.md", "tests/test_obligations.py"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        # The pattern itself is the one line allowed to spell the ids.
        found = [m.group(0) for line in text.splitlines()
                 if "private = re.compile" not in line
                 for m in private.finditer(line)]
        assert found == [], (rel, found)
    cited = re.findall(r"governance/decisions/[\w.-]+\.md",
                       (ROOT / "cli/compass_pkg/routing.py").read_text(encoding="utf-8"))
    assert cited, "routing.py names no decision for the issue layer's order"
    for path in cited:
        assert (ROOT / path).is_file(), path


def test_ob_8_the_routing_policy_records_what_the_replays_showed():
    policy = (ROOT / "governance" / "routing-policy.md").read_text(encoding="utf-8")
    for word in ("dimension_orders", "hit policy", "reproduce-first", "expedited",
                 "tests/test_obligations.py", "landed_by"):
        assert word in policy, f"routing-policy.md does not mention {word}"
