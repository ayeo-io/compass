"""The shipped defaults exist as data in catalogue form, in a preset directory.

An adapter converts today's routing policy and guardrails file into one layer
document in catalogue form. Its output, run once over today's files, is
committed under `governance/presets/default/`. These tests tie that committed
data to the two files it came from and to the decisions that shape it: the
catalogue names (ADR-041), the preset directory (ADR-042), the lock set
(ADR-039) and the architect's ruling on stage-mode ranks.

The stage-mode ranks follow the architect's ruling recorded in
`governance/decisions/2026-10-06-stage-mode-ranks-cover-the-depth-ladder-only.md`.

Scenario ids: `DP-1` to `DP-6` (issue `default-preset-data`).
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

from compass_pkg import catalogue_check, catalogue_spec, legacy_adapter, legacy_views  # noqa: E402

PRESET = ROOT / "governance" / "presets" / "default"
POLICY = ROOT / "governance" / "routing-policy.yml"
GUARDRAILS = ROOT / "governance" / "guardrails.yml"
SIDECAR = ROOT / "governance" / "legacy-views.yml"
RANK_RULING = (ROOT / "governance" / "decisions"
               / "2026-10-06-stage-mode-ranks-cover-the-depth-ladder-only.md")
CATALOGUE_FILES = {name: PRESET / f"{name}.yml" for name in catalogue_spec.CATALOGUES}


def _load(path):
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def _today():
    return _load(POLICY), _load(GUARDRAILS)


def _preset():
    """The committed catalogue files as one layer document."""
    doc = {"schema": 1}
    for name, path in CATALOGUE_FILES.items():
        part = _load(path)
        assert part["schema"] == 1, path
        doc[name] = part[name]
    return doc


# --- the adapter equals the committed preset (`DP-1`) --------------------------

def _adapter_part(preset):
    """The preset without what the adapter never wrote: the human checks and
    the stage entry and exit lists, added after the preset became the source."""
    part = copy.deepcopy(preset)
    part["checks"] = {n: c for n, c in part["checks"].items()
                       if legacy_views.has_implementation(c)}
    for stage in part["stages"].values():
        stage.pop("entry", None)
        stage.pop("exit", None)
    return part


def test_dp_1_the_adapter_of_todays_files_equals_the_committed_preset():
    policy, guardrails = _today()
    adapted = legacy_adapter.adapt(policy, guardrails)
    committed = _adapter_part(_preset())
    assert set(adapted) == {"schema", *catalogue_spec.CATALOGUES}
    for name in catalogue_spec.CATALOGUES:
        assert adapted[name] == committed[name], name
    assert adapted == committed
    assert _load(PRESET / "evidence-types.yml") == \
        legacy_adapter.adapt_evidence_types(guardrails)


def test_dp_1_a_gate_removed_from_one_approach_breaks_the_match():
    policy, guardrails = _today()
    planted = copy.deepcopy(policy)
    planted["route_shapes"]["regular"]["gates"].remove("verify.security")
    assert legacy_adapter.adapt(planted, guardrails) != _adapter_part(_preset())
    # The same fault in the guardrails file is caught too.
    planted_g = copy.deepcopy(guardrails)
    planted_g["defaults"][0]["checks"].remove("suite-passed")
    assert legacy_adapter.adapt(policy, planted_g) != _adapter_part(_preset())


# The preset plus its sidecar must hold everything today's two files hold, so
# that a generator can rebuild them. This rebuild is written here, apart from
# the adapter, so the adapter is not compared with its own output.

_RENAMED_BACK = {"force_minimum_approach": "force_minimum_route",
                 "forbid_approach": "forbid_route"}


def _when_back(when, keys):
    if not isinstance(when, dict):
        return when
    return {keys.get(k, k): ([_when_back(c, keys) for c in v] if k == "any_of" else v)
            for k, v in when.items()}


def _rebuild(preset, sidecar, types):
    rp, gs = sidecar["routing_policy"], sidecar["guardrails"]

    def legacy_rule(rule_id, rule):
        out = {"id": rule_id}
        if "when" in rule:
            out["when"] = _when_back(rule["when"], rp["when_keys"])
        for key, value in rule.get("then", {}).items():
            out[_RENAMED_BACK.get(key, key)] = value
        if "rationale" in rule:
            out["rationale"] = rule["rationale"]
        out.update(rp["legacy_values"].get(rule_id, {}))
        order = rp["rule_key_order"].get(rule_id)
        if order:
            assert set(order) == set(out), rule_id
            out = {k: out[k] for k in order}
        return out

    def rules_of(name, skip=()):
        return [legacy_rule(i, r) for i, r in preset["rules"][name]["rules"].items()
                if i not in skip]

    approaches = preset["approaches"]
    vocabulary = {name: d["values"] for name, d in preset["dimensions"].items()
                  if name != "labels"}
    vocabulary["labels_common"] = preset["dimensions"]["labels"]["common"]
    policy = {
        "version": rp["version"],
        "routing_strategies": {
            "default_shapes": rules_of("default_shapes", rp["generated_rules"]),
            "default_route": rp["default_route"],
            "biases": [r["rationale"] for r in preset["rules"]["biases"]["rules"].values()],
            "role_defaults": rules_of("role_defaults"),
            "advisory_strategies": rules_of("advisory"),
        },
        "routing_guardrails": {
            "floors": rules_of("floors"), "caps": rules_of("caps"),
            "loop_ceilings": rules_of("loop_ceilings"),
            "immovable_gates": rules_of("immovable_gates"),
            "role_rules": rules_of("role_rules"),
        },
        "assessment_vocabulary": vocabulary,
        "autonomy_checkpoints": {
            level: {a: approaches[a]["checkpoints"][level] for a in row
                    if level in approaches[a].get("checkpoints", {})}
            for level, row in rp["autonomy_checkpoints"].items()},
        "route_shapes": {
            name: {"weight": a["weight"], "stages": a["stages"], "gates": a["gates"],
                   "subtask_ceiling": a["subtask_ceiling"], "artifacts": a["artifacts"]}
            for name, a in approaches.items()},
    }

    def guardrails_of(ships):
        out = []
        for gate_id, gate in preset["gates"].items():
            if gate["kind"] != "guardrail" or gate["applies_to"]["ships"] is not ships:
                continue
            item = {"id": gate_id, "name": gate["name"], "statement": gate["statement"],
                    "checks": gate["checks"]}
            if "when" in gate:
                item["applies_when"] = _when_back(gate["when"], gs["when_keys"])
            item["checked_at"] = gs["checked_at"][gate_id]
            order = gs["key_order"].get(gate_id)
            if order:
                assert set(order) == set(item), gate_id
                item = {k: item[k] for k in order}
            out.append(item)
        return out

    checks = {}
    for name, check in preset["checks"].items():
        if not legacy_views.has_implementation(check):
            continue
        checks[name] = {"description": check["statement"]}
        if "blocking_when" in check:
            checks[name]["blocking_when"] = _when_back(check["blocking_when"],
                                                       gs["when_keys"])
    guardrails = {
        "version": gs["version"],
        "checks": checks,
        "evidence_types": types["evidence_types"],
        "gate_evidence_requirements": {
            g: e["accepts"] for g, e in preset["gates"].items()
            if e["kind"] == "review" and "accepts" in e},
        "defaults": guardrails_of(True),
        "spike_guardrails": guardrails_of(False),
        "project": gs["project"],
    }
    return policy, guardrails


def _rebuilt(preset=None, sidecar=None):
    return _rebuild(preset if preset is not None else _preset(),
                    sidecar if sidecar is not None else _load(SIDECAR),
                    _load(PRESET / "evidence-types.yml"))


def _rule_lists(policy, guardrails):
    """Every list of rules or guardrails, so key order can be compared."""
    lists = [*policy["routing_strategies"].get("default_shapes", []),
             *policy["routing_strategies"].get("role_defaults", []),
             *policy["routing_strategies"].get("advisory_strategies", [])]
    for group in policy["routing_guardrails"].values():
        lists += group
    lists += guardrails["defaults"] + guardrails["spike_guardrails"]
    return [list(item) for item in lists]


def _evaluations(policy):
    """The evaluator's answer for a grid of assessments, as comparable text."""
    import itertools
    import json
    from compass_pkg.routing import evaluate_route
    vocabulary = policy["assessment_vocabulary"]
    out = []
    for risk, fam, size, goal, urgency, role, labels in itertools.product(
            vocabulary["risk"], vocabulary["familiarity"], vocabulary["size"],
            vocabulary["goal"], vocabulary["urgency"], ["engineer", "product-owner",
                                                        "product-marketer"],
            ([], ["auth"], ["migrations", "public-api"])):
        reading = {"risk": risk, "familiarity": fam, "size": size, "goal": goal,
                   "urgency": urgency, "role": role, "labels": labels}
        for autonomy in ("controlled", "balanced", "autonomous"):
            try:
                result = evaluate_route(reading, policy, autonomy)
            except Exception as exc:  # an assessment the policy refuses
                result = {"error": str(exc)}
            out.append(json.dumps(result, sort_keys=True, default=str))
    return out


