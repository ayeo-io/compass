"""Waivers: shape, authority, approval, the derived covered revision, the
field-level re-check and attribution by residual layer (ADR-039).

The module is pure, so tests pass layer documents, resolved configurations and
an evidence registry as data. `waiver_fixtures` holds the small ones.

Scenario ids: `WV-1` to `WV-8` (issue `waivers`).
"""
from __future__ import annotations

import copy
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

import waiver_fixtures as fx  # noqa: E402


def _api():
    from compass_pkg import waivers
    return waivers


def _codes(findings):
    return sorted(f.code for f in findings)


# --- WV-1: finding a waiver and its shape ----------------------------------------

def test_wv_1_a_set_waiver_gets_an_id_scope_operation_and_fields():
    found, faults = _api().find(fx.severity_layer(fx.project_waiver()), "project")
    assert faults == []
    assert [w.id for w in found] == ["project:checks.tests-pass"]
    w = found[0]
    assert (w.scope, w.catalogue, w.entry, w.operation) == (
        "project", "checks", "tests-pass", "set")
    assert w.fields == ("severity",)


def test_wv_1_replace_names_the_fields_it_writes_and_remove_the_whole_entry():
    api = _api()
    replace = {"checks": {"tests-pass": {
        "replace": True, "statement": "It passed.", "kind": "deterministic",
        "impl": "suite-passed", "severity": "advisory", "on_skipped": "fail",
        "locked": True, "waiver": fx.project_waiver()}}}
    found, _ = api.find(replace, "project")
    assert found[0].operation == "replace"
    assert found[0].fields == ("statement", "kind", "impl", "severity", "on_skipped")
    remove = {"checks": {"no-secrets": {"remove": True, "waiver": fx.project_waiver()}}}
    found, _ = api.find(remove, "project")
    assert found[0].operation == "remove"
    assert found[0].fields == (api.WHOLE_ENTRY,)


def test_wv_1_a_waiver_in_an_entry_with_no_operation_is_a_fault():
    layer = {"checks": {"new-check": {
        "statement": "x", "kind": "deterministic", "severity": "advisory",
        "on_skipped": "fail", "waiver": fx.project_waiver()}}}
    found, faults = _api().find(layer, "project")
    assert found == []
    assert _codes(faults) == ["W-NO-OPERATION"]


def test_wv_1_an_entry_with_no_waiver_is_not_a_waiver():
    found, faults = _api().find(fx.severity_layer(None), "project")
    assert (found, faults) == ([], [])


def _shape(layer, scope="project", today=fx.TODAY):
    api = _api()
    found, faults = api.find(layer, scope)
    assert not faults, faults
    return api.check_shape(found[0], today)


def test_wv_1_a_complete_project_waiver_has_no_shape_finding():
    assert _shape(fx.severity_layer(fx.project_waiver())) == []


@pytest.mark.parametrize("over,code", [
    ({"reason": ""}, "W-REASON"),
    ({"reason": None}, "W-REASON"),
    ({"approved_by": ""}, "W-APPROVED-BY"),
    ({"approved_by": None}, "W-APPROVED-BY"),
    ({"approved_on": None}, "W-APPROVED-ON-MISSING"),
    ({"approved_on": date(2026, 10, 8)}, "W-APPROVED-ON-FUTURE"),
    ({"approved_on": "2026-10-08"}, "W-APPROVED-ON-FUTURE"),
    ({"approved_on": "last tuesday"}, "W-APPROVED-ON-FORM"),
])
def test_wv_1_project_waiver_shape_faults(over, code):
    findings = _shape(fx.severity_layer(fx.project_waiver(**over)))
    assert _codes(findings) == [code]
    assert findings[0].level == "error"


def test_wv_1_today_is_a_valid_approval_date_and_a_string_date_is_read():
    assert _shape(fx.severity_layer(fx.project_waiver(approved_on=fx.TODAY))) == []
    assert _shape(fx.severity_layer(fx.project_waiver(approved_on="2026-10-07"))) == []


def test_wv_1_an_issue_waiver_has_reason_and_approver_and_no_date():
    assert _shape(fx.severity_layer(fx.issue_waiver()), "issue") == []
    bad = fx.issue_waiver(approved_on=date(2026, 10, 5))
    assert _codes(_shape(fx.severity_layer(bad), "issue")) == ["W-APPROVED-ON-ISSUE"]


