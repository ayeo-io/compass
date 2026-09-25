"""`multiagent-run-recorded` (`G4`): a multiagent issue's manifest shows the
run that built it completed - every subtask done, with a passing last review
round.

Before this check, nothing read the `subtasks:` record back: an issue could
land with no subtask ever marked done, or with one still failing its last
review round, and `compass check` would say nothing. `multiagent-run-recorded`
closes that gap for an issue created on or after 2026-09-25, the day
`docs/multiagent-protocol.md` landed (ADR-006: a new mechanism no-ops for
issues that predate it).

Table of conditions: `technical-design.md` section 3 of the issue
`dispatch-protocol`. Scenario id: `DPR-1`.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

from compass_pkg.check_results import NOTHING_TO_CHECK  # noqa: E402
from compass_pkg.multiagent_check import (  # noqa: E402
    RUN_RECORD_REQUIRED_FROM, _check_multiagent_run_recorded)

TASK_DIR = "/does/not/matter"  # the check reads only the manifest dict


def _task(**over):
    body = {
        "stages": {"breakdown": "multiagent"},
        "created": "2026-09-25",
        "status": "active",
        "gates": [{"id": "verify.correctness", "status": "pass"}],
        "subtasks": [
            {"id": "subtask-1", "status": "done",
             "review_rounds": [{"round": 1, "verdict": "pass"}]},
        ],
    }
    body.update(over)
    return body


# --- row 1: breakdown is not multiagent -------------------------------------

def test_row_1_not_multiagent_breakdown_is_nothing_to_check():
    task = _task(stages={"breakdown": "standard"})
    passed, detail = _check_multiagent_run_recorded(task, TASK_DIR)
    assert passed is NOTHING_TO_CHECK, detail


def test_row_1_no_stages_at_all_is_nothing_to_check():
    task = _task()
    del task["stages"]
    passed, detail = _check_multiagent_run_recorded(task, TASK_DIR)
    assert passed is NOTHING_TO_CHECK, detail


# --- row 2: created is before the start date, or missing --------------------

def test_row_2_created_before_the_start_date_is_nothing_to_check():
    assert RUN_RECORD_REQUIRED_FROM.isoformat() == "2026-09-25"
    task = _task(created="2026-09-24", subtasks=[])  # would otherwise fail
    passed, detail = _check_multiagent_run_recorded(task, TASK_DIR)
    assert passed is NOTHING_TO_CHECK, detail


def test_row_2_missing_created_is_nothing_to_check():
    task = _task(subtasks=[])
    del task["created"]
    passed, detail = _check_multiagent_run_recorded(task, TASK_DIR)
    assert passed is NOTHING_TO_CHECK, detail


# --- row 3: still in flight ---------------------------------------------------

def test_row_3_a_gate_not_yet_passed_and_not_landed_is_nothing_to_check():
    task = _task(gates=[{"id": "verify.correctness", "status": "pending"}],
                subtasks=[])  # would otherwise fail
    passed, detail = _check_multiagent_run_recorded(task, TASK_DIR)
    assert passed is NOTHING_TO_CHECK, detail


def test_row_3_no_gates_recorded_yet_is_nothing_to_check():
    task = _task(gates=[], subtasks=[])
    passed, detail = _check_multiagent_run_recorded(task, TASK_DIR)
    assert passed is NOTHING_TO_CHECK, detail


def test_row_3_landed_with_no_gates_passed_still_applies():
    """`status: landed` alone makes the issue ready, whatever its gates say -
    a landed issue is not "still in flight"."""
    task = _task(status="landed",
                gates=[{"id": "verify.correctness", "status": "pending"}],
                subtasks=[])
    passed, detail = _check_multiagent_run_recorded(task, TASK_DIR)
    assert passed is False, detail


# --- row 4: no subtasks -------------------------------------------------------

def test_row_4_no_subtasks_fails():
    task = _task(subtasks=[])
    passed, detail = _check_multiagent_run_recorded(task, TASK_DIR)
    assert passed is False
    assert "subtasks" in detail.lower()


def test_row_4_missing_subtasks_key_fails():
    task = _task()
    del task["subtasks"]
    passed, detail = _check_multiagent_run_recorded(task, TASK_DIR)
    assert passed is False
    assert "subtasks" in detail.lower()


# --- row 5: a subtask whose status is not done --------------------------------

def test_row_5_a_subtask_not_done_fails_and_names_it():
    task = _task(subtasks=[
        {"id": "subtask-1", "status": "done",
         "review_rounds": [{"round": 1, "verdict": "pass"}]},
        {"id": "subtask-2", "status": "reviewing",
         "review_rounds": [{"round": 1, "verdict": "pass"}]},
    ])
    passed, detail = _check_multiagent_run_recorded(task, TASK_DIR)
    assert passed is False
    assert "subtask-2" in detail
    assert "subtask-1" not in detail


# --- row 6: a subtask whose last review round is missing or fail -------------

def test_row_6_a_subtask_with_no_review_rounds_fails_and_names_it():
    task = _task(subtasks=[
        {"id": "subtask-1", "status": "done", "review_rounds": []},
    ])
    passed, detail = _check_multiagent_run_recorded(task, TASK_DIR)
    assert passed is False
    assert "subtask-1" in detail


def test_row_6_a_subtask_whose_last_round_failed_fails_and_names_it():
    task = _task(subtasks=[
        {"id": "subtask-1", "status": "done",
         "review_rounds": [{"round": 1, "verdict": "fail"}]},
    ])
    passed, detail = _check_multiagent_run_recorded(task, TASK_DIR)
    assert passed is False
    assert "subtask-1" in detail


def test_row_6_a_later_failing_round_after_a_pass_still_fails():
    """Q1: the subtask passes on its LAST round's verdict, so a later fail
    after an earlier pass is still the last word on it."""
    task = _task(subtasks=[
        {"id": "subtask-1", "status": "done",
         "review_rounds": [{"round": 1, "verdict": "pass"},
                           {"round": 2, "verdict": "fail"}]},
    ])
    passed, detail = _check_multiagent_run_recorded(task, TASK_DIR)
    assert passed is False
    assert "subtask-1" in detail


def test_row_6_a_later_passing_round_after_a_fail_clears_it():
    task = _task(subtasks=[
        {"id": "subtask-1", "status": "done",
         "review_rounds": [{"round": 1, "verdict": "fail"},
                           {"round": 2, "verdict": "pass"}]},
    ])
    passed, detail = _check_multiagent_run_recorded(task, TASK_DIR)
    assert passed is True, detail


# --- row 7: otherwise, pass ---------------------------------------------------

def test_row_7_every_subtask_done_with_a_passing_last_round_passes():
    task = _task(subtasks=[
        {"id": "subtask-1", "status": "done",
         "review_rounds": [{"round": 1, "verdict": "pass"}]},
        {"id": "subtask-2", "status": "done",
         "review_rounds": [{"round": 1, "verdict": "fail"},
                           {"round": 2, "verdict": "pass"}]},
    ])
    passed, detail = _check_multiagent_run_recorded(task, TASK_DIR)
    assert passed is True, detail


def test_row_7_a_landed_issue_with_a_complete_record_passes():
    task = _task(status="landed", gates=[])
    passed, detail = _check_multiagent_run_recorded(task, TASK_DIR)
    assert passed is True, detail


# --- through `compass check`: the name reaches the printed output ------------

def test_compass_check_prints_the_check_by_name_for_a_multiagent_issue(
        run_cli, make_task):
    """DPR-1: `compass check` names `multiagent-run-recorded` for a
    multiagent issue, whatever it finds."""
    make_task("multiagent-issue", {
        "assessment": {"risk": "contained", "familiarity": "brownfield-mapped",
                     "size": "small", "intent": "delivery"},
        "delivery_approach": "standard",
        "stages": {"breakdown": "multiagent"},
        "created": "2026-09-25",
        "scenarios": [], "evidence": [], "gates": [], "changed_files": [],
    })
    r = run_cli("check", "--verbose", "--issue", "multiagent-issue")
    combined = r.stdout + r.stderr
    assert "multiagent-run-recorded" in combined, combined