def test_dp_1_the_rebuilt_files_evaluate_every_assessment_as_today_does():
    assert SIDECAR.is_file(), "governance/legacy-views.yml is missing"
    policy, _ = _today()
    rebuilt_policy, _ = _rebuilt()
    today = _evaluations(policy)
    assert len(today) > 1000
    assert _evaluations(rebuilt_policy) == today


def test_dp_1_a_changed_block_phase_or_checked_at_fails_the_rebuild_comparison():
    policy, guardrails = _today()
    assert SIDECAR.is_file(), "governance/legacy-views.yml is missing"
    sidecar = _load(SIDECAR)
    sidecar["routing_policy"]["legacy_values"]["RP-ROLE-001"]["block_phase"] = "plan"
    changed_policy, _ = _rebuilt(sidecar=sidecar)
    assert changed_policy != policy
    assert _evaluations(changed_policy) != _evaluations(policy)
    sidecar = _load(SIDECAR)
    sidecar["guardrails"]["checked_at"]["G3"] = ["verify"]
    _, changed_guardrails = _rebuilt(sidecar=sidecar)
    assert changed_guardrails != guardrails


def test_dp_1_the_preset_and_its_sidecar_rebuild_todays_two_files():
    assert SIDECAR.is_file(), "governance/legacy-views.yml is missing"
    policy, guardrails = _today()
    rebuilt_policy, rebuilt_guardrails = _rebuilt()
    assert rebuilt_policy == policy
    assert rebuilt_guardrails == guardrails
    assert _rule_lists(rebuilt_policy, rebuilt_guardrails) == _rule_lists(policy, guardrails)
    for group in ("autonomy_checkpoints",):
        for level in policy[group]:
            assert list(rebuilt_policy[group][level]) == list(policy[group][level])


