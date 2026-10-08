"""Layered `compass policy lint` and `compass policy effective` (ADR-035,
ADR-037, ADR-039, ADR-042, ADR-043).

The engine in `policy_lint` is pure: unit tests hand it layer documents.
`classifier_fixtures` holds the small parent configuration, so a test
classifies a layer in a fraction of a second. The end-to-end tests run the
real CLI in a scratch project against the committed preset.

Scenario ids: `PL-1` to `PL-12` (issue `policy-lint`). Each test name starts
with its scenario id.
"""
from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

TODAY = date(2026, 10, 7)
CLI = ROOT / "cli" / "compass"


def _api():
    from compass_pkg import policy_lint
    return policy_lint


# --- helpers ---------------------------------------------------------------------

def _env(home):
    return {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(home),
            "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "NO_COLOR": "1",
            "COLUMNS": "100", "PYTHONDONTWRITEBYTECODE": "1",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}


def _run(cwd, *argv):
    r = subprocess.run([sys.executable, str(CLI), *argv], cwd=cwd, env=_env(cwd),
                       capture_output=True, text=True, timeout=180)
    return r.returncode, r.stdout, r.stderr


def _project(tmp_path, compass_yml=None, old_config=None):
    """A scratch project root: `.compass/` makes it the root."""
    (tmp_path / ".compass").mkdir(exist_ok=True)
    if compass_yml is not None:
        (tmp_path / "compass.yml").write_text(
            compass_yml if isinstance(compass_yml, str) else yaml.safe_dump(compass_yml),
            encoding="utf-8")
    if old_config is not None:
        (tmp_path / ".compass" / "config.yml").write_text(old_config, encoding="utf-8")
    return tmp_path


# --- PL-1: legacy or layered ----------------------------------------------------------

LEGACY_PASS = ("compass policy lint: PASS - routing-policy.yml and guardrails.yml "
               "are structurally valid.")


def test_pl_1_a_project_with_no_compass_yml_gets_todays_output(tmp_path):
    code, out, _ = _run(_project(tmp_path), "policy", "lint")
    assert code == 0
    assert out.startswith(LEGACY_PASS), out


def test_pl_1_the_framework_repository_keeps_the_legacy_lint():
    code, out, _ = _run(ROOT, "policy", "lint")
    assert code == 0
    assert out.startswith(LEGACY_PASS), out


def test_pl_1_a_project_with_a_compass_yml_runs_the_layered_lint(tmp_path):
    root = _project(tmp_path, {"schema": 1})
    code, out, _ = _run(root, "policy", "lint", "--json")
    assert code == 0, out
    assert json.loads(out).get("mode") == "layered"


def test_pl_1_a_compass_yml_with_no_schema_beside_the_old_file_is_not_read(tmp_path):
    root = _project(tmp_path, "owner: someone\n", old_config="autonomy: balanced\n")
    code, out, _ = _run(root, "policy", "lint")
    assert out.startswith(LEGACY_PASS), out


def test_pl_1_a_compass_yml_with_no_schema_and_no_old_file_is_read(tmp_path):
    root = _project(tmp_path, "autonomy: balanced\n")
    code, out, _ = _run(root, "policy", "lint", "--json")
    assert json.loads(out).get("mode") == "layered"


def test_pl_1_compass_ci_still_calls_the_legacy_function():
    from compass_pkg import analyze, governance
    assert analyze.cmd_policy_lint is governance.cmd_policy_lint


# --- the small parent and the layer builders -------------------------------------

def _layer(doc, kind="project", name=None):
    from compass_pkg.layers import Layer
    return Layer(name or {"parent": "default"}.get(kind, kind), kind, doc, "digest")


def _parent_doc():
    import classifier_fixtures
    return {"schema": 1, **classifier_fixtures.base()}


def _lint(project=None, issue=None, parent=True, **kwargs):
    kwargs.setdefault("today", TODAY)
    kwargs.setdefault("cache", _CACHE)
    return _api().lint_chain(
        _layer(_parent_doc(), "parent") if parent is True else parent,
        None if project is None else _layer({"schema": 1, **project}),
        None if issue is None else _layer(issue, "issue"), **kwargs)


_CACHE = {}


def _codes(report, level=None):
    return sorted(f.code for f in report.findings if level in (None, f.level))


def _one(report, code):
    found = [f for f in report.findings if f.code == code]
    assert len(found) == 1, [(f.code, f.path) for f in report.findings]
    return found[0]


def _new_check(**over):
    body = {"statement": "A check.", "kind": "deterministic", "impl": "suite-passed",
            "severity": "advisory", "on_skipped": "fail"}
    body.update(over)
    return body


# --- PL-2: the per-layer group --------------------------------------------------------

def test_pl_2_a_clean_chain_has_no_findings_and_no_stop():
    report = _lint(project={"checks": {"extra": _new_check()}})
    assert report.findings == []
    assert report.stopped_after is None


def test_pl_2_a_schema_fault_is_reported_with_its_layer_and_path():
    report = _lint(project={"stages": "oops", "foo": 1})
    found = {(f.code, f.layer, f.path, f.group, f.level) for f in report.findings}
    assert found == {("L-SCHEMA", "project", "stages", "layer", "error"),
                     ("L-SCHEMA", "project", "foo", "layer", "error")}
    assert report.stopped_after == "layer"


def test_pl_2_every_layer_is_checked_not_only_the_first_with_a_fault():
    report = _lint(project={"stages": "oops"},
                   issue={"gates": "oops"})
    assert {(f.layer, f.path) for f in report.findings} == {
        ("project", "stages"), ("issue", "gates")}


def test_pl_2_an_unknown_impl_is_reported_whether_added_or_set():
    report = _lint(project={"checks": {
        "extra": _new_check(impl="no-such-impl"),
        "tests-pass": {"set": {"impl": "also-missing"}}}})
    assert {(f.code, f.path) for f in report.findings} == {
        ("L-IMPL-UNKNOWN", "checks.extra.impl"),
        ("L-IMPL-UNKNOWN", "checks.tests-pass.set.impl")}


def test_pl_2_a_templated_impl_is_its_own_finding():
    report = _lint(project={"checks": {"extra": _new_check(impl="{{ the-impl }}")}})
    assert _codes(report) == ["L-IMPL-TEMPLATED"]


def test_pl_2_a_settings_key_in_a_parent_is_refused_by_name():
    parent = _parent_doc()
    parent["allow_project_commands"] = True
    report = _lint(parent=_layer(parent, "parent"))
    found = _one(report, "L-SETTINGS-KEY")
    assert (found.layer, found.path) == ("default", "allow_project_commands")
    assert "never in a parent" in found.message


def test_pl_2_an_unlock_outside_the_project_layer_is_refused():
    report = _lint(issue={"checks": {"tests-pass": {"unlock": True}}})
    assert [(f.code, f.layer, f.path) for f in report.findings] == [
        ("L-UNLOCK-PLACEMENT", "issue", "checks.tests-pass.unlock")]


def test_pl_2_a_top_level_unlocks_key_is_refused():
    report = _lint(project={"unlocks": ["checks.tests-pass"]})
    assert _codes(report) == ["L-UNLOCK-PLACEMENT"]


def test_pl_2_approved_on_on_an_issue_waiver_is_refused():
    waiver = {"reason": "A reason.", "approved_by": "EV-1", "approved_on": "2026-10-01"}
    report = _lint(issue={"checks": {"tests-pass": {
        "set": {"severity": "advisory"}, "waiver": waiver}}})
    found = _one(report, "W-APPROVED-ON-ISSUE")
    assert (found.layer, found.group, found.level) == ("issue", "layer", "error")
    assert found.path == "issue:checks.tests-pass"


