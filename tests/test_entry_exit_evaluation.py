"""Stage entry and exit lists are evaluated behind the capability `entry-exit-evaluation`.

With the capability on, a stage's entry checks must pass before work in it and
its exit checks before it is left. A human check is a tick in the issue's
requirements review (entry lists) or verification report (exit lists). A list
whose producing stage was skipped or collapsed gives the verdict the check's
`on_skipped` names. With the capability off, nothing changes.

Scenario ids: `EE-1` to `EE-14` (issue `entry-exit-evaluation`). Each test name
starts with its scenario id.
"""
from __future__ import annotations

import copy
import dataclasses
import json
import re
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

from test_generation_store import (SLUG, _evaluate_write, _manifest, _project,  # noqa: E402
                                   _run, _write_manifest)
from test_ready_and_done_data import (DONE_IDS, READY_IDS, DONE_TEMPLATE,  # noqa: E402
                                      READY_TEMPLATE, template_items)

CAPABILITY = "entry-exit-evaluation"
READY = template_items(READY_TEMPLATE, "### Definition of Ready")
DONE = template_items(DONE_TEMPLATE, "### Definition of Done")


# --- helpers ---------------------------------------------------------------------

def _checklist(heading, items, ticked):
    body = "".join(f"- [{'x' if i in ticked else ' '}] {text}\n"
                   for i, text in enumerate(items))
    return f"# Document\n\n### {heading}\n\n{body}\nNext stage: x\n"


def _write_review(task_dir, ticked=range(7)):
    (task_dir / "requirements-review.md").write_text(
        _checklist("Definition of Ready", READY, set(ticked)), encoding="utf-8")


def _write_report(task_dir, ticked=range(7)):
    (task_dir / "verification-report.md").write_text(
        _checklist("Definition of Done", DONE, set(ticked)), encoding="utf-8")


def _config_project(tmp_path, capability=True, manifest=None, **manifest_changes):
    """A scratch project whose `compass.yml` sets the capability, with an issue
    (regular route, plan the current stage) and its directory."""
    compass_yml = {"schema": 1}
    if capability:
        compass_yml["capabilities"] = {CAPABILITY: True}
    root, task_dir = _project(tmp_path, manifest=manifest, compass_yml=compass_yml)
    body = _manifest(task_dir)
    body.update({"delivery_approach": "regular", "current_phase": "plan",
                 "stages": {"assess": "full", "define": "full", "refine": "light",
                            "plan": "full", "breakdown": "multiagent",
                            "implement": "full", "verify": "full", "ship": "full"}})
    body.update(manifest_changes)
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False),
                                           encoding="utf-8")
    return root, task_dir


def _view(root, monkeypatch, mutate=None):
    """The live view of the project at `root`, with its resolved configuration
    changed by `mutate` (a function of the dict)."""
    from compass_pkg import effective
    monkeypatch.chdir(root)
    view = effective.view_or_legacy(None)
    if mutate:
        resolved = copy.deepcopy(view.resolved)
        mutate(resolved)
        view = dataclasses.replace(view, resolved=resolved)
    return view


def _rows(view, task_dir):
    from compass_pkg import stage_lists
    task = yaml.safe_load((task_dir / "manifest.yml").read_text(encoding="utf-8"))
    return stage_lists.evaluate(view, task, str(task_dir))


def _by_check(rows):
    return {row.check: row for row in rows}


# --- EE-1: the capability off changes nothing ---------------------------------------

def test_ee_1_with_the_capability_off_no_reader_shows_a_list(tmp_path):
    root, task_dir = _config_project(tmp_path, capability=False)
    assert _evaluate_write(root)[0] == 0
    _write_review(task_dir, ticked=())
    code, out, err = _run(root, "check", "--issue", SLUG, "--json")
    rows = json.loads(out)["checks"]
    assert not [r for r in rows if r["guardrail"].startswith("stage:")], rows
    assert not [r for r in rows if r["name"] in READY_IDS + DONE_IDS], rows
    code, out, err = _run(root, "next", "--issue", SLUG)
    assert "entry" not in out and "exit" not in out, out
    code, out, err = _run(root, "issue", "receipt", "--issue", SLUG)
    assert "Stage lists" not in out, out