def _planted_rebuilds():
    """Each fault the review planted, applied to the committed data."""
    assert SIDECAR.is_file(), "governance/legacy-views.yml is missing"
    def planted(edit):
        preset, sidecar = _preset(), _load(SIDECAR)
        edit(preset, sidecar)
        return _rebuilt(preset, sidecar)

    def drop_role_effects(p, s):
        del p["rules"]["role_rules"]["rules"]["RP-ROLE-002"]["then"]["block_phase"]
        del p["rules"]["role_rules"]["rules"]["RP-ROLE-002"]["then"]["require_artifact"]

    def drop_caps(p, s):
        p["rules"]["caps"]["rules"].clear()

    def raise_loop_limits(p, s):
        for rule in p["rules"]["loop_ceilings"]["rules"].values():
            rule["then"]["limit"] += 1

    def null_ceiling(p, s):
        p["approaches"]["regular"]["subtask_ceiling"] = None

    def drop_biases(p, s):
        p["rules"]["biases"]["rules"].clear()

    def last_checked_at(p, s):
        s["guardrails"]["checked_at"]["G1"] = s["guardrails"]["checked_at"]["G1"][-1:]

    def drop_sidecar_value(p, s):
        s["routing_policy"]["legacy_values"]["RP-ROLE-001"].pop("block_phase")

    def drop_fallback_marker(p, s):
        s["routing_policy"]["generated_rules"] = []

    def change_row_order(p, s):
        s["routing_policy"]["autonomy_checkpoints"]["controlled"].reverse()

    def lose_when_spelling(p, s):
        s["guardrails"]["when_keys"] = {}

    return {fn.__name__: planted(fn) for fn in (
        drop_role_effects, drop_caps, raise_loop_limits, null_ceiling, drop_biases,
        last_checked_at, drop_sidecar_value, drop_fallback_marker, change_row_order,
        lose_when_spelling)}


def test_dp_1_each_planted_loss_makes_the_rebuild_differ():
    policy, guardrails = _today()
    for name, (rebuilt_policy, rebuilt_guardrails) in _planted_rebuilds().items():
        same = (rebuilt_policy == policy and rebuilt_guardrails == guardrails
                and _rule_lists(rebuilt_policy, rebuilt_guardrails)
                == _rule_lists(policy, guardrails)
                and all(list(rebuilt_policy["autonomy_checkpoints"][lv])
                        == list(policy["autonomy_checkpoints"][lv])
                        for lv in policy["autonomy_checkpoints"]))
        assert not same, f"the rebuild did not notice: {name}"


def test_dp_1_the_role_rules_keep_every_effect_the_policy_gives_them():
    policy, _ = _today()
    rules = _preset()["rules"]["role_rules"]["rules"]
    for legacy in policy["routing_guardrails"]["role_rules"]:
        then = rules[legacy["id"]]["then"]
        for key in ("require_artifact", "gate", "block_phase", "until"):
            assert (key in legacy) == (key in then), (legacy["id"], key)
    second = rules["RP-ROLE-002"]["then"]
    assert second.get("require_artifact") == "intent"
    assert second.get("block_phase") == "plan"
    assert "until" in second and "until" not in rules["RP-ROLE-002"]


