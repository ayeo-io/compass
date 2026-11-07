"""The checks, lists, checkpoints and hooks read a path issue (ADR-092).

A path issue is one whose manifest holds `evidence_required`. It runs
assess, specify, build and ship, has no `stages:` map and owes no Definition
of Ready. An issue assessed before
9.0.0 keeps every rule it had, so each test of a path rule has an old-issue
twin that checks the old verdict does not move.

No verb writes a path manifest yet, so every test here writes one by hand.

Issue: ayeo-io/compass-delivery#351 [Replace the approaches and eight stages
with one four-stage path].
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

from test_entry_exit_evaluation import _config_project, _rows, _view  # noqa: E402
from test_ready_and_done_data import DONE_IDS, READY_IDS  # noqa: E402

#: The evidence the standard row owes (`RP-EVID-STANDARD`), with the `S17` tokens.
STANDARD = ["scenarios", "red-before-green", "suite-green", "correctness", "governance",
            "traceability", "regression", "security", "clarity", "outer-loop", "isolation",
            "layering", "definition-of-done"]
#: The evidence the light row owes (`RP-EVID-LIGHT`): no Definition of Done.
LIGHT = ["scenarios", "red-before-green", "suite-green", "correctness", "governance",
         "traceability", "outer-loop"]
OLD_STAGES = {"assess": "thorough", "define": "thorough", "refine": "lightweight",
              "plan": "thorough", "breakdown": "skipped", "implement": "thorough",
              "verify": "thorough", "ship": "thorough"}


def _path_task(**changes):
    """A path manifest: `evidence_required`, the gates and checkpoints, no `stages:`."""
    task = {
        "schema_version": "2.0", "issue": "feature", "created": "2026-11-05",
        "status": "active", "delivery_approach": "delivery",
        "assessment": {"risk": "contained", "familiarity": "brownfield-mapped",
                       "size": "medium", "goal": "delivery", "urgency": "none",
                       "labels": []},
        "evidence_required": list(STANDARD),
        "gates": [{"id": g, "status": "pending", "evidence": []} for g in (
            "verify.correctness", "verify.governance", "verify.traceability",
            "verify.regression", "verify.security", "verify.clarity")],
        "acceptance_strategy": {"state": "on", "routing": "on", "applies": True,
                                "why": "behavior"},
        "checkpoints": [],
        "checkpoint_outcomes": [],
        "scenarios": [{"id": "TRC-001", "intent": "INT-1", "tests": ["tests/test_x.py::t"]}],
        "evidence": [],
    }
    task.update(changes)
    return task


def _old_task(**changes):
    task = _path_task(delivery_approach="regular", stages=dict(OLD_STAGES))
    task.pop("evidence_required")
    task.update(changes)
    return task


def _path_project(tmp_path, **changes):
    """A project with the entry and exit lists on, holding one path issue."""
    root, task_dir = _config_project(tmp_path)
    body = yaml.safe_load((task_dir / "manifest.yml").read_text(encoding="utf-8"))
    for key in ("stages", "current_phase"):
        body.pop(key, None)
    body.update(delivery_approach="delivery", evidence_required=list(STANDARD))
    body.update(changes)
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False),
                                           encoding="utf-8")
    return root, task_dir


# --- the stage lists ---------------------------------------------------------------------

def test_a_path_issue_has_its_lists_on_the_path_stages(tmp_path, monkeypatch):
    root, task_dir = _path_project(tmp_path)
    rows = _rows(_view(root, monkeypatch), task_dir)
    stages = {row.stage for row in rows}
    assert stages <= {"assess", "specify", "build", "ship"}, stages
    done = [row.check for row in rows if row.label == "stage:build:exit"]
    assert done == DONE_IDS, [(row.label, row.check) for row in rows]


def test_a_path_issue_owes_no_definition_of_ready(tmp_path, monkeypatch):
    root, task_dir = _path_project(tmp_path)
    rows = _rows(_view(root, monkeypatch), task_dir)
    assert not [row for row in rows if row.check.startswith("dor-")], rows


def test_a_path_issue_reads_the_lists_of_a_path_configuration(tmp_path, monkeypatch):
    def path_stages(resolved):
        resolved["stages"] = {
            "assess": {"order": 1}, "specify": {"order": 2},
            "build": {"order": 3, "exit": list(DONE_IDS)},
            "ship": {"order": 4, "entry": ["dod-suite-green"]}}
    root, task_dir = _path_project(tmp_path)
    rows = _rows(_view(root, monkeypatch, path_stages), task_dir)
    assert [row.check for row in rows if row.label == "stage:build:exit"] == DONE_IDS
    assert [row.check for row in rows if row.label == "stage:ship:entry"] == [
        "dod-suite-green"]


def test_a_path_issue_that_owes_no_definition_of_done_has_nothing_to_check(
        tmp_path, monkeypatch):
    root, task_dir = _path_project(tmp_path, evidence_required=list(LIGHT))
    rows = _rows(_view(root, monkeypatch), task_dir)
    done = [row for row in rows if row.label == "stage:build:exit"]
    assert done and all(row.status == "nothing-to-check" for row in done), done


def test_an_old_issue_keeps_its_legacy_lists(tmp_path, monkeypatch):
    root, task_dir = _config_project(tmp_path)
    rows = _rows(_view(root, monkeypatch), task_dir)
    assert [row.check for row in rows if row.label == "stage:plan:entry"] == READY_IDS
    assert [row.check for row in rows if row.label == "stage:verify:exit"] == DONE_IDS


# --- the Definition of Done items ---------------------------------------------------------

def test_the_definition_of_done_reads_the_build_exit_list(tmp_path, monkeypatch):
    from compass_pkg import item_records

    def path_stages(resolved):
        resolved["stages"] = {"assess": {"order": 1}, "build": {"order": 3,
                                                               "exit": ["dod-suite-green"]},
                              "ship": {"order": 4}}
    root, _ = _path_project(tmp_path)
    view = _view(root, monkeypatch, path_stages)
    assert [c for c, _ in item_records.listed_checks(view, "dod")] == ["dod-suite-green"]


def test_the_definition_of_done_falls_back_to_verify_for_an_old_configuration(
        tmp_path, monkeypatch):
    from compass_pkg import item_records
    root, _ = _path_project(tmp_path)
    view = _view(root, monkeypatch)
    assert [c for c, _ in item_records.listed_checks(view, "dod")] == DONE_IDS


def test_a_path_issue_has_only_the_definition_of_done_list():
    from compass_pkg import item_records
    assert item_records.lists_of(_path_task()) == ("dod",)
    assert item_records.lists_of(_old_task()) == tuple(item_records.LISTS)


def test_a_path_issue_cannot_record_a_definition_of_ready_item(tmp_path, monkeypatch):
    from compass_pkg import item_records
    root, _ = _path_project(tmp_path)
    view = _view(root, monkeypatch)
    problem = item_records.unlisted_problem(view, "dor-summary-filled", "compass x",
                                            task=_path_task())
    assert problem and "dor-summary-filled" in problem, problem
    assert "Definition of Ready" not in problem.split("The issue lists")[1], problem
    assert item_records.unlisted_problem(view, "dor-summary-filled", "compass x",
                                         task=_old_task()) is None


# --- dod-evidence-typed ----------------------------------------------------------------------

def _dod(tmp_path, monkeypatch, task):
    from compass_pkg import checks
    root, task_dir = _path_project(tmp_path)
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(task, sort_keys=False),
                                           encoding="utf-8")
    monkeypatch.chdir(root)
    return checks._check_dod_evidence_typed(task, str(task_dir))


def _passed(task):
    for gate in task["gates"]:
        gate.update(status="pass", evidence=["EV-1"])
    return task


def test_a_path_issue_that_owes_no_definition_of_done_has_none(tmp_path, monkeypatch):
    from compass_pkg.check_results import NOTHING_TO_CHECK
    passed, detail = _dod(tmp_path, monkeypatch, _passed(_path_task(evidence_required=LIGHT)))
    assert passed is NOTHING_TO_CHECK, detail
    assert "definition-of-done" in detail, detail


def test_a_path_issue_that_owes_the_definition_of_done_is_judged(tmp_path, monkeypatch):
    passed, detail = _dod(tmp_path, monkeypatch, _passed(_path_task()))
    assert passed is False, detail
    assert all(f"{item} is open" in detail for item in DONE_IDS), detail


def test_a_path_issue_is_judged_whatever_its_verify_mode_says(tmp_path, monkeypatch):
    # A path issue has no stages map. The old rule reads `verify: thorough`, so it
    # would find nothing owed; the path rule reads `evidence_required`.
    passed, detail = _dod(tmp_path, monkeypatch,
                          _passed(_path_task(stages={"verify": "lightweight"})))
    assert passed is False, detail


def test_a_path_issue_waits_for_its_gates(tmp_path, monkeypatch):
    from compass_pkg.check_results import NOTHING_TO_CHECK
    passed, detail = _dod(tmp_path, monkeypatch, _path_task())
    assert passed is NOTHING_TO_CHECK, detail
    assert "gate" in detail, detail


def test_an_old_issue_keeps_the_verify_is_thorough_rule(tmp_path, monkeypatch):
    from compass_pkg.check_results import NOTHING_TO_CHECK
    task = _passed(_old_task())
    task["stages"]["verify"] = "lightweight"
    passed, detail = _dod(tmp_path, monkeypatch, task)
    assert passed is NOTHING_TO_CHECK, detail
    assert "verify stage is lightweight" in detail, detail


# --- stage 1 of the four-layer acceptance strategy ---------------------------------------

def test_on_a_path_issue_stage_one_ends_at_specify():
    from compass_pkg.acceptance_strategy import stage_one
    untested = _path_task(scenarios=[{"id": "TRC-001", "intent": "INT-1"}])
    assert stage_one(untested, "outer") is True
    assert stage_one(untested, "inner") is False
    assert stage_one(_path_task(), "outer") is False


def test_on_a_path_issue_a_listed_specify_checkpoint_holds_stage_one_open():
    from compass_pkg.acceptance_strategy import stage_one
    waiting = _path_task(checkpoints=["assess", "specify"])
    assert stage_one(waiting, "outer") is True
    answered = _path_task(checkpoints=["assess", "specify"], checkpoint_outcomes=[
        {"stage": "specify", "outcome": "waited", "by": "jed", "at": "2026-11-05T00:00:00Z",
         "evidence": "EV-CP-1"}])
    assert stage_one(answered, "outer") is False


def test_an_old_issue_keeps_the_refine_rule_for_stage_one():
    from compass_pkg.acceptance_strategy import stage_one
    assert stage_one(_old_task(), "outer") is True
    quick = _old_task(stages=dict(OLD_STAGES, refine="collapsed"))
    assert stage_one(quick, "outer") is False


# --- checkpoints -------------------------------------------------------------------------

def test_the_checkpoint_stages_are_the_path_stages_and_the_legacy_ones():
    from compass_pkg import core, path_readers, policy
    assert set(core.CHECKPOINT_STAGES) == {"assess", "specify", "build", "ship", "define",
                                           "refine", "plan", "implement", "verify"}
    assert core.LEGACY_CHECKPOINT_STAGES == ("assess", "define", "refine", "plan",
                                             "implement", "verify")
    # The routing and the classifier keep the legacy stages, so an old issue's
    # checkpoints do not move. The table check accepts both sets (ADR-092).
    assert policy.CHECKPOINT_STAGES == core.LEGACY_CHECKPOINT_STAGES
    assert policy.TABLE_CHECKPOINT_STAGES == core.CHECKPOINT_STAGES
    assert path_readers.checkpoint_stages_of(_path_task()) == ("assess", "specify", "build",
                                                              "ship")
    assert path_readers.checkpoint_stages_of(_old_task()) == core.LEGACY_CHECKPOINT_STAGES


def _outcome(stage):
    return {"stage": stage, "outcome": "skipped", "by": "spec-author",
            "at": "2026-11-05T00:00:00Z"}


def test_a_path_issue_reads_its_path_checkpoints():
    from compass_pkg import checkpoint_outcomes as co
    task = _path_task(checkpoints=["assess", "specify", "define"],
                      checkpoint_outcomes=[_outcome("specify"), _outcome("define")])
    assert list(co.outcomes(task)) == ["specify"]
    assert co.listed(task) == ["assess", "specify"]
    assert co.missing(task) == ["assess"]


def test_an_old_issue_reads_its_checkpoints_as_before():
    from compass_pkg import checkpoint_outcomes as co
    task = _old_task(checkpoints=["define", "ship", "specify"],
                     checkpoint_outcomes=[_outcome("define"), _outcome("ship")])
    assert list(co.outcomes(task)) == ["define"]
    assert co.listed(task) == ["define"]


def test_a_path_issue_takes_an_outcome_only_at_a_path_stage():
    from compass_pkg import checkpoint_outcomes as co
    from compass_pkg.core import CompassError
    co.refuse_stage(_path_task(), "specify", "verb")
    with pytest.raises(CompassError, match="not a stage of the four-stage path"):
        co.refuse_stage(_path_task(), "define", "verb")


def test_an_old_issue_still_refuses_a_path_stage():
    from compass_pkg import checkpoint_outcomes as co
    from compass_pkg.core import CompassError
    co.refuse_stage(_old_task(), "define", "verb")
    for stage in ("specify", "ship"):
        with pytest.raises(CompassError, match="is not a checkpoint stage"):
            co.refuse_stage(_old_task(), stage, "verb")


def test_the_stage_reviews_of_a_path_issue_are_at_build_and_ship():
    from compass_pkg import checkpoint_outcomes as co
    assert co.stage_reviews(_path_task()) == {"build": "builder", "ship": "verifier"}
    assert co.stage_reviews(_old_task()) == {"implement": "builder", "verify": "verifier"}


def test_a_path_checkpoint_request_holds_its_stage_review(tmp_path):
    from compass_pkg import checkpoint_outcomes as co
    labels = {stage: (co.review(_path_task(), str(tmp_path), stage) or {}).get("stage")
              for stage in ("specify", "build", "ship")}
    assert labels == {"specify": "stage 1", "build": "stage 2", "ship": "stage 3"}


def test_the_manifest_schema_takes_a_path_checkpoint_and_a_legacy_one():
    import json

    import jsonschema
    schema = json.loads((ROOT / "schemas" / "manifest.schema.json").read_text())
    props = schema["properties"]

    def errors(key, value):
        return list(jsonschema.Draft7Validator(props[key]).iter_errors(value))
    for stage in ("specify", "build", "ship", "define", "verify"):
        assert not errors("checkpoints", [stage]), stage
        assert not errors("checkpoint_outcomes", [_outcome(stage)]), stage
    assert errors("checkpoints", ["breakdown"])
    assert errors("checkpoint_outcomes", [_outcome("breakdown")])


# --- the loop a red defaults to ----------------------------------------------------------

def _loop(tmp_path, task):
    from compass_pkg import tdd
    (tmp_path / "manifest.yml").write_text(yaml.safe_dump(task), encoding="utf-8")
    return tdd.default_loop(str(tmp_path))


@pytest.mark.parametrize("routing, loop", [("existing-dsl", "outer"), ("on", "inner"),
                                           ("existing-dsl-isolation", "inner")])
def test_a_path_issue_routed_to_the_existing_dsl_defaults_to_the_outer_loop(
        tmp_path, routing, loop):
    held = {"state": "on", "routing": routing, "applies": True, "why": "behavior"}
    assert _loop(tmp_path, _path_task(acceptance_strategy=held)) == loop


def test_an_old_issue_keeps_its_default_loop(tmp_path):
    held = {"state": "on", "routing": "existing-dsl", "applies": True, "why": "behavior"}
    assert _loop(tmp_path, _old_task(acceptance_strategy=held)) == "inner"


# --- the pre-tool hook: acceptance before code -------------------------------------------

VERDICT = ROOT / "hooks" / "py" / "pre_tool_acceptance_verdict.py"


def _verdict(tmp_path, task):
    path = tmp_path / "manifest.yml"
    path.write_text(yaml.safe_dump(task), encoding="utf-8")
    env = dict(os.environ, PYTHONPATH=str(ROOT / "cli"))
    r = subprocess.run([sys.executable, str(VERDICT), str(path)], capture_output=True,
                       text=True, env=env, stdin=subprocess.DEVNULL, timeout=60)
    assert r.returncode == 0, r.stderr
    return r.stdout.split()


def test_the_hook_blocks_a_path_issue_with_no_scenario(tmp_path):
    assert "block-path" in _verdict(tmp_path, _path_task(scenarios=[]))


def test_the_hook_allows_a_path_issue_with_a_scenario(tmp_path):
    assert not {"block", "block-path"} & set(_verdict(tmp_path, _path_task()))


def test_the_hook_keeps_the_define_thorough_rule_for_an_old_issue(tmp_path):
    assert "block" in _verdict(tmp_path, _old_task(scenarios=[]))
    light = _old_task(scenarios=[], stages=dict(OLD_STAGES, define="lightweight"))
    assert not {"block", "block-path"} & set(_verdict(tmp_path, light))


def test_the_path_refusal_names_compass_scenario_add():
    from compass_pkg.refusals import render
    text = " ".join(render("no-scenario", slug="demo", target="src/app.py", tool="Edit").split())
    assert "compass scenario add" in text, text
    assert "define: thorough" not in text, text


# --- the stop hook: the hotfix follow-up -------------------------------------------------

STOP = ROOT / "hooks" / "stop.sh"


def _stop(tmp_path, task):
    work = tmp_path / ".compass" / "work" / "demo"
    work.mkdir(parents=True)
    (tmp_path / ".compass" / "config.yml").write_text("version: 1.0.0\n", encoding="utf-8")
    task = dict(task, issue="demo", follow_ups=[
        {"id": "FU-1", "status": "outstanding", "description": "promote the reproduction"}])
    (work / "manifest.yml").write_text(yaml.safe_dump(task), encoding="utf-8")
    r = subprocess.run(["bash", str(STOP)], input="{}", cwd=str(tmp_path),
                       capture_output=True, text=True, timeout=120,
                       env={"PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": str(tmp_path),
                            "CLAUDE_PROJECT_DIR": str(tmp_path)})
    return r.stderr


def _live_defect(task):
    task["assessment"] = dict(task["assessment"], urgency="live-defect")
    return task


def test_the_stop_hook_warns_of_a_path_hotfix_reproduction_but_not_its_follow_up(tmp_path):
    # A path issue's follow-up links to a GitHub issue and need not be resolved
    # (ADR-093), so only the reproduction warning stays on a path hotfix.
    warned = _stop(tmp_path, _live_defect(_path_task()))
    assert "no promoted reproduction scenario" in warned or "never promoted" in warned, warned
    assert "OUTSTANDING FOLLOW-UP" not in warned, warned


def test_the_stop_hook_does_not_warn_without_the_live_defect_setting(tmp_path):
    assert "OUTSTANDING FOLLOW-UP" not in _stop(tmp_path, _path_task())


def test_the_stop_hook_keeps_reading_the_approach_on_an_old_issue(tmp_path):
    # An old regular issue with a live-defect urgency was never warned about;
    # only the hotfix approach was.
    assert "OUTSTANDING FOLLOW-UP" not in _stop(tmp_path, _live_defect(_old_task()))


def test_the_stop_hook_warns_of_an_old_hotfix(tmp_path):
    assert "OUTSTANDING FOLLOW-UP" in _stop(tmp_path / "b",
                                            _old_task(delivery_approach="hotfix"))