def test_pl_2_a_fault_in_the_group_stops_the_merge_and_later_groups():
    report = _lint(project={"stages": "oops",
                            "checks": {"ghost": {"set": {"severity": "advisory"}}}})
    assert _codes(report) == ["L-SCHEMA"]       # no M-SET-UNKNOWN: the merge did not run
    assert report.stopped_after == "layer"


def test_pl_2_a_duplicate_key_in_the_project_file_is_a_load_finding(tmp_path):
    root = _project(tmp_path, "schema: 1\nowner: a\nowner: b\n")
    code, out, _ = _run(root, "policy", "lint", "--json")
    document = json.loads(out)
    assert code == 1
    assert [(f["code"], f["layer"], f["group"]) for f in document["findings"]] == [
        ("L-LOAD", "project", "layer")]
    assert "duplicate key" in document["findings"][0]["message"]


NON_TEXT_CHECK = ("schema: 1\nchecks:\n  docs-mention:\n    statement: x\n"
                  "    kind: deterministic\n    impl: suite-passed\n"
                  "    severity: advisory\n    on: [ship]\n")


def _one_finding(document, code):
    assert [f["code"] for f in document["findings"]] == [code], document
    return document["findings"][0]


def test_pl_2_a_non_text_key_in_the_project_file_is_a_finding_not_a_traceback(tmp_path):
    code, out, err = _run(_project(tmp_path, NON_TEXT_CHECK), "policy", "lint", "--json")
    assert "Traceback" not in err, err
    assert code == 1
    finding = _one_finding(json.loads(out), "L-KEY-NOT-TEXT")
    assert (finding["level"], finding["layer"], finding["group"]) == (
        "error", "project", "layer")
    assert finding["path"] == "checks.docs-mention"
    assert "True" in finding["message"] and '"on":' in finding["message"]


def test_pl_2_a_non_text_key_in_a_settings_section_is_refused_too(tmp_path):
    root = _project(tmp_path, "schema: 1\nprices:\n  2: 3\n")
    code, out, err = _run(root, "policy", "lint", "--json")
    assert "Traceback" not in err, err
    finding = _one_finding(json.loads(out), "L-KEY-NOT-TEXT")
    assert finding["path"] == "prices"
    assert "2" in finding["message"] and '"2":' in finding["message"]


def test_pl_2_a_non_text_key_in_an_issue_config_is_a_finding(tmp_path):
    root = _project(tmp_path, {"schema": 1})
    issue = root / ".compass" / "work" / "t"
    issue.mkdir(parents=True)
    (issue / "manifest.yml").write_text(
        "schema_version: '2.0'\nissue: t\nconfig:\n  checks:\n    tests-pass:\n"
        "      set:\n        yes: 1\n", encoding="utf-8")
    code, out, err = _run(root, "policy", "lint", "--json", "--issue", "t")
    assert "Traceback" not in err, err
    finding = _one_finding(json.loads(out), "L-KEY-NOT-TEXT")
    assert (finding["layer"], finding["path"]) == ("issue", "checks.tests-pass.set")


def test_pl_2_policy_effective_refuses_a_non_text_key_with_the_message(tmp_path):
    code, out, err = _run(_project(tmp_path, NON_TEXT_CHECK), "policy", "show")
    assert "Traceback" not in err, err
    assert code == 2
    assert "L-KEY-NOT-TEXT" in err and "checks.docs-mention" in err and '"on":' in err


def test_pl_2_a_chain_built_from_a_non_text_key_is_refused_by_the_loader():
    from compass_pkg import layers
    from compass_pkg.core import CompassError
    with pytest.raises(CompassError, match=r'checks\.c.*"on":'):
        layers.build_chain(project=_layer({"schema": 1, "checks": {"c": {True: 1}}}))


# --- PL-3: the merge group ---------------------------------------------------------

MERGE_CASES = {
    "M-ADD-EXISTS": ({"checks": {"tests-pass": _new_check()}}, "checks.tests-pass"),
    "M-ADD-PARTIAL": ({"checks": {"fresh": {"statement": "Only a statement."}}},
                      "checks.fresh"),
    "M-SET-UNKNOWN": ({"checks": {"ghost": {"set": {"severity": "advisory"}}}},
                      "checks.ghost"),
    "M-REPLACE-UNKNOWN": ({"checks": {"ghost": {"replace": True, **_new_check()}}},
                          "checks.ghost"),
    "M-REMOVE-UNKNOWN": ({"checks": {"ghost": {"remove": True}}}, "checks.ghost"),
    "M-LIST-REMOVE-ABSENT": ({"gates": {"G1": {"set": {"checks": {"remove": ["ghost"]}}}}},
                             "gates.G1.set.checks"),
    "M-LIST-ADD-PRESENT": ({"gates": {"G1": {"set": {"checks": {"add": ["tests-pass"]}}}}},
                           "gates.G1.set.checks"),
    "M-REF-REMOVED": ({"checks": {"tests-pass": {"remove": True}}}, "checks.tests-pass"),
    "M-FIELD-LAYER": ({"stages": {"define": {"set": {"mode": "light"}}}},
                      "stages.define.set.mode"),
    "M-OP-CONFLICT": ({"checks": {"tests-pass": {"set": {"severity": "advisory"},
                                                 "remove": True}}}, "checks.tests-pass"),
}


@pytest.mark.parametrize("code", sorted(MERGE_CASES))
def test_pl_3_each_merge_refusal_is_reported_with_its_layer_and_path(code):
    project, path = MERGE_CASES[code]
    report = _lint(project=project)
    found = _one(report, code)
    assert (found.layer, found.path, found.group, found.level) == (
        "project", path, "merge", "error")
    assert report.stopped_after == "merge"


def test_pl_3_every_fault_of_the_refused_layer_is_reported_together():
    report = _lint(project={"checks": {"ghost": {"remove": True},
                                       "phantom": {"set": {"severity": "advisory"}}}})
    assert _codes(report) == ["M-REMOVE-UNKNOWN", "M-SET-UNKNOWN"]


def test_pl_3_the_layers_after_the_refused_one_are_not_merged():
    report = _lint(project={"checks": {"ghost": {"remove": True}}},
                   issue={"checks": {"phantom": {"set": {"severity": "advisory"}}}})
    assert {(f.code, f.layer) for f in report.findings} == {("M-REMOVE-UNKNOWN", "project")}


def test_pl_3_a_parent_that_does_not_apply_is_reported_under_its_own_name():
    parent = _parent_doc()
    parent["checks"]["ghost"] = {"remove": True}
    report = _lint(parent=_layer(parent, "parent"))
    found = _one(report, "M-REMOVE-UNKNOWN")
    assert found.layer == "default"


# --- PL-4: the resolved group --------------------------------------------------------

def _rule_set(hit, then, kind="floors"):
    return {"rules": {"mine": {"kind": kind, "hit": hit, "rules": {
        "R1": {"order": 1, "when": {}, "then": then}}}}}


def test_pl_4_an_id_nothing_defines_is_reported_with_the_field_that_names_it():
    report = _lint(project={
        "gates": {"G9": {"kind": "review", "checks": ["ghost"]}},
        "approaches": {"regular": {"set": {"gates": {"add": ["no-gate"]}}}}})
    found = {(f.code, f.layer, f.path, f.group) for f in report.findings}
    assert found == {("M-REF-UNKNOWN", "project", "gates.G9.checks", "resolved"),
                     ("M-REF-UNKNOWN", "project", "approaches.regular.gates", "resolved")}
    assert report.stopped_after == "resolved"
    assert any("ghost" in f.message for f in report.findings)


def test_pl_4_two_approaches_with_one_weight_are_a_tie_blamed_on_the_later_layer():
    extra = {"weight": 2, "ships": True, "stages": {"define": "light"}}
    report = _lint(project={"approaches": {"extra": extra}})
    found = _one(report, "M-WEIGHT-TIE")
    assert (found.layer, found.path) == ("project", "approaches.extra.weight")
    assert "extra" in found.message and "regular" in found.message