def test_dp_1_the_rendered_files_are_what_is_committed():
    policy, guardrails = _today()
    files = legacy_adapter.preset_files(policy, guardrails)
    assert set(files) == {"preset.yml", "evidence-types.yml",
                          *(f"{n}.yml" for n in catalogue_spec.CATALOGUES)}
    for name, text in files.items():
        committed = (PRESET / name).read_text(encoding="utf-8")
        if name in ("checks.yml", "stages.yml"):
            # These two gained the human checks and the stage lists after the
            # adapter wrote them; what the adapter wrote is unchanged.
            wrote = yaml.safe_load(text)
            kept = _adapter_part({"checks": {}, "stages": {}, **yaml.safe_load(committed)})
            assert kept[name[:-4]] == wrote[name[:-4]], name
        else:
            assert committed == text, name
        assert text.startswith("#"), name
        assert "source of the shipped defaults" in " ".join(text.splitlines()[:5]), name
    # The legacy-view values sit beside the legacy files, not in the preset.
    assert not (PRESET / "legacy.yml").exists()
    assert SIDECAR.read_text(encoding="utf-8") == \
        legacy_adapter.legacy_views_text(policy, guardrails)


# --- the preset names itself and checks as a parent (`DP-2`) -------------------

def test_dp_2_preset_yml_names_default_at_6_0_0_with_capabilities_off():
    preset = _load(PRESET / "preset.yml")
    assert preset["id"] == "default"
    assert preset["version"] == "6.0.0"
    assert preset["schema"] == 1
    assert preset["capabilities"] == {name: False for name in catalogue_spec.CAPABILITIES}


def test_dp_2_the_preset_checks_with_no_error_as_a_parent():
    layer = _preset()
    layer["capabilities"] = _load(PRESET / "preset.yml")["capabilities"]
    assert catalogue_check.check_layer(layer, "parent") == []


def test_dp_2_the_check_can_fail_on_the_preset():
    layer = _preset()
    layer["approaches"]["quick-fix"]["colour"] = "red"
    assert catalogue_check.check_layer(layer, "parent") != []


def test_dp_2_every_catalogue_is_filled_and_the_approach_catalogue_is_not_named_routes():
    preset = _preset()
    for name in catalogue_spec.CATALOGUES:
        assert preset[name], name
    assert not (PRESET / "routes.yml").exists()
    assert set(preset["approaches"]) == {"spike", "quick-fix", "regular", "hotfix", "full"}
    assert len(preset["stages"]) == 8
    floors = preset["rules"]["floors"]
    effects = {k for rule in floors["rules"].values() for k in rule["then"]}
    assert "force_minimum_approach" in effects
    assert "force_minimum_route" not in effects
    assert floors["hit"]["force_minimum_approach"] == "max"


# --- stage-mode ranks (`DP-3`) ------------------------------------------------

# The architect's ruling: a rank only for the modes on the depth ladder.
RULED_RANKS = {
    ("assess", "light"): 2, ("assess", "full"): 3,
    ("define", "collapsed"): 1, ("define", "light"): 2, ("define", "full"): 3,
    ("define", "reproduce-first"): None,
    ("refine", "skipped"): 0, ("refine", "collapsed"): 1,
    ("refine", "light"): 2, ("refine", "full"): 3,
    ("plan", "collapsed"): 1, ("plan", "full"): 3,
    ("breakdown", "skipped"): 0, ("breakdown", "multiagent"): None,
    ("implement", "explore"): None, ("implement", "full"): 3,
    ("implement", "expedited"): None,
    ("verify", "conclude"): None, ("verify", "light"): 2, ("verify", "full"): 3,
    ("ship", "graduate-or-discard"): None, ("ship", "light"): 2,
    ("ship", "full"): 3, ("ship", "full-plus-backfill"): 4,
}


def test_dp_3_every_mode_has_the_ruled_rank_or_none():
    stages = _preset()["stages"]
    seen = {}
    for stage, entry in stages.items():
        for mode, body in entry["modes"].items():
            seen[(stage, mode)] = body.get("rank")
    assert seen == RULED_RANKS


def test_dp_3_stages_run_in_the_order_the_policy_lists_them():
    policy, _ = _today()
    stages = _preset()["stages"]
    listed = list(policy["route_shapes"]["full"]["stages"])
    assert sorted(stages, key=lambda s: stages[s]["order"]) == listed
    assert [stages[s]["order"] for s in listed] == list(range(1, len(listed) + 1))


def test_dp_3_every_approach_uses_a_mode_its_stage_declares():
    preset = _preset()
    for approach, entry in preset["approaches"].items():
        assert set(entry["stages"]) == set(preset["stages"]), approach
        for stage, mode in entry["stages"].items():
            assert mode in preset["stages"][stage]["modes"], (approach, stage, mode)


