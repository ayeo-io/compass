"""Configuration layers load into a chain and one merge grammar resolves it.

A project extends a parent and states only its differences (ADR-035). The
layers module finds and loads each layer and builds the chain; the merge
module applies the entry and field operations and records where each field
came from. Neither reads the network or writes a file, and merge never
classifies or evaluates.

Scenario ids: `LM-1` to `LM-11` (issue `layers-and-merge`).
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

from compass_pkg import layers, merge  # noqa: E402
from compass_pkg.core import CompassError  # noqa: E402


def _parent():
    """A small parent: two checks, a gate that uses them, an approach."""
    return {
        "checks": {
            "suite-passed": {"statement": "The suite passes.", "kind": "deterministic",
                             "severity": "blocking", "on_skipped": "fail",
                             "accepts": ["test-run"],
                             "params": {"timeout": 60, "retries": 1}},
            "reviewed": {"statement": "A person reviewed it.", "kind": "human",
                         "severity": "advisory", "on_skipped": "pass"},
        },
        "gates": {
            "verify.correctness": {"kind": "review", "checks": ["suite-passed"]},
        },
        "approaches": {
            "regular": {"weight": 2, "stages": {"verify": "full"},
                        "gates": ["verify.correctness"]},
        },
    }


def _config():
    config, _ = merge.apply({}, _parent(), "parent", "root")
    return config


def _code(exc_info):
    return {code for code, _, _ in exc_info.value.errors}


def _write(root, text):
    (root / "compass.yml").write_text(text)


# --- loading (`LM-1`) ------------------------------------------------------------

def test_lm_1_a_project_file_splits_layer_keys_from_settings_keys(tmp_path):
    _write(tmp_path, "schema: 1\nautonomy: balanced\nadoption: enforced\n"
                     "checks:\n  extra:\n    statement: s\n    kind: human\n"
                     "    severity: advisory\n    on_skipped: pass\n")
    layer, settings = layers.load_project_layer(tmp_path)
    assert layer.kind == "project"
    assert set(layer.doc) == {"schema", "checks"}
    assert settings == {"autonomy": "balanced", "adoption": "enforced"}


def test_lm_1_a_duplicate_key_is_refused_naming_the_file(tmp_path):
    _write(tmp_path, "schema: 1\nschema: 1\n")
    with pytest.raises(CompassError) as exc:
        layers.load_project_layer(tmp_path)
    assert "compass.yml" in str(exc.value) and "duplicate key" in str(exc.value)


def test_lm_1_no_project_file_loads_no_layer(tmp_path):
    assert layers.load_project_layer(tmp_path) is None


def test_lm_1_the_project_root_is_the_first_folder_with_compass_or_git(tmp_path):
    (tmp_path / ".git").mkdir()
    inner = tmp_path / "a" / "b"
    inner.mkdir(parents=True)
    (tmp_path / "a" / "compass.yml").write_text("schema: 1\n")  # not the root: ignored
    assert Path(layers.find_project_root(inner)) == tmp_path
    assert layers.load_project_layer(layers.find_project_root(inner)) is None


def test_lm_1_an_issue_layer_is_the_manifests_config(tmp_path):
    manifest = tmp_path / "manifest.yml"
    manifest.write_text("issue: x\nconfig:\n  autonomy: controlled\n")
    layer = layers.load_issue_layer(manifest)
    assert layer.kind == "issue" and layer.doc == {"autonomy": "controlled"}
    manifest.write_text("issue: x\n")
    assert layers.load_issue_layer(manifest) is None


# --- digests (`LM-2`) ------------------------------------------------------------

def test_lm_2_the_digest_ignores_key_order_settings_and_preset():
    one = {"schema": 1, "checks": {"a": {"set": {"severity": "advisory"}}}}
    two = {"checks": {"a": {"set": {"severity": "advisory"}}}, "schema": 1,
           "autonomy": "controlled", "preset": {"note": "x"}}
    assert layers.layer_digest(one) == layers.layer_digest(two)
    assert layers.layer_digest(one).startswith("sha256:")


def test_lm_2_a_changed_catalogue_value_changes_the_digest():
    one = {"checks": {"a": {"set": {"severity": "advisory"}}}}
    two = {"checks": {"a": {"set": {"severity": "blocking"}}}}
    assert layers.layer_digest(one) != layers.layer_digest(two)


# --- the chain (`LM-3`) ----------------------------------------------------------

def test_lm_3_the_chain_runs_parent_then_project_then_issue(tmp_path):
    _write(tmp_path, "schema: 1\nautonomy: balanced\n")
    project, _ = layers.load_project_layer(tmp_path)
    issue = layers.Layer("issue", "issue", {"autonomy": "controlled"},
                         layers.layer_digest({"autonomy": "controlled"}, "issue"))
    chain = layers.build_chain(parent=_parent(), project=project, issue=issue)
    assert [(layer.name, layer.kind) for layer in chain] == [
        ("parent", "parent"), ("project", "project"), ("issue", "issue")]
    assert all(layer.digest.startswith("sha256:") for layer in chain)


def test_lm_3_a_settings_key_in_a_parent_is_refused_by_name():
    with pytest.raises(CompassError) as exc:
        layers.build_chain(parent={"autonomy": "autonomous", "checks": {}})
    assert "autonomy" in str(exc.value) and "parent" in str(exc.value)


def test_lm_3_a_layer_that_fails_its_structural_check_is_refused():
    with pytest.raises(CompassError) as exc:
        layers.build_chain(parent={"checkz": {}})
    assert "checkz" in str(exc.value)


# --- entry operations (`LM-4`) ---------------------------------------------------

def test_lm_4_a_full_entry_adds():
    config, _ = merge.apply(_config(), {"checks": {"lint": {
        "statement": "Lint passes.", "kind": "deterministic",
        "severity": "advisory", "on_skipped": "pass"}}}, "project", "project")
    assert config["checks"]["lint"]["severity"] == "advisory"
    assert "suite-passed" in config["checks"]


def test_lm_4_set_changes_named_fields_only():
    config, _ = merge.apply(_config(), {"checks": {"reviewed": {
        "set": {"severity": "blocking"}}}}, "project", "project")
    assert config["checks"]["reviewed"]["severity"] == "blocking"
    assert config["checks"]["reviewed"]["kind"] == "human"


def test_lm_4_replace_swaps_the_whole_entry():
    config, _ = merge.apply(_config(), {"checks": {"reviewed": {
        "replace": True, "statement": "New.", "kind": "judged",
        "severity": "advisory", "on_skipped": "pass"}}}, "project", "project")
    assert config["checks"]["reviewed"] == {
        "statement": "New.", "kind": "judged", "severity": "advisory",
        "on_skipped": "pass"}


def test_lm_4_remove_deletes_an_unreferenced_entry():
    config, _ = merge.apply(_config(), {"checks": {"reviewed": {"remove": True}}},
                            "project", "project")
    assert "reviewed" not in config["checks"]


def test_lm_4_resolve_applies_the_chain_in_order():
    chain = layers.build_chain(parent=_parent(), project=layers.Layer(
        "project", "project",
        {"checks": {"reviewed": {"set": {"severity": "blocking"}}}}, "sha256:x"))
    config, _ = merge.resolve(chain)
    assert config["checks"]["reviewed"]["severity"] == "blocking"


def test_lm_4_on_a_check_an_entry_level_locked_is_the_locked_field():
    config, _ = merge.apply(_config(), {"checks": {"suite-passed": {"locked": True}}},
                            "parent", "parent")
    assert config["checks"]["suite-passed"]["locked"] is True


# --- field operations (`LM-5`) ---------------------------------------------------

def _set(field, value, catalogue="checks", entry="suite-passed", kind="project"):
    return merge.apply(_config(), {catalogue: {entry: {"set": {field: value}}}},
                       kind, kind)[0][catalogue][entry][field]


def test_lm_5_a_scalar_replaces():
    assert _set("severity", "advisory") == "advisory"


def test_lm_5_a_plain_list_replaces_the_whole_list():
    assert _set("accepts", ["command-output"]) == ["command-output"]


def test_lm_5_a_list_takes_add_and_remove():
    assert _set("accepts", {"add": ["artifact"], "remove": ["test-run"]}) == ["artifact"]
    assert _set("accepts", {"add": ["artifact"]}) == ["test-run", "artifact"]


def test_lm_5_a_plain_map_replaces_the_whole_map():
    assert _set("params", {"timeout": 5}) == {"timeout": 5}


def test_lm_5_a_map_changes_key_by_key():
    assert _set("params", {"set": {"timeout": 5, "extra": 1}, "remove": ["retries"]}) == {
        "timeout": 5, "extra": 1}


# --- provenance (`LM-6`) ---------------------------------------------------------

def test_lm_6_every_resolved_field_names_its_layer_and_operation():
    chain = [layers.Layer("parent", "parent", _parent(), "sha256:p"),
             layers.Layer("project", "project", {"checks": {
                 "reviewed": {"set": {"severity": "blocking"}},
                 "lint": {"statement": "s", "kind": "human", "severity": "advisory",
                          "on_skipped": "pass"}}}, "sha256:q")]
    config, provenance = merge.resolve(chain)
    assert provenance["checks.reviewed.severity"] == {"layer": "project", "operation": "set"}
    assert provenance["checks.reviewed.kind"] == {"layer": "parent", "operation": "add"}
    assert provenance["checks.lint"] == {"layer": "project", "operation": "add"}
    assert provenance["checks.lint.kind"] == {"layer": "project", "operation": "add"}
    for catalogue, entries in config.items():
        for entry_id, entry in entries.items():
            for field in entry:
                assert f"{catalogue}.{entry_id}.{field}" in provenance


def test_lm_6_a_replaced_entry_and_a_removed_one():
    config, provenance = merge.apply(
        _config(), {"checks": {"reviewed": {
            "replace": True, "statement": "n", "kind": "human",
            "severity": "advisory", "on_skipped": "pass"}}}, "project", "project")
    assert provenance["checks.reviewed.statement"]["operation"] == "replace"
    config, provenance = merge.apply(
        {"checks": _config()["checks"]}, {"checks": {"reviewed": {"remove": True}}},
        "project", "project", provenance={"checks.reviewed.kind": {"layer": "p",
                                                                   "operation": "add"}})
    assert not [k for k in provenance if k.startswith("checks.reviewed")]


# --- failures (`LM-7`, `LM-8`, `LM-9`, `LM-10`, `LM-11`) -------------------------

def _fails(layer_doc, code, path_part, kind="project", config=None):
    with pytest.raises(merge.MergeError) as exc:
        merge.apply(_config() if config is None else config, layer_doc, kind, kind)
    assert isinstance(exc.value, CompassError)
    assert code in str(exc.value) and path_part in str(exc.value)
    assert code in _code(exc)
    assert any(path_part in path for c, path, _ in exc.value.errors if c == code)


def test_lm_7_set_on_an_unknown_target():
    _fails({"checks": {"nope": {"set": {"severity": "advisory"}}}},
           "M-SET-UNKNOWN", "checks.nope")


def test_lm_7_replace_on_an_unknown_target():
    _fails({"checks": {"nope": {"replace": True, "statement": "s", "kind": "human",
                                "severity": "advisory", "on_skipped": "pass"}}},
           "M-REPLACE-UNKNOWN", "checks.nope")


def test_lm_7_remove_on_an_unknown_target():
    _fails({"checks": {"nope": {"remove": True}}}, "M-REMOVE-UNKNOWN", "checks.nope")


def test_lm_7_a_full_entry_for_an_id_that_exists():
    _fails({"checks": {"reviewed": {"statement": "s", "kind": "human",
                                    "severity": "advisory", "on_skipped": "pass"}}},
           "M-ADD-EXISTS", "checks.reviewed")


def test_lm_7_a_partial_add():
    _fails({"checks": {"new": {"statement": "s"}}}, "M-ADD-PARTIAL", "checks.new")


def test_lm_7_two_operations_on_one_id():
    _fails({"checks": {"reviewed": {"set": {"severity": "advisory"}, "remove": True}}},
           "M-OP-CONFLICT", "checks.reviewed")
    _fails({"checks": {"reviewed": {"set": {"severity": "advisory"},
                                    "kind": "human"}}},
           "M-OP-CONFLICT", "checks.reviewed")


def test_lm_7_one_id_in_two_split_documents():
    first = {"checks": {"reviewed": {"set": {"severity": "advisory"}}}}
    second = {"checks": {"reviewed": {"set": {"on_skipped": "fail"}}}}
    with pytest.raises(merge.MergeError) as exc:
        merge.combine([first, second])
    assert _code(exc) == {"M-OP-DUPLICATE"}
    assert "checks.reviewed" in str(exc.value)
    assert merge.combine([first, {"gates": {}}]) == {
        "checks": first["checks"], "gates": {}}


def test_lm_7_an_unknown_field_in_set():
    _fails({"checks": {"reviewed": {"set": {"colour": "red"}}}},
           "M-FIELD-UNKNOWN", "checks.reviewed.set.colour")


def test_lm_8_a_list_operation_outside_set():
    _fails({"checks": {"new": {"statement": "s", "kind": "human", "severity": "advisory",
                               "on_skipped": "pass",
                               "accepts": {"add": ["artifact"]}}}},
           "M-LIST-OP-OUTSIDE-SET", "checks.new.accepts")


def test_lm_8_a_map_operation_outside_set():
    _fails({"checks": {"new": {"statement": "s", "kind": "human", "severity": "advisory",
                               "on_skipped": "pass", "params": {"set": {"a": 1}}}}},
           "M-MAP-OP-OUTSIDE-SET", "checks.new.params")


def test_lm_8_removing_an_item_the_list_does_not_hold():
    _fails({"checks": {"suite-passed": {"set": {"accepts": {"remove": ["artifact"]}}}}},
           "M-LIST-REMOVE-ABSENT", "checks.suite-passed.set.accepts")


def test_lm_8_adding_an_item_the_list_holds():
    _fails({"checks": {"suite-passed": {"set": {"accepts": {"add": ["test-run"]}}}}},
           "M-LIST-ADD-PRESENT", "checks.suite-passed.set.accepts")


def test_lm_8_removing_a_map_key_the_map_does_not_hold():
    _fails({"checks": {"suite-passed": {"set": {"params": {"remove": ["nope"]}}}}},
           "M-MAP-REMOVE-ABSENT", "checks.suite-passed.set.params")


def test_lm_8_an_operation_form_with_a_stray_key_is_refused():
    _fails({"checks": {"suite-passed": {"set": {"accepts": {"add": ["a"], "x": 1}}}}},
           "M-FIELD-SHAPE", "checks.suite-passed.set.accepts")


def test_lm_9_an_operation_a_layer_may_not_use():
    _fails({"checks": {"reviewed": {"replace": True, "statement": "n", "kind": "human",
                                    "severity": "advisory", "on_skipped": "pass"}}},
           "M-OP-LAYER", "checks.reviewed.replace", kind="issue")
    _fails({"checks": {"reviewed": {"remove": True}}},
           "M-OP-LAYER", "checks.reviewed.remove", kind="issue")
    _fails({"checks": {"reviewed": {"unlock": True}}},
           "M-OP-LAYER", "checks.reviewed.unlock", kind="parent")


def test_lm_9_a_stages_mode_outside_the_issue_layer():
    stages = {"stages": {"verify": {"order": 7, "modes": {"full": {}}}}}
    config, _ = merge.apply({}, stages, "parent", "parent")
    _fails({"stages": {"verify": {"set": {"mode": "full"}}}},
           "M-FIELD-LAYER", "stages.verify.set.mode", config=config)
    resolved, _ = merge.apply(config, {"stages": {"verify": {"set": {"mode": "full"}}}},
                              "issue", "issue")
    assert resolved["stages"]["verify"]["mode"] == "full"


def test_lm_10_removing_an_entry_something_refers_to_names_each_referrer():
    with pytest.raises(merge.MergeError) as exc:
        merge.apply(_config(), {"checks": {"suite-passed": {"remove": True}}},
                    "project", "project")
    assert _code(exc) == {"M-REF-REMOVED"}
    assert "gates.verify.correctness.checks" in str(exc.value)


def test_lm_10_the_same_layer_may_detach_the_referrer_and_remove():
    config, _ = merge.apply(_config(), {
        "gates": {"verify.correctness": {"set": {"checks": {"remove": ["suite-passed"]}}}},
        "checks": {"suite-passed": {"remove": True}}}, "project", "project")
    assert "suite-passed" not in config["checks"]


def test_lm_10_references_by_map_key_and_scalar_are_found():
    with pytest.raises(merge.MergeError) as exc:
        merge.apply(_config(), {"gates": {"verify.correctness": {"remove": True}}},
                    "project", "project")
    assert "approaches.regular.gates" in str(exc.value)


def test_lm_11_one_error_reports_every_fault_and_inputs_stay_unchanged():
    config = _config()
    before = copy.deepcopy(config)
    layer_doc = {"checks": {"nope": {"set": {"severity": "advisory"}},
                            "reviewed": {"set": {"colour": "red"}},
                            "new": {"statement": "s"}}}
    layer_before = copy.deepcopy(layer_doc)
    with pytest.raises(merge.MergeError) as exc:
        merge.apply(config, layer_doc, "project", "project")
    assert {c for c, _, _ in exc.value.errors} == {
        "M-SET-UNKNOWN", "M-FIELD-UNKNOWN", "M-ADD-PARTIAL"}
    assert config == before and layer_doc == layer_before


# --- review fixes ----------------------------------------------------------------

WORKED = """\
schema: 1
extends: compass:default@6
owner: jed72
autonomy: balanced
checks:
  dor-affected-surface-named:
    set: { severity: advisory }
    waiver:
      reason: "Scenarios are written at plan in this repo."
      approved_by: jed72
      approved_on: 2026-10-05