def test_pl_4_an_effect_with_no_hit_policy_is_reported():
    report = _lint(project=_rule_set({}, {"add_gate": "verify.correctness"}))
    found = _one(report, "M-HIT-MISSING")
    assert (found.layer, found.path) == ("project", "rules.mine.hit.add_gate")


def test_pl_4_a_hit_policy_the_effect_does_not_allow_is_reported():
    report = _lint(project=_rule_set({"add_gate": "first"},
                                     {"add_gate": "verify.correctness"}))
    found = _one(report, "M-HIT-DISALLOWED")
    assert found.path == "rules.mine.hit.add_gate"
    assert "collect" in found.message


def test_pl_4_an_effect_the_table_does_not_know_has_no_allowed_policy():
    report = _lint(project=_rule_set({"nonsense": "collect"}, {"nonsense": 1}))
    assert _codes(report) == ["M-EFFECT-UNKNOWN", "M-HIT-DISALLOWED"]


def test_pl_4_a_name_or_alias_collision_is_reported():
    report = _lint(project={"vocabulary": {
        "checks.tests-pass": {"name": "Tests", "aliases": ["green"]},
        "checks.no-secrets": {"name": "Green"}}})
    assert _codes(report) == ["M-ALIAS-COLLISION"]


def test_pl_4_a_dependency_cycle_between_artifacts_is_reported_once():
    report = _lint(project={"artifacts": {
        "a": {"file": "a.md", "depends_on": ["b"]},
        "b": {"file": "b.md", "depends_on": ["a"]}}})
    found = _one(report, "M-CYCLE")
    assert found.path == "artifacts.a.depends_on"
    assert "a -> b -> a" in found.message


def test_pl_4_the_committed_preset_has_nothing_to_report():
    parent, _ = _api().load_parent()
    report = _api().lint_chain(parent, None, today=TODAY)
    assert report.findings == []


# --- PL-5: the locks group -----------------------------------------------------------

def _locked_parent(level=True, entry=("checks", "tests-pass")):
    parent = _parent_doc()
    parent[entry[0]][entry[1]]["locked"] = level
    return _layer(parent, "parent")


def _owner_unlock(owner="owner-1", approver="owner-1"):
    return {"owner": owner, "checks": {"tests-pass": {
        "unlock": True, "set": {"severity": "advisory"},
        "waiver": {"reason": "A reason.", "approved_by": approver,
                   "approved_on": "2026-10-01"}}}}


def test_pl_5_a_loosening_of_a_locked_entry_is_a_lock_refusal():
    report = _lint(parent=_locked_parent(),
                   project={"checks": {"tests-pass": {"set": {"severity": "advisory"}}}})
    found = _one(report, "K-LOCK-REFUSED")
    assert (found.layer, found.path, found.group, found.level) == (
        "project", "checks.tests-pass", "locks", "error")
    assert found.detail["field"] == "checks.severity"
    assert found.detail["outcome"] == "looser"
    assert found.detail["level"] is True
    assert not found.message.startswith("project layer")
    assert report.stopped_after == "locks"


def test_pl_5_the_same_loosening_with_no_lock_is_not_a_lock_refusal():
    report = _lint(project={"checks": {"tests-pass": {"set": {"severity": "advisory"}}}})
    assert not [c for c in _codes(report) if c.startswith("K-")]


def test_pl_5_a_refused_unlock_is_reported_and_a_hard_lock_has_no_unlock():
    report = _lint(parent=_locked_parent("hard"), project=_owner_unlock())
    found = _one(report, "K-UNLOCK-REFUSED")
    assert (found.layer, found.path) == ("project", "checks.tests-pass")
    assert "hard" in found.message


def test_pl_5_an_unlock_the_owner_approved_lifts_a_soft_lock():
    report = _lint(parent=_locked_parent(), project=_owner_unlock())
    assert not [c for c in _codes(report) if c.startswith("K-")]


def test_pl_5_an_unlock_approved_by_someone_else_is_refused():
    report = _lint(parent=_locked_parent(), project=_owner_unlock(approver="other"))
    assert "K-UNLOCK-REFUSED" in _codes(report)


def test_pl_5_an_evaluator_fault_is_one_finding_and_not_also_a_lock_refusal():
    report = _lint(parent=_locked_parent(),
                   project={"approaches": {"regular": {"set": {"ships": False}}}})
    assert [(f.code, f.group, f.level) for f in report.findings] == [
        ("E-EVALUATION", "locks", "error")]
    assert "evaluator treats it as shipping" in report.findings[0].message
    assert "no lock can be shown" not in report.findings[0].message
    assert len(report.errors) == 1


def test_pl_5_more_than_eight_labels_is_one_unprovable_finding():
    names = [f"label-{i}" for i in range(9)]
    project = {"rules": {"floors": {"set": {"rules": {"set": {"F-MANY": {
        "order": 5, "when": {"labels_any": names},
        "then": {"force_minimum_approach": "regular"}}}}}}}}
    report = _lint(parent=_locked_parent(), project=project)
    found = _one(report, "K-UNPROVABLE")
    assert found.path == "configuration"
    assert "eight" in found.message


# --- PL-6: classification and waivers ------------------------------------------------

import waiver_fixtures as fx  # noqa: E402


def _loosen(waiver=None, owner="owner-1", check="tests-pass", severity="advisory"):
    project = {"owner": owner, "checks": {check: {"set": {"severity": severity}}}}
    if waiver is not None:
        project["checks"][check]["waiver"] = waiver
    return project


def test_pl_6_an_unwaived_loosening_is_an_error_naming_the_point_and_the_values():
    report = _lint(project=_loosen())
    found = _one(report, "C-LOOSENING")
    assert (found.layer, found.path, found.group, found.level) == (
        "project", "checks.tests-pass.severity", "classification", "error")
    assert found.detail["field"] == "checks.severity"
    assert found.detail["key"] == "tests-pass"
    assert (found.detail["parent"], found.detail["child"]) == ("blocking", "advisory")
    assert found.detail["assessment"]["risk"] == "contained"
    assert found.detail["result"] == "loosening"
    assert "at risk contained" in found.message
    assert report.stopped_after == "classification"


def test_pl_6_a_valid_project_waiver_excuses_its_entry():
    report = _lint(project=_loosen(fx.project_waiver(approved_by="owner-1")))
    assert report.findings == []


def test_pl_6_a_waiver_with_a_fault_is_an_error_and_excuses_nothing():
    report = _lint(project=_loosen(fx.project_waiver(approved_by="someone-else")))
    assert _codes(report) == ["C-LOOSENING", "W-APPROVER-NOT-ALLOWED"]
    fault = _one(report, "W-APPROVER-NOT-ALLOWED")
    assert (fault.layer, fault.path, fault.group) == (
        "project", "project:checks.tests-pass", "classification")


def test_pl_6_a_waiver_on_another_entry_does_not_excuse_a_loosening():
    project = _loosen()
    project["checks"]["no-secrets"] = {"set": {"on_skipped": "pass"},
                                       "waiver": fx.project_waiver(approved_by="owner-1")}
    report = _lint(project=project)
    assert _codes(report, "error") == ["C-LOOSENING"]


def test_pl_6_an_unneeded_waiver_is_a_warning_and_does_not_fail():
    parent = _parent_doc()
    parent["checks"]["no-secrets"]["severity"] = "advisory"
    project = {"owner": "owner-1", "checks": {"no-secrets": {
        "set": {"severity": "blocking"},
        "waiver": fx.project_waiver(approved_by="owner-1")}}}
    report = _lint(parent=_layer(parent, "parent"), project=project)
    found = _one(report, "W-UNNEEDED")
    assert (found.level, found.path, found.layer) == (
        "warning", "project:checks.no-secrets", "project")
    assert report.ok and report.stopped_after is None


