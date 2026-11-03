"""`suite-passed` needs a red for each scenario, before that scenario's green.

`suite-passed` checks guardrail `G1`, that a change is tested before it lands.
It accepted any one red on the issue, so a reader could not tell which
scenarios had a failing test before the code. On an issue created on or after
the per-scenario cutoff, each scenario that needs a test must have a red bound
to it whose timestamp is not after the scenario's first green. A red of either
loop counts. A scenario closed by an acceptance declared in time, and a
`verifiable: narrative` scenario, need no red. An issue created and worked
before the cutoff keeps the rule it had, and the pass detail gives a notice
that names what it lacks under the new rule.

Scenario ids: RPS-1 to RPS-8, from ayeo-io/compass-delivery#347, the issue that
asks for a red for each scenario before its green.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
sys.path.insert(0, str(ROOT / "cli"))

from compass_pkg.checks import _check_suite_passed  # noqa: E402
from compass_pkg.red_first import RED_PER_SCENARIO_FROM  # noqa: E402

AFTER = str(RED_PER_SCENARIO_FROM)
BEFORE = "2026-10-01"
SLUG = "sample"

T1 = AFTER + "T09:00:00+00:00"
T2 = AFTER + "T10:00:00+00:00"
T3 = AFTER + "T11:00:00+00:00"
OLD = BEFORE + "T09:00:00+00:00"

RED = {"exit_code": 1, "passed": False, "command": "pytest"}
GREEN = {"exit_code": 0, "passed": True, "command": "pytest"}


def _issue(tmp_path, scenarios=("S-1", "S-2"), created=AFTER, narrative=()):
    task_dir = tmp_path / ".compass" / "work" / SLUG
    (task_dir / "evidence").mkdir(parents=True)
    task = {
        "schema_version": "2.0", "issue": SLUG, "created": created,
        "status": "active",
        "scenarios": [dict({"id": s, "intent": "INT-1", "tests": ["t"]},
                           **({"verifiable": "narrative"} if s in narrative else {}))
                      for s in scenarios],
        "evidence": [],
    }
    return task, task_dir


def _red(task_dir, name, stamp, scenario=None, **extra):
    body = dict(RED, timestamp=stamp, scenario=scenario, **extra)
    (task_dir / "evidence" / f"{name}.json").write_text(json.dumps(body))


def _green(task, task_dir, name, stamp, scenario=None, **extra):
    body = dict(GREEN, timestamp=stamp, scenario=scenario, **extra)
    (task_dir / "evidence" / f"{name}.json").write_text(json.dumps(body))
    entry = {"id": f"EV-{name}", "type": "test-run", "path": f"evidence/{name}.json"}
    if scenario:
        entry["scenario"] = scenario
    task["evidence"].append(entry)


def _check(task, task_dir):
    return _check_suite_passed(task, str(task_dir))


# --- RPS-1: a scenario with no red is named ----------------------------------------

def test_rps_1_two_scenarios_and_one_red_fails_naming_the_scenario_without_one(tmp_path):
    task, task_dir = _issue(tmp_path)
    _red(task_dir, "red-S-1", T1, "S-1")
    _green(task, task_dir, "green-S-1", T2, "S-1")
    _green(task, task_dir, "green", T3)
    ok, why = _check(task, task_dir)
    assert ok is False, why
    assert "no red: S-2" in why
    assert "S-1" not in why.split("no red:")[1].split(".")[0]
    assert "compass tdd-red --scenario" in why


def test_rps_1_compass_check_fails_naming_the_scenario_without_a_red(tmp_path):
    """The check as `compass check` runs it, on a project on disk."""
    task_dir = tmp_path / ".compass" / "work" / SLUG
    (task_dir / "evidence").mkdir(parents=True)
    (task_dir / "manifest.yml").write_text(
        f"schema_version: '2.0'\nissue: {SLUG}\ncreated: '{AFTER}'\n"
        "status: active\nscenarios:\n"
        "- id: S-1\n  intent: INT-1\n  tests: [t]\n"
        "- id: S-2\n  intent: INT-1\n  tests: [t]\n"
        "evidence:\n- id: EV-green\n  type: test-run\n  path: evidence/green.json\n",
        encoding="utf-8")
    _red(task_dir, "red-S-1", T1, "S-1")
    (task_dir / "evidence" / "green.json").write_text(json.dumps(dict(GREEN, timestamp=T2)))
    result = subprocess.run(
        [sys.executable, str(CLI), "check", "--issue", SLUG, "--json"],
        cwd=tmp_path, capture_output=True, text=True)
    report = json.loads(result.stdout)
    rows = [r for r in report["checks"] if r["name"] == "suite-passed"]
    assert rows and all(r["status"] == "fail" for r in rows), rows
    assert "no red: S-2" in rows[0]["detail"]


def test_rps_1_an_unbound_red_counts_for_a_sole_scenario_only(tmp_path):
    task, task_dir = _issue(tmp_path, scenarios=("S-1",))
    _red(task_dir, "red", T1)
    _green(task, task_dir, "green", T2)
    ok, why = _check(task, task_dir)
    assert ok is True, why
    assert "red before its first green: S-1" in why

    task, task_dir = _issue(tmp_path / "two")
    _red(task_dir, "red", T1)
    _green(task, task_dir, "green", T2)
    ok, why = _check(task, task_dir)
    assert ok is False, why
    assert "no red: S-1, S-2" in why


# --- RPS-2: a red after its scenario's first green is named --------------------------

def test_rps_2_a_red_after_the_scenarios_first_green_fails(tmp_path):
    task, task_dir = _issue(tmp_path)
    _red(task_dir, "red-S-1", T1, "S-1")
    _green(task, task_dir, "green-S-1", T2, "S-1")
    _green(task, task_dir, "green-S-2", T1, "S-2")
    _red(task_dir, "red-S-2", T3, "S-2")
    ok, why = _check(task, task_dir)
    assert ok is False, why
    assert "red after its first green: S-2" in why
    assert T3 in why and T1 in why


def test_rps_2_an_unbound_green_is_the_first_green_of_a_scenario_with_no_bound_one(tmp_path):
    task, task_dir = _issue(tmp_path, scenarios=("S-1",))
    _green(task, task_dir, "green", T1)
    _red(task_dir, "red-S-1", T2, "S-1")
    ok, why = _check(task, task_dir)
    assert ok is False, why
    assert "red after its first green: S-1" in why


def test_rps_2_a_red_in_the_same_second_as_its_green_counts(tmp_path):
    """Records carry the time to the second, and a fast test can go red and green
    within one."""
    task, task_dir = _issue(tmp_path, scenarios=("S-1",))
    _red(task_dir, "red-S-1", T1, "S-1")
    _green(task, task_dir, "green-S-1", T1, "S-1")
    ok, why = _check(task, task_dir)
    assert ok is True, why
    assert "red before its first green: S-1" in why


# --- RPS-3: each scenario with a red first passes, from either loop -----------------

def test_rps_3_a_red_before_the_green_of_each_scenario_passes(tmp_path):
    task, task_dir = _issue(tmp_path)
    _red(task_dir, "red-S-1", T1, "S-1")
    _red(task_dir, "red-S-2.outer", T1, "S-2", loop="outer")
    _green(task, task_dir, "green-S-1", T2, "S-1")
    _green(task, task_dir, "green-S-2.outer", T2, "S-2", loop="outer")
    _green(task, task_dir, "green", T3)
    ok, why = _check(task, task_dir)
    assert ok is True, why
    assert "red before its first green: S-1, S-2" in why


def test_rps_3_one_run_bound_to_several_scenarios_counts_for_each(tmp_path):
    task, task_dir = _issue(tmp_path)
    for sid in ("S-1", "S-2"):
        _red(task_dir, f"red-{sid}.outer", T1, sid, loop="outer", run_id="r1",
             scenarios_in_run=["S-1", "S-2"])
    _green(task, task_dir, "green", T2)
    ok, why = _check(task, task_dir)
    assert ok is True, why
    assert "red before its first green: S-1, S-2" in why


def test_rps_3_a_red_that_does_not_count_does_not_cover_its_scenario(tmp_path):
    """A stamped red edited after it was written is no red, as for the issue."""
    task, task_dir = _issue(tmp_path)
    _red(task_dir, "red-S-1", T1, "S-1")
    _red(task_dir, "red-S-2", T1, "S-2", content_digest="sha256:edited")
    _green(task, task_dir, "green", T2)
    ok, why = _check(task, task_dir)
    assert ok is False, why
    assert "no red: S-2" in why


# --- RPS-4: an acceptance or a narrative scenario needs no red ------------------------

def test_rps_4_a_narrative_scenario_needs_no_red(tmp_path):
    task, task_dir = _issue(tmp_path, narrative=("S-2",))
    _red(task_dir, "red-S-1", T1, "S-1")
    _green(task, task_dir, "green", T2)
    ok, why = _check(task, task_dir)
    assert ok is True, why
    assert "narrative: S-2" in why


def test_rps_4_an_acceptance_bound_to_a_scenario_closes_that_scenario_only(tmp_path):
    task, task_dir = _issue(tmp_path, scenarios=("S-1", "S-2", "S-3"))
    _red(task_dir, "red-S-1", T1, "S-1")
    _green(task, task_dir, "green-S-1", T2, "S-1")
    _green(task, task_dir, "acceptance-S-2", T3, "S-2", kind="validation", declared_at=T1)
    ok, why = _check(task, task_dir)
    assert ok is False, why
    assert "no red: S-3" in why
    assert "S-2" not in why.split("no red:")[1].split(".")[0]


def test_rps_4_an_unbound_acceptance_declared_in_time_closes_every_scenario(tmp_path):
    task, task_dir = _issue(tmp_path)
    _green(task, task_dir, "acceptance", T2, kind="refactor", declared_at=T1)
    ok, why = _check(task, task_dir)
    assert ok is True, why
    assert "closed by an acceptance: S-1, S-2" in why


def test_rps_4_an_acceptance_declared_after_the_first_green_closes_nothing(tmp_path):
    task, task_dir = _issue(tmp_path)
    _red(task_dir, "red-S-1", T1, "S-1")
    _green(task, task_dir, "green-S-1", T1, "S-1")
    _green(task, task_dir, "acceptance-S-2", T3, "S-2", kind="validation", declared_at=T2)
    ok, why = _check(task, task_dir)
    assert ok is False, why
    assert "no red: S-2" in why


def test_rps_4_an_issue_of_narrative_scenarios_still_needs_one_red(tmp_path):
    """The per-scenario rule adds to the rule for the issue; it does not lift it."""
    task, task_dir = _issue(tmp_path, scenarios=("S-1",), narrative=("S-1",))
    _green(task, task_dir, "green", T2)
    ok, why = _check(task, task_dir)
    assert ok is False, why
    assert "no red is on record" in why


# --- RPS-5: an older issue keeps its rule, with a notice ------------------------------

@pytest.mark.parametrize("created", [BEFORE, None])
def test_rps_5_an_issue_created_and_worked_before_the_cutoff_passes_with_a_notice(
        tmp_path, created):
    task, task_dir = _issue(tmp_path, created=created)
    if created is None:
        del task["created"]
    _red(task_dir, "red-S-1", OLD, "S-1")
    _green(task, task_dir, "green", OLD)
    ok, why = _check(task, task_dir)
    assert ok is True, why
    assert "notice" in why.lower()
    assert "no red: S-2" in why
    assert AFTER in why


def test_rps_5_an_older_issue_that_meets_the_new_rule_has_no_notice(tmp_path):
    task, task_dir = _issue(tmp_path, created=BEFORE)
    _red(task_dir, "red-S-1", OLD, "S-1")
    _red(task_dir, "red-S-2", OLD, "S-2")
    _green(task, task_dir, "green", OLD)
    ok, why = _check(task, task_dir)
    assert ok is True, why
    assert "notice" not in why.lower()


def test_rps_5_an_issue_with_no_scenarios_has_no_notice(tmp_path):
    task, task_dir = _issue(tmp_path, scenarios=(), created=BEFORE)
    _green(task, task_dir, "green", OLD)
    ok, why = _check(task, task_dir)
    assert ok is True, why
    assert "notice" not in why.lower()


# --- RPS-6: a backdated issue whose work all comes after the cutoff gets the rule ----

def test_rps_6_a_backdated_issue_with_no_work_before_the_cutoff_gets_the_rule(tmp_path):
    task, task_dir = _issue(tmp_path, created=BEFORE)
    _red(task_dir, "red-S-1", T1, "S-1")
    _green(task, task_dir, "green", T2)
    ok, why = _check(task, task_dir)
    assert ok is False, why
    assert "no red: S-2" in why
    assert "`created:` is earlier" in why


def test_rps_6_an_older_issue_with_work_before_the_cutoff_keeps_its_rule(tmp_path):
    """Work recorded before the change shows the issue was in flight under the
    old rule, so later work on it does not change the rule."""
    task, task_dir = _issue(tmp_path, created=BEFORE)
    _red(task_dir, "red-S-1", OLD, "S-1")
    _green(task, task_dir, "green", T2)
    ok, why = _check(task, task_dir)
    assert ok is True, why
    assert "no red: S-2" in why


# --- RPS-7: the archive keeps its verdicts ------------------------------------------

def test_rps_7_the_cutoff_is_after_every_archived_issue():
    """Every archived issue was created before the cutoff, so none gains the rule."""
    import yaml
    late = []
    for manifest in sorted((ROOT / ".compass" / "work").glob("*/manifest.yml")):
        created = (yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}).get("created")
        if created and str(created)[:10] >= AFTER:
            late.append(manifest.parent.name)
    assert late == []


# --- RPS-8: the governance text states the rule --------------------------------------

def test_rps_8_the_check_statement_states_the_per_scenario_rule():
    import yaml
    doc = yaml.safe_load((ROOT / "governance" / "presets" / "default" / "checks.yml")
                         .read_text(encoding="utf-8"))
    text = " ".join(doc["checks"]["suite-passed"]["statement"].split())
    assert "each scenario" in text
    assert AFTER in text