def test_dp_3_the_ranks_reproduce_todays_lift_to_full():
    # Today's lift raises collapsed, skipped and light to full and leaves
    # every other mode alone; a rank below full is exactly those three.
    stages = _preset()["stages"]
    lifted = {mode for entry in stages.values()
              for mode, body in entry["modes"].items()
              if body.get("rank") is not None and body["rank"] < 3}
    assert lifted == {"collapsed", "skipped", "light"}


# --- the lock set (`DP-4`) ----------------------------------------------------

def _locks(preset):
    found = {}
    for catalogue in catalogue_spec.CATALOGUES:
        for entry_id, entry in preset[catalogue].items():
            if isinstance(entry, dict) and entry.get("locked"):
                found[f"{catalogue}.{entry_id}"] = entry["locked"]
    return found


def _assert_the_shipped_lock_set(preset):
    _, guardrails = _today()
    guardrail = {g["id"]: g for g in guardrails["defaults"]}
    spike = {g["id"]: g for g in guardrails["spike_guardrails"]}
    expected = {
        "stages.assess": True, "stages.verify": True, "stages.ship": True,
        "rules.immovable_gates": True,
        "gates.verify.correctness": True, "gates.verify.governance": True,
        "gates.verify.traceability": True,
        "gates.G1": True, "gates.G2": True, "gates.G3": True, "gates.G4": True,
        "gates.G5": "hard", "checks.human-approval-present": "hard",
        "gates.spike.conclude": True, "gates.S1": True, "gates.S2": True,
        "approaches.spike": True,
    }
    for gate in ("G1", "G2", "G3", "G4"):
        for check in guardrail[gate]["checks"]:
            expected[f"checks.{check}"] = True
    for gate in spike.values():
        for check in gate["checks"]:
            expected[f"checks.{check}"] = True
    assert _locks(preset) == expected


def test_dp_4_the_locks_are_the_shipped_lock_set():
    _assert_the_shipped_lock_set(_preset())


def test_dp_4_floors_caps_ceilings_and_advisory_rules_are_not_locked():
    rules = _preset()["rules"]
    for name in ("floors", "caps", "loop_ceilings", "advisory"):
        assert "locked" not in rules[name], name
    assert _preset()["approaches"]["spike"]["ships"] is False
    for name in ("quick-fix", "regular", "hotfix", "full"):
        assert _preset()["approaches"][name]["ships"] is True


def test_dp_4_the_preset_file_summarises_the_locks():
    summary = _load(PRESET / "preset.yml")["locks"]
    hard = sorted(k for k, v in _locks(_preset()).items() if v == "hard")
    assert sorted(summary["hard"]) == hard
    assert "gates.G5" in summary["hard"]
    assert "gates.G4" in summary["locked"] and "gates.G5" not in summary["locked"]


def test_dp_4_an_unlocked_g5_or_an_extra_lock_fails_the_lock_set_check():
    preset = _preset()
    del preset["gates"]["G5"]["locked"]
    with pytest.raises(AssertionError):
        _assert_the_shipped_lock_set(preset)
    softened = _preset()
    softened["checks"]["human-approval-present"]["locked"] = True
    with pytest.raises(AssertionError):
        _assert_the_shipped_lock_set(softened)
    extra = _preset()
    extra["rules"]["floors"]["locked"] = True
    with pytest.raises(AssertionError):
        _assert_the_shipped_lock_set(extra)


# --- old key names, no mutation, no reader (`DP-5`) ----------------------------

def _with_old_names(policy):
    old = copy.deepcopy(policy)
    shapes = old["route_shapes"]
    old["route_shapes"] = {
        {"quick-fix": "express", "regular": "standard", "full": "expedition"}.get(k, k): v
        for k, v in shapes.items()}
    strategies = old["routing_strategies"]
    strategies["default_route"] = "standard"
    for rule in strategies["default_shapes"]:
        rule["lean_toward"] = {"quick-fix": "express", "regular": "standard",
                               "full": "expedition"}.get(rule["lean_toward"],
                                                          rule["lean_toward"])
    for rule in old["routing_guardrails"]["floors"]:
        if rule.get("force_minimum_route") == "full":
            rule["force_minimum_route"] = "expedition"
    table = old["autonomy_checkpoints"]
    for level, row in list(table.items()):
        table[level] = {{"quick-fix": "express", "regular": "standard",
                         "full": "expedition"}.get(k, k): v for k, v in row.items()}
    vocabulary = old.pop("assessment_vocabulary")
    old["assessment_vocabulary"] = {
        {"risk": "blast_radius", "familiarity": "terrain", "size": "magnitude",
         "goal": "intent", "labels_common": "touches_common"}.get(k, k): v
        for k, v in vocabulary.items()}
    return old


def test_dp_5_old_key_names_convert_to_the_same_preset():
    policy, guardrails = _today()
    old = _with_old_names(policy)
    assert old != policy
    assert legacy_adapter.adapt(old, guardrails) == legacy_adapter.adapt(policy, guardrails)