def test_pl_6_a_legacy_waiver_is_a_warning_and_still_excuses():
    report = _lint(project=_loosen({"reason": "Migrated.", "approved_by": "LEGACY"}))
    assert [(f.code, f.level) for f in report.findings] == [("W-LEGACY", "warning")]
    assert report.ok


def test_pl_6_an_issue_layer_is_classified_against_the_project_result():
    report = _lint(project={"owner": "jed72"}, issue={"checks": {
        "tests-pass": {"set": {"severity": "advisory"}}}})
    found = _one(report, "C-LOOSENING")
    assert (found.layer, found.path) == ("issue", "checks.tests-pass.severity")


def test_pl_6_an_issue_waiver_needs_the_approval_record_it_names():
    issue = {"checks": {"tests-pass": {"set": {"severity": "advisory"},
                                       "waiver": fx.issue_waiver(approved_by="EV-1")}}}
    approved = _lint(project={"owner": "jed72"}, issue=issue,
                     registry=[fx.approval(approver="jed72")])
    assert approved.findings == []
    missing = _lint(project={"owner": "jed72"}, issue=issue)
    assert "W-APPROVAL-MISSING" in _codes(missing)


def test_pl_6_the_full_grid_gives_the_same_verdict_as_the_grouped_one():
    grouped = _lint(project=_loosen())
    full = _lint(project=_loosen(), exhaustive=True)
    assert _codes(grouped) == _codes(full) == ["C-LOOSENING"]


def test_pl_6_an_evaluator_fault_with_no_locks_is_one_finding():
    report = _lint(project={"approaches": {"regular": {"set": {"ships": False}}}})
    assert [(f.code, f.group) for f in report.findings] == [("E-EVALUATION", "classification")]
    assert "evaluator treats it as shipping" in report.findings[0].message


# --- PL-7: a vocabulary change is its own warning ------------------------------------

def test_pl_7_an_added_dimension_value_is_a_warning_apart_from_the_classification():
    report = _lint(project={"dimensions": {"familiarity": {"set": {"values": {
        "add": ["brownfield-mapped"]}}}}})
    found = _one(report, "V-VOCABULARY-CHANGE")
    assert (found.level, found.layer, found.path, found.group) == (
        "warning", "project", "dimensions.familiarity.values", "classification")
    assert found.detail == {"dimension": "familiarity", "added": ["brownfield-mapped"],
                            "removed": []}
    assert report.ok
    assert _codes(report) == ["V-VOCABULARY-CHANGE"]


def test_pl_7_a_removed_dimension_value_names_the_value_and_what_it_stops():
    report = _lint(project={"dimensions": {"size": {"set": {"values": {
        "remove": ["small"]}}}}})
    found = _one(report, "V-VOCABULARY-CHANGE")
    assert found.detail == {"dimension": "size", "added": [], "removed": ["small"]}
    assert "stored assessment" in found.message


def test_pl_7_a_change_that_leaves_the_values_alone_reports_no_vocabulary_change():
    report = _lint(project={"checks": {"extra": _new_check()}})
    assert "V-VOCABULARY-CHANGE" not in _codes(report)


# --- PL-8: the text output, the options and the exit codes ---------------------------

def test_pl_8_a_clean_project_prints_pass_and_exits_0(tmp_path):
    code, out, _ = _run(_project(tmp_path, {"schema": 1}), "policy", "lint")
    assert (code, out.splitlines()[0]) == (0, "compass policy lint: PASS")


def test_pl_8_a_fault_prints_fail_and_one_line_each_and_exits_1(tmp_path):
    root = _project(tmp_path, {"schema": 1, "stages": "oops", "foo": 1})
    code, out, _ = _run(root, "policy", "lint")
    lines = out.splitlines()
    assert code == 1
    assert lines[0] == "compass policy lint: FAIL"
    assert len(lines) == 3
    assert lines[1].startswith("  - L-SCHEMA [project] foo: ")
    assert lines[2].startswith("  - L-SCHEMA [project] stages: ")


def test_pl_8_a_warning_is_printed_and_never_fails(tmp_path):
    root = _project(tmp_path, {"schema": 1})
    below = root / "docs"
    below.mkdir()
    (below / "compass.yml").write_text("schema: 1\n", encoding="utf-8")
    code, out, _ = _run(below, "policy", "lint")
    lines = out.splitlines()
    assert code == 0
    assert lines[0] == "compass policy lint: PASS"
    assert lines[1].startswith("  - warning L-IGNORED-FILE [project] docs/compass.yml: ")


def test_pl_8_file_lints_one_compass_yml_over_the_shipped_default(tmp_path):
    bad = tmp_path / "other.yml"
    bad.write_text("schema: 1\nstages: oops\n", encoding="utf-8")
    code, out, _ = _run(tmp_path, "policy", "lint", "--file", str(bad))
    assert code == 1 and "L-SCHEMA [project] stages" in out
    good = tmp_path / "good.yml"
    good.write_text("schema: 1\n", encoding="utf-8")
    assert _run(tmp_path, "policy", "lint", "--file", str(good))[0] == 0


def test_pl_8_a_file_that_is_not_there_exits_2(tmp_path):
    code, _, err = _run(tmp_path, "policy", "lint", "--file", str(tmp_path / "none.yml"))
    assert code == 2
    assert "no such file" in err


def test_pl_8_issue_adds_the_manifests_config_as_the_issue_layer(tmp_path):
    root = _project(tmp_path, {"schema": 1})
    work = root / ".compass" / "work" / "demo"
    work.mkdir(parents=True)
    (work / "manifest.yml").write_text(
        "schema_version: '2.0'\nissue: demo\nconfig:\n  stages: oops\n", encoding="utf-8")
    assert _run(root, "policy", "lint")[0] == 0           # never reads an issue unasked
    code, out, _ = _run(root, "policy", "lint", "--issue", "demo")
    assert code == 1
    assert "L-SCHEMA [issue] stages" in out


def test_pl_8_an_issue_that_does_not_exist_exits_2(tmp_path):
    code, _, err = _run(_project(tmp_path, {"schema": 1}), "policy", "lint",
                        "--issue", "nope")
    assert code == 2 and "nope" in err


def test_pl_8_exhaustive_runs_the_full_grid_and_still_passes_a_clean_project(tmp_path):
    code, out, _ = _run(_project(tmp_path, {"schema": 1}), "policy", "lint", "--exhaustive")
    assert (code, out.splitlines()[0]) == (0, "compass policy lint: PASS")


# --- PL-9: `policy lint --json` --------------------------------------------------------
# The shapes below are the public contract from 6.0.0. A change to a key, its
# order or a code is a change to the contract, so it fails here.

LINT_KEYS = ["schema", "mode", "result", "layers", "stopped_after", "counts", "findings"]
FINDING_KEYS = ["code", "level", "layer", "path", "group", "message", "detail"]


def _json(root, *argv):
    code, out, err = _run(root, "policy", "lint", "--json", *argv)
    return code, json.loads(out), err


def test_pl_9_a_passing_layered_project_has_the_pinned_envelope(tmp_path):
    code, document, _ = _json(_project(tmp_path, {"schema": 1}))
    assert code == 0
    assert list(document) == LINT_KEYS
    assert document["schema"] == 1
    assert document["mode"] == "layered"
    assert document["result"] == "pass"
    assert document["layers"] == [{"name": "default", "kind": "parent"},
                                  {"name": "project", "kind": "project"}]
    assert document["stopped_after"] is None
    assert document["counts"] == {"errors": 0, "warnings": 0}
    assert document["findings"] == []