"""


def test_lm_1_a_project_file_with_a_waiver_date_loads_and_digests(tmp_path):
    _write(tmp_path, WORKED)
    layer, settings = layers.load_project_layer(tmp_path)
    assert layer.digest.startswith("sha256:") and settings == {"autonomy": "balanced"}
    again = layers.layer_digest(layer.doc)
    assert again == layer.digest


def test_lm_1_a_non_mapping_manifest_is_refused(tmp_path):
    manifest = tmp_path / "manifest.yml"
    manifest.write_text("- a\n- b\n")
    with pytest.raises(CompassError):
        layers.load_issue_layer(manifest)
    with pytest.raises(CompassError):
        layers.load_issue_layer(["x"])


def test_lm_1_the_root_walk_uses_the_cores_boundary_markers():
    from compass_pkg.core import BOUNDARY_MARKERS
    assert layers.BOUNDARY_MARKERS is BOUNDARY_MARKERS


def test_lm_2_an_issue_layers_autonomy_changes_its_digest():
    assert layers.layer_digest({"autonomy": "controlled"}, "issue") != \
        layers.layer_digest({"autonomy": "autonomous"}, "issue")


def test_lm_3_build_chain_checks_the_project_and_issue_layers():
    bad = layers.Layer("project", "project", {"checkz": {}}, "sha256:x")
    with pytest.raises(CompassError, match="checkz"):
        layers.build_chain(project=bad)
    bad_issue = layers.Layer("issue", "issue", {"checks": {"a": {"replace": True}}}, "sha256:x")
    with pytest.raises(CompassError, match="replace"):
        layers.build_chain(issue=bad_issue)


def test_lm_3_a_parent_given_as_a_layer_is_checked_like_any_other():
    with_settings = layers.Layer("parent", "parent", {"autonomy": "autonomous"}, "sha256:x")
    with pytest.raises(CompassError, match="autonomy"):
        layers.build_chain(parent=with_settings)
    malformed = layers.Layer("parent", "parent", {"checkz": {}}, "sha256:x")
    with pytest.raises(CompassError, match="checkz"):
        layers.build_chain(parent=malformed)


def test_lm_3_each_layers_kind_must_match_its_slot():
    wrong = layers.Layer("p", "issue", {}, "sha256:x")
    with pytest.raises(CompassError, match="kind"):
        layers.build_chain(parent=wrong)
    with pytest.raises(CompassError, match="kind"):
        layers.build_chain(project=wrong)
    with pytest.raises(CompassError, match="kind"):
        layers.build_chain(issue=layers.Layer("i", "project", {}, "sha256:x"))


def test_lm_4_a_successful_apply_leaves_its_inputs_unchanged():
    config, layer_doc = _config(), {"checks": {"reviewed": {"set": {"severity": "blocking"}}}}
    before, layer_before = copy.deepcopy(config), copy.deepcopy(layer_doc)
    merge.apply(config, layer_doc, "project", "project")
    assert config == before and layer_doc == layer_before


def test_lm_5_a_map_set_keeps_the_keys_it_does_not_name():
    result = _set("params", {"set": {"timeout": 5}})
    assert result == {"timeout": 5, "retries": 1}


def test_lm_5_a_list_add_naming_an_item_twice_is_refused():
    _fails({"checks": {"suite-passed": {"set": {"accepts": {"add": ["a", "a"]}}}}},
           "M-FIELD-SHAPE", "checks.suite-passed.set.accepts")


def test_lm_5_a_map_key_both_set_and_removed_is_refused():
    _fails({"checks": {"suite-passed": {"set": {"params": {
        "set": {"timeout": 2}, "remove": ["timeout"]}}}}},
        "M-OP-CONFLICT", "checks.suite-passed.set.params")


def test_lm_6_removing_a_gate_keeps_the_provenance_of_a_gate_that_shares_its_prefix():
    parent = {"gates": {"verify": {"kind": "review"},
                        "verify.correctness": {"kind": "review"}}}
    config, prov = merge.apply({}, parent, "parent", "parent")
    config, prov = merge.apply(config, {"gates": {"verify": {"remove": True}}},
                               "project", "project", prov)
    assert "gates.verify.correctness.kind" in prov and "gates.verify.correctness" in prov
    assert "gates.verify" not in prov and "gates.verify.kind" not in prov
    config, prov = merge.apply(config, {"gates": {"verify.correctness": {
        "replace": True, "kind": "guardrail"}}}, "project", "project", prov)
    assert prov["gates.verify.correctness.kind"]["layer"] == "project"


def test_lm_6_a_field_a_replacement_drops_loses_its_provenance():
    parent = {"gates": {"g": {"kind": "review", "name": "G"}}}
    config, prov = merge.apply({}, parent, "parent", "parent")
    assert "gates.g.name" in prov
    config, prov = merge.apply(config, {"gates": {"g": {"replace": True, "kind": "review"}}},
                               "project", "project", prov)
    assert "gates.g.name" not in prov
    assert prov["gates.g.kind"] == {"layer": "project", "operation": "replace"}


def test_lm_7_an_empty_replace_is_a_partial_entry():
    _fails({"checks": {"reviewed": {"replace": True}}}, "M-ADD-PARTIAL", "checks.reviewed")


def test_lm_7_a_non_true_operation_value_is_refused():
    _fails({"checks": {"reviewed": {"remove": False}}}, "M-FIELD-SHAPE",
           "checks.reviewed.remove")
    _fails({"checks": {"reviewed": {"replace": "yes", "statement": "n", "kind": "human",
                                    "severity": "advisory", "on_skipped": "pass"}}},
           "M-FIELD-SHAPE", "checks.reviewed.replace")


def test_lm_10_a_map_key_reference_is_found():
    config = {"stages": {"verify": {"order": 7, "modes": {"full": {}}}},
              "approaches": {"regular": {"weight": 1, "stages": {"verify": "full"}}}}
    with pytest.raises(merge.MergeError) as exc:
        merge.apply(config, {"stages": {"verify": {"remove": True}}}, "parent", "parent")
    assert "approaches.regular.stages" in str(exc.value)


def test_lm_10_a_scalar_reference_is_found():
    config = {"approaches": {
        "base": {"weight": 1, "stages": {}},
        "kid": {"weight": 2, "stages": {}, "extends": "base"}}}
    with pytest.raises(merge.MergeError) as exc:
        merge.apply(config, {"approaches": {"base": {"remove": True}}}, "parent", "parent")
    assert "approaches.kid.extends" in str(exc.value)
    config = {"stages": {"verify": {"order": 7, "modes": {}}},
              "gates": {"g": {"kind": "review", "stage": "verify"}}}
    with pytest.raises(merge.MergeError) as exc:
        merge.apply(config, {"stages": {"verify": {"remove": True}}}, "parent", "parent")
    assert "gates.g.stage" in str(exc.value)


def test_lm_10_a_requires_list_names_capabilities_not_checks():
    config = _config()
    config["checks"]["reviewed"]["requires"] = ["suite-passed"]
    config2, _ = merge.apply(config, {"checks": {"suite-passed": {"remove": True}},
                                      "gates": {"verify.correctness": {
                                          "set": {"checks": []}}}}, "project", "project")
    assert "suite-passed" not in config2["checks"]