def _old_spellings(policy):
    """Today's policy with the retired dimension and stage names back in."""
    dims = {"risk": "blast_radius", "size": "magnitude", "familiarity": "terrain",
            "labels_any": "touches_any"}
    stages = {"refine": "clarify", "implement": "build", "ship": "land"}

    def when(w):
        if not isinstance(w, dict):
            return w
        return {dims.get(k, k): ([when(c) for c in v] if k == "any_of" else v)
                for k, v in w.items()}

    old = copy.deepcopy(policy)
    for group in old["routing_guardrails"].values():
        for rule in group:
            if "when" in rule:
                rule["when"] = when(rule["when"])
            if "never_skip" in rule:
                rule["never_skip"] = [stages.get(x, x) for x in rule["never_skip"]]
    for rule in old["routing_strategies"]["default_shapes"]:
        rule["when"] = when(rule["when"])
    for shape in old["route_shapes"].values():
        shape["stages"] = {stages.get(k, k): v for k, v in shape["stages"].items()}
    for row in old["autonomy_checkpoints"].values():
        for name, listed in row.items():
            row[name] = [stages.get(x, x) for x in listed]
    return old


def test_dp_5_old_dimension_and_stage_names_convert_to_the_same_preset():
    policy, guardrails = _today()
    old = _old_spellings(policy)
    assert old != policy
    assert legacy_adapter.adapt(old, guardrails) == legacy_adapter.adapt(policy, guardrails)


def test_dp_5_old_when_keys_in_the_guardrails_file_convert_too():
    policy, guardrails = _today()
    new = copy.deepcopy(guardrails)
    new["defaults"][4]["applies_when"] = {"any_of": [
        {"labels_any": ["auth", "payments", "personal-data", "migrations"]},
        {"risk": "critical"}]}
    new["checks"]["scenarios-are-executable"]["blocking_when"] = {
        "risk": ["cross-cutting", "critical"]}
    new["defaults"][0]["checked_at"] = ["verify", "ship"]
    assert new != guardrails
    assert legacy_adapter.adapt(policy, new) == legacy_adapter.adapt(policy, guardrails)


# --- a copied policy converts without losing or failing (`DP-5`) ----------------

def _adapted(policy, guardrails):
    try:
        return legacy_adapter.adapt(policy, guardrails)
    except Exception as exc:  # report a failure to convert as a failed assertion
        raise AssertionError(f"the adapter raised {type(exc).__name__}: {exc}")


def test_dp_5_a_cap_with_forbid_route_and_no_worktree_limit_converts():
    policy, guardrails = _today()
    planted = copy.deepcopy(policy)
    planted["routing_guardrails"]["caps"].append(
        {"id": "RP-CAP-900", "forbid_route": "full", "rationale": "A planted cap."})
    cap = _adapted(planted, guardrails)["rules"]["caps"]["rules"]["RP-CAP-900"]
    assert cap["then"] == {"forbid_approach": "full"}


def test_dp_5_a_role_rule_with_a_gate_and_no_artifact_converts():
    policy, guardrails = _today()
    planted = copy.deepcopy(policy)
    planted["routing_guardrails"]["role_rules"].append(
        {"id": "RP-ROLE-900", "when": {"role": "qa"}, "gate": "verify.claims",
         "rationale": "A planted rule."})
    rule = _adapted(planted, guardrails)["rules"]["role_rules"]["rules"]["RP-ROLE-900"]
    assert rule["then"] == {"gate": "verify.claims"}


def test_dp_5_a_shape_with_the_old_phases_block_reads_as_stages():
    policy, guardrails = _today()
    planted = copy.deepcopy(policy)
    shape = planted["route_shapes"]["regular"]
    shape["phases"] = shape.pop("stages")
    adapted = _adapted(planted, guardrails)
    assert adapted["approaches"]["regular"]["stages"] == policy["route_shapes"]["regular"]["stages"]
    assert adapted == _adapted(policy, guardrails)


def test_dp_5_a_shape_with_no_subtask_ceiling_gets_the_default_of_one():
    policy, guardrails = _today()
    planted = copy.deepcopy(policy)
    del planted["route_shapes"]["quick-fix"]["subtask_ceiling"]
    del planted["route_shapes"]["full"]["subtask_ceiling"]
    adapted = _adapted(planted, guardrails)["approaches"]
    assert adapted["quick-fix"]["subtask_ceiling"] == 1
    assert adapted["full"]["subtask_ceiling"] == 1


def test_dp_5_the_adapter_leaves_its_input_unchanged():
    policy, guardrails = _today()
    before = copy.deepcopy((policy, guardrails))
    legacy_adapter.adapt(policy, guardrails)
    legacy_adapter.adapt_evidence_types(guardrails)
    legacy_adapter.preset_files(policy, guardrails)
    assert (policy, guardrails) == before