@pytest.mark.parametrize("key", ["covers", "approvals", "id"])
def test_wv_1_no_other_key_is_allowed_so_covers_is_a_fault(key):
    waiver = fx.project_waiver(**{key: "sha256:abc"})
    assert _codes(_shape(fx.severity_layer(waiver))) == ["W-KEY-UNKNOWN"]


def test_wv_1_a_legacy_waiver_is_accepted_with_a_warning_and_unapproved_is_not():
    legacy = fx.project_waiver(approved_by="LEGACY", approved_on=None)
    findings = _shape(fx.severity_layer(legacy))
    assert _codes(findings) == ["W-LEGACY"]
    assert findings[0].level == "warning"
    assert "no approval recorded" in findings[0].message
    dated = fx.project_waiver(approved_by="LEGACY")
    assert "W-LEGACY-DATED" in _codes(_shape(fx.severity_layer(dated)))
    unapproved = fx.project_waiver(approved_by="UNAPPROVED", approved_on=None)
    assert "W-UNAPPROVED" in _codes(_shape(fx.severity_layer(unapproved)))


# --- WV-2: authority -------------------------------------------------------------

def _waiver(scope, **over):
    api = _api()
    layer = fx.severity_layer(fx.issue_waiver(**over) if scope == "issue"
                              else fx.project_waiver(**over))
    found, faults = api.find(layer, scope)
    assert not faults
    return found[0]


def test_wv_2_an_issue_waiver_takes_the_project_list_or_the_owner():
    api = _api()
    listed = {"owner": "jed72", "approvers": {"issue-waiver": ["qa-lead", "jed72"]}}
    assert api.allowed_approvers(_waiver("issue"), listed, None) == (
        ["qa-lead", "jed72"], None)
    assert api.allowed_approvers(_waiver("issue"), {"owner": "jed72"}, None) == (
        ["jed72"], None)


def test_wv_2_a_project_waiver_takes_the_parents_list_or_the_project_owner():
    api = _api()
    parent = {"approvers": {"project-waiver": ["steward"]}}
    project = {"owner": "jed72", "approvers": {"issue-waiver": ["qa-lead"]}}
    assert api.allowed_approvers(_waiver("project"), project, parent) == (
        ["steward"], None)
    assert api.allowed_approvers(_waiver("project"), project, {}) == (["jed72"], None)
    assert api.allowed_approvers(_waiver("project"), project, None) == (["jed72"], None)


def test_wv_2_the_other_kinds_list_is_never_read():
    api = _api()
    project = {"owner": "jed72", "approvers": {"project-waiver": ["steward"]}}
    assert api.allowed_approvers(_waiver("issue"), project, None)[0] == ["jed72"]
    parent = {"approvers": {"issue-waiver": ["qa-lead"]}}
    assert api.allowed_approvers(_waiver("project"), {"owner": "jed72"}, parent)[0] == [
        "jed72"]


@pytest.mark.parametrize("scope", ["issue", "project"])
@pytest.mark.parametrize("project", [None, {}, {"approvers": {"issue-waiver": ["x"]}}])
def test_wv_2_no_owner_fails_whatever_lists_exist(scope, project):
    parent = {"approvers": {"project-waiver": ["steward"]}}
    names, finding = _api().allowed_approvers(_waiver(scope), project, parent)
    assert names == []
    assert finding.code == "W-NO-OWNER" and finding.level == "error"
    assert "owner" in finding.message


def test_wv_2_a_list_that_is_not_a_list_of_names_is_a_fault():
    names, finding = _api().allowed_approvers(
        _waiver("issue"), {"owner": "jed72", "approvers": {"issue-waiver": "jed72"}}, None)
    assert names == [] and finding.code == "W-APPROVERS-SHAPE"


def test_wv_2_a_project_waiver_passes_when_its_approver_is_allowed():
    project = {"owner": "jed72"}
    assert _api().check(_waiver("project"), today=fx.TODAY, project=project,
                        parent=None) == []


def test_wv_2_a_project_waiver_fails_when_its_approver_is_not_allowed():
    project = {"owner": "jed72"}
    findings = _api().check(_waiver("project", approved_by="mallory"), today=fx.TODAY,
                            project=project, parent=None)
    assert _codes(findings) == ["W-APPROVER-NOT-ALLOWED"]
    assert "jed72" in findings[0].message and "mallory" in findings[0].message


def test_wv_2_the_parents_list_replaces_the_owner_for_a_project_waiver():
    project, parent = {"owner": "jed72"}, {"approvers": {"project-waiver": ["steward"]}}
    api = _api()
    assert _codes(api.check(_waiver("project"), today=fx.TODAY, project=project,
                            parent=parent)) == ["W-APPROVER-NOT-ALLOWED"]
    assert api.check(_waiver("project", approved_by="steward"), today=fx.TODAY,
                     project=project, parent=parent) == []


