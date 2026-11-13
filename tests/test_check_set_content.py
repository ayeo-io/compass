"""The check set holds the shipped defaults, and the legacy adapter still reads a copy.

Until 9.0.0 the shipped defaults lived in a preset directory,
`governance/presets/default/`, which the legacy adapter wrote once from the two
governance files. 9.0.0 replaced the preset with the fixed check set
(`governance/check-set.yml`, ADR-094) and deleted the preset, its sidecar and
the generator of the two views, so the cases that tied them together went too.
These tests keep what still holds: the content of the check set (the catalogue
names of ADR-041, the stage-mode ranks of the architect's ruling, the
references, the checks and evidence types of the frozen guardrails file) and the
conversions of the adapter, which still reads a project's own copy.

The stage-mode ranks follow the architect's ruling recorded in
`governance/decisions/2026-10-06-stage-mode-ranks-cover-the-depth-ladder-only.md`.

Scenario ids: `DP-1` to `DP-6` (issue `default-preset-data`). Moved from the
tests of the default preset.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

from compass_pkg import catalogue_spec, check_set  # noqa: E402

sys.path.insert(0, str(ROOT / "tests"))
import legacy_copy  # noqa: E402
from check_set_files import view as shipped_view  # noqa: E402

RANK_RULING = (ROOT / "governance" / "decisions"
               / "2026-10-06-stage-mode-ranks-cover-the-depth-ladder-only.md")


def _load(path):
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def _today():
    """The check set in the shape of the two 8.x views 9.0.0 deleted (ADR-098)."""
    return shipped_view("routing-policy.yml"), shipped_view("guardrails.yml")


def _v8():
    """The two files of the 8.0.4 governance copy. They hold the five 8.x
    approaches, the floors that raised a minimum approach and the caps, which the
    shipped default no longer declares (ADR-092), so the conversions of an old
    copied policy are tested on them."""
    import tarfile
    sys.path.insert(0, str(ROOT / "tests"))
    from compat_baseline import GOVERNANCE_8_0_4
    with tarfile.open(GOVERNANCE_8_0_4) as tar:
        return tuple(yaml.safe_load(tar.extractfile(f"governance/{name}").read())
                     for name in ("routing-policy.yml", "guardrails.yml"))


def _preset():
    """The check set as one document in catalogue form, with the two catalogues
    9.0.0 left empty (`artifacts`, `readiness`) and the display names as
    `vocabulary`."""
    resolved = check_set.resolved()
    return {"schema": 1, **{name: resolved.get(name) or {}
                            for name in catalogue_spec.CATALOGUES}}


# --- the catalogues of the check set (`DP-2`) ------------------------------------

def test_dp_2_the_check_set_ships_every_capability_off():
    capabilities = check_set.load()["capabilities"]
    # A capability 9.0.0 removed (ADR-091) stays valid and is not shipped.
    from compass_pkg import removed_parts
    assert capabilities == {name: False for name in catalogue_spec.CAPABILITIES
                            if name not in removed_parts.CAPABILITIES}
    assert "artifact-freshness" not in capabilities


def test_dp_2_every_catalogue_is_filled_and_the_approach_catalogue_is_not_named_routes():
    preset = _preset()
    for name in catalogue_spec.CATALOGUES:
        # 9.0.0 declares no document kind (ADR-091) and no readiness signal
        # (ADR-093); each file stays, empty.
        assert preset[name] or name in ("artifacts", "readiness"), name
    assert preset["artifacts"] == {}
    assert preset["readiness"] == {}
    # One path of four stages and the spike (ADR-092). No floor raises a minimum
    # approach any more, and no caps rule set is shipped.
    assert set(preset["approaches"]) == {"spike", "delivery"}
    assert list(preset["stages"]) == ["assess", "specify", "build", "ship"]
    floors = preset["rules"]["floors"]
    effects = {k for rule in floors["rules"].values() for k in rule["then"]}
    # ADR-099: no shipped floor adds a gate; a project's own floor can.
    assert effects == {"require_skill"}
    assert "force_minimum_approach" not in floors["hit"]
    assert "caps" not in preset["rules"]


# --- stage-mode ranks (`DP-3`) ------------------------------------------------

# The architect's ruling: a rank only for the modes on the depth ladder.
# The path stages declare only the modes an approach names (ADR-092).
RULED_RANKS = {
    ("assess", "lightweight"): 2, ("assess", "thorough"): 3,
    ("specify", "thorough"): 3,
    ("build", "thorough"): 3, ("build", "explore"): None,
    ("ship", "thorough"): 3, ("ship", "graduate-or-discard"): None,
}

# The ruling of 6 October 2026 names the modes by the words they had then. A
# merged decision record never changes, so it is read through the new names.
RULING_WORDS = {"lightweight": "light", "thorough": "full",
                "thorough-with-follow-up": "full-plus-backfill"}


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
    listed = list(policy["route_shapes"]["delivery"]["stages"])
    assert sorted(stages, key=lambda s: stages[s]["order"]) == listed
    assert [stages[s]["order"] for s in listed] == list(range(1, len(listed) + 1))


def test_dp_3_every_approach_uses_a_mode_its_stage_declares():
    preset = _preset()
    from compass_pkg.stable_ids import SPIKE_STAGE_IDS
    for approach, entry in preset["approaches"].items():
        # A spike explores in build and concludes in ship; it has no specify stage.
        wanted = set(SPIKE_STAGE_IDS) if approach == "spike" else set(preset["stages"])
        assert set(entry["stages"]) == wanted, approach
        for stage, mode in entry["stages"].items():
            assert mode in preset["stages"][stage]["modes"], (approach, stage, mode)


def test_dp_3_the_ranks_reproduce_todays_lift_to_full():
    # Today's lift raises collapsed, skipped and lightweight to thorough and
    # leaves every other mode alone; a rank below thorough is one of those
    # three. The path stages declare only `lightweight` of them (ADR-092).
    stages = _preset()["stages"]
    lifted = {mode for entry in stages.values()
              for mode, body in entry["modes"].items()
              if body.get("rank") is not None and body["rank"] < 3}
    assert lifted == {"lightweight"}


# --- no lock (`DP-4`) ---------------------------------------------------------


def test_dp_4_no_entry_is_locked_and_only_the_spike_ships_nothing():
    """No lock exists since 9.0.0 (ADR-094): `never_waived` holds the two hard
    locks of 8.x (`tests/test_check_set.py`), and no entry holds `locked`."""
    preset = _preset()
    assert "locked" not in str(sorted(preset.items()))
    assert _preset()["approaches"]["spike"]["ships"] is False
    assert _preset()["approaches"]["delivery"]["ships"] is True


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
    policy, guardrails = _v8()
    old = _with_old_names(policy)
    assert old != policy
    assert legacy_copy.adapt(old, guardrails) == legacy_copy.adapt(policy, guardrails)


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
    policy, guardrails = _v8()
    old = _old_spellings(policy)
    assert old != policy
    assert legacy_copy.adapt(old, guardrails) == legacy_copy.adapt(policy, guardrails)


def test_dp_5_old_when_keys_in_the_guardrails_file_convert_too():
    policy, guardrails = _v8()
    new = copy.deepcopy(guardrails)
    new["defaults"][4]["applies_when"] = {
        "labels_any": ["auth", "payments", "personal-data", "migrations"]}
    new["checks"]["scenarios-are-executable"]["blocking_when"] = {
        "risk": ["cross-cutting", "critical"]}
    new["defaults"][0]["checked_at"] = ["verify", "ship"]
    assert new != guardrails
    assert legacy_copy.adapt(policy, new) == legacy_copy.adapt(policy, guardrails)


# --- a copied policy converts without losing or failing (`DP-5`) ----------------

def _adapted(policy, guardrails):
    try:
        return legacy_copy.adapt(policy, guardrails)
    except Exception as exc:  # report a failure to convert as a failed assertion
        raise AssertionError(f"the adapter raised {type(exc).__name__}: {exc}")


def test_dp_5_a_cap_with_forbid_route_and_no_worktree_limit_converts():
    policy, guardrails = _v8()
    planted = copy.deepcopy(policy)
    planted["routing_guardrails"]["caps"].append(
        {"id": "RP-CAP-900", "forbid_route": "full", "rationale": "A planted cap."})
    cap = _adapted(planted, guardrails)["rules"]["caps"]["rules"]["RP-CAP-900"]
    assert cap["then"] == {"forbid_approach": "full"}


def test_dp_5_a_role_rule_with_a_gate_and_no_artifact_converts():
    policy, guardrails = _v8()
    planted = copy.deepcopy(policy)
    # A 6.x copy still holds role rules; the adapter converts them as before.
    planted["routing_guardrails"].setdefault("role_rules", []).append(
        {"id": "RP-ROLE-900", "when": {"role": "qa"}, "gate": "verify.claims",
         "rationale": "A planted rule."})
    rule = _adapted(planted, guardrails)["rules"]["role_rules"]["rules"]["RP-ROLE-900"]
    assert rule["then"] == {"gate": "verify.claims"}


def test_dp_5_an_artifact_rule_with_a_gate_and_no_artifact_converts():
    policy, guardrails = _v8()
    planted = copy.deepcopy(policy)
    # 9.0.0 declares no artifact rule (ADR-091); a 7.0.0 copy still holds the block.
    planted["routing_guardrails"].setdefault("artifact_rules", []).append(
        {"id": "RP-ART-900", "when": {"artifacts_any": ["ui-contract"]},
         "gate": "verify.claims", "rationale": "A planted rule."})
    rule = _adapted(planted, guardrails)["rules"]["artifact_rules"]["rules"]["RP-ART-900"]
    assert rule["then"] == {"gate": "verify.claims"}


def test_dp_5_a_shape_with_the_old_phases_block_reads_as_stages():
    policy, guardrails = _v8()
    planted = copy.deepcopy(policy)
    shape = planted["route_shapes"]["regular"]
    shape["phases"] = shape.pop("stages")
    adapted = _adapted(planted, guardrails)
    assert adapted["approaches"]["regular"]["stages"] == policy["route_shapes"]["regular"]["stages"]
    assert adapted == _adapted(policy, guardrails)


def test_dp_5_a_shape_with_no_subtask_ceiling_gets_the_default_of_one():
    policy, guardrails = _v8()
    planted = copy.deepcopy(policy)
    del planted["route_shapes"]["quick-fix"]["subtask_ceiling"]
    del planted["route_shapes"]["full"]["subtask_ceiling"]
    adapted = _adapted(planted, guardrails)["approaches"]
    assert adapted["quick-fix"]["subtask_ceiling"] == 1
    assert adapted["full"]["subtask_ceiling"] == 1


def test_dp_5_the_adapter_leaves_its_input_unchanged():
    policy, guardrails = _v8()
    before = copy.deepcopy((policy, guardrails))
    legacy_copy.adapt(policy, guardrails)
    legacy_copy.adapt_evidence_types(guardrails)
    assert (policy, guardrails) == before


def test_dp_5_no_shipped_code_reads_the_adapter_and_nothing_reads_a_live_preset():
    """The adapter is the test helper `tests/legacy_copy.py` since 9.0.0 stopped
    reading a governance copy (ADR-098), so no shipped file names it. The live
    preset went in 9.0.0 (ADR-094), so no file names it either."""
    hits, preset = [], []
    for top in ("cli", "hooks", "scripts"):
        for path in sorted((ROOT / top).rglob("*")):
            parts = path.relative_to(ROOT).parts
            if not path.is_file() or "vendor" in parts or "__pycache__" in parts:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if "legacy_adapter" in text or "legacy_copy" in text:
                hits.append("/".join(parts))
            if "presets/default/" in text or '"presets", "default")' in text:
                preset.append("/".join(parts))
    assert hits == [], hits
    assert preset == [], preset


def test_dp_5_the_adapter_is_not_in_core_and_core_stays_in_bounds():
    core = (ROOT / "cli" / "compass_pkg" / "core.py").read_text(encoding="utf-8")
    assert len(core.splitlines()) <= 1200
    assert "legacy_adapter" not in core and "legacy_copy" not in core


# --- references and evidence types (`DP-6`) -----------------------------------

def test_dp_6_every_reference_in_the_preset_resolves():
    preset = _preset()
    gates, stages = preset["gates"], preset["stages"]
    artifacts, checks = preset["artifacts"], preset["checks"]
    for approach, entry in preset["approaches"].items():
        for gate in entry["gates"]:
            assert gate in gates, (approach, gate)
        for artifact in entry.get("artifacts") or {}:
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


def test_dp_6_the_checks_declare_their_severity():
    checks = {n: c for n, c in _preset()["checks"].items() if c["kind"] == "deterministic"}
    blocking = checks["scenarios-are-executable"]
    assert blocking["blocking_when"] == {"risk": ["cross-cutting", "critical"]}
    assert all(c["severity"] == ("advisory" if n in legacy_copy.ADVISORY_CHECKS
                                 else "blocking") for n, c in checks.items())


def test_dp_6_every_accepted_type_is_a_declared_evidence_type():
    types = {"evidence_types": check_set.resolved()["evidence_types"]}
    gates = _preset()["gates"]
    for gate in gates.values():
        for accepted in gate.get("accepts", []):
            assert accepted in types["evidence_types"]
    for gate in gates.values():
        if gate.get("accepts"):
            assert gate["kind"] == "review"


def test_dp_6_the_guardrails_apply_to_shipping_and_the_spike_ones_off_ships():
    gates = _preset()["gates"]
    for gid in ("G1", "G2", "G3", "G4", "G5"):
        assert gates[gid]["kind"] == "guardrail"
        assert gates[gid]["applies_to"] == {"ships": True}
    for gid in ("S1", "S2"):
        assert gates[gid]["applies_to"] == {"ships": False}
    assert gates["G5"]["when"] == {
        "labels_any": ["auth", "payments", "personal-data", "migrations"]}


# --- on_skipped and the ranking ruling ----------------------------------------

# Read from the modules that return `NOTHING_TO_CHECK` for the check: checks.py
# (scenarios-are-executable, claim-traces-to-scenario, command-passes),
# borrowed_docs.py, binding.py (evidence-matches-tree), render_check.py,
# landed_by.py, artifact_status.py and evidence_identity.py. The check
# declared-tests-resolve passes with a note instead, so it is `pass`.
EXPECTED_ON_SKIPPED = {
    "scenarios-are-executable": "not-applicable",
    "claim-traces-to-scenario": "not-applicable",
    "command-passes": "not-applicable",
    "borrowed-documents-answered": "not-applicable",
    "evidence-matches-tree": "not-applicable",
    "evidence-identity-matches": "not-applicable",
    "dod-evidence-typed": "not-applicable",
    "landed-by-resolves": "not-applicable",
    "artifacts-approved": "not-applicable",
    "nfr-rows-resolved": "not-applicable",
    "contracts-declared": "not-applicable",
    "design-within-word-ceiling": "not-applicable",
    "acceptance-applicability-agrees": "not-applicable",
    "outer-loop-recorded": "not-applicable",
    "acceptance-support-present": "not-applicable",
    "outer-loop-attempts-recorded": "not-applicable",
    "isolation-proven": "not-applicable",
    "layering-test-passed": "not-applicable",
    "ship-approval-present": "not-applicable",
    "request-recorded": "not-applicable",
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
    # The ruling names the legacy stages. A path stage takes the rank the ruling
    # gives the same mode on a legacy stage it shows (ADR-092).
    from compass_pkg.stable_ids import LEGACY_TO_PATH
    for (stage, mode), rank in RULED_RANKS.items():
        shown = "none" if rank is None else str(rank)
        was = RULING_WORDS.get(mode, mode)
        legacy = [s for s, path in LEGACY_TO_PATH.items() if path == stage]
        assert any(f"| `{s}` | `{was}` | {shown} |" in text for s in legacy), (stage, mode)


