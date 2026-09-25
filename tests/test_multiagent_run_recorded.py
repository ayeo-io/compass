"""`multiagent-run-recorded`, under the evidence-not-assertion guardrail
(`G4`): a multiagent issue's manifest shows the run that built it completed
- every subtask done, with a passing last review round.

These tests check every row of the check's condition table: which issues it
reads (a multiagent issue, ready to judge, that either already records a
`subtasks:` key or was created on or after 2026-09-26), what makes it fail
(no `subtasks:`, an entry not done, a last review round that did not pass),
what it names in a fail, and what makes it pass.

Table of conditions: `technical-design.md` section 3 of the issue
`dispatch-protocol`. Scenario id: `DPR-1`.
"""
from __future__ import annotations

import datetime
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


# --- row 2: no `subtasks:` key, and created is before the cutoff or missing -
#
# The requirements review's correction (Q2): an issue that already records a
# `subtasks:` key is judged on it whatever its date. An issue with no
# `subtasks:` key is judged only if created on or after 2026-09-26 - the
# case `evidence-binding` raised at integration, an issue created
# 2026-09-25 whose breakdown ran without a subtask record, is nothing to
# check.

def test_row_2_no_subtasks_key_before_the_cutoff_is_nothing_to_check():
    assert RUN_RECORD_REQUIRED_FROM.isoformat() == "2026-09-26"
    task = _task(created="2026-09-24")  # would otherwise fail
    del task["subtasks"]
    passed, detail = _check_multiagent_run_recorded(task, TASK_DIR)
    assert passed is NOTHING_TO_CHECK, detail


def test_row_2_no_subtasks_key_created_2026_09_25_is_nothing_to_check():
    """`evidence-binding`'s own case: created the day the protocol landed,
    with no `subtasks:` key, is nothing to check - the day before the
    cutoff."""
    task = _task(created="2026-09-25")  # would otherwise fail
    del task["subtasks"]
    passed, detail = _check_multiagent_run_recorded(task, TASK_DIR)
    assert passed is NOTHING_TO_CHECK, detail


def test_row_2_no_subtasks_key_missing_created_is_nothing_to_check():
    task = _task()
    del task["subtasks"]
    del task["created"]
    passed, detail = _check_multiagent_run_recorded(task, TASK_DIR)
    assert passed is NOTHING_TO_CHECK, detail


def test_row_2_no_subtasks_key_created_as_a_date_object_before_the_cutoff_is_nothing_to_check():
    """YAML loads an unquoted `created: 2026-09-25` as a `datetime.date`, not
    a string."""
    task = _task(created=datetime.date(2026, 9, 25))
    del task["subtasks"]
    passed, detail = _check_multiagent_run_recorded(task, TASK_DIR)
    assert passed is NOTHING_TO_CHECK, detail


def test_row_2_no_subtasks_key_created_as_a_date_object_on_the_cutoff_applies():
    task = _task(created=datetime.date(2026, 9, 26))
    del task["subtasks"]
    passed, detail = _check_multiagent_run_recorded(task, TASK_DIR)
    assert passed is False, detail


def test_row_2_no_subtasks_key_created_as_a_non_date_string_is_treated_as_in_scope():
    """A `created:` present but not an ISO date is not trusted to mean 'this
    issue predates the protocol', so the check still applies to it."""
    task = _task(created="recently")
    del task["subtasks"]
    passed, detail = _check_multiagent_run_recorded(task, TASK_DIR)
    assert passed is False, detail


def test_row_2_a_subtasks_key_created_2026_09_25_with_a_complete_record_passes():
    """An issue that already records a `subtasks:` key is judged on it
    whatever its date - even the day before the cutoff."""
    task = _task(created="2026-09-25")
    passed, detail = _check_multiagent_run_recorded(task, TASK_DIR)
    assert passed is True, detail


def test_row_2_a_subtasks_key_created_2026_09_25_with_an_incomplete_record_fails():
    task = _task(created="2026-09-25", subtasks=[
        {"id": "subtask-1", "status": "reviewing",
         "review_rounds": [{"round": 1, "verdict": "pass"}]},
    ])
    passed, detail = _check_multiagent_run_recorded(task, TASK_DIR)
    assert passed is False, detail
    assert "subtask-1" in detail


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
    """An issue created on or after the cutoff, with no `subtasks:` key,
    fails - it did not predate the protocol, so it is judged."""
    task = _task(created="2026-09-26")
    del task["subtasks"]
    passed, detail = _check_multiagent_run_recorded(task, TASK_DIR)
    assert passed is False
    assert "subtasks" in detail.lower()