def test_wv_2_a_shape_fault_ends_the_check_before_authority():
    findings = _api().check(_waiver("project", reason=""), today=fx.TODAY,
                            project={}, parent=None)
    assert _codes(findings) == ["W-REASON"]


def test_wv_2_a_legacy_waiver_is_a_warning_and_never_asks_for_an_approver():
    legacy = _waiver("project", approved_by="LEGACY", approved_on=None)
    findings = _api().check(legacy, today=fx.TODAY, project={"owner": "jed72"},
                            parent=None)
    assert _codes(findings) == ["W-LEGACY"]


# --- WV-3: the approval record for an issue waiver --------------------------------

DESCRIBED = {"id": "issue:checks.tests-pass", "fields": {"severity": {"from": "blocking", "to": "advisory"}}}
OWNER = {"owner": "jed72"}


def _issue_check(registry, described=DESCRIBED, project=OWNER, **over):
    return _api().check(_waiver("issue", **over), today=fx.TODAY, project=project,
                        parent=None, registry=registry, described=described)


def test_wv_3_a_matching_approval_record_passes():
    assert _issue_check([fx.approval()]) == []


def test_wv_3_the_record_is_found_by_the_id_the_waiver_names():
    other = fx.approval(id="EV-2", approver="mallory")
    assert _issue_check([other, fx.approval()]) == []
    assert _codes(_issue_check([other])) == ["W-APPROVAL-MISSING"]
    assert _codes(_issue_check([])) == ["W-APPROVAL-MISSING"]


@pytest.mark.parametrize("over,code", [
    ({"type": "test-run"}, "W-APPROVAL-TYPE"),
    ({"decision": "rejected"}, "W-APPROVAL-DECISION"),
    ({"decision": None}, "W-APPROVAL-DECISION"),
    ({"role": None}, "W-APPROVAL-FIELDS"),
    ({"approver": None}, "W-APPROVAL-FIELDS"),
    ({"scope": None}, "W-APPROVAL-FIELDS"),
    ({"timestamp": None}, "W-APPROVAL-FIELDS"),
    ({"approver": "mallory"}, "W-APPROVER-NOT-ALLOWED"),
    ({"waiver": None}, "W-APPROVAL-WAIVER"),
])
def test_wv_3_a_record_that_is_not_an_approval_by_an_allowed_person(over, code):
    record = fx.approval()
    record.update(over)
    record = {k: v for k, v in record.items() if v is not None}
    assert _codes(_issue_check([record])) == [code]


@pytest.mark.parametrize("change", [
    lambda w: w.update(scope="project"),
    lambda w: w.update(entry="checks.no-secrets"),
    lambda w: w["fields"].update(on_skipped={"from": "fail", "to": "pass"}),
    lambda w: w["fields"].pop("severity"),
    lambda w: w["fields"]["severity"].update(to="blocking"),
    lambda w: w["fields"]["severity"].update({"from": "advisory"}),
])
def test_wv_3_the_record_must_name_this_waivers_entry_and_values(change):
    record = fx.approval()
    change(record["waiver"])
    findings = _issue_check([record])
    assert _codes(findings) == ["W-APPROVAL-WAIVER"]
    assert "tests-pass" in findings[0].message


def test_wv_3_the_issue_list_decides_who_may_approve_the_record():
    project = {"owner": "jed72", "approvers": {"issue-waiver": ["qa-lead"]}}
    assert _codes(_issue_check([fx.approval()], project=project)) == [
        "W-APPROVER-NOT-ALLOWED"]
    assert _issue_check([fx.approval(approver="qa-lead")], project=project) == []


def test_wv_3_without_the_derived_values_the_record_cannot_be_matched():
    assert _codes(_issue_check([fx.approval()], described=None)) == [
        "W-APPROVAL-UNCHECKED"]


# --- WV-4: the derived covered revision and the recorded parent values -----------

def test_wv_4_a_project_waiver_covers_the_extends_pin():
    api = _api()
    assert api.covered_revision("project", extends="compass:default@6") == {
        "kind": "parent", "ref": "compass:default@6"}
    mapped = {"from": "github:acme/rules#4f2a9c1", "approved_by": "jed72"}
    assert api.covered_revision("project", extends=mapped) == {
        "kind": "parent", "ref": "github:acme/rules#4f2a9c1"}
    assert api.covered_revision("project") is None