def test_ee_1_a_view_with_the_capability_off_gives_no_rows(tmp_path, monkeypatch):
    root, task_dir = _config_project(tmp_path, capability=False)
    assert _rows(_view(root, monkeypatch), task_dir) == []

    def add_project_check(resolved):
        # A check that needs no capability is still not evaluated: the
        # capability switches the evaluation of the lists, not only the
        # shipped checks.
        resolved["checks"]["project-tick"] = {"statement": "x", "kind": "human",
                                              "severity": "blocking", "on_skipped": "fail"}
        resolved["stages"]["plan"]["entry"] = ["project-tick"]

    assert _rows(_view(root, monkeypatch, add_project_check), task_dir) == []


# --- EE-2: the Definition of Done is not owed by an approach that does not ship -------------

def test_ee_2_a_spike_owes_no_done_check_and_a_delivery_owes_all_seven(tmp_path, monkeypatch):
    from compass_pkg import obligations
    root, _ = _config_project(tmp_path)
    config = _view(root, monkeypatch).config
    on = (CAPABILITY,)
    spike = obligations.obligations(config, {"risk": "trivial", "familiarity": "greenfield",
                                             "size": "small", "goal": "exploration"},
                                    capabilities=on)
    assert spike.approach == "spike"
    assert spike.exit["verify"] == ()
    delivery = obligations.obligations(config, {"risk": "contained",
                                                "familiarity": "brownfield-mapped",
                                                "size": "standard", "goal": "delivery"},
                                       capabilities=on)
    assert delivery.exit["verify"] == tuple(sorted(DONE_IDS))
    assert delivery.entry["plan"] == tuple(sorted(READY_IDS))


def test_ee_2_a_check_can_name_ships_in_its_when(tmp_path, monkeypatch):
    from compass_pkg import obligations
    root, _ = _config_project(tmp_path)

    def mutate(resolved):
        resolved["checks"]["only-shipping"] = {
            "statement": "x", "kind": "human", "severity": "blocking",
            "on_skipped": "fail", "when": {"ships": True}}
        resolved["checks"]["only-not-shipping"] = {
            "statement": "y", "kind": "human", "severity": "blocking",
            "on_skipped": "fail", "when": {"ships": False}}
        resolved["stages"]["verify"]["exit"] += ["only-shipping", "only-not-shipping"]

    config = _view(root, monkeypatch, mutate).config
    spike = obligations.obligations(config, {"risk": "trivial", "familiarity": "greenfield",
                                             "size": "small", "goal": "exploration"})
    regular = obligations.obligations(config, {"risk": "contained",
                                               "familiarity": "greenfield",
                                               "size": "standard"})
    assert "only-not-shipping" in spike.exit["verify"]
    assert "only-shipping" not in spike.exit["verify"]
    assert "only-shipping" in regular.exit["verify"]
    assert "only-not-shipping" not in regular.exit["verify"]


def test_ee_2_the_classifier_sees_the_ships_condition_come_and_go(tmp_path, monkeypatch):
    from compass_pkg import classify
    root, _ = _config_project(tmp_path)
    parent = _view(root, monkeypatch).config
    child = copy.deepcopy(parent)
    for check_id in DONE_IDS:
        del child["checks"][check_id]["when"]
    on = (CAPABILITY,)
    tighter = classify.classify(parent, child, parent_capabilities=on, child_capabilities=on)
    assert tighter.result == "tightening", tighter.reason
    looser = classify.classify(child, parent, parent_capabilities=on, child_capabilities=on)
    assert looser.result == "loosening", looser.reason


# --- EE-3: a human check is a tick ---------------------------------------------------------

def test_ee_3_a_ticked_box_passes_and_an_unticked_one_fails(tmp_path, monkeypatch):
    root, task_dir = _config_project(tmp_path)
    _write_review(task_dir, ticked=[0, 1, 2, 3, 4, 5])
    rows = _by_check(_rows(_view(root, monkeypatch), task_dir))
    assert rows["dor-summary-filled"].status == "pass"
    last = rows["dor-approach-still-fits"]
    assert last.status == "fail"
    assert "not ticked" in last.detail and "requirements-review.md" in last.detail
    assert (last.stage, last.side, last.due) == ("plan", "entry", True)


