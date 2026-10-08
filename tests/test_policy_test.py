"""`compass policy test` and `compass policy init-preset` (issue `policy-test-init-preset`).

`policy test` runs a preset's fixture assessments and reports, for each
fixture, whether the computed approach, gates, stages and checks match what
the fixture expects. `init-preset` scaffolds a preset repository. These tests
run the CLI in a temporary folder and, for a git parent, point
`COMPASS_PARENT_REMOTE_BASE` at a local repository, so nothing reaches the
network.

Scenario ids: `PT-1` to `PT-10`. Each test name starts with its scenario id.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))
from parent_fixtures import REAL_GIT, make_remote  # noqa: E402

CLI = ROOT / "cli" / "compass"

SMALL = {"risk": "contained", "familiarity": "brownfield-mapped", "size": "small",
         "goal": "delivery", "role": "engineer", "labels": []}
QUICK_FIX_GATES = ["G1", "G2", "G3", "G4", "verify.correctness", "verify.governance",
                   "verify.traceability"]
PRESET = {"schema": 1, "owner": "acme-team"}
# A preset that adds one gate to the quick fix approach: a fixture that expects
# the extra gate passes only when the fixtures run over the preset.
ADDS_A_GATE = {"schema": 1, "owner": "acme-team", "approaches": {
    "quick-fix": {"set": {"gates": {"add": ["verify.clarity"]}}}}}
UNLOCK = {"schema": 1, "owner": "acme-team", "checks": {"suite-passed": {"unlock": True}}}
UNKNOWN_IMPL = {"schema": 1, "owner": "acme-team", "checks": {"evil": {
    "name": "evil", "kind": "mechanical", "impl": "rm-rf", "blocking_when": "fail"}}}
LOCKED_LOOSENED = {"schema": 1, "owner": "acme-team", "checks": {
    "suite-passed": {"set": {"severity": "advisory"}}}}


# --- helpers -------------------------------------------------------------------------

def _env(home, extra=None):
    env = {"PATH": os.environ.get("PATH", REAL_GIT), "HOME": str(home), "LANG": "C.UTF-8",
           "LC_ALL": "C.UTF-8", "NO_COLOR": "1", "COLUMNS": "100",
           "PYTHONDONTWRITEBYTECODE": "1", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
           "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}
    env.update(extra or {})
    return env


def _run(cwd, *argv, env=None):
    done = subprocess.run([sys.executable, str(CLI), *argv], cwd=cwd, env=_env(cwd, env),
                          capture_output=True, text=True, timeout=180)
    return done.returncode, done.stdout, done.stderr


def _fixture(expect, assessment=None, **extra):
    return {"assessment": dict(SMALL if assessment is None else assessment),
            "expect": expect, **extra}


GOOD = _fixture({"approach": "quick-fix"})


def _preset(tmp_path, doc=None, fixtures=None, folder="preset"):
    """A preset folder: a `compass.yml` and one fixture file per entry of
    `fixtures` (a name mapped to a mapping, or to text written as it is)."""
    root = tmp_path / folder
    (root / "compass-fixtures").mkdir(parents=True)
    (root / "compass.yml").write_text(yaml.safe_dump(PRESET if doc is None else doc),
                                      encoding="utf-8")
    for name, body in (fixtures if fixtures is not None else {"small": GOOD}).items():
        text = body if isinstance(body, str) else yaml.safe_dump(body)
        (root / "compass-fixtures" / f"{name}.yml").write_text(text, encoding="utf-8")
    return root


def _test(tmp_path, preset, *extra, env=None):
    code, out, err = _run(tmp_path, "policy", "test", str(preset), *extra, env=env)
    return code, out, err


def _json(tmp_path, preset, *extra, env=None):
    code, out, err = _run(tmp_path, "policy", "test", str(preset), "--json", *extra, env=env)
    assert out.strip().startswith("{"), (code, out, err)
    return code, json.loads(out)


# --- PT-1: a matching fixture passes -----------------------------------------------------

def test_pt_1_a_matching_fixture_is_reported_as_passing(tmp_path):
    code, out, err = _test(tmp_path, _preset(tmp_path))
    assert code == 0, (out, err)
    assert "PASS" in out
    assert "small" in out
    assert "1 passed" in out


def test_pt_2_the_fixtures_run_over_the_preset_and_not_the_default_alone(tmp_path):
    gates = sorted(QUICK_FIX_GATES + ["verify.clarity"])
    fixture = _fixture({"approach": "quick-fix", "gates": gates})
    with_gate = _preset(tmp_path, ADDS_A_GATE, {"small": fixture}, folder="with")
    without = _preset(tmp_path, PRESET, {"small": fixture}, folder="without")
    assert _test(tmp_path, with_gate)[0] == 0
    code, report = _json(tmp_path, without)
    assert code == 1
    assert report["fixtures"][0]["mismatches"][0]["field"] == "gates"


def test_pt_1_the_expected_stages_and_checks_are_compared(tmp_path):
    from compass_pkg import obligations, replay
    shipped = replay.resolve_ref("default@6", ROOT)
    owed = obligations.obligations(shipped.config, SMALL, capabilities=shipped.capabilities)
    checks = sorted({c for ids in owed.gate_checks.values() for c in ids})
    fixture = _fixture({"approach": "quick-fix", "gates": QUICK_FIX_GATES, "checks": checks,
                        "stages": {"implement": "full", "plan": "collapsed"}})
    code, out, err = _test(tmp_path, _preset(tmp_path, fixtures={"all-four": fixture}))
    assert code == 0, (out, err)


def test_pt_1_gates_and_checks_are_sets_and_their_order_in_the_file_does_not_matter(tmp_path):
    fixture = _fixture({"approach": "quick-fix", "gates": list(reversed(QUICK_FIX_GATES))})
    code, out, err = _test(tmp_path, _preset(tmp_path, fixtures={"reversed": fixture}))
    assert code == 0, (out, err)


# --- PT-2: a difference fails and is named -------------------------------------------------

DIFFERENCES = [
    ("approach", {"approach": "full"}, "full", "quick-fix"),
    ("gates", {"gates": ["G1"]}, ["G1"], QUICK_FIX_GATES),
    ("stages.implement", {"stages": {"implement": "light"}}, "light", "full"),
    ("checks", {"checks": ["suite-passed"]}, ["suite-passed"], None),
]


@pytest.mark.parametrize("field,expect,expected,actual", DIFFERENCES,
                         ids=[d[0] for d in DIFFERENCES])
def test_pt_2_a_difference_fails_the_fixture_and_names_the_field(
        tmp_path, field, expect, expected, actual):
    preset = _preset(tmp_path, fixtures={"small": _fixture(expect)})
    code, report = _json(tmp_path, preset)
    assert code == 1
    assert report["result"] == "fail"
    fixture = report["fixtures"][0]
    assert fixture["status"] == "fail"
    assert [m["field"] for m in fixture["mismatches"]] == [field]
    mismatch = fixture["mismatches"][0]
    assert mismatch["expected"] == expected
    if actual is not None:
        assert mismatch["actual"] == actual
    code, out, _ = _test(tmp_path, preset)
    assert code == 1
    assert "FAIL" in out and field in out and "expected" in out


def test_pt_2_one_failing_fixture_does_not_hide_a_passing_one(tmp_path):
    preset = _preset(tmp_path, fixtures={"a-good": GOOD, "b-bad": _fixture({"approach": "full"})})
    code, report = _json(tmp_path, preset)
    assert code == 1
    assert [f["status"] for f in report["fixtures"]] == ["pass", "fail"]
    assert report["totals"] == {"fixtures": 2, "passed": 1, "failed": 1}


# --- PT-3: the framework locks and the data-only rules ------------------------------------

LINT_CASES = [(UNLOCK, "L-UNLOCK-PLACEMENT"), (UNKNOWN_IMPL, "L-IMPL-UNKNOWN"),
              ({**PRESET, "autonomy": "balanced"}, "L-SETTINGS-KEY"),
              ({**PRESET, "allow_project_commands": True}, "L-SETTINGS-KEY"),
              (LOCKED_LOOSENED, "K-LOCK-REFUSED")]


@pytest.mark.parametrize("doc,code_wanted", LINT_CASES,
                         ids=[c[1] + str(i) for i, c in enumerate(LINT_CASES)])
def test_pt_3_a_preset_that_breaks_a_rule_fails_before_any_fixture_runs(
        tmp_path, doc, code_wanted):
    code, report = _json(tmp_path, _preset(tmp_path, doc))
    assert code == 1
    assert report["result"] == "fail"
    assert report["lint"]["ok"] is False
    assert report["lint"]["stopped_after"] in ("layer", "locks"), report["lint"]
    assert code_wanted in [f["code"] for f in report["lint"]["findings"]], report["lint"]
    assert report["fixtures_run"] is False
    assert report["fixtures"] == []


def test_pt_3_every_finding_names_the_preset_layer_and_never_the_project(tmp_path):
    cases = {"load": ("schema: [\n", "L-LOAD"),
             "extends": (yaml.safe_dump({"schema": 1, "extends": "github:acme/x@1"}),
                         "L-PARENT-NO-SHA"),
             "waiver": (yaml.safe_dump(_loosening(_waiver("someone-else"))), "W-")}
    for name, (text, code_wanted) in cases.items():
        preset = _preset(tmp_path, fixtures={}, folder=name)
        (preset / "compass.yml").write_text(text, encoding="utf-8")
        _, out, _ = _run(tmp_path, "policy", "test", str(preset), "--json")
        report = json.loads(out)
        found = [f for f in report["lint"]["findings"] if f["code"].startswith(code_wanted)]
        assert found, (name, report["lint"])
        for finding in report["lint"]["findings"]:
            assert finding["layer"] == "preset", (name, finding)
            assert not finding["path"].startswith("project"), (name, finding)


def test_pt_3_the_text_report_names_the_finding(tmp_path):
    code, out, _ = _test(tmp_path, _preset(tmp_path, UNLOCK))
    assert code == 1
    assert "L-UNLOCK-PLACEMENT" in out
    assert "not run" in out


@pytest.mark.parametrize("value", ["yes", 1, "true"])
def test_pt_3_a_capability_switch_that_is_not_true_or_false_is_refused_by_the_lint(
        tmp_path, value):
    doc = {**PRESET, "capabilities": {"entry-exit-evaluation": value}}
    code, report = _json(tmp_path, _preset(tmp_path, doc))
    assert code == 1 and report["fixtures_run"] is False


def test_pt_3_the_text_report_shows_the_fixture_path_from_the_preset_folder(tmp_path):
    code, out, _ = _test(tmp_path, _preset(tmp_path))
    assert code == 0 and "(compass-fixtures/small.yml)" in out


# --- PT-3: a preset's waiver is approved by the preset's own owner -----------------------

def _loosening(waiver=None, owner="acme-team", **extra):
    entry = {"set": {"gates": {"remove": ["verify.clarity"]}}}
    if waiver is not None:
        entry["waiver"] = waiver
    doc = {"schema": 1, "approaches": {"regular": entry}, **extra}
    if owner:
        doc["owner"] = owner
    return doc


def _waiver(by="acme-team"):
    return {"reason": "the team reviews clarity in pairing", "approved_by": by,
            "approved_on": "2026-10-01"}


def _codes_of(report):
    return [f["code"] for f in report["lint"]["findings"]]


def test_pt_3_a_loosening_preset_with_a_waiver_approved_by_its_owner_passes(tmp_path):
    code, report = _json(tmp_path, _preset(tmp_path, _loosening(_waiver())))
    assert code == 0, report["lint"]
    assert report["lint"]["findings"] == []


def test_pt_3_a_loosening_preset_without_a_waiver_fails(tmp_path):
    code, report = _json(tmp_path, _preset(tmp_path, _loosening()))
    assert code == 1
    assert "C-LOOSENING" in _codes_of(report)


def test_pt_3_a_waiver_approved_by_someone_else_than_the_owner_fails(tmp_path):
    code, report = _json(tmp_path, _preset(tmp_path, _loosening(_waiver("someone-else"))))
    assert code == 1
    assert "C-LOOSENING" in _codes_of(report) or any(
        c.startswith("W-") for c in _codes_of(report)), report["lint"]


def test_pt_3_a_waiver_in_a_preset_with_no_owner_fails(tmp_path):
    code, report = _json(tmp_path, _preset(tmp_path, _loosening(_waiver(), owner=None)))
    assert code == 1
    assert "W-NO-OWNER" in _codes_of(report)


def test_pt_3_the_owner_of_the_project_that_runs_the_test_is_not_consulted(tmp_path):
    """The working folder holds a project whose owner would approve the waiver."""
    (tmp_path / "compass.yml").write_text(yaml.safe_dump({"schema": 1, "owner": "someone-else"}),
                                          encoding="utf-8")
    code, report = _json(tmp_path, _preset(tmp_path, _loosening(_waiver("someone-else"))))
    assert code == 1


# --- PT-4: a malformed fixture ---------------------------------------------------------------

MALFORMED = {
    "unparseable": "assessment: [\n",
    "unknown-key": _fixture({"approach": "quick-fix"}, bogus=1),
    "no-assessment": {"expect": {"approach": "quick-fix"}},
    "no-expect": {"assessment": SMALL},
    "empty-expect": _fixture({}),
    "unknown-expect-key": _fixture({"approach": "quick-fix", "speed": "fast"}),
    "rejected-value": _fixture({"approach": "quick-fix"}, assessment={**SMALL, "risk": "enormous"}),
    "not-a-mapping": "- just\n- a list\n",
    "name-not-text": _fixture({"approach": "quick-fix"}, name=["a", "list"]),
    "empty-stages": _fixture({"approach": "quick-fix", "stages": {}}),
    "stages-not-a-mapping": _fixture({"stages": ["implement"]}),
    "stage-mode-not-text": _fixture({"stages": {"implement": 1}}),
    "gates-not-a-list": _fixture({"gates": "G1"}),
    "gate-id-not-text": _fixture({"gates": [1]}),
    "checks-not-a-list": _fixture({"checks": "suite-passed"}),
    "approach-not-text": _fixture({"approach": 5}),
    "assessment-key-unknown": _fixture({"approach": "quick-fix"},
                                       assessment={**SMALL, "colour": "red"}),
    "labels-not-a-list": _fixture({"approach": "quick-fix"},
                                  assessment={**SMALL, "labels": "auth"}),
    "label-not-text": _fixture({"approach": "quick-fix"}, assessment={**SMALL, "labels": [1]}),
}


@pytest.mark.parametrize("name", sorted(MALFORMED))
def test_pt_4_a_malformed_fixture_is_an_error_and_fails_the_run(tmp_path, name):
    preset = _preset(tmp_path, fixtures={"a-good": GOOD, "z-bad": MALFORMED[name]})
    code, report = _json(tmp_path, preset)
    assert code == 1
    assert [f["status"] for f in report["fixtures"]] == ["pass", "error"], report
    bad = report["fixtures"][1]
    assert bad["file"] == "z-bad.yml"
    assert bad["message"], "an error names its reason"
    assert bad["mismatches"] == []
    assert report["totals"] == {"fixtures": 2, "passed": 1, "failed": 1}


def test_pt_4_the_error_text_shows_in_the_text_report(tmp_path):
    preset = _preset(tmp_path, fixtures={"bad": MALFORMED["unknown-key"]})
    code, out, _ = _test(tmp_path, preset)
    assert code == 1
    assert "ERROR" in out and "bogus" in out


def test_pt_4_an_empty_gates_or_checks_list_is_an_expectation_that_none_are_owed(tmp_path):
    fixture = _fixture({"gates": []})
    code, report = _json(tmp_path, _preset(tmp_path, fixtures={"none": fixture}))
    assert code == 1
    assert report["fixtures"][0]["status"] == "fail"
    assert report["fixtures"][0]["mismatches"][0]["field"] == "gates"


def test_pt_4_a_stage_the_result_does_not_hold_has_a_null_actual(tmp_path):
    fixture = _fixture({"stages": {"no-such-stage": "full"}})
    code, report = _json(tmp_path, _preset(tmp_path, fixtures={"s": fixture}))
    assert code == 1
    assert report["fixtures"][0]["mismatches"] == [
        {"field": "stages.no-such-stage", "expected": "full", "actual": None}]


def test_pt_4_a_yaml_error_names_the_fixture_by_its_path_in_the_preset(tmp_path):
    preset = _preset(tmp_path, fixtures={"bad": "assessment: [\n"})
    _, report = _json(tmp_path, preset)
    message = report["fixtures"][0]["message"]
    assert str(tmp_path) not in message and "compass-fixtures/bad.yml" in message


def test_pt_4_a_multi_line_error_stays_under_its_fixture_in_the_text_report(tmp_path):
    preset = _preset(tmp_path, fixtures={"bad": "assessment: [\n  - a\nexpect: {\n"})
    _, out, _ = _run(tmp_path, "policy", "test", str(preset))
    lines = out.splitlines()
    start = next(i for i, line in enumerate(lines) if "ERROR" in line)
    rest = [line for line in lines[start + 1:] if not line.startswith("  problem")]
    assert rest and all(line.startswith("      ") for line in rest), out


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads any file")
def test_pt_4_a_fixture_file_that_cannot_be_read_is_an_error_on_that_fixture(tmp_path):
    preset = _preset(tmp_path, fixtures={"a-good": GOOD, "z-locked": GOOD})
    locked = preset / "compass-fixtures" / "z-locked.yml"
    locked.chmod(0)
    try:
        code, report = _json(tmp_path, preset)
    finally:
        locked.chmod(0o600)
    assert code == 1
    assert [f["status"] for f in report["fixtures"]] == ["pass", "error"]


# --- PT-5: nothing to run, and nothing to read ----------------------------------------------

def test_pt_5_a_preset_with_no_fixtures_fails(tmp_path):
    preset = _preset(tmp_path, fixtures={})
    code, report = _json(tmp_path, preset)
    assert code == 1
    assert report["fixtures"] == []
    assert any("no fixtures" in p for p in report["problems"]), report["problems"]


def test_pt_5_a_preset_with_no_fixture_folder_fails(tmp_path):
    preset = _preset(tmp_path)
    for child in (preset / "compass-fixtures").iterdir():
        child.unlink()
    (preset / "compass-fixtures").rmdir()
    code, report = _json(tmp_path, preset)
    assert code == 1
    assert any("no fixtures" in p for p in report["problems"])


def test_pt_5_a_sub_folder_of_fixtures_fails_and_is_not_skipped_silently(tmp_path):
    preset = _preset(tmp_path)
    group = preset / "compass-fixtures" / "meets" / "banking"
    group.mkdir(parents=True)
    (group / "one.yml").write_text(yaml.safe_dump(GOOD), encoding="utf-8")
    code, report = _json(tmp_path, preset)
    assert code == 1
    assert report["totals"]["fixtures"] == 1
    assert any("compass-fixtures/meets" in p and "not read" in p for p in report["problems"])


def test_pt_5_a_folder_with_no_compass_yml_is_an_input_error(tmp_path):
    (tmp_path / "empty").mkdir()
    code, out, err = _run(tmp_path, "policy", "test", "empty")
    assert code == 2
    assert "compass.yml" in out + err


def test_pt_5_a_missing_folder_is_an_input_error(tmp_path):
    code, out, err = _run(tmp_path, "policy", "test", "nowhere")
    assert code == 2
    assert "nowhere" in out + err and "no such folder" in out + err


def test_pt_5_a_file_given_as_the_preset_folder_is_an_input_error(tmp_path):
    (tmp_path / "compass.yml").write_text("schema: 1\n", encoding="utf-8")
    code, out, err = _run(tmp_path, "policy", "test", "compass.yml")
    assert code == 2
    assert "not a folder" in out + err


def test_pt_5_a_yaml_file_and_a_hidden_file_are_handled_by_name(tmp_path):
    preset = _preset(tmp_path)
    (preset / "compass-fixtures" / "other.yaml").write_text(yaml.safe_dump(GOOD), encoding="utf-8")
    (preset / "compass-fixtures" / ".hidden.yml").write_text("not: [a fixture", encoding="utf-8")
    (preset / "compass-fixtures" / "notes.md").write_text("words\n", encoding="utf-8")
    code, report = _json(tmp_path, preset)
    assert code == 1
    assert report["totals"]["fixtures"] == 1
    assert [p for p in report["problems"] if "other.yaml" in p and ".yml" in p]
    assert len(report["problems"]) == 1, "a hidden file and a note are not problems"


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads any file")
def test_pt_5_a_compass_yml_that_cannot_be_read_is_an_input_error(tmp_path):
    preset = _preset(tmp_path)
    (preset / "compass.yml").chmod(0)
    try:
        code, out, err = _run(tmp_path, "policy", "test", str(preset))
    finally:
        (preset / "compass.yml").chmod(0o600)
    assert code == 2
    assert "compass.yml" in out + err and "cannot be read" in out + err


def test_pt_5_a_compass_yml_that_is_not_utf_8_is_an_input_error(tmp_path):
    preset = _preset(tmp_path)
    (preset / "compass.yml").write_bytes(b"schema: 1\nowner: \xff\xfe\n")
    code, out, err = _run(tmp_path, "policy", "test", str(preset))
    assert code == 2
    assert "cannot be read" in out + err


def test_pt_5_a_compass_yml_that_is_readable_but_malformed_is_a_lint_error(tmp_path):
    preset = _preset(tmp_path)
    (preset / "compass.yml").write_text("schema: [\n", encoding="utf-8")
    code, report = _json(tmp_path, preset)
    assert code == 1
    assert "L-LOAD" in _codes_of(report)
    assert report["fixtures_run"] is False


def test_pt_5_a_broken_link_named_like_a_fixture_is_a_problem(tmp_path):
    preset = _preset(tmp_path)
    os.symlink(tmp_path / "nowhere.yml", preset / "compass-fixtures" / "x.yml")
    code, report = _json(tmp_path, preset)
    assert code == 1
    assert [p for p in report["problems"] if "x.yml" in p and "not a file" in p], report


@pytest.mark.parametrize("name", ["upper.YML", "other.yaml", "mixed.Yaml"])
def test_pt_5_a_fixture_file_with_another_spelling_of_the_suffix_is_a_problem(tmp_path, name):
    preset = _preset(tmp_path)
    (preset / "compass-fixtures" / name).write_text(yaml.safe_dump(GOOD), encoding="utf-8")
    code, report = _json(tmp_path, preset)
    assert code == 1
    assert [p for p in report["problems"] if name in p and "end in .yml" in p], report


def test_pt_5_the_folder_defaults_to_the_working_folder(tmp_path):
    preset = _preset(tmp_path)
    code, out, err = _run(preset, "policy", "test")
    assert code == 0, (out, err)


# --- PT-6: the --json report -------------------------------------------------------------------

def test_pt_6_the_json_report_has_the_documented_keys_in_the_documented_order(tmp_path):
    preset = _preset(tmp_path, fixtures={"a-good": GOOD, "b-bad": _fixture({"approach": "full"})})
    code, out, _ = _run(tmp_path, "policy", "test", str(preset), "--json")
    report = json.loads(out)
    assert list(report) == ["schema", "preset", "result", "lint", "fixtures_run", "totals",
                            "fixtures", "problems"]
    assert report["schema"] == 1
    assert report["preset"] == "preset"
    assert list(report["lint"]) == ["ok", "stopped_after", "findings"]
    assert list(report["totals"]) == ["fixtures", "passed", "failed"]
    assert list(report["fixtures"][0]) == ["file", "name", "status", "mismatches", "message"]
    assert report["fixtures"][0]["file"] == "a-good.yml"
    assert list(report["fixtures"][1]["mismatches"][0]) == ["field", "expected", "actual"]
    assert report["problems"] == []
    assert code == 1


def test_pt_6_a_lint_finding_has_the_same_keys_as_policy_lint(tmp_path):
    _, report = _json(tmp_path, _preset(tmp_path, UNLOCK))
    assert list(report["lint"]["findings"][0]) == [
        "code", "level", "layer", "path", "group", "message", "detail"]


def test_pt_6_the_json_report_is_the_same_on_two_runs(tmp_path):
    preset = _preset(tmp_path)
    first = _run(tmp_path, "policy", "test", str(preset), "--json")[1]
    second = _run(tmp_path, "policy", "test", str(preset), "--json")[1]
    assert first == second


def test_pt_6_the_report_never_holds_an_absolute_path(tmp_path):
    preset = _preset(tmp_path)
    _, out, _ = _run(tmp_path, "policy", "test", str(preset), "--json")
    assert str(tmp_path) not in out


def test_pt_6_a_preset_outside_the_working_folder_shows_its_own_name_only(tmp_path):
    preset = _preset(tmp_path, folder="elsewhere")
    other = tmp_path / "work"
    other.mkdir()
    code, out, _ = _run(other, "policy", "test", str(preset), "--json")
    report = json.loads(out)
    assert code == 0 and report["preset"] == "elsewhere"
    assert str(tmp_path) not in out
    code, out, _ = _run(other, "policy", "test", str(preset))
    assert str(tmp_path) not in out


def test_pt_6_fixtures_are_listed_in_file_name_order(tmp_path):
    preset = _preset(tmp_path, fixtures={"b": GOOD, "a": GOOD, "c": GOOD})
    _, report = _json(tmp_path, preset)
    assert [f["file"] for f in report["fixtures"]] == ["a.yml", "b.yml", "c.yml"]


def test_pt_6_a_fixture_name_defaults_to_its_file_stem_and_can_be_set(tmp_path):
    preset = _preset(tmp_path, fixtures={"plain": GOOD, "named": {**GOOD, "name": "Small work"}})
    _, report = _json(tmp_path, preset)
    assert {f["file"]: f["name"] for f in report["fixtures"]} == {
        "named.yml": "Small work", "plain.yml": "plain"}


# --- PT-7: init-preset scaffolds a preset that passes -----------------------------------------

def test_pt_7_init_preset_writes_the_four_files(tmp_path):
    code, out, err = _run(tmp_path, "policy", "init-preset", "acme-preset", "--owner", "acme-team")
    assert code == 0, (out, err)
    folder = tmp_path / "acme-preset"
    names = sorted(str(p.relative_to(folder)) for p in folder.rglob("*") if p.is_file())
    assert names == [".gitignore", "README.md", "compass-fixtures/example.yml", "compass.yml"]
    example = yaml.safe_load((folder / "compass-fixtures" / "example.yml").read_text("utf-8"))
    assert "verify.clarity" in example["expect"]["gates"]
    doc = yaml.safe_load((folder / "compass.yml").read_text(encoding="utf-8"))
    assert doc["schema"] == 1 and doc["owner"] == "acme-team"
    for line in names:
        assert line in out


def test_pt_7_the_scaffold_passes_policy_test_where_it_stands(tmp_path):
    assert _run(tmp_path, "policy", "init-preset", "acme-preset", "--owner", "acme-team")[0] == 0
    code, out, err = _run(tmp_path / "acme-preset", "policy", "test")
    assert code == 0, (out, err)
    assert "1 passed" in out


def test_pt_7_the_scaffold_is_clean_under_policy_lint_and_ignores_the_cache(tmp_path):
    _run(tmp_path, "policy", "init-preset", "acme-preset", "--owner", "acme-team")
    folder = tmp_path / "acme-preset"
    code, out, err = _run(folder, "policy", "lint", "--file", "compass.yml")
    assert code == 0, (out, err)
    assert ".compass/" in (folder / ".gitignore").read_text(encoding="utf-8")


def test_pt_7_the_readme_says_how_to_test_and_how_to_extend_it(tmp_path):
    _run(tmp_path, "policy", "init-preset", "acme-preset", "--owner", "acme-team")
    text = (tmp_path / "acme-preset" / "README.md").read_text(encoding="utf-8")
    assert "compass policy test" in text
    assert "extends: github:" in text
    assert "compass-fixtures" in text
    assert "docs/policy-test.md" in text


def test_pt_7_the_owner_is_required(tmp_path):
    code, out, err = _run(tmp_path, "policy", "init-preset", "acme-preset")
    assert code == 2
    assert "--owner" in out + err
    assert not (tmp_path / "acme-preset").exists()


@pytest.mark.parametrize("owner", ["", "   "])
def test_pt_7_an_empty_owner_is_an_input_error(tmp_path, owner):
    code, out, err = _run(tmp_path, "policy", "init-preset", "acme-preset", "--owner", owner)
    assert code == 2
    assert "--owner" in out + err
    assert not (tmp_path / "acme-preset").exists()


def test_pt_7_an_owner_with_yaml_characters_is_written_as_a_string(tmp_path):
    owner = "Acme: Platform #1 {core}"
    assert _run(tmp_path, "policy", "init-preset", "acme-preset", "--owner", owner)[0] == 0
    doc = yaml.safe_load((tmp_path / "acme-preset" / "compass.yml").read_text(encoding="utf-8"))
    assert doc["owner"] == owner
    assert _run(tmp_path / "acme-preset", "policy", "test")[0] == 0


def test_pt_7_an_existing_empty_folder_is_filled(tmp_path):
    (tmp_path / "acme-preset").mkdir()
    code, _, err = _run(tmp_path, "policy", "init-preset", "acme-preset", "--owner", "acme-team")
    assert code == 0, err


def test_pt_7_the_json_report_lists_what_was_written(tmp_path):
    code, out, _ = _run(tmp_path, "policy", "init-preset", "acme-preset", "--owner", "acme-team",
                        "--json")
    report = json.loads(out)
    assert list(report) == ["schema", "dir", "result", "files"]
    assert report["result"] == "written" and report["dir"] == "acme-preset"
    assert report["files"] == [".gitignore", "README.md", "compass-fixtures/example.yml",
                               "compass.yml"]
    assert code == 0


def test_pt_7_an_owner_outside_the_basic_plane_is_written_as_the_same_text(tmp_path):
    owner = "Team \U0001F680 Zoe"
    assert _run(tmp_path, "policy", "init-preset", "acme-preset", "--owner", owner)[0] == 0
    folder = tmp_path / "acme-preset"
    text = (folder / "compass.yml").read_text(encoding="utf-8")
    assert "\\ud" not in text.lower() and owner in text
    doc = yaml.safe_load(text)
    assert doc["owner"] == owner
    (folder / "compass.yml").read_text(encoding="utf-8").encode("utf-8")
    code, out, err = _run(folder, "policy", "effective")
    assert code == 0, err


@pytest.mark.parametrize("owner", ["two\nlines", "tab\there", "bell\x07"])
def test_pt_7_an_owner_with_a_control_character_is_an_input_error(tmp_path, owner):
    code, out, err = _run(tmp_path, "policy", "init-preset", "acme-preset", "--owner", owner)
    assert code == 2
    assert "one line" in out + err
    assert not (tmp_path / "acme-preset").exists()


def test_pt_7_the_readme_promises_no_ci_workflow(tmp_path):
    _run(tmp_path, "policy", "init-preset", "acme-preset", "--owner", "acme-team")
    text = (tmp_path / "acme-preset" / "README.md").read_text(encoding="utf-8")
    assert "workflow" not in text.lower()


# --- PT-8: init-preset never overwrites -------------------------------------------------------

@pytest.mark.parametrize("existing", ["compass.yml", "README.md", ".gitignore",
                                      "compass-fixtures/example.yml"])
def test_pt_8_an_existing_file_is_refused_and_nothing_is_written(tmp_path, existing):
    folder = tmp_path / "acme-preset"
    (folder / "compass-fixtures").mkdir(parents=True)
    (folder / existing).write_text("mine\n", encoding="utf-8")
    code, out, err = _run(tmp_path, "policy", "init-preset", "acme-preset", "--owner", "acme-team")
    assert code == 1
    assert existing in out + err
    assert (folder / existing).read_text(encoding="utf-8") == "mine\n"
    assert sorted(p.name for p in folder.rglob("*") if p.is_file()) == [Path(existing).name]


def test_pt_8_the_refusal_in_json_names_the_files(tmp_path):
    folder = tmp_path / "acme-preset"
    folder.mkdir()
    (folder / "README.md").write_text("mine\n", encoding="utf-8")
    code, out, _ = _run(tmp_path, "policy", "init-preset", "acme-preset", "--owner", "acme-team",
                        "--json")
    report = json.loads(out)
    assert code == 1
    assert report["result"] == "refused" and report["files"] == ["README.md"]


def test_pt_8_a_broken_link_in_the_place_of_a_file_counts_as_an_existing_file(tmp_path):
    folder = tmp_path / "acme-preset"
    folder.mkdir()
    os.symlink(tmp_path / "nowhere", folder / "README.md")
    code, out, err = _run(tmp_path, "policy", "init-preset", "acme-preset", "--owner", "acme-team")
    assert code == 1 and "README.md" in out + err
    assert sorted(p.name for p in folder.iterdir()) == ["README.md"]


def test_pt_8_a_file_that_appears_after_the_check_is_never_overwritten(tmp_path, monkeypatch):
    from compass_pkg import preset_init
    from compass_pkg.core import CompassError
    folder = tmp_path / "acme-preset"
    folder.mkdir()
    (folder / "README.md").write_text("mine\n", encoding="utf-8")
    monkeypatch.setattr(preset_init.os.path, "lexists", lambda path: False)
    with pytest.raises(CompassError):
        preset_init.scaffold(folder, "acme-team")
    assert (folder / "README.md").read_text(encoding="utf-8") == "mine\n"


@pytest.mark.skipif(os.geteuid() == 0, reason="root can write to any folder")
def test_pt_8_a_failed_write_names_the_files_already_written(tmp_path):
    folder = tmp_path / "acme-preset"
    (folder / "compass-fixtures").mkdir(parents=True)
    (folder / "compass-fixtures").chmod(0o500)
    try:
        code, out, err = _run(tmp_path, "policy", "init-preset", "acme-preset", "--owner",
                              "acme-team")
    finally:
        (folder / "compass-fixtures").chmod(0o700)
    assert code == 2
    assert "already written: .gitignore, README.md" in out + err
    assert (folder / "README.md").is_file() and not (folder / "compass.yml").exists()


def test_pt_8_a_file_where_the_folder_should_be_is_an_input_error(tmp_path):
    (tmp_path / "acme-preset").write_text("a file\n", encoding="utf-8")
    code, out, err = _run(tmp_path, "policy", "init-preset", "acme-preset", "--owner", "acme-team")
    assert code == 2
    assert "acme-preset" in out + err


@pytest.mark.skipif(os.geteuid() == 0, reason="root can write to any folder")
def test_pt_8_a_folder_that_cannot_be_written_is_an_input_error(tmp_path):
    folder = tmp_path / "locked"
    folder.mkdir()
    folder.chmod(0o500)
    try:
        code, out, err = _run(tmp_path, "policy", "init-preset", "locked", "--owner", "acme-team")
    finally:
        folder.chmod(0o700)
    assert code == 2
    assert "locked" in out + err and "Traceback" not in err


# --- PT-9: a preset that extends a pinned git parent ---------------------------------------------

def _extending(tmp_path):
    base = tmp_path / "remotes"
    sha = make_remote(base, repo="base", files={"compass.yml": yaml.safe_dump(ADDS_A_GATE)})
    doc = {"schema": 1, "owner": "acme-team", "extends": f"github:acme/base@1.0.0#{sha}"}
    fixture = _fixture({"approach": "quick-fix",
                        "gates": sorted(QUICK_FIX_GATES + ["verify.clarity"])})
    preset = _preset(tmp_path, doc, {"small": fixture})
    return preset, {"COMPASS_PARENT_REMOTE_BASE": str(base)}, sha


def test_pt_9_fixtures_run_over_the_pinned_git_parent_and_the_preset(tmp_path):
    preset, env, sha = _extending(tmp_path)
    code, out, err = _test(tmp_path, preset, env=env)
    assert code == 0, (out, err)
    assert (preset / ".compass" / "cache" / "parents" / "acme" / "base" / sha / "compass.yml").is_file()


def test_pt_9_offline_with_the_parent_uncached_fails_with_the_lint_code(tmp_path):
    preset, env, _ = _extending(tmp_path)
    code, report = _json(tmp_path, preset, "--offline", env=env)
    assert code == 1
    assert "L-PARENT-NOT-CACHED" in [f["code"] for f in report["lint"]["findings"]]
    assert report["fixtures_run"] is False


def test_pt_9_offline_runs_from_the_cache_once_it_is_filled(tmp_path):
    preset, env, _ = _extending(tmp_path)
    assert _test(tmp_path, preset, env=env)[0] == 0
    code, out, err = _test(tmp_path, preset, "--offline", env={"COMPASS_PARENT_REMOTE_BASE": "/x"})
    assert code == 0, (out, err)


def test_pt_9_a_parent_that_breaks_the_data_only_rules_fails_the_preset(tmp_path):
    base = tmp_path / "remotes"
    sha = make_remote(base, repo="base", files={"compass.yml": yaml.safe_dump(
        {**PRESET, "autonomy": "balanced"})})
    doc = {"schema": 1, "owner": "acme-team", "extends": f"github:acme/base@1.0.0#{sha}"}
    code, report = _json(tmp_path, _preset(tmp_path, doc),
                         env={"COMPASS_PARENT_REMOTE_BASE": str(base)})
    assert code == 1
    assert "L-SETTINGS-KEY" in [f["code"] for f in report["lint"]["findings"]]


# --- PT-10: help, descriptions, corpus and the owning doc --------------------------------------

DOC = ROOT / "docs" / "policy-test.md"


def test_pt_10_the_help_states_the_exit_codes_and_the_options(tmp_path):
    code, out, _ = _run(tmp_path, "policy", "test", "--help")
    flat = " ".join(out.split())
    assert code == 0
    for word in ("PRESET_DIR", "--json", "--offline", "compass-fixtures", "Exit 0", "1", "2"):
        assert word in flat, word
    code, out, _ = _run(tmp_path, "policy", "init-preset", "--help")
    flat = " ".join(out.split())
    assert code == 0
    for word in ("DIR", "--owner", "--json", "never overwrites", "Exit 0"):
        assert word in flat, word


def test_pt_10_both_verbs_are_described_and_listed_under_policy(tmp_path):
    from compass_pkg.verb_help import VERB_DESCRIPTIONS
    assert "policy test" in VERB_DESCRIPTIONS and "policy init-preset" in VERB_DESCRIPTIONS
    code, out, _ = _run(tmp_path, "policy", "--help")
    assert code == 0 and "test" in out and "init-preset" in out


def test_pt_10_the_contract_corpus_holds_both_verbs_with_a_true_reason():
    corpus = (ROOT / "tests" / "fixtures" / "compat" / "contract-4-commands.yml").read_text(
        encoding="utf-8")
    entries = {e["id"]: e for e in yaml.safe_load(corpus)["entries"]}
    for wanted in ("policy-test-passes", "policy-test-fails", "policy-test-no-preset",
                   "policy-init-preset-writes", "policy-init-preset-refused"):
        assert wanted in entries, wanted
    assert "Added on purpose by policy-test-init-preset" in corpus
    assert entries["policy-test-passes"]["exit"] == 0
    assert entries["policy-test-fails"]["exit"] == 1
    assert entries["policy-test-no-preset"]["exit"] == 2
    assert entries["policy-init-preset-writes"]["exit"] == 0
    assert entries["policy-init-preset-refused"]["exit"] == 1


def test_pt_10_the_owning_doc_is_listed_and_owns_the_module():
    readme = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    assert "(policy-test.md)" in readme
    assert re.search(r"`cli/compass_pkg/preset_test\.py`[^|]*\| `docs/policy-test\.md`", readme)


def test_pt_10_the_doc_names_every_key_code_status_and_exit_code():
    text = DOC.read_text(encoding="utf-8")
    keys = ["schema", "preset", "result", "lint", "fixtures_run", "totals", "fixtures",
            "problems", "ok", "stopped_after", "findings", "passed", "failed", "file", "name",
            "status", "mismatches", "message", "field", "expected", "actual", "dir", "files",
            "pass", "fail", "error", "written", "refused", "assessment", "expect", "approach",
            "gates", "stages", "checks", "--offline", "--owner", "L-UNLOCK-PLACEMENT",
            "L-SETTINGS-KEY", "L-IMPL-UNKNOWN", "K-LOCK-REFUSED", "C-LOOSENING", "W-NO-OWNER",
            "compass-fixtures/"]
    for word in keys:
        assert f"`{word}`" in text, f"`{word}` is not set in code style in the doc"
    assert "fixture groups" in text, "the doc says what a later release adds"
    for code in ("Exit 0", "Exit 1", "Exit 2"):
        assert text.count(code) >= 2, f"{code} is stated for both commands"
    for sentence in ("cannot be read", "not UTF-8", "malformed", "some files",
                     "empty `stages` mapping", "own `owner`"):
        assert sentence in text, sentence


def test_pt_10_the_help_and_the_readme_say_what_exit_two_means():
    from compass_pkg import preset_init
    from compass_pkg.verb_help import VERB_DESCRIPTIONS
    said = "2 when the folder or its compass.yml is missing, cannot be read or is not UTF-8"
    assert said in VERB_DESCRIPTIONS["policy test"]
    assert "readable but malformed" in VERB_DESCRIPTIONS["policy test"]
    assert "2 means the folder or its `compass.yml` is missing, cannot be read or is not UTF-8" \
        in " ".join(preset_init.README.split())


def test_pt_10_the_new_files_name_no_private_design_id():
    """The design these commands come from is private; no tracked text may cite
    its ids."""
    files = ["cli/compass_pkg/preset_test.py", "cli/compass_pkg/preset_init.py",
             "docs/policy-test.md", "tests/test_policy_test.py"]
    found = [f for f in files if re.search(r"\bPRD\b|\bCF-\d|\bPS-\d|\bS3\.\d", (ROOT / f).read_text(
        encoding="utf-8"))]
    assert not found, found