def test_wv_4_an_issue_waiver_covers_the_generations_project_revision():
    api = _api()
    versions = {"project": {"digest": "sha256:a71e"}, "resolver": "1.0.0"}
    assert api.covered_revision("issue", versions=versions) == {
        "kind": "project-revision", "digest": "sha256:a71e"}
    assert api.covered_revision("issue", versions={"resolver": "1.0.0"}) is None
    assert api.covered_revision("issue") is None


def _described(scope="project", layer=None, **over):
    api = _api()
    parent = fx.parent_config()
    layer = layer or fx.severity_layer(
        fx.project_waiver() if scope == "project" else fx.issue_waiver())
    found, faults = api.find(layer, scope)
    assert not faults
    child = fx.resolve(parent, layer, "project" if scope == "project" else "issue")
    return api.describe(found[0], parent, child, {"kind": "parent", "ref": "p@1"}), \
        parent, child


def test_wv_4_the_record_holds_the_parent_value_and_the_new_value_of_each_field():
    record, _, _ = _described()
    assert record == {
        "id": "project:checks.tests-pass", "scope": "project",
        "entry": "checks.tests-pass", "operation": "set",
        "fields": {"severity": {"from": "blocking", "to": "advisory"}},
        "approved_by": "jed72", "approved_on": "2026-10-05",
        "covered": {"kind": "parent", "ref": "p@1"}}


def test_wv_4_an_issue_record_has_no_date_and_never_a_covers_key():
    record, _, _ = _described("issue")
    assert "approved_on" not in record and "covers" not in record
    assert record["approved_by"] == "EV-1" and record["scope"] == "issue"
    assert "covers" not in _described()[0]


def test_wv_4_a_list_field_is_recorded_whole_and_an_absent_one_as_none():
    layer = {"checks": {"tests-pass": {
        "set": {"accepts": ["test-run", "manual-review"], "reviewers": ["qa"]},
        "waiver": fx.project_waiver()}}}
    parent = fx.parent_config()
    parent["checks"]["tests-pass"]["accepts"] = ["test-run"]
    found, _ = _api().find(layer, "project")
    child = fx.resolve(parent, layer)
    fields = _api().describe(found[0], parent, child, None)["fields"]
    assert fields == {
        "accepts": {"from": ["test-run"], "to": ["test-run", "manual-review"]},
        "reviewers": {"from": None, "to": ["qa"]}}


def test_wv_4_a_removed_entry_records_the_whole_parent_entry():
    layer = {"checks": {"no-secrets": {"remove": True, "waiver": fx.project_waiver()}}}
    layer["gates"] = {"verify.security": {"set": {"checks": {"remove": ["no-secrets"]}}}}
    parent = fx.parent_config()
    found, _ = _api().find(layer, "project")
    child = fx.resolve(parent, layer)
    fields = _api().describe(found[0], parent, child, None)["fields"]
    assert fields == {"(entry)": {"from": parent["checks"]["no-secrets"], "to": None}}


def test_wv_4_the_record_shares_nothing_with_the_configurations():
    record, parent, _ = _described()
    record["fields"]["severity"]["from"] = "changed"
    assert parent["checks"]["tests-pass"]["severity"] == "blocking"


# --- WV-5: the field-level re-check when a revision moves --------------------------

def _record(layer=None, scope="project"):
    return _described(scope, layer)[0]


def test_wv_5_an_unchanged_parent_invalidates_nothing():
    assert _api().recheck([_record()], fx.parent_config()) == []


def test_wv_5_a_changed_waived_field_names_entry_field_old_new_and_project_value():
    moved = fx.parent_config()
    moved["checks"]["tests-pass"]["severity"] = "advisory-plus"
    found = _api().recheck([_record()], moved)
    assert len(found) == 1
    inv = found[0]
    assert (inv.waiver_id, inv.entry, inv.field) == (
        "project:checks.tests-pass", "checks.tests-pass", "severity")
    assert (inv.old, inv.new, inv.project) == ("blocking", "advisory-plus", "advisory")
    for part in ("checks.tests-pass", "severity", "blocking", "advisory-plus", "advisory"):
        assert part in inv.reason


def test_wv_5_a_change_anywhere_else_invalidates_nothing():
    moved = fx.parent_config()
    moved["checks"]["tests-pass"]["on_skipped"] = "pass"        # same entry, other field
    moved["checks"]["no-secrets"]["severity"] = "advisory"      # other entry
    moved["gates"]["verify.correctness"]["accepts"].append("manual-review")
    moved["rules"]["floors"]["rules"]["F-1"]["order"] = 7
    assert _api().recheck([_record()], moved) == []