def test_pl_9_each_finding_has_the_pinned_keys_in_order(tmp_path):
    root = _project(tmp_path, {"schema": 1, "stages": "oops"})
    code, document, _ = _json(root)
    assert code == 1
    assert document["result"] == "fail"
    assert document["stopped_after"] == "layer"
    assert document["counts"] == {"errors": 1, "warnings": 0}
    (finding,) = document["findings"]
    assert list(finding) == FINDING_KEYS
    assert (finding["code"], finding["level"], finding["layer"], finding["path"],
            finding["group"], finding["detail"]) == (
        "L-SCHEMA", "error", "project", "stages", "layer", None)
    assert isinstance(finding["message"], str) and finding["message"]


def test_pl_9_a_classification_finding_carries_its_detail_object():
    report = _lint(project=_loosen())
    detail = _api().lint_json(report)["findings"][0]["detail"]
    assert list(detail) == ["result", "assessment", "outcome", "field", "key", "parent",
                            "child"]
    assert detail["result"] == "loosening"


def test_pl_9_a_lock_finding_carries_its_detail_object():
    report = _lint(parent=_locked_parent(),
                   project={"checks": {"tests-pass": {"set": {"severity": "advisory"}}}})
    detail = _api().lint_json(report)["findings"][0]["detail"]
    assert list(detail) == ["field", "key", "outcome", "level", "parent", "child", "where"]


def test_pl_9_findings_come_in_group_then_layer_then_path_order():
    report = _lint(project={"stages": "oops", "foo": 1, "bar": 2},
                   issue={"gates": "oops"})
    paths = [(f.layer, f.path) for f in _api().lint_chain(
        _layer(_parent_doc(), "parent"),
        _layer({"schema": 1, "stages": "oops", "foo": 1, "bar": 2}),
        _layer({"gates": "oops"}, "issue"), today=TODAY).findings]
    assert paths == [("project", "bar"), ("project", "foo"), ("project", "stages"),
                     ("issue", "gates")]
    assert [f.group for f in report.findings] == ["layer"] * 4