def test_row_4_a_subtasks_mapping_fails_and_says_it_is_not_a_list():
    """A `subtasks:` value that is a mapping - the key is present, so the
    message must say the value is the wrong type, not that nothing is
    recorded."""
    task = _task(subtasks={"s1": {"status": "done"}})
    passed, detail = _check_multiagent_run_recorded(task, TASK_DIR)
    assert passed is False
    assert "not a list" in detail.lower()


def test_row_4_a_subtask_entry_that_is_not_a_mapping_fails_named_by_position():
    """A `subtasks:` entry that is not a mapping - a bare string in place
    of the record - fails, named by its position, rather than being
    dropped from the list before judgement."""
    task = _task(subtasks=[
        "subtask-9",
        {"id": "s1", "status": "done",
         "review_rounds": [{"round": 1, "verdict": "pass"}]},
    ])
    passed, detail = _check_multiagent_run_recorded(task, TASK_DIR)
    assert passed is False
    assert "subtasks[0]" in detail
    assert "s1" not in detail


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
    """The requirements review's rule (Q1): the subtask passes on its LAST
    round's verdict, so a later fail after an earlier pass is still the
    last word on it."""
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


def test_row_6_a_malformed_trailing_round_is_not_a_pass():
    """The last entry of `review_rounds`, whatever its type, is the one
    that must carry `verdict: pass` - a malformed last round does not let
    an earlier pass stand in for it."""
    task = _task(subtasks=[
        {"id": "subtask-1", "status": "done",
         "review_rounds": [{"round": 1, "verdict": "pass"}, "fail"]},
    ])
    passed, detail = _check_multiagent_run_recorded(task, TASK_DIR)
    assert passed is False
    assert "subtask-1" in detail


def test_a_subtask_id_that_is_not_a_string_does_not_error():
    """The requirements review's rule that YAML types stay readable
    (Q1): an unquoted `id: 3` loads as an int, and joining it into the
    message with a string list must not raise `TypeError`."""
    task = _task(subtasks=[{"id": 3, "status": "reviewing"}])
    passed, detail = _check_multiagent_run_recorded(task, TASK_DIR)
    assert passed is False
    assert "3" in detail


def test_a_review_rounds_value_that_is_a_mapping_fails_named_not_errors():
    """A `review_rounds:` value that is not a list - a mapping in place of
    the list, an easy hand-edit mistake - must fail the subtask by name,
    not raise `KeyError` out of the check."""
    task = _task(subtasks=[
        {"id": "subtask-1", "status": "done",
         "review_rounds": {"round": 1, "verdict": "pass"}},
    ])
    passed, detail = _check_multiagent_run_recorded(task, TASK_DIR)
    assert passed is False
    assert "subtask-1" in detail


def test_a_review_rounds_value_that_is_a_number_fails_named_not_errors():
    """A `review_rounds:` value that is not a list - a bare number - must
    fail the subtask by name, not raise `TypeError` out of the check."""
    task = _task(subtasks=[
        {"id": "subtask-1", "status": "done", "review_rounds": 5},
    ])
    passed, detail = _check_multiagent_run_recorded(task, TASK_DIR)
    assert passed is False
    assert "subtask-1" in detail


def test_not_done_and_a_failed_round_on_a_different_subtask_are_both_named():
    """Every problem is reported in one run, rather than stopping at the
    first category and making the reader run again to learn about the
    next one."""
    task = _task(subtasks=[
        {"id": "subtask-1", "status": "reviewing",
         "review_rounds": [{"round": 1, "verdict": "pass"}]},
        {"id": "subtask-2", "status": "done",
         "review_rounds": [{"round": 1, "verdict": "fail"}]},
    ])
    passed, detail = _check_multiagent_run_recorded(task, TASK_DIR)
    assert passed is False
    assert "subtask-1" in detail
    assert "subtask-2" in detail


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