def test_ee_3_an_item_whose_text_differs_is_not_a_tick(tmp_path, monkeypatch):
    root, task_dir = _config_project(tmp_path)
    _write_review(task_dir)
    path = task_dir / "requirements-review.md"
    path.write_text(path.read_text(encoding="utf-8").replace(
        "No open questions", "No open questions at all"), encoding="utf-8")
    rows = _by_check(_rows(_view(root, monkeypatch), task_dir))
    row = rows["dor-no-open-questions"]
    assert row.status == "fail" and "no checklist item" in row.detail


def test_ee_3_a_missing_document_fails_every_check_it_would_hold(tmp_path, monkeypatch):
    root, task_dir = _config_project(tmp_path)
    rows = [r for r in _rows(_view(root, monkeypatch), task_dir) if r.due]
    assert {r.check for r in rows} == set(READY_IDS)
    assert all(r.status == "fail" and "not found" in r.detail for r in rows)


def test_ee_3_a_tick_after_the_section_ends_does_not_count(tmp_path, monkeypatch):
    root, task_dir = _config_project(tmp_path)
    ready = _checklist("Definition of Ready", READY, set()).split("\nNext stage:")[0]
    later = "".join(f"- [x] {text}\n" for text in READY)
    (task_dir / "requirements-review.md").write_text(
        ready + "\n### Later notes\n\n" + later, encoding="utf-8")
    rows = _rows(_view(root, monkeypatch), task_dir)
    assert rows and all(r.status == "fail" for r in rows if r.due)


def test_ee_3_a_tick_in_another_section_does_not_count(tmp_path, monkeypatch):
    root, task_dir = _config_project(tmp_path)
    (task_dir / "requirements-review.md").write_text(
        _checklist("Something else", READY, set(range(7))), encoding="utf-8")
    rows = _rows(_view(root, monkeypatch), task_dir)
    assert all(r.status == "fail" for r in rows if r.due)


# --- EE-4: a skipped list gives the verdict on_skipped names --------------------------------

def test_ee_4_a_collapsed_refine_makes_the_ready_checks_not_applicable(tmp_path, monkeypatch):
    root, task_dir = _config_project(tmp_path)
    body = _manifest(task_dir)
    body["stages"].update({"refine": "collapsed", "plan": "full"})
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False),
                                           encoding="utf-8")
    rows = [r for r in _rows(_view(root, monkeypatch), task_dir) if r.due]
    assert {r.check for r in rows} == set(READY_IDS)
    assert all(r.status == "nothing-to-check" for r in rows)
    assert "refine" in rows[0].detail and "collapsed" in rows[0].detail


def test_ee_4_a_collapsed_plan_does_not_skip_the_ready_checks(tmp_path, monkeypatch):
    """The Definition of Ready is produced by refine, not by the stage it opens."""
    root, task_dir = _config_project(tmp_path)
    _write_manifest(task_dir, stages={"refine": "full", "plan": "collapsed"})
    rows = [r for r in _rows(_view(root, monkeypatch), task_dir) if r.due]
    assert rows and all(r.status == "fail" for r in rows)


@pytest.mark.parametrize("value, status", [("fail", "fail"), ("pass", "pass"),
                                           ("not-applicable", "nothing-to-check")])
def test_ee_4_the_on_skipped_value_decides_the_verdict(tmp_path, monkeypatch, value, status):
    root, task_dir = _config_project(tmp_path)
    _write_manifest(task_dir, stages={"refine": "skipped", "plan": "full"})

    def mutate(resolved):
        resolved["checks"]["dor-summary-filled"]["on_skipped"] = value

    rows = _by_check(_rows(_view(root, monkeypatch, mutate), task_dir))
    assert rows["dor-summary-filled"].status == status