def test_pl_9_the_same_input_gives_the_same_bytes_whatever_the_key_order(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    first = _project(tmp_path / "a", {"schema": 1, "stages": "oops", "foo": 1})
    second = _project(tmp_path / "b", "foo: 1\nstages: oops\nschema: 1\n")
    one = _run(first, "policy", "lint", "--json")[1]
    two = _run(second, "policy", "lint", "--json")[1]
    assert one == two
    assert one == _run(first, "policy", "lint", "--json")[1]


def test_pl_9_the_json_names_no_path_outside_the_project_and_no_time(tmp_path):
    root = _project(tmp_path, {"schema": 1, "stages": "oops"})
    out = _run(root, "policy", "lint", "--json")[1]
    assert str(tmp_path) not in out


def test_pl_9_legacy_mode_uses_the_same_envelope(tmp_path):
    code, document, _ = _json(_project(tmp_path))
    assert code == 0
    assert list(document) == LINT_KEYS
    assert document["mode"] == "legacy"
    assert document["layers"] == [{"name": "legacy", "kind": "legacy"}]
    assert document["findings"] == [] and document["stopped_after"] is None


def test_pl_9_a_legacy_fault_is_a_finding_with_the_legacy_layer(tmp_path):
    root = _project(tmp_path)
    governance = root / "governance"
    governance.mkdir()
    for name in ("routing-policy.yml", "guardrails.yml"):
        (governance / name).write_text((ROOT / "governance" / name).read_text(
            encoding="utf-8"), encoding="utf-8")
    (governance / "quarantine.yml").write_text(yaml.safe_dump({
        "version": "1.0.0", "quarantined": [{"test": "t", "reason": "r",
                                             "added": "2026-05-25"}]}), encoding="utf-8")
    code, document, _ = _json(root)
    assert code == 1
    assert document["result"] == "fail"
    assert document["counts"]["errors"] == 1
    (finding,) = [f for f in document["findings"] if f["level"] == "error"]
    assert list(finding) == FINDING_KEYS
    assert (finding["code"], finding["layer"], finding["group"], finding["path"]) == (
        "LEGACY-STRUCTURE", "legacy", "legacy", "quarantine.yml")
    assert "tracking_task" in finding["message"]


# --- PL-10: `policy effective` ---------------------------------------------------------

def _effective(project=None, issue=None, parent=None, **kwargs):
    parent = parent or _layer(_parent_doc(), "parent")
    return _api().resolve_effective(
        parent, None if project is None else _layer({"schema": 1, **project}),
        None if issue is None else _layer(issue, "issue"), **kwargs)


def _row(effective, path):
    found = [r for r in effective.rows if r.path == path]
    assert len(found) == 1, [r.path for r in effective.rows if path.split(".")[0] in r.path]
    return found[0]


def test_pl_10_a_parent_field_has_its_value_source_and_operation():
    row = _row(_effective(), "checks.tests-pass.severity")
    assert (row.value, row.source, row.op, row.waiver, row.note) == (
        "blocking", "default", "add", None, None)


def test_pl_10_the_source_of_the_parent_carries_its_version():
    eff = _effective(meta={"id": "default", "version": "6.0.0"})
    assert _row(eff, "checks.tests-pass.severity").source == "default@6.0.0"
    assert eff.layers[0] == {"name": "default", "kind": "parent", "version": "6.0.0",
                             "digest": "digest"}


def test_pl_10_a_project_change_shows_the_project_as_source_and_a_set_operation():
    eff = _effective(project={"owner": "owner-1", "checks": {"tests-pass": {
        "set": {"severity": "advisory"},
        "waiver": fx.project_waiver(approved_by="owner-1")}}})
    row = _row(eff, "checks.tests-pass.severity")
    assert (row.value, row.source, row.op) == ("advisory", "project", "set")
    assert row.waiver == {"id": "project:checks.tests-pass", "scope": "project",
                          "approved_by": "owner-1", "approved_on": "2026-10-05"}
    assert _row(eff, "checks.tests-pass.on_skipped").source == "default"
    assert _row(eff, "checks.tests-pass.on_skipped").waiver is None


def test_pl_10_a_project_check_shows_the_add_operation_for_each_field():
    eff = _effective(project={"checks": {"extra": _new_check()}})
    rows = [r for r in eff.rows if r.path.startswith("checks.extra.")]
    assert {r.op for r in rows} == {"add"} and {r.source for r in rows} == {"project"}
    assert len(rows) == len(_new_check())


def test_pl_10_an_issue_waiver_shows_its_evidence_id():
    issue = {"checks": {"tests-pass": {"set": {"severity": "advisory"},
                                       "waiver": fx.issue_waiver(approved_by="EV-1")}}}
    row = _row(_effective(project={"owner": "jed72"}, issue=issue),
               "checks.tests-pass.severity")
    assert (row.source, row.op) == ("issue", "set")
    assert row.waiver == {"id": "issue:checks.tests-pass", "scope": "issue",
                          "approved_by": "EV-1", "approved_on": None}


def test_pl_10_capabilities_owner_and_approvers_are_fields_too():
    parent = _parent_doc()
    parent["capabilities"] = {"entry-exit-evaluation": False}
    eff = _effective(parent=_layer(parent, "parent"),
                     project={"owner": "owner-1", "capabilities": {"entry-exit-evaluation": True},
                              "approvers": {"issue-waiver": ["a"]}})
    capability = _row(eff, "capabilities.entry-exit-evaluation")
    assert (capability.value, capability.source, capability.op) == (True, "project", "set")
    assert (_row(eff, "owner").value, _row(eff, "owner").source) == ("owner-1", "project")
    assert _row(eff, "approvers.issue-waiver").value == ["a"]


def test_pl_10_a_stage_list_is_inactive_while_its_capability_is_off():
    parent = _parent_doc()
    parent["capabilities"] = {"entry-exit-evaluation": False}
    parent["stages"]["define"]["entry"] = ["tests-pass"]
    off = _effective(parent=_layer(parent, "parent"))
    assert _row(off, "stages.define.entry").note == "inactive: entry-exit-evaluation off"
    assert _row(off, "stages.define.order").note is None
    on = _effective(parent=_layer(parent, "parent"),
                    project={"capabilities": {"entry-exit-evaluation": True}})
    assert _row(on, "stages.define.entry").note is None


def test_pl_10_the_order_is_capabilities_owner_approvers_then_each_catalogue_by_id():
    parent = _parent_doc()
    parent["capabilities"] = {"entry-exit-evaluation": False, "artifact-freshness": True}
    eff = _effective(parent=_layer(parent, "parent"), project={"owner": "o"})
    paths = [r.path for r in eff.rows]
    assert paths[:3] == ["capabilities.artifact-freshness",
                         "capabilities.entry-exit-evaluation", "owner"]
    heads = []
    for path in paths[3:]:
        head = path.split(".")[0]
        if not heads or heads[-1] != head:
            heads.append(head)
    assert heads == ["dimensions", "stages", "approaches", "rules", "checks", "gates"]
    checks = [p.split(".")[1] for p in paths if p.startswith("checks.")]
    assert checks == sorted(checks)


def test_pl_10_a_configuration_that_cannot_resolve_is_an_error():
    from compass_pkg.core import CompassError
    with pytest.raises(CompassError) as caught:
        _effective(project={"stages": "oops"})
    assert "policy lint" in str(caught.value)
    with pytest.raises(CompassError):
        _effective(project={"checks": {"ghost": {"remove": True}}})


def test_pl_10_the_text_has_one_line_per_field_with_source_operation_and_waiver():
    eff = _effective(project={"owner": "owner-1", "checks": {"tests-pass": {
        "set": {"severity": "advisory"},
        "waiver": fx.project_waiver(approved_by="owner-1")}}})
    lines = _api().effective_text(eff)
    line = next(l for l in lines if l.startswith("checks.tests-pass.severity "))
    assert "advisory" in line and "project (set, waiver by owner-1, 2026-10-05)" in line
    assert sum(1 for l in lines if l.startswith("checks.")) == sum(
        1 for r in eff.rows if r.path.startswith("checks."))


def test_pl_10_the_cli_prints_the_preset_with_its_version_and_inactive_lists(tmp_path):
    code, out, _ = _run(_project(tmp_path, {"schema": 1}), "policy", "show")
    assert code == 0, out
    assert "default@6.0.0" in out
    assert "(inactive: entry-exit-evaluation off)" in out
    assert out.splitlines()[0].startswith("compass policy show: project")


def test_pl_10_a_project_with_no_compass_yml_shows_the_shipped_default(tmp_path):
    code, out, _ = _run(_project(tmp_path), "policy", "show")
    assert code == 0 and "default@6.0.0" in out


def test_pl_10_issue_resolves_the_manifests_config_over_the_project_file(tmp_path):
    root = _project(tmp_path, {"schema": 1})
    work = root / ".compass" / "work" / "demo"
    work.mkdir(parents=True)
    (work / "manifest.yml").write_text(
        "schema_version: '2.0'\nissue: demo\nconfig:\n  stages:\n    define:\n"
        "      set: {mode: light}\n", encoding="utf-8")
    code, out, _ = _run(root, "policy", "show", "--issue", "demo")
    assert code == 0, out
    assert out.splitlines()[0].startswith("compass policy show: issue demo")
    line = next(l for l in out.splitlines() if l.startswith("stages.define.mode "))
    assert "issue (set)" in line


# --- PL-11: `policy effective --json` ----------------------------------------------------
# The shape below is the public contract from 6.0.0.

EFFECTIVE_KEYS = ["schema", "scope", "layers", "fields"]
FIELD_KEYS = ["path", "value", "source", "op", "waiver", "note"]
LAYER_KEYS = ["name", "kind", "version", "digest"]
WAIVER_KEYS = ["id", "scope", "approved_by", "approved_on"]


def _effective_json(root, *argv):
    code, out, err = _run(root, "policy", "show", "--json", *argv)
    return code, (json.loads(out) if out.strip() else None), err


def test_pl_11_the_document_has_the_pinned_envelope_scope_and_layers(tmp_path):
    code, document, _ = _effective_json(_project(tmp_path, {"schema": 1}))
    assert code == 0
    assert list(document) == EFFECTIVE_KEYS
    assert document["schema"] == 1
    assert document["scope"] == {"kind": "project", "issue": None, "resolved": "live"}
    parent, project = document["layers"]
    assert list(parent) == LAYER_KEYS and list(project) == LAYER_KEYS
    assert (parent["name"], parent["kind"], parent["version"]) == ("default", "parent", "6.0.0")
    assert (project["name"], project["kind"], project["version"]) == ("project", "project", None)
    assert parent["digest"].startswith("sha256:") and project["digest"].startswith("sha256:")


def test_pl_11_each_field_has_the_pinned_keys_and_the_first_one_is_known(tmp_path):
    _, document, _ = _effective_json(_project(tmp_path, {"schema": 1}))
    assert all(list(f) == FIELD_KEYS for f in document["fields"])
    assert document["fields"][0] == {
        "path": "capabilities.artifact-freshness", "value": False,
        "source": "default@6.0.0", "op": "add", "waiver": None, "note": None}


def test_pl_11_every_resolved_field_of_the_preset_is_listed(tmp_path):
    import yaml as _yaml
    _, document, _ = _effective_json(_project(tmp_path, {"schema": 1}))
    listed = {f["path"] for f in document["fields"]}
    directory = ROOT / "governance" / "presets" / "default"
    from compass_pkg import catalogue_spec
    expected = set()
    for name in catalogue_spec.CATALOGUES:
        part = _yaml.safe_load((directory / f"{name}.yml").read_text(encoding="utf-8"))
        for entry_id, entry in part[name].items():
            expected |= {f"{name}.{entry_id}.{k}" for k in entry
                         if k in catalogue_spec.FIELDS[name]}
    assert expected <= listed
    assert listed - expected <= {p for p in listed if p.split(".")[0] in (
        "capabilities", "owner", "approvers") or p.endswith(".locked")}


def test_pl_11_json_and_text_list_the_same_fields(tmp_path):
    root = _project(tmp_path, {"schema": 1})
    _, document, _ = _effective_json(root)
    text = _run(root, "policy", "show")[1].splitlines()
    assert len(text) - 2 == len(document["fields"])


def test_pl_11_a_waiver_is_an_object_with_the_pinned_keys():
    eff = _effective(project={"owner": "owner-1", "checks": {"tests-pass": {
        "set": {"severity": "advisory"},
        "waiver": fx.project_waiver(approved_by="owner-1")}}})
    document = _api().effective_json(eff)
    field = next(f for f in document["fields"] if f["path"] == "checks.tests-pass.severity")
    assert list(field["waiver"]) == WAIVER_KEYS
    assert field["waiver"]["approved_on"] == "2026-10-05"


def test_pl_11_the_note_of_an_inactive_list_is_in_the_field(tmp_path):
    _, document, _ = _effective_json(_project(tmp_path, {"schema": 1}))
    notes = {f["note"] for f in document["fields"] if f["note"]}
    assert notes == {"inactive: entry-exit-evaluation off"}


def test_pl_11_issue_scope_names_the_issue_and_marks_the_issue_layer(tmp_path):
    root = _project(tmp_path, {"schema": 1})
    work = root / ".compass" / "work" / "demo"
    work.mkdir(parents=True)
    (work / "manifest.yml").write_text(
        "schema_version: '2.0'\nissue: demo\nconfig:\n  stages:\n    define:\n"
        "      set: {mode: light}\n", encoding="utf-8")
    code, document, _ = _effective_json(root, "--issue", "demo")
    assert code == 0
    assert document["scope"] == {"kind": "issue", "issue": "demo", "resolved": "live"}
    assert [l["name"] for l in document["layers"]] == ["default", "project", "issue"]
    mode = next(f for f in document["fields"] if f["path"] == "stages.define.mode")
    assert (mode["value"], mode["source"], mode["op"]) == ("light", "issue", "set")


def test_pl_11_the_same_input_gives_the_same_bytes_and_no_local_path(tmp_path):
    root = _project(tmp_path, {"schema": 1})
    one = _run(root, "policy", "show", "--json")[1]
    assert one == _run(root, "policy", "show", "--json")[1]
    assert str(tmp_path) not in one


def test_pl_11_nothing_to_resolve_exits_2_with_no_document(tmp_path):
    root = _project(tmp_path, {"schema": 1, "stages": "oops"})
    code, out, err = _run(root, "policy", "show", "--json")
    assert code == 2
    assert out.strip() == ""
    assert "policy lint" in err


# --- PL-12: documented, in the corpus, within the caps --------------------------------

def test_pl_12_both_verbs_describe_themselves(tmp_path):
    root = _project(tmp_path)
    out = _run(root, "policy", "show", "--help")[1]
    assert "source layer" in out and "--issue" in out and "--json" in out
    out = _run(root, "policy", "lint", "--help")[1]
    for option in ("--file", "--exhaustive", "--issue", "--json"):
        assert option in out
    assert "layer" in out


def test_pl_12_the_owning_doc_documents_both_json_shapes_and_every_code():
    text = (ROOT / "docs" / "policy-lint.md").read_text(encoding="utf-8")
    for key in LINT_KEYS + FINDING_KEYS + FIELD_KEYS + LAYER_KEYS + WAIVER_KEYS:
        assert f"`{key}`" in text, key
    for code in _api().FINDING_CODES:
        assert f"`{code}`" in text, code


def test_pl_12_every_code_the_module_names_is_listed():
    import re
    source = (ROOT / "cli" / "compass_pkg" / "policy_lint.py").read_text(encoding="utf-8")
    named = set(re.findall(r'"((?:[LKCEVW]|M)-[A-Z][A-Z-]+|LEGACY-[A-Z-]+)"', source))
    assert named <= set(_api().FINDING_CODES) | {"M-", "L-", "K-"}, \
        named - set(_api().FINDING_CODES)
    assert len(_api().FINDING_CODES) == len(set(_api().FINDING_CODES))


def test_pl_12_the_corpus_records_each_new_verb_with_its_reason():
    text = (ROOT / "tests" / "fixtures" / "compat" / "contract-4-commands.yml").read_text(
        encoding="utf-8")
    lines = text.splitlines()
    for entry in ("policy-effective-shipped", "policy-lint-layered",
                  "policy-lint-layered-broken"):
        index = lines.index(f"- id: {entry}")
        reason = [l for l in lines[max(0, index - 3):index] if l.startswith("#")]
        assert reason and "Added on purpose by policy-lint" in reason[0], entry


def test_pl_12_the_owning_docs_table_names_both_modules():
    text = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    row = next(l for l in text.splitlines() if "cli/compass_pkg/policy_lint.py" in l)
    assert "cli/compass_pkg/policy_cmd.py" in row and "docs/policy-lint.md" in row


def test_pl_12_core_py_stays_within_its_cap():
    lines = (ROOT / "cli" / "compass_pkg" / "core.py").read_text(encoding="utf-8").splitlines()
    assert len(lines) <= 1200


# --- review 1: fixes ---------------------------------------------------------------------

def _raw_preset_paths():
    directory = ROOT / "governance" / "presets" / "default"
    from compass_pkg import catalogue_spec
    out = set()
    for name in catalogue_spec.CATALOGUES:
        part = yaml.safe_load((directory / f"{name}.yml").read_text(encoding="utf-8"))
        for entry_id, entry in part[name].items():
            out |= {f"{name}.{entry_id}.{key}" for key in entry}
    return out


def test_pl_10_every_key_of_every_raw_preset_entry_is_listed_even_a_lock(tmp_path):
    _, document, _ = _effective_json(_project(tmp_path, {"schema": 1}))
    listed = {f["path"] for f in document["fields"]}
    assert _raw_preset_paths() - listed == set()
    locked = next(f for f in document["fields"] if f["path"] == "stages.assess.locked")
    assert (locked["value"], locked["source"], locked["op"]) == (True, "default@6.0.0", "add")


def test_pl_10_a_lock_on_a_stage_follows_the_stages_own_fields_and_names_its_layer():
    parent = _parent_doc()
    parent["stages"]["define"]["locked"] = True
    eff = _effective(parent=_layer(parent, "parent"), project={
        "stages": {"verify": {"locked": "hard"}}})
    paths = [r.path for r in eff.rows if r.path.startswith("stages.define.")]
    assert paths == ["stages.define.order", "stages.define.modes", "stages.define.locked"]
    assert _row(eff, "stages.verify.locked").source == "project"
    assert _row(eff, "stages.verify.locked").value == "hard"
    assert [r for r in eff.rows if r.path == "checks.tests-pass.locked"] == []


def test_pl_10_a_lifted_lock_is_not_listed():
    parent = _parent_doc()
    parent["checks"]["tests-pass"]["locked"] = True
    eff = _effective(parent=_layer(parent, "parent"), project=_owner_unlock())
    assert [r for r in eff.rows if r.path == "checks.tests-pass.locked"] == []
    kept = _effective(parent=_layer(parent, "parent"))
    assert _row(kept, "checks.tests-pass.locked").value is True


def _absolute(text):
    return text is not None and ("/private/" in text or "/tmp/" in text
                                 or "/var/" in text or "/Users/" in text)


def _no_absolute_path(document):
    for finding in document["findings"]:
        assert not _absolute(finding["message"]), finding
        assert not _absolute(json.dumps(finding["detail"])), finding
        assert not _absolute(finding["path"]), finding


def test_pl_8_a_load_finding_names_the_file_from_the_project_root(tmp_path):
    root = _project(tmp_path, "schema: 1\nowner: a\nowner: b\n")
    code, document, _ = _json(root)
    _no_absolute_path(document)
    (finding,) = document["findings"]
    assert finding["path"] == "compass.yml"
    assert finding["message"].startswith("compass.yml:3: duplicate key")


def test_pl_8_a_file_outside_the_project_is_named_by_its_basename(tmp_path):
    bad = tmp_path / "other.yml"
    bad.write_text("schema: 1\nowner: a\nowner: b\n", encoding="utf-8")
    elsewhere = tmp_path / "work"
    elsewhere.mkdir()
    code, out, _ = _run(_project(elsewhere), "policy", "lint", "--json", "--file", str(bad))
    document = json.loads(out)
    _no_absolute_path(document)
    (finding,) = document["findings"]
    assert finding["path"] == "other.yml"
    assert finding["message"].startswith("other.yml:3: duplicate key")


def test_pl_8_a_file_inside_the_project_is_named_from_its_root(tmp_path):
    root = _project(tmp_path)
    (root / "sub").mkdir()
    (root / "sub" / "x.yml").write_text("a: [1\n", encoding="utf-8")
    code, out, _ = _run(root, "policy", "lint", "--json", "--file", str(root / "sub" / "x.yml"))
    document = json.loads(out)
    _no_absolute_path(document)
    assert document["findings"][0]["path"] == "sub/x.yml"


def test_pl_8_a_yaml_error_is_one_line_in_the_text_output(tmp_path):
    root = _project(tmp_path, "a: [1, 2\nb: 3\n")
    code, out, _ = _run(root, "policy", "lint")
    assert code == 1
    assert len(out.splitlines()) == 2
    assert out.splitlines()[1].startswith("  - L-LOAD [project] compass.yml: compass.yml:")


def test_pl_9_the_layers_name_the_project_when_its_file_did_not_load(tmp_path):
    code, document, _ = _json(_project(tmp_path, "a: [1\n"))
    assert [l["name"] for l in document["layers"]] == ["default", "project"]


EFFECT_TARGET_CASES = [
    ("lean_toward", "first", "nonesuch"), ("force_minimum_approach", "max", "nonesuch"),
    ("never_skip", "collect", ["nostage"]), ("require_phase", "collect", "nostage"),
    ("block_phase", "collect", "nostage"), ("add_gate", "collect", "nogate"),
    ("gate", "collect", "nogate"), ("add_artifact", "collect", "noartifact"),
    ("require_artifact", "collect", "noartifact"),
    ("suggest_artifact", "collect", "noartifact"),
]


@pytest.mark.parametrize("effect,policy,value", EFFECT_TARGET_CASES)
def test_pl_4_an_effect_that_names_an_id_nothing_defines_is_reported(effect, policy, value):
    report = _lint(project=_rule_set({effect: policy}, {effect: value}))
    found = _one(report, "M-REF-UNKNOWN")
    assert (found.layer, found.path, found.group) == (
        "project", f"rules.mine.rules.R1.then.{effect}", "resolved")
    assert "nonesuch" in found.message or "no" in found.message


def test_pl_4_an_effect_that_names_a_defined_id_is_not_reported():
    ok = _lint(project=_rule_set({"add_gate": "collect", "force_minimum_approach": "max",
                                  "never_skip": "collect"},
                                 {"add_gate": "verify.correctness",
                                  "force_minimum_approach": "full",
                                  "never_skip": ["define", "verify"]}))
    assert ok.findings == []


def test_pl_4_a_misspelt_effect_key_is_refused_and_a_qualifier_is_not():
    bad = _lint(project=_rule_set({}, {"force_minimum_aproach": "full"}))
    found = _one(bad, "M-EFFECT-UNKNOWN")
    assert found.path == "rules.mine.rules.R1.then.force_minimum_aproach"
    good = _lint(project=_rule_set({"limit": "min"}, {"ceiling": "run_cycles", "limit": 3,
                                                      "until": "a date"}))
    assert good.findings == []


def test_pl_6_the_refusal_path_names_the_approach_and_the_stage_that_changed():
    report = _lint(project={"owner": "o", "approaches": {"regular": {"set": {
        "stages": {"set": {"define": "light"}}}}}})
    found = _one(report, "C-LOOSENING")
    assert found.path == "approaches.regular.stages.define"
    assert found.detail["field"] == "approaches.stages"


def test_pl_6_the_refusal_path_of_an_approach_field_with_no_key_names_the_approach():
    report = _lint(project={"owner": "o", "approaches": {"full": {"set": {
        "subtask_ceiling": 9}}}})
    assert _one(report, "C-LOOSENING").path == "approaches.full.subtask_ceiling"


def test_pl_6_the_refusal_path_of_a_check_or_gate_field_is_unchanged():
    report = _lint(project={"owner": "o", "gates": {"verify.correctness": {"set": {
        "checks": {"remove": ["tests-pass"]}}}}})
    assert "gates.verify.correctness.checks" in [f.path for f in report.findings]


def test_pl_6_an_evaluator_fault_shared_by_two_layers_is_one_finding():
    report = _lint(project={"approaches": {"regular": {"set": {"ships": False}}}},
                   issue={"checks": {"tests-pass": {"set": {"on_skipped": "pass"}}}})
    assert [f.code for f in report.findings] == ["E-EVALUATION"]


def test_pl_5_the_evaluator_finding_holds_the_evaluators_text_and_nothing_of_the_lock():
    report = _lint(parent=_locked_parent(),
                   project={"approaches": {"regular": {"set": {"ships": False}}}})
    message = report.findings[0].message
    assert "unlock cannot help" not in message and "fix the configuration" not in message
    assert message.endswith("evaluator treats it as shipping")


def _help(root, *argv):
    return " ".join(_run(root, *argv, "--help")[1].split())


def test_pl_12_issue_help_says_that_no_issue_is_read_without_it(tmp_path):
    root = _project(tmp_path)
    for verb in ("lint", "show"):
        text = _help(root, "policy", verb)
        assert "COMPASS_ISSUE" in text and "current-task" in text, verb
        assert "no issue" in text.lower(), verb


def test_pl_8_a_project_with_no_compass_yml_lints_an_issues_config_over_the_default(tmp_path):
    root = _project(tmp_path)
    work = root / ".compass" / "work" / "demo"
    work.mkdir(parents=True)
    (work / "manifest.yml").write_text(
        "schema_version: '2.0'\nissue: demo\nconfig:\n  stages: oops\n", encoding="utf-8")
    code, out, _ = _run(root, "policy", "lint", "--issue", "demo")
    assert code == 1
    assert "L-SCHEMA [issue] stages" in out
    code, document, _ = _json(root, "--issue", "demo")
    assert document["mode"] == "layered"
    assert [l["name"] for l in document["layers"]] == ["default", "issue"]


def test_pl_10_the_text_says_what_the_view_is_and_what_still_reads_the_old_files(tmp_path):
    code, out, _ = _run(_project(tmp_path, {"schema": 1}), "policy", "show")
    second = out.splitlines()[1]
    assert "resolves to" in second
    assert "compass check" in second and "evaluator" in second
    assert "generation store" in second


def test_pl_12_the_doc_names_every_code_the_modules_name():
    import re
    text = (ROOT / "docs" / "policy-lint.md").read_text(encoding="utf-8")
    pattern = re.compile(r'"((?:M|W)-[A-Z][A-Z-]+|(?:[LKCEV])-[A-Z][A-Z-]+|LEGACY-[A-Z-]+)"')
    named = set()
    for name in ("merge.py", "waivers.py", "catalogue_check.py", "policy_lint.py"):
        named |= set(pattern.findall(
            (ROOT / "cli" / "compass_pkg" / name).read_text(encoding="utf-8")))
    assert named, "the scan found no code"
    assert {c for c in named if f"`{c}`" not in text} == set()


def test_pl_9_the_legacy_json_keeps_a_waived_rule_as_an_info_finding(tmp_path):
    root = _project(tmp_path)
    governance = root / "governance"
    governance.mkdir()
    for name in ("routing-policy.yml", "guardrails.yml"):
        (governance / name).write_text((ROOT / "governance" / name).read_text(
            encoding="utf-8"), encoding="utf-8")
    policy = yaml.safe_load((governance / "routing-policy.yml").read_text(encoding="utf-8"))
    policy["routing_guardrails"]["waived"] = [{"id": "RP-CAP-001", "reason": "A reason."}]
    (governance / "routing-policy.yml").write_text(yaml.safe_dump(policy), encoding="utf-8")
    code, document, _ = _json(root)
    assert code == 0
    info = [f for f in document["findings"] if f["level"] == "info"]
    assert [(f["code"], f["path"]) for f in info] == [("LEGACY-WAIVED", "RP-CAP-001")]
    assert document["counts"]["errors"] == 0
    assert document["counts"]["warnings"] == len(
        [f for f in document["findings"] if f["level"] == "warning"])


def test_pl_1_a_public_wrapper_answers_what_the_settings_reader_answers(tmp_path):
    from compass_pkg import project_settings
    root = _project(tmp_path, "autonomy: balanced\n")
    assert project_settings.compass_yml_counts(str(root)) is True
    assert project_settings.compass_yml_counts(str(tmp_path / "nowhere")) is False