def test_wv_5_a_list_field_compares_as_a_whole_list():
    api = _api()
    layer = {"checks": {"tests-pass": {"set": {"accepts": ["test-run", "manual-review"]},
                                       "waiver": fx.project_waiver()}}}
    parent = fx.parent_config()
    parent["checks"]["tests-pass"]["accepts"] = ["test-run", "command-output"]
    found, _ = api.find(layer, "project")
    record = api.describe(found[0], parent, fx.resolve(parent, layer), None)
    assert api.recheck([record], copy.deepcopy(parent)) == []
    moved = copy.deepcopy(parent)
    moved["checks"]["tests-pass"]["accepts"].append("security-review")
    found = api.recheck([record], moved)
    assert [i.field for i in found] == ["accepts"]
    assert found[0].old == ["test-run", "command-output"]
    assert found[0].new == ["test-run", "command-output", "security-review"]
    assert found[0].project == ["test-run", "manual-review"]


def test_wv_5_each_differing_field_is_one_invalidation_in_field_order():
    layer = {"checks": {"tests-pass": {
        "set": {"severity": "advisory", "on_skipped": "pass"},
        "waiver": fx.project_waiver()}}}
    moved = fx.parent_config()
    moved["checks"]["tests-pass"]["severity"] = "x"
    moved["checks"]["tests-pass"]["on_skipped"] = "y"
    assert [i.field for i in _api().recheck([_record(layer)], moved)] == [
        "severity", "on_skipped"]
    moved["checks"]["tests-pass"]["severity"] = "blocking"
    assert [i.field for i in _api().recheck([_record(layer)], moved)] == ["on_skipped"]


def test_wv_5_an_entry_the_new_parent_no_longer_defines_invalidates_the_waiver():
    moved = fx.parent_config()
    del moved["checks"]["tests-pass"]
    found = _api().recheck([_record()], moved)
    assert len(found) == 1 and found[0].field is None
    assert found[0].new is None
    assert "no longer defines" in found[0].reason


def test_wv_5_a_removed_entry_waiver_is_invalidated_by_any_change_to_the_entry():
    layer = {"checks": {"no-secrets": {"remove": True, "waiver": fx.project_waiver()}},
             "gates": {"verify.security": {"set": {"checks": {"remove": ["no-secrets"]}}}}}
    record = _record(layer)
    assert _api().recheck([record], fx.parent_config()) == []
    moved = fx.parent_config()
    moved["checks"]["no-secrets"]["severity"] = "advisory"
    found = _api().recheck([record], moved)
    assert [i.field for i in found] == ["(entry)"]


def test_wv_5_an_issue_record_is_rechecked_the_same_way():
    record = _record(scope="issue")
    moved = fx.parent_config()
    moved["checks"]["tests-pass"]["severity"] = "advisory"
    found = _api().recheck([record], moved)
    assert [i.waiver_id for i in found] == ["issue:checks.tests-pass"]


def test_wv_5_the_recheck_reads_and_changes_nothing_it_is_given():
    record, moved = _record(), fx.parent_config()
    moved["checks"]["tests-pass"]["severity"] = "z"
    before = (copy.deepcopy(record), copy.deepcopy(moved))
    _api().recheck([record], moved)
    assert (record, moved) == before


# --- WV-6: attribution by residual layer -------------------------------------------

def _attribute(layer, scope="project", kind="project", parent=None, **kwargs):
    api = _api()
    parent = parent or fx.parent_config()
    waivers, faults = api.find(layer, scope)
    assert not faults
    child = fx.resolve(parent, layer, kind)
    return api.attribute(parent, child, waivers, **kwargs)


def _waived_severity():
    return {"set": {"severity": "advisory"}, "waiver": fx.project_waiver()}


def test_wv_6_a_waived_loosening_is_excused_for_the_fields_it_changes():
    layer = {"checks": {"tests-pass": _waived_severity()}}
    result = _attribute(layer)
    assert result.result == "excused"
    assert result.refusal is None
    assert result.excused == {"project:checks.tests-pass": ["severity"]}
    assert result.residual.result == "equivalent"
    assert result.unneeded == []


def test_wv_6_the_unwaived_part_of_the_layer_is_what_gets_classified():
    layer = {"checks": {
        "tests-pass": _waived_severity(),
        "extra": {"statement": "x", "kind": "deterministic", "impl": "suite-passed",
                  "severity": "blocking", "on_skipped": "fail"}},
        "gates": {"verify.correctness": {"set": {"checks": {"add": ["extra"]}}}}}
    result = _attribute(layer)
    assert result.residual.result == "tightening"
    assert result.result == "excused"