def test_ee_4_a_document_recorded_as_omitted_is_skipped(tmp_path, monkeypatch):
    root, task_dir = _config_project(tmp_path)
    _write_manifest(task_dir, artifacts=[{"kind": "requirements-review",
                                          "status": "omitted", "reason": "not earned"}])
    rows = [r for r in _rows(_view(root, monkeypatch), task_dir) if r.due]
    assert rows and all(r.status == "nothing-to-check" for r in rows)


def test_ee_4_a_spike_owes_the_ready_checks_as_not_applicable_and_no_done_check(tmp_path, monkeypatch):
    root, task_dir = _config_project(tmp_path)
    _write_manifest(task_dir, delivery_approach="spike", current_phase="ship",
                    assessment={"risk": "trivial", "familiarity": "greenfield",
                                "size": "small", "goal": "exploration"},
                    stages={"assess": "light", "define": "collapsed", "refine": "skipped",
                            "plan": "collapsed", "breakdown": "skipped",
                            "implement": "explore", "verify": "conclude",
                            "ship": "graduate-or-discard"})
    rows = _rows(_view(root, monkeypatch), task_dir)
    assert not [r for r in rows if r.check in DONE_IDS]
    ready = [r for r in rows if r.check in READY_IDS]
    assert ready and all(r.status == "nothing-to-check" for r in ready)


# --- EE-5: when a list is due ------------------------------------------------------------------

@pytest.mark.parametrize("current, due_entry, due_exit", [
    ("define", [], []),
    ("plan", ["plan"], []),
    ("verify", ["plan"], []),
    ("ship", ["plan"], ["verify"]),
    (None, ["plan"], ["verify"]),
])
def test_ee_5_a_list_is_due_by_the_current_stage(tmp_path, monkeypatch, current, due_entry, due_exit):
    root, task_dir = _config_project(tmp_path)
    body = _manifest(task_dir)
    body.pop("current_phase")
    if current:
        body["current_phase"] = current
    else:
        body["status"] = "landed"
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False),
                                           encoding="utf-8")
    rows = _rows(_view(root, monkeypatch), task_dir)
    assert {r.stage for r in rows if r.due and r.side == "entry"} == set(due_entry)
    assert {r.stage for r in rows if r.due and r.side == "exit"} == set(due_exit)
    assert {(r.stage, r.side) for r in rows} == {("plan", "entry"), ("verify", "exit")}


def test_ee_5_the_exit_of_the_current_stage_is_reported_but_not_due(tmp_path, monkeypatch):
    root, task_dir = _config_project(tmp_path)
    _write_manifest(task_dir, current_phase="verify")
    _write_report(task_dir, ticked=[0, 1])
    rows = [r for r in _rows(_view(root, monkeypatch), task_dir) if r.side == "exit"]
    assert len(rows) == 7 and not any(r.due for r in rows)
    assert [r.status for r in rows[:3]] == ["pass", "pass", "fail"]


# --- EE-6: a deterministic check in a list runs its implementation ------------------------------

def _with_scenario_check(resolved):
    resolved["checks"]["list-scenarios-have-tests"] = {
        "statement": "Every scenario has a test.", "kind": "deterministic",
        "impl": "scenarios-have-tests", "severity": "blocking", "on_skipped": "fail"}
    resolved["stages"]["plan"]["entry"] = ["list-scenarios-have-tests"]


def test_ee_6_a_deterministic_check_in_a_list_runs_and_reports(tmp_path, monkeypatch):
    root, task_dir = _config_project(
        tmp_path, scenarios=[{"id": "S-1", "title": "t", "intent": "I", "tests": []}])
    view = _view(root, monkeypatch, _with_scenario_check)
    row = _by_check(_rows(view, task_dir))["list-scenarios-have-tests"]
    assert row.status == "fail" and row.due
    _write_manifest(task_dir, scenarios=[{"id": "S-1", "title": "t", "intent": "I",
                                          "tests": ["tests/x.py::t"]}])
    row = _by_check(_rows(view, task_dir))["list-scenarios-have-tests"]
    assert row.status == "pass"