def test_dp_5_only_the_adapter_and_the_view_generator_read_the_preset():
    """The generator of the two legacy views (issue `generated-legacy-views`)
    is the one reader of the preset besides the adapter that wrote it. It must
    not import the adapter, so a fault in one cannot hide in both."""
    hits = []
    for top in ("cli", "hooks", "scripts"):
        for path in sorted((ROOT / top).rglob("*")):
            parts = path.relative_to(ROOT).parts
            if not path.is_file() or "vendor" in parts or "__pycache__" in parts:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if "legacy_adapter" in text or "presets/default" in text:
                hits.append("/".join(parts))
    assert hits == ["cli/compass_pkg/legacy_adapter.py",
                    "cli/compass_pkg/legacy_views.py",
                    "cli/compass_pkg/legacy_views_template.py",
                    "scripts/generate-legacy-views.py"], hits
    generator = (ROOT / "cli" / "compass_pkg" / "legacy_views.py").read_text(encoding="utf-8")
    assert "import legacy_adapter" not in generator
    assert "compass_pkg.legacy_adapter" not in generator


def test_dp_5_the_adapter_is_not_in_core_and_core_stays_in_bounds():
    core = (ROOT / "cli" / "compass_pkg" / "core.py").read_text(encoding="utf-8")
    assert len(core.splitlines()) <= 1200
    assert "legacy_adapter" not in core


# --- references and evidence types (`DP-6`) -----------------------------------

def test_dp_6_every_reference_in_the_preset_resolves():
    preset = _preset()
    gates, stages = preset["gates"], preset["stages"]
    artifacts, checks = preset["artifacts"], preset["checks"]
    for approach, entry in preset["approaches"].items():
        for gate in entry["gates"]:
            assert gate in gates, (approach, gate)
        for artifact in entry["artifacts"]:
            assert artifact in artifacts, (approach, artifact)
        for level, listed in entry["checkpoints"].items():
            assert level in catalogue_spec.AUTONOMY
            assert set(listed) <= set(stages), (approach, level)
    for gate_id, gate in gates.items():
        for check in gate.get("checks", []):
            assert check in checks, (gate_id, check)
        if "stage" in gate:
            assert gate["stage"] in stages, gate_id
    for rule_set in preset["rules"].values():
        for rule_id, rule in rule_set["rules"].items():
            then = rule.get("then", {})
            for key in ("add_gate", "gate"):
                if key in then:
                    assert then[key] in gates, rule_id
            for key in ("add_artifact", "require_artifact", "suggest_artifact"):
                if key in then:
                    assert then[key] in artifacts, rule_id
            for key in ("force_minimum_approach", "lean_toward"):
                if key in then:
                    assert then[key] in preset["approaches"], rule_id
            for stage in then.get("never_skip", []):
                assert stage in stages, rule_id
            for key in ("require_phase", "block_phase"):
                if key in then:
                    assert then[key] in stages, rule_id
    for key in preset["vocabulary"]:
        catalogue, _, entry_id = key.partition(".")
        assert catalogue in catalogue_spec.CATALOGUES, key
        assert entry_id in preset[catalogue], key
    for entry in preset["checks"].values():
        if entry["kind"] == "human":
            continue
        assert entry["kind"] == "deterministic"
        assert entry["impl"] in preset["checks"]
    for stage_id, stage in stages.items():
        for side in ("entry", "exit"):
            for check in stage.get(side, []):
                assert check in checks, (stage_id, side, check)


def test_dp_6_the_checks_are_the_guardrail_files_registry():
    _, guardrails = _today()
    checks = {n: c for n, c in _preset()["checks"].items()
              if legacy_views.has_implementation(c)}
    assert set(checks) == set(guardrails["checks"])
    for name, entry in guardrails["checks"].items():
        assert checks[name]["statement"] == entry["description"]
    blocking = checks["scenarios-are-executable"]
    assert blocking["blocking_when"] == {"risk": ["cross-cutting", "critical"]}
    assert all(c["severity"] == "blocking" for c in checks.values())


def test_dp_6_the_evidence_types_and_accepted_types_equal_the_guardrails_file():
    _, guardrails = _today()
    types = _load(PRESET / "evidence-types.yml")
    assert types["schema"] == 1
    assert set(types["evidence_types"]) == set(guardrails["evidence_types"])
    for name, entry in guardrails["evidence_types"].items():
        assert types["evidence_types"][name]["description"] == entry["description"]
    gates = _preset()["gates"]
    for gate, accepted in guardrails["gate_evidence_requirements"].items():
        assert gates[gate]["kind"] == "review"
        assert gates[gate]["accepts"] == accepted
    for gate in gates.values():
        for accepted in gate.get("accepts", []):
            assert accepted in types["evidence_types"]