def test_wv_6_an_unwaived_loosening_is_refused_with_its_point_and_values():
    layer = {"checks": {"tests-pass": _waived_severity(),
                        "no-secrets": {"set": {"on_skipped": "pass"}}}}
    result = _attribute(layer)
    assert result.result == "refused"
    assert result.excused == {}
    assert result.refusal["result"] == "loosening"
    change = result.refusal["point"]["changes"][0]
    assert change["field"] == "checks.on_skipped" and change["key"] == "no-secrets"
    assert (change["parent"], change["child"]) == ("fail", "pass")
    assert "no-secrets" in result.refusal["reason"]


def test_wv_6_a_waiver_on_one_entry_never_excuses_another_entry():
    layer = {"checks": {"tests-pass": _waived_severity(),
                        "no-secrets": {"set": {"severity": "advisory"}}}}
    result = _attribute(layer)
    assert result.result == "refused"
    assert result.refusal["point"]["changes"][0]["key"] == "no-secrets"


def test_wv_6_an_unwaived_change_that_cannot_be_compared_is_refused():
    layer = {"checks": {"tests-pass": _waived_severity(),
                        "no-secrets": {"set": {"impl": "suite-passed"}}}}
    result = _attribute(layer)
    assert result.result == "refused"
    assert result.refusal["result"] == "incomparable"


def test_wv_6_a_layer_with_no_waiver_is_classified_as_it_is():
    api = _api()
    loosen = {"checks": {"tests-pass": {"set": {"severity": "advisory"}}}}
    assert _attribute(loosen).result == "refused"
    tighten = {"checks": {"x": {"statement": "x", "kind": "deterministic",
                                "impl": "suite-passed", "severity": "blocking",
                                "on_skipped": "fail"}},
               "gates": {"verify.correctness": {"set": {"checks": {"add": ["x"]}}}}}
    result = _attribute(tighten)
    assert result.result == "accepted" and result.excused == {}
    assert api.attribute(fx.parent_config(), fx.parent_config(), []).result == "accepted"


def test_wv_6_a_waived_detach_of_a_check_from_its_gate_is_excused():
    layer = {"gates": {"verify.security": {
        "set": {"checks": {"remove": ["no-secrets"]}},
        "waiver": fx.project_waiver()}}}
    result = _attribute(layer)
    assert result.result == "excused"
    assert result.excused == {"project:gates.verify.security": ["checks"]}


def test_wv_6_a_waived_removal_is_excused_for_the_whole_entry():
    layer = {"checks": {"no-secrets": {"remove": True, "waiver": fx.project_waiver()}},
             "gates": {"verify.security": {"set": {"checks": {"remove": ["no-secrets"]}},
                                           "waiver": fx.project_waiver()}}}
    result = _attribute(layer)
    assert result.result == "excused"
    assert result.excused == {"project:checks.no-secrets": ["(entry)"],
                              "project:gates.verify.security": ["checks"]}
    assert result.unneeded == []        # neither can stand alone, so both stay
    unwaived_detach = copy.deepcopy(layer)
    del unwaived_detach["gates"]["verify.security"]["waiver"]
    assert _attribute(unwaived_detach).result == "refused"


def test_wv_6_an_issue_waiver_on_a_stage_mode_is_attributed_the_same_way():
    layer = {"stages": {"verify": {"set": {"mode": "light"},
                                   "waiver": fx.issue_waiver()}}}
    result = _attribute(layer, scope="issue", kind="issue")
    assert result.result == "excused"
    assert result.excused == {"issue:stages.verify": ["mode"]}
    unwaived = {"stages": {"verify": {"set": {"mode": "light"}}}}
    assert _attribute(unwaived, scope="issue", kind="issue").result == "refused"


def test_wv_6_a_refusal_costs_one_classification_and_names_nothing_waived(monkeypatch):
    from compass_pkg import classify as real
    calls = []
    monkeypatch.setattr(_api(), "_classify",
                        lambda *a, **k: calls.append(1) or real.classify(*a, **k))
    layer = {"checks": {"tests-pass": _waived_severity(),
                        "no-secrets": {"set": {"severity": "advisory"}}}}
    _attribute(layer)
    assert len(calls) == 1


# --- WV-7: the unneeded-waiver warning ---------------------------------------------