def test_ee_6_a_list_that_is_not_due_does_not_run_the_implementation(tmp_path, monkeypatch):
    root, task_dir = _config_project(
        tmp_path, scenarios=[{"id": "S-1", "title": "t", "intent": "I", "tests": []}])
    _write_manifest(task_dir, current_phase="define")
    row = _by_check(_rows(_view(root, monkeypatch, _with_scenario_check), task_dir)
                    )["list-scenarios-have-tests"]
    assert (row.status, row.due) == ("pending", False)


def test_ee_6_a_skipped_list_does_not_run_the_implementation(tmp_path, monkeypatch):
    root, task_dir = _config_project(
        tmp_path, scenarios=[{"id": "S-1", "title": "t", "intent": "I", "tests": []}])
    _write_manifest(task_dir, stages={"refine": "full", "plan": "skipped"})

    def mutate(resolved):
        _with_scenario_check(resolved)
        resolved["checks"]["list-scenarios-have-tests"]["on_skipped"] = "not-applicable"

    row = _by_check(_rows(_view(root, monkeypatch, mutate), task_dir))["list-scenarios-have-tests"]
    assert row.status == "nothing-to-check"


# --- EE-7: kinds this increment does not evaluate fail closed ----------------------------------

@pytest.mark.parametrize("kind, extra", [
    ("judged", {"inputs": ["acceptance-criteria"]}),
    ("evidence", {"accepts": ["test-run"]}),
])
def test_ee_7_a_judged_or_evidence_check_fails_closed(tmp_path, monkeypatch, kind, extra):
    root, task_dir = _config_project(tmp_path)

    def mutate(resolved):
        resolved["checks"]["extra"] = {"statement": "x", "kind": kind, "severity": "blocking",
                                       "on_skipped": "fail", **extra}
        resolved["stages"]["plan"]["entry"] = ["extra"]

    row = _by_check(_rows(_view(root, monkeypatch, mutate), task_dir))["extra"]
    assert row.status == "fail" and "not evaluated" in row.detail


def test_ee_7_an_advisory_check_that_fails_does_not_fail(tmp_path, monkeypatch):
    root, task_dir = _config_project(tmp_path)
    _write_review(task_dir, ticked=())

    def mutate(resolved):
        resolved["checks"]["dor-summary-filled"]["severity"] = "advisory"

    rows = _by_check(_rows(_view(root, monkeypatch, mutate), task_dir))
    row = rows["dor-summary-filled"]
    assert row.status == "pass" and row.detail.startswith("advisory")
    assert rows["dor-problem-traces-up"].status == "fail"


# --- EE-8: compass check reports the rows and counts them ----------------------------------------

def _committed(tmp_path, **changes):
    root, task_dir = _config_project(tmp_path, **changes)
    code, out, err = _evaluate_write(root)
    assert code == 0, out + err
    _write_manifest(task_dir, current_phase="plan")
    return root, task_dir


def test_ee_8_check_json_carries_one_row_per_due_check(tmp_path):
    root, task_dir = _committed(tmp_path)
    _write_review(task_dir, ticked=range(6))
    code, out, err = _run(root, "check", "--issue", SLUG, "--json")
    data = json.loads(out)
    rows = [r for r in data["checks"] if r["guardrail"] == "stage:plan:entry"]
    assert [r["name"] for r in rows] == READY_IDS
    assert [r["status"] for r in rows] == ["pass"] * 6 + ["fail"]
    assert set(rows[0]) == {"guardrail", "name", "status", "detail"}
    assert code != 0 and data["failed"] >= 1
    assert not [r for r in data["checks"] if r["guardrail"].startswith("stage:verify")]


def test_ee_8_a_failed_list_check_adds_one_to_the_failed_count(tmp_path):
    root, task_dir = _committed(tmp_path)
    _write_review(task_dir)
    ticked = json.loads(_run(root, "check", "--issue", SLUG, "--json")[1])
    _write_review(task_dir, ticked=range(6))
    short = json.loads(_run(root, "check", "--issue", SLUG, "--json")[1])
    assert short["failed"] == ticked["failed"] + 1
    assert short["ran"] == ticked["ran"] >= 7
    (tmp_path / "off").mkdir()
    capability_off, off_dir = _config_project(tmp_path / "off", capability=False)
    assert _evaluate_write(capability_off)[0] == 0
    off = json.loads(_run(capability_off, "check", "--issue", SLUG, "--json")[1])
    assert ticked["ran"] == off["ran"] + 7


