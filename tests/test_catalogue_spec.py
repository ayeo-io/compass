"""The configuration catalogues have one field table, a validator and a schema.

The configuration foundation turns delivery approaches, stages, checks,
gates, artifacts, dimensions, rules and display names into eight catalogues
a project extends (ADR-035). Every later piece - the merge, the classifier,
locks, lint - reads their shapes from one table, so that table, a validator
that needs no `jsonschema`, and the schema generated from it come first.

Scenario ids: `CS-1` to `CS-5` (issue `catalogue-spec`).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

from compass_pkg import catalogue_check, catalogue_spec  # noqa: E402
from compass_pkg.core import reading_matches  # noqa: E402


# --- the field table (`CS-1`) ----------------------------------------------------

def test_cs_1_the_table_names_the_eight_catalogues_and_their_fields():
    assert catalogue_spec.CATALOGUES == (
        "dimensions", "stages", "approaches", "rules", "checks", "gates",
        "artifacts", "vocabulary")
    for name in catalogue_spec.CATALOGUES:
        fields = catalogue_spec.FIELDS[name]
        assert fields, name
        for field, spec in fields.items():
            assert spec["merge"] in catalogue_spec.MERGE_KINDS, (name, field)
            assert spec["compare"] in catalogue_spec.COMPARE_KINDS, (name, field)
    assert catalogue_spec.FIELDS["checks"]["accepts"]["compare"] == "way-set"
    assert catalogue_spec.FIELDS["checks"]["severity"]["compare"] == "ordered"
    assert catalogue_spec.FIELDS["approaches"]["weight"]["compare"] == "never"


def test_cs_1_the_shared_obligation_fields_cap_and_capabilities():
    assert catalogue_spec.LABEL_CAP == 8
    assert set(catalogue_spec.CAPABILITIES) == {"entry-exit-evaluation", "artifact-freshness"}
    obligations = catalogue_spec.OBLIGATION_FIELDS
    assert obligations["checks.accepts"] == "way-set"
    assert obligations["checks.approvers"] == "way-set"
    assert obligations["stages.entry"] == "obligation-set"
    assert obligations["checks.kind"] == "identity"
    # Weight orders approaches for floors and is never compared (ADR-037).
    assert not any(key.endswith(".weight") for key in obligations)


# --- the validator (`CS-2`) ----------------------------------------------------------

GOOD = {
    "schema": 1,
    "extends": "compass:default@6",
    "owner": "jed72",
    "autonomy": "balanced",
    "adoption": "enforced",
    "checks": {"CHK-ADR": {"statement": "An ADR records the design decision.",
                           "kind": "evidence", "accepts": ["artifact"],
                           "when": {"risk": {"at_least": "cross-cutting"}},
                           "severity": "blocking", "on_skipped": "fail"}},
    "stages": {"plan": {"set": {"exit": {"add": ["CHK-ADR"]}}}},
}


def test_cs_2_a_well_formed_project_file_passes():
    assert catalogue_check.check_layer(GOOD, "project") == []


@pytest.mark.parametrize("change, named", [
    ({"routes": {}}, "routes"),
    ({"checks": {"CHK-X": {"statment": "typo"}}}, "statment"),
    ({"checks": {"9-bad-id": {"statement": "x"}}}, "9-bad-id"),
    ({"unlocks": ["CHK-ADR"]}, "unlocks"),
])
def test_cs_2_a_bad_project_file_is_refused_by_name(change, named):
    errors = catalogue_check.check_layer({**GOOD, **change}, "project")
    assert any(named in e for e in errors), errors


def test_cs_2_a_settings_key_in_a_parent_is_refused():
    errors = catalogue_check.check_layer({"extends": "compass:default@6",
                                          "adoption": "advisory"}, "parent")
    assert any("adoption" in e and "settings" in e for e in errors), errors
    assert catalogue_check.check_layer({"extends": "compass:default@6",
                                        "preset": {"name": "x"}}, "parent") == []


def test_cs_2_the_issue_layer_takes_only_its_own_keys():
    assert catalogue_check.check_layer(
        {"stages": {"refine": {"set": {"mode": "collapsed"}}}, "autonomy": "controlled",
         "approach": "regular"}, "issue") == []
    errors = catalogue_check.check_layer({"owner": "jed72"}, "issue")
    assert any("owner" in e for e in errors), errors


# --- dimensions (`CS-3`) ------------------------------------------------------------

@pytest.mark.parametrize("entry, named", [
    ({"type": "ranked", "values": ["a"]}, "ranked"),
    ({"type": "ordered-enum", "values": ["a", "b"]}, "tighter"),
    ({"type": "set"}, "open"),
])
def test_cs_3_a_bad_dimension_is_refused(entry, named):
    errors = catalogue_check.check_layer({"dimensions": {"blast": entry}}, "project")
    assert any(named in e for e in errors), errors


def test_cs_3_at_least_needs_an_ordered_dimension():
    doc = {"checks": {"CHK-X": {"statement": "x", "kind": "human", "severity": "advisory",
                                "on_skipped": "pass",
                                "when": {"familiarity": {"at_least": "greenfield"}}}}}
    errors = catalogue_check.check_layer(doc, "project")
    assert any("at_least" in e and "familiarity" in e for e in errors), errors


# --- at_least in when-clauses (`CS-4`) -----------------------------------------------------

def test_cs_4_at_least_matches_by_order():
    when = {"risk": {"at_least": "cross-cutting"}}
    assert reading_matches(when, {"risk": "critical"})
    assert reading_matches(when, {"risk": "cross-cutting"})
    assert not reading_matches(when, {"risk": "contained"})
    assert not reading_matches(when, {"risk": "trivial"})
    orders = {"size": ["s", "m", "l"]}
    assert reading_matches({"size": {"at_least": "m"}}, {"size": "l"}, orders=orders)
    assert not reading_matches({"size": {"at_least": "m"}}, {"size": "s"}, orders=orders)


def test_cs_4_the_existing_forms_match_as_before():
    assert reading_matches({"risk": ["critical", "cross-cutting"]}, {"risk": "critical"})
    assert reading_matches({"labels_any": ["auth"]}, {"labels": ["auth"]})
    assert reading_matches({"any_of": [{"risk": "critical"}, {"labels_any": ["auth"]}]},
                           {"risk": "trivial", "labels": ["auth"]})
    assert not reading_matches({"risk": "critical"}, {"risk": "trivial"})


# --- the generated schema (`CS-5`) ------------------------------------------------------

def test_cs_5_the_committed_schema_is_the_generated_one():
    committed = json.loads((ROOT / "schemas" / "compass.schema.json").read_text(encoding="utf-8"))
    assert committed == catalogue_check.schema(), (
        "schemas/compass.schema.json is out of date; regenerate it with "
        "json.dumps(catalogue_check.schema(), indent=2, sort_keys=True)")


# --- review 1 ----------------------------------------------------------------------

def test_cs_1_the_obligation_table_holds_every_row_adr_037_names():
    # Pinned in full: a missing row compares as equivalent, so a gap here
    # would let a loosening through unseen (ADR-037).
    assert catalogue_spec.OBLIGATION_FIELDS == {
        "approaches.stages": "ordered",
        "approaches.gates": "obligation-set",
        "approaches.artifacts": "obligation-set",
        "approaches.artifacts.depth": "ordered",
        "approaches.checkpoints": "obligation-set",
        "approaches.subtask_ceiling": "ceiling",
        "approaches.ships": "identity",
        "stages.mode": "ordered",
        "stages.order": "identity",
        "stages.entry": "obligation-set",
        "stages.exit": "obligation-set",
        "gates.stage": "identity",
        "gates.checks": "obligation-set",
        "gates.accepts": "way-set",
        "checks.kind": "identity",
        "checks.impl": "identity",
        "checks.params": "ceiling",
        "checks.accepts": "way-set",
        "checks.reviewers": "way-set",
        "checks.approvers": "way-set",
        "checks.inputs": "obligation-set",
        "checks.severity": "ordered",
        "checks.on_skipped": "ordered",
        "checks.statement": "identity",
        "rules.ceilings": "ceiling",
        "evaluation.max_worktrees": "ceiling",
        "evaluation.required_skills": "obligation-set",
        "evaluation.blocked_stages": "obligation-set",
        "evaluation.required_artifacts": "obligation-set",
    }
    assert catalogue_spec.ARTIFACT_DEPTHS == ("light", "full")


def test_cs_2_a_non_string_key_inside_set_is_reported_not_raised():
    errors = catalogue_check.check_layer({"checks": {"CHK-X": {"set": {1: "x"}}}}, "project")
    assert any("checks.CHK-X.set" in e for e in errors), errors


@pytest.mark.parametrize("layer, entry, named", [
    ("issue", {"unlock": True}, "unlock"),
    ("parent", {"unlock": True}, "unlock"),
    ("issue", {"locked": True}, "locked"),
    ("issue", {"remove": True}, "remove"),
    ("issue", {"replace": True, "statement": "x"}, "replace"),
])
def test_cs_2_an_operation_a_layer_may_not_carry_is_refused(layer, entry, named):
    errors = catalogue_check.check_layer({"checks": {"suite-passed": entry}}, layer)
    assert any(named in e and layer in e for e in errors), errors
    assert catalogue_check.check_layer({"checks": {"suite-passed": {"unlock": True}}},
                                       "project") == []


def test_cs_2_unlocks_at_the_top_gets_its_own_message():
    errors = catalogue_check.check_layer({"unlocks": ["x"]}, "project")
    assert any("an unlock sits in the entry" in e for e in errors), errors


@pytest.mark.parametrize("change, named", [
    ({"capabilities": {"entry-exit-evalution": True}}, "entry-exit-evalution"),
    ({"autonomy": "yolo"}, "yolo"),
    ({"adoption": "lax"}, "lax"),
    ({"stages": {"plan": {"set": {"entry": "CHK-X"}}}}, "entry"),
    ({"stages": {"plan": {"order": "four", "modes": {}}}}, "order"),
    ({"checks": {"CHK-X": {"set": {"statment": "x"}}}}, "statment"),
    ({"checks": {"CHK-X": {"set": {"severity": "fatal"}}}}, "fatal"),
    ({"gates": {"G9": {"kind": "wall"}}}, "wall"),
    ({"checks": {"CHK-X": {"set": {"locked": "soft"}}}}, "soft"),
    ({"approvers": {"issue-waivers": ["x"]}}, "issue-waivers"),
])
def test_cs_2_types_and_enumerations_are_checked(change, named):
    errors = catalogue_check.check_layer({**GOOD, **change}, "project")
    assert any(named in e for e in errors), errors


def test_cs_3_values_are_needed_by_every_enum_and_a_declared_order_counts():
    errors = catalogue_check.check_layer({"dimensions": {"blast": {"type": "enum"}}}, "project")
    assert any("values" in e for e in errors), errors
    doc = {"dimensions": {"tier": {"type": "ordered-enum", "values": ["a", "b"],
                                   "tighter": "higher"}},
           "checks": {"CHK-X": {"statement": "x", "kind": "human", "severity": "advisory",
                                "on_skipped": "pass", "when": {"tier": {"at_least": "b"}}}}}
    assert catalogue_check.check_layer(doc, "project") == []
    assert catalogue_check.check_layer(
        {"dimensions": {"risk": {"locked": True}}}, "project") == []


@pytest.mark.parametrize("when", [
    {"risk": {"at_least": "critcal"}},
    {"any_of": [{"familiarity": {"at_least": "greenfield"}}]},
])
def test_cs_3_a_bad_threshold_or_dimension_is_refused_wherever_it_sits(when):
    for catalogue, entry in (
            ("checks", {"statement": "x", "kind": "human", "severity": "advisory",
                        "on_skipped": "pass", "when": when}),
            ("rules", {"kind": "floors", "hit": {}, "rules": {"R-1": {"when": when}}})):
        errors = catalogue_check.check_layer({catalogue: {"E-1": entry}}, "project")
        assert any("at_least" in e for e in errors), (catalogue, errors)


def test_cs_4_orders_given_are_used_even_when_empty_and_reach_any_of():
    assert not reading_matches({"risk": {"at_least": "trivial"}}, {"risk": "critical"},
                               orders={"risk": []})
    orders = {"tier": ["a", "b"]}
    assert reading_matches({"any_of": [{"tier": {"at_least": "b"}}]}, {"tier": "b"},
                           orders=orders)


def test_cs_5_the_schema_checks_inside_set_and_the_enumerations():
    schema = catalogue_check.schema()
    check = schema["properties"]["checks"]["patternProperties"][catalogue_spec.ID_PATTERN]
    assert check["properties"]["set"]["additionalProperties"] is False
    assert check["properties"]["severity"] == {"enum": list(catalogue_spec.SEVERITIES)}
    assert schema["properties"]["autonomy"] == {"enum": list(catalogue_spec.AUTONOMY)}


# --- every documented setting is a settings key ---------------------------------------

def test_governance_drift_is_accepted_and_split_as_a_setting():
    from compass_pkg import layers
    doc = {"schema": 1, "governance_drift": "strict"}
    assert catalogue_check.check_layer(doc, "project") == []
    layer, settings = layers.split_project_file(doc)
    assert settings == {"governance_drift": "strict"}
    assert "governance_drift" not in layer


def test_every_documented_setting_is_a_settings_key():
    import re
    text = (ROOT / "docs" / "configuration.md").read_text(encoding="utf-8")
    table = text.split("## Settings", 1)[1].split("\n###", 1)[0]
    documented = set(re.findall(r"^\| `([a-z_]+)`", table, flags=re.M))
    assert documented - set(catalogue_spec.SETTINGS_KEYS) == set()