def _tightening_gate_waiver():
    return {"gates": {"verify.correctness": {
        "set": {"checks": {"add": ["no-secrets"]}}, "waiver": fx.project_waiver()}}}


def test_wv_7_a_waiver_on_a_change_that_loosens_nothing_is_unneeded():
    result = _attribute(_tightening_gate_waiver())
    assert result.result == "excused"
    assert result.unneeded == ["project:gates.verify.correctness"]


def test_wv_7_a_waiver_on_a_change_with_no_effect_is_unneeded():
    layer = {"checks": {"tests-pass": {"set": {"severity": "blocking"},
                                       "waiver": fx.project_waiver()}}}
    assert _attribute(layer).unneeded == ["project:checks.tests-pass"]


def test_wv_7_a_needed_waiver_is_not_reported():
    assert _attribute({"checks": {"tests-pass": _waived_severity()}}).unneeded == []


def test_wv_7_each_waiver_is_judged_alone_so_only_the_idle_one_is_reported():
    layer = _tightening_gate_waiver()
    layer["checks"] = {"tests-pass": _waived_severity()}
    result = _attribute(layer)
    assert result.unneeded == ["project:gates.verify.correctness"]
    assert sorted(result.excused) == ["project:checks.tests-pass",
                                      "project:gates.verify.correctness"]


def test_wv_7_two_needed_waivers_are_both_kept():
    layer = {"checks": {"tests-pass": _waived_severity(),
                        "no-secrets": {"set": {"severity": "advisory"},
                                       "waiver": fx.project_waiver()}}}
    result = _attribute(layer)
    assert result.result == "excused" and result.unneeded == []


def test_wv_7_the_cost_is_one_classification_per_waiver_plus_one(monkeypatch):
    from compass_pkg import classify as real
    calls = []
    monkeypatch.setattr(_api(), "_classify",
                        lambda *a, **k: calls.append(1) or real.classify(*a, **k))
    layer = _tightening_gate_waiver()
    layer["checks"] = {"tests-pass": _waived_severity()}
    _attribute(layer)
    assert len(calls) == 3


def test_wv_7_no_waiver_means_no_extra_classification(monkeypatch):
    from compass_pkg import classify as real
    calls = []
    monkeypatch.setattr(_api(), "_classify",
                        lambda *a, **k: calls.append(1) or real.classify(*a, **k))
    _attribute({"checks": {"tests-pass": {"set": {"severity": "blocking"}}}})
    assert len(calls) == 1


# --- WV-8: the module's declarations ------------------------------------------------

MODULE = ROOT / "cli" / "compass_pkg" / "waivers.py"


def test_wv_8_the_module_declares_its_dependencies():
    text = MODULE.read_text(encoding="utf-8")
    header = text.split("from __future__", 1)[0]
    assert "# DEPENDENCY:" in header
    assert "compass_pkg.classify" in header and "compass_pkg.catalogue_spec" in header


def test_wv_8_the_module_is_pure():
    """It reads no file and writes none: an approvals directory would need one."""
    import re
    text = MODULE.read_text(encoding="utf-8")
    code = "\n".join(line for line in text.splitlines()
                     if not line.lstrip().startswith("#"))
    for pattern in (r"\bimport os\b", r"\bopen\(", r"\bPath\(", r"\bimport yaml\b",
                    r"\bsubprocess\b", r"\bpathlib\b"):
        assert not re.search(pattern, code), pattern


def test_wv_8_only_locks_imports_it_and_no_command_exposes_it():
    import re
    pattern = re.compile(r"^\s*(from compass_pkg import [^\n]*\bwaivers\b|"
                         r"from compass_pkg\.waivers import|import compass_pkg\.waivers)",
                         re.M)
    users = []
    for path in sorted((ROOT / "cli").rglob("*.py")):
        if path.name == "waivers.py" or "vendor" in path.parts:
            continue
        if pattern.search(path.read_text(encoding="utf-8")):
            users.append(path.name)
    # locks.py routes an unlock through `check` (ADR-039).
    assert users == ["locks.py"], users
    for name in ("cli/compass", "cli/compass_pkg/_all.py"):
        assert "waivers" not in (ROOT / name).read_text(encoding="utf-8"), name
    core = (ROOT / "cli" / "compass_pkg" / "core.py").read_text(encoding="utf-8")
    assert len(core.splitlines()) <= 1200


def test_wv_8_there_is_no_approvals_directory_and_no_covers_field():
    assert not (ROOT / "approvals").exists()
    assert not (ROOT / ".compass" / "approvals").exists()
    from compass_pkg import catalogue_spec
    for fields in catalogue_spec.FIELDS.values():
        assert "covers" not in fields