def test_ee_8_check_passes_when_the_due_list_is_ticked(tmp_path):
    root, task_dir = _committed(tmp_path)
    _write_review(task_dir)
    code, out, err = _run(root, "check", "--issue", SLUG, "--json")
    rows = [r for r in json.loads(out)["checks"] if r["guardrail"] == "stage:plan:entry"]
    assert [r["status"] for r in rows] == ["pass"] * 7


def test_ee_8_the_summary_names_a_failed_list_check(tmp_path):
    root, task_dir = _committed(tmp_path)
    _write_review(task_dir, ticked=range(6))
    code, out, err = _run(root, "check", "--issue", SLUG)
    assert "dor-approach-still-fits" in out
    code, out, err = _run(root, "check", "--issue", SLUG, "--verbose")
    assert "entry checks of plan" in out and "PASS dor-summary-filled" in out


def test_ee_8_the_results_file_records_the_list_checks(tmp_path):
    root, task_dir = _committed(tmp_path)
    _write_review(task_dir)
    _run(root, "check", "--issue", SLUG)
    results = yaml.safe_load((task_dir / "generations" / "1" / "results.yml")
                             .read_text(encoding="utf-8"))
    assert results["runs"]["dor-summary-filled"]["verdict"] == "pass"


def test_ee_8_a_spike_check_reports_the_ready_list_as_not_applicable(tmp_path):
    root, task_dir = _config_project(
        tmp_path, assessment={"risk": "trivial", "familiarity": "greenfield",
                              "size": "small", "goal": "exploration", "role": "engineer",
                              "labels": []})
    assert _evaluate_write(root)[0] == 0
    _write_manifest(task_dir, current_phase="ship")
    code, out, err = _run(root, "check", "--issue", SLUG, "--json")
    data = json.loads(out)
    assert data["approach"] == "spike"
    stage = [r for r in data["checks"] if r["guardrail"].startswith("stage:")]
    assert stage and {r["status"] for r in stage} == {"nothing-to-check"}
    assert not [r for r in stage if r["name"] in DONE_IDS]


# --- EE-9: compass next names an unmet entry list ------------------------------------------------

def test_ee_9_next_names_the_unmet_entry_checks_of_the_current_stage(tmp_path):
    root, task_dir = _committed(tmp_path)
    _write_review(task_dir, ticked=range(5))
    (task_dir / "delivery-approach.md").write_text("# a\n", encoding="utf-8")
    code, out, err = _run(root, "next", "--issue", SLUG)
    assert code == 0, err
    line = out.strip()
    assert line.startswith("Plan")
    assert "entry not met: dor-no-open-questions, dor-approach-still-fits" in line, line
    _write_review(task_dir)
    code, out, err = _run(root, "next", "--issue", SLUG)
    assert "entry" not in out, out


# --- EE-10: the receipt lists the checks and their state -----------------------------------------

def test_ee_10_the_receipt_shows_each_list_with_its_state(tmp_path):
    root, task_dir = _committed(tmp_path)
    _write_review(task_dir, ticked=range(6))
    code, out, err = _run(root, "issue", "receipt", "--issue", SLUG)
    assert code == 0, err
    assert "Stage lists" in out
    assert "plan entry (due)" in out and "verify exit (not yet due)" in out
    assert re.search(r"dor-approach-still-fits\s+fail", out), out
    assert re.search(r"dor-summary-filled\s+pass", out), out


def _project_check_config():
    return {"schema": 1, "capabilities": {CAPABILITY: True},
            "checks": {"list-scenarios-have-tests": {
                "statement": "Every scenario has a test.", "kind": "deterministic",
                "impl": "scenarios-have-tests", "severity": "blocking",
                "on_skipped": "fail"}},
            "stages": {"plan": {"set": {"entry": {"add": ["list-scenarios-have-tests"]}}}}}