def test_dp_6_the_guardrails_keep_their_names_and_the_spike_ones_apply_off_ships():
    _, guardrails = _today()
    gates = _preset()["gates"]
    for g in guardrails["defaults"]:
        assert gates[g["id"]]["name"] == g["name"]
        assert gates[g["id"]]["kind"] == "guardrail"
        assert gates[g["id"]]["applies_to"] == {"ships": True}
    for g in guardrails["spike_guardrails"]:
        assert gates[g["id"]]["applies_to"] == {"ships": False}
    assert gates["G5"]["when"] == {"any_of": [
        {"labels_any": ["auth", "payments", "personal-data", "migrations"]},
        {"risk": "critical"}]}


# --- on_skipped and the ranking ruling ----------------------------------------

# Read from the modules that return `NOTHING_TO_CHECK` for the check: checks.py
# (scenarios-are-executable, claim-traces-to-scenario, command-passes),
# borrowed_docs.py, binding.py (evidence-matches-tree), dashboard.py,
# landed_by.py, multiagent_check.py and evidence_identity.py. The check
# declared-tests-resolve passes with a note instead, so it is `pass`.
EXPECTED_ON_SKIPPED = {
    "scenarios-are-executable": "not-applicable",
    "claim-traces-to-scenario": "not-applicable",
    "command-passes": "not-applicable",
    "borrowed-documents-answered": "not-applicable",
    "evidence-matches-tree": "not-applicable",
    "evidence-identity-matches": "not-applicable",
    "dashboard-current": "not-applicable",
    "landed-by-resolves": "not-applicable",
    "multiagent-run-recorded": "not-applicable",
    "declared-tests-resolve": "pass",
}


def test_dp_6_on_skipped_follows_what_each_check_returns_when_it_cannot_run():
    checks = _preset()["checks"]
    for name, entry in checks.items():
        if entry["kind"] == "human":
            continue  # the human checks are in tests/test_ready_and_done_data.py
        assert entry["on_skipped"] == EXPECTED_ON_SKIPPED.get(name, "fail"), name


def test_dp_3_the_rank_ruling_is_recorded_in_the_repository():
    assert RANK_RULING.is_file(), "the ranking ruling is not recorded"
    text = RANK_RULING.read_text(encoding="utf-8")
    assert "| `ship` | `full-plus-backfill` | 4 |" in text
    for (stage, mode), rank in RULED_RANKS.items():
        shown = "none" if rank is None else str(rank)
        assert f"| `{stage}` | `{mode}` | {shown} |" in text, (stage, mode)


# --- the sidecar holds spellings, never a changed value (`DP-1`) ---------------

def _spelling_of(key, value):
    from compass_pkg import core
    renames = core._stage_key_renames()
    if key in ("block_phase", "require_phase"):
        return renames.get(value, value)
    if key in ("require_artifact", "suggest_artifact", "add_artifact"):
        return value[:-3] if value.endswith(".md") else value
    raise AssertionError(f"{key} is not a value the sidecar may respell")


def _assert_sidecar_only_respells(preset, sidecar):
    for rule_id, values in sidecar["routing_policy"]["legacy_values"].items():
        rule = next(r for rs in preset["rules"].values()
                    for i, r in rs["rules"].items() if i == rule_id)
        for key, legacy in values.items():
            assert _spelling_of(key, legacy) == rule["then"][key], (rule_id, key)


def test_dp_1_every_sidecar_value_is_only_another_spelling_of_the_preset_value():
    assert SIDECAR.is_file(), "governance/legacy-views.yml is missing"
    _assert_sidecar_only_respells(_preset(), _load(SIDECAR))
    # A preset value changed behind a sidecar that still holds today's value is refused.
    preset = _preset()
    preset["rules"]["loop_ceilings"]["rules"]["RP-LOOP-001"]["then"]["limit"] += 1
    sidecar = _load(SIDECAR)
    sidecar["routing_policy"]["legacy_values"]["RP-LOOP-001"] = {"limit": 3}
    with pytest.raises(AssertionError):
        _assert_sidecar_only_respells(preset, sidecar)
    changed = _preset()
    changed["rules"]["role_rules"]["rules"]["RP-ROLE-001"]["then"]["block_phase"] = "plan"
    with pytest.raises(AssertionError):
        _assert_sidecar_only_respells(changed, _load(SIDECAR))


def test_dp_1_each_gate_stage_is_the_first_stage_of_its_checked_at_list():
    from compass_pkg import core
    renames = core._stage_key_renames()
    _, guardrails = _today()
    gates = _preset()["gates"]
    for group in ("defaults", "spike_guardrails"):
        for guardrail in guardrails[group]:
            first = guardrail["checked_at"][0]
            assert gates[guardrail["id"]]["stage"] == renames.get(first, first), guardrail["id"]