def test_wv_8_the_owning_doc_names_the_module_and_exists():
    readme = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    rows = [line for line in readme.splitlines()
            if line.startswith("|") and "cli/compass_pkg/waivers.py" in line]
    assert len(rows) == 1, "docs/README.md needs one owning-doc row for waivers.py"
    owner = rows[0].split("|")[2].strip().strip("`")
    assert owner == "architecture/decisions/ADR-039-waivers-locks-and-unlocks.md"
    assert (ROOT / owner).is_file(), owner


def test_wv_4_a_list_in_the_record_is_a_copy_not_the_configurations_list():
    api = _api()
    layer = {"checks": {"tests-pass": {"set": {"accepts": ["test-run"]},
                                       "waiver": fx.project_waiver()}}}
    parent = fx.parent_config()
    parent["checks"]["tests-pass"]["accepts"] = ["command-output"]
    child = fx.resolve(parent, layer)
    found, _ = api.find(layer, "project")
    record = api.describe(found[0], parent, child, None)
    record["fields"]["accepts"]["from"].append("planted")
    record["fields"]["accepts"]["to"].append("planted")
    assert parent["checks"]["tests-pass"]["accepts"] == ["command-output"]
    assert child["checks"]["tests-pass"]["accepts"] == ["test-run"]


# --- review fixes -----------------------------------------------------------------

def test_wv_1_legacy_is_a_project_shape_only_so_an_issue_waiver_with_it_is_a_fault():
    findings = _shape(fx.severity_layer(fx.issue_waiver(approved_by="LEGACY")), "issue")
    assert "W-LEGACY-ISSUE" in _codes(findings)
    assert all(f.level == "error" for f in findings)


def test_wv_3_an_issue_waiver_with_legacy_gets_no_approval_from_it():
    findings = _api().check(_waiver("issue", approved_by="LEGACY"), today=fx.TODAY,
                            project={}, parent=None, registry=[], described=DESCRIBED)
    assert "W-LEGACY-ISSUE" in _codes(findings)
    findings = _api().check(_waiver("issue", approved_by="LEGACY"), today=fx.TODAY,
                            project=OWNER, parent=None, registry=[], described=DESCRIBED)
    assert any(f.level == "error" for f in findings)


def test_wv_1_locked_beside_a_set_is_not_a_waived_field():
    layer = {"checks": {"tests-pass": {
        "set": {"severity": "advisory", "locked": True},
        "waiver": fx.project_waiver()}}}
    found, _ = _api().find(layer, "project")
    assert found[0].fields == ("severity",)


@pytest.mark.parametrize("approvers", [["x"], "x", 3])
@pytest.mark.parametrize("scope", ["issue", "project"])
def test_wv_2_a_malformed_approvers_key_is_a_finding_not_a_crash(scope, approvers):
    layer = {"owner": "jed72", "approvers": approvers}
    names, finding = _api().allowed_approvers(_waiver(scope), layer, layer)
    assert names == [] and finding.code == "W-APPROVERS-SHAPE"


def test_wv_2_an_empty_approver_list_says_so_in_the_message():
    project = {"owner": "jed72", "approvers": {"issue-waiver": []}}
    names, finding = _api().allowed_approvers(_waiver("issue"), project, None)
    assert names == [] and finding is None
    findings = _api().check(_waiver("project", approved_by="x"), today=fx.TODAY,
                            project=OWNER, parent={"approvers": {"project-waiver": []}})
    assert findings[0].message.endswith("no approver is named")


def test_wv_3_a_record_field_needs_both_from_and_to():
    for gone in ("from", "to"):
        record = fx.approval()
        del record["waiver"]["fields"]["severity"][gone]
        described = {"id": "issue:checks.tests-pass",
                     "fields": {"severity": {gone: None, ("to" if gone == "from" else "from"):
                                             "advisory" if gone == "from" else "blocking"}}}
        findings = _issue_check([record], described=described)
        assert _codes(findings) == ["W-APPROVAL-WAIVER"], gone


def test_wv_3_the_derived_record_must_belong_to_this_waiver():
    other = dict(DESCRIBED, id="issue:checks.no-secrets")
    assert _codes(_issue_check([fx.approval()], described=other)) == [
        "W-APPROVAL-UNCHECKED"]
    assert _codes(_issue_check([fx.approval()], described={"fields": DESCRIBED["fields"]})) == [
        "W-APPROVAL-UNCHECKED"]