def test_ee_10_the_receipt_does_not_run_a_deterministic_check_but_check_does(tmp_path):
    root, task_dir = _project(tmp_path, compass_yml=_project_check_config())
    assert _evaluate_write(root)[0] == 0
    _write_manifest(task_dir, current_phase="plan")
    _write_review(task_dir)
    code, out, err = _run(root, "issue", "receipt", "--issue", SLUG)
    assert re.search(r"list-scenarios-have-tests\s+pending", out), out
    code, out, err = _run(root, "check", "--issue", SLUG, "--json")
    rows = {r["name"]: r for r in json.loads(out)["checks"]
            if r["guardrail"] == "stage:plan:entry"}
    assert rows["list-scenarios-have-tests"]["status"] == "fail"
    assert rows["dor-summary-filled"]["status"] == "pass"


# --- EE-11: the existing Definition of Done check keeps running ---------------------------------

def test_ee_11_dod_evidence_typed_still_runs_with_the_capability_on(tmp_path):
    root, task_dir = _committed(tmp_path)
    _write_report(task_dir, ticked=())
    code, out, err = _run(root, "check", "--issue", SLUG, "--json")
    rows = {r["name"]: r for r in json.loads(out)["checks"]}
    assert rows["dod-evidence-typed"]["status"] == "fail"
    assert "bare unchecked DoD item" in rows["dod-evidence-typed"]["detail"]


# --- EE-12: the default preset, help text and owning doc -----------------------------------------

def test_ee_12_every_done_check_carries_the_ships_condition():
    checks = yaml.safe_load((ROOT / "governance" / "presets" / "default" / "checks.yml")
                            .read_text(encoding="utf-8"))["checks"]
    for check_id in DONE_IDS:
        assert checks[check_id].get("when") == {"ships": True}, check_id
    for check_id in READY_IDS:
        assert "when" not in checks[check_id], check_id


def test_ee_12_the_help_text_and_the_owning_doc_describe_the_lists():
    from compass_pkg import verb_help
    for verb in ("check", "next"):
        assert CAPABILITY in verb_help.VERB_DESCRIPTIONS[verb], verb
    doc = (ROOT / "docs" / "entry-exit-evaluation.md").read_text(encoding="utf-8")
    for needle in (CAPABILITY, "stage:<stage>:<entry|exit>", "on_skipped", "ships",
                   "entry not met"):
        assert needle in doc, needle
    router = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    assert "entry-exit-evaluation.md" in router


# --- EE-13: an unreadable stage name or a project stage is handled ------------------------------

def test_ee_13_a_project_stage_list_is_evaluated_in_its_place(tmp_path, monkeypatch):
    root, task_dir = _config_project(tmp_path)
    _write_manifest(task_dir, current_phase="implement")

    def mutate(resolved):
        resolved["checks"]["scenario-ids"] = {
            "statement": "Every scenario has an id.", "kind": "deterministic",
            "impl": "scenario-has-id-and-intent", "severity": "blocking",
            "on_skipped": "not-applicable"}
        resolved["stages"]["implement"]["entry"] = ["scenario-ids"]

    rows = [r for r in _rows(_view(root, monkeypatch, mutate), task_dir)
            if r.check == "scenario-ids"]
    assert [(r.stage, r.side, r.due) for r in rows] == [("implement", "entry", True)]


def test_ee_13_a_list_naming_an_unknown_check_is_reported_not_raised(tmp_path, monkeypatch):
    root, task_dir = _config_project(tmp_path)

    def mutate(resolved):
        resolved["stages"]["plan"]["entry"] = ["no-such-check"]

    row = _by_check(_rows(_view(root, monkeypatch, mutate), task_dir))["no-such-check"]
    assert row.status == "fail" and "not defined" in row.detail


# --- EE-14: a check inactive for the assessment is not owed -------------------------------------

def test_ee_14_a_check_whose_when_does_not_match_is_not_listed(tmp_path, monkeypatch):
    root, task_dir = _config_project(tmp_path)

    def mutate(resolved):
        resolved["checks"]["dor-summary-filled"]["when"] = {"risk": "critical"}

    rows = _by_check(_rows(_view(root, monkeypatch, mutate), task_dir))
    assert "dor-summary-filled" not in rows
    assert "dor-problem-traces-up" in rows
