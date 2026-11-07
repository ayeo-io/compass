"""The lint of `compass.yml` as a file of settings (`compass_pkg.settings_lint`).

Once Compass runs one fixed set of checks (ADR-094), `compass.yml` holds
settings only. The lint refuses a key the file cannot hold and a value that is
malformed or would not only add, warns about a key 9.0.0 removed, refuses a
git parent, and keeps the integrity rule: every check names an implementation
the CLI holds. The schema and the layer check know the four new keys. Nothing
runs this lint from the command line yet (#357, step 7).
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from compass_pkg import check_set, effective, settings_lint
from compass_pkg.atomic_io import load_yaml_strict
from compass_pkg.core import CompassError

ROOT = Path(__file__).resolve().parent.parent
GOOD = {
    "schema": 1, "owner": "sam", "autonomy": "balanced", "adoption": "enforced",
    "allow_project_commands": True, "language": "en-US",
    "acceptance_strategy": {"state": "on"},
    "signoff_labels": ["billing"],
    "require_evidence": [{"when": {"risk": {"at_least": "cross-cutting"}},
                          "add": ["architecture"]},
                         {"when": {"any_of": [{"labels_any": ["billing"]},
                                              {"urgency": "live-defect"}]},
                          "add": ["reproduce-first"]}],
    "agent_review": "on",
    "project_checks": [{"id": "arch-fitness", "name": "Architecture fitness",
                        "command": "make arch", "stage": "ship"}],
    "capabilities": {"entry-exit-evaluation": True},
}


@pytest.fixture(scope="module", params=["check-set", "live-default"])
def base(request, tmp_path_factory):
    """The check set, and the live default for a project with no `compass.yml`."""
    if request.param == "check-set":
        return check_set.resolved()
    return effective.resolve_live(str(tmp_path_factory.mktemp("bare"))).resolved


def _codes(findings):
    return [(f.code, f.path) for f in findings]


def test_a_file_of_settings_passes(base):
    assert settings_lint.lint(GOOD, base) == []
    assert settings_lint.lint({"schema": 1}, base) == []


def test_the_defaults_of_two_switches_are_accepted(base):
    doc = {"agent_review": "off", "capabilities": {"entry-exit-evaluation": False}}
    assert settings_lint.lint(doc, base) == []
    assert settings_lint.lint({"agent_review": False}, base) == []


@pytest.mark.parametrize("doc, path", [
    ({"bogus": 1}, "bogus"),
    ({"approach": "regular"}, "approach"),
])
def test_an_unknown_key_is_refused(base, doc, path):
    assert _codes(settings_lint.lint(doc, base)) == [("L-SETTING-UNKNOWN", path)]


@pytest.mark.parametrize("doc, path", [
    ({"signoff_labels": "billing"}, "signoff_labels"),
    ({"signoff_labels": ["billing", ""]}, "signoff_labels"),
    ({"require_evidence": {"add": ["security"]}}, "require_evidence"),
    ({"require_evidence": [{"when": {}}]}, "require_evidence[0].add"),
    ({"require_evidence": [{"add": []}]}, "require_evidence[0].add"),
    ({"require_evidence": [{"add": ["approval"]}]}, "require_evidence[0].add"),
    ({"require_evidence": [{"add": ["security"], "remove": ["clarity"]}]},
     "require_evidence[0].remove"),
    ({"require_evidence": [{"add": ["security"], "when": {"risk": "critcal"}}]},
     "require_evidence[0].when.risk"),
    ({"require_evidence": [{"add": ["security"], "when": {"blast": "x"}}]},
     "require_evidence[0].when.blast"),
    ({"require_evidence": [{"add": ["security"], "when": {"goal": {"at_least": "delivery"}}}]},
     "require_evidence[0].when.goal"),
    ({"require_evidence": [{"add": ["security"], "when": {"any_of": [{"size": "huge"}]}}]},
     "require_evidence[0].when.any_of[0].size"),
    ({"agent_review": "sometimes"}, "agent_review"),
    ({"agent_review": 1}, "agent_review"),
    ({"project_checks": {"id": "x"}}, "project_checks"),
    ({"project_checks": [{"id": "G5", "name": "n", "command": "c", "stage": "ship"}]},
     "project_checks[0].id"),
    ({"project_checks": [{"id": "suite-passed", "name": "n", "command": "c",
                          "stage": "ship"}]}, "project_checks[0].id"),
    ({"project_checks": [{"id": "agent-review", "name": "n", "command": "c",
                          "stage": "ship"}]}, "project_checks[0].id"),
    ({"project_checks": [{"id": "has space", "name": "n", "command": "c",
                          "stage": "ship"}]}, "project_checks[0].id"),
    ({"project_checks": [{"id": "x", "name": "n", "command": "c", "stage": "specify"}]},
     "project_checks[0].stage"),
    ({"project_checks": [{"id": "x", "name": "n", "stage": "ship"}]},
     "project_checks[0].command"),
    ({"project_checks": [{"id": "x", "name": "n", "command": "c", "stage": "ship",
                          "severity": "advisory"}]}, "project_checks[0].severity"),
    ({"project_checks": [{"id": "x", "name": "n", "command": "c", "stage": "ship"},
                         {"id": "x", "name": "m", "command": "d", "stage": "build"}]},
     "project_checks[1].id"),
    ({"capabilities": {"readiness-floor": True}}, "capabilities.readiness-floor"),
    ({"capabilities": {"entry-exit-evaluation": "yes"}},
     "capabilities.entry-exit-evaluation"),
    ({"autonomy": "sometimes"}, "autonomy"),
    ({"owner": ""}, "owner"),
])
def test_a_value_that_is_malformed_or_does_not_only_add_is_refused(base, doc, path):
    found = settings_lint.lint(doc, base)
    assert ("L-SETTING-INVALID", path) in _codes(found), _codes(found)
    assert all(f.level == "error" for f in found if f.code == "L-SETTING-INVALID")


@pytest.mark.parametrize("key, value", [
    ("checks", {"suite-passed": {"set": {"severity": "advisory"}}}),
    ("gates", {}), ("rules", {}), ("stages", {}), ("dimensions", {}), ("vocabulary", {}),
    ("extends", "compass:default@6"), ("preset", {}), ("preset_index", "x"),
    ("approaches", {}), ("models", {}), ("readiness", {}),
])
def test_a_removed_key_warns_and_is_not_refused(base, key, value):
    found = settings_lint.lint({key: value}, base)
    assert _codes(found) == [("L-SETTING-REMOVED", key)]
    assert found[0].level == "warning"


def test_a_removed_approver_list_warns(base):
    found = settings_lint.lint({"approvers": {"project-waiver": ["sam"],
                                              "issue-waiver": ["sam"]}}, base)
    assert _codes(found) == [("L-SETTING-REMOVED", "approvers.project-waiver")]


def test_a_removed_capability_turned_on_warns(base):
    found = settings_lint.lint({"capabilities": {"artifact-freshness": True}}, base)
    assert _codes(found) == [("L-SETTING-REMOVED", "capabilities.artifact-freshness")]


def test_a_removed_catalogue_is_named_once_not_once_per_entry(base):
    doc = {"stages": {"define": {"set": {"mode": "thorough"}}},
           "checks": {"dor-summary-filled": {"remove": True}}}
    assert _codes(settings_lint.lint(doc, base)) == [("L-SETTING-REMOVED", "stages"),
                                                      ("L-SETTING-REMOVED", "checks")]


@pytest.mark.parametrize("extends", ["github:team/policy@main#0123abc",
                                     {"from": "github:team/policy@main#0123abc"}])
def test_a_git_parent_is_refused(base, extends):
    found = settings_lint.lint({"extends": extends}, base)
    assert _codes(found) == [("L-PARENT-REMOVED", "extends")]
    assert found[0].level == "error"


def test_errors_come_before_warnings(base):
    found = settings_lint.lint({"checks": {}, "bogus": 1}, base)
    assert [f.level for f in found] == ["error", "warning"]


def test_without_a_base_only_the_shape_is_checked():
    doc = {"project_checks": [{"id": "G5", "name": "n", "command": "c", "stage": "ship"}],
           "require_evidence": [{"add": ["security"], "when": {"risk": "critcal"}}]}
    assert settings_lint.lint(doc) == []


def test_this_repositorys_compass_yml_has_no_error(base):
    found = settings_lint.lint(load_yaml_strict(str(ROOT / "compass.yml")), base)
    assert [f for f in found if f.level == "error"] == []


def test_not_a_mapping_is_refused():
    assert _codes(settings_lint.lint(["schema"])) == [("L-SETTING-INVALID", "(top level)")]


def test_every_finding_code_is_declared(base):
    docs = [{"bogus": 1}, {"autonomy": "x"}, {"checks": {}},
            {"extends": "github:a/b@c#0123abc"}]
    seen = {f.code for doc in docs for f in settings_lint.lint(doc, base)}
    assert seen <= set(settings_lint.CODES)


# --- the integrity rule ------------------------------------------------------------

def test_the_shipped_configuration_passes_the_integrity_rule(base):
    assert settings_lint.integrity(base) == []


def test_a_check_with_an_implementation_the_cli_lacks_fails_the_integrity_rule(base):
    broken = copy.deepcopy(base)
    broken["checks"]["suite-passed"]["impl"] = "suite-passed-v2"
    broken["checks"]["no-impl"] = {"kind": "deterministic", "statement": "x"}
    assert [p for p, _ in settings_lint.integrity(broken)] == [
        "checks.suite-passed.impl", "checks.no-impl.impl"]
    found = settings_lint.lint({"schema": 1}, broken)
    assert ("L-IMPL-UNKNOWN", "checks.suite-passed.impl") in _codes(found)


def test_a_judged_or_human_check_needs_no_implementation(base):
    assert settings_lint.integrity({"checks": {
        "a": {"kind": "judged"}, "b": {"kind": "human"}}}) == []


# --- the settings, a governance copy and the schema ------------------------------

def test_the_lint_accepts_the_settings_and_refuses_a_bad_shape():
    assert settings_lint.lint(GOOD) == []
    found = settings_lint.lint({"signoff_labels": "billing"})
    assert [(f.code, f.path, f.message) for f in found] == [
        ("L-SETTING-INVALID", "signoff_labels", "expected a list of label names")]


@pytest.mark.parametrize("key", ["signoff_labels", "require_evidence", "agent_review",
                                 "project_checks"])
def test_a_governance_copy_cannot_hold_a_tighten_only_setting(key):
    """A project's own governance copy is the one configuration besides
    `compass.yml` (until #359); a setting belongs in `compass.yml` only."""
    with pytest.raises(CompassError, match=f"legacy: {key} is a settings key and belongs "
                                           f"in the project's own compass.yml"):
        effective._legacy_config({key: GOOD[key]})


def test_the_committed_schema_holds_the_five_settings():
    schema = json.loads((ROOT / "schemas" / "compass.schema.json").read_text(encoding="utf-8"))
    assert schema == settings_lint.schema()
    props = schema["properties"]
    for key in ("signoff_labels", "require_evidence", "agent_review", "project_checks",
                "capabilities"):
        assert key in props, key
    assert props["project_checks"]["items"]["properties"]["stage"]["enum"] == ["build", "ship"]
    from compass_pkg.evidence_required import TOKENS
    token = props["require_evidence"]["items"]["properties"]["add"]["items"]
    assert token["enum"] == list(TOKENS)


def test_the_schema_accepts_the_good_file_and_refuses_a_lowering():
    jsonschema = pytest.importorskip("jsonschema")
    schema = settings_lint.schema()
    jsonschema.validate(GOOD, schema)
    for bad in ({"require_evidence": [{"add": ["security"], "remove": ["clarity"]}]},
                {"project_checks": [dict(GOOD["project_checks"][0], severity="advisory")]},
                {"agent_review": "sometimes"},
                {"require_evidence": [{"add": ["approval"]}]}):
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(bad, schema)
