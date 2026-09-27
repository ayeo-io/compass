"""A red from a command that ran no test does not unlock code edits.

A runner Compass does not recognise is judged by its exit code alone. A
real runner that fails prints why, so a silent command that also names none
of the issue's declared test files ran no test: `compass tdd-red -- false`
is the one-word way to unlock the pre-tool hook without writing a test.
Such a red is refused, and no `.red` marker is written.

This stops the one-word forgery, not a determined one: a command that
prints something and exits non-zero still records a red, and the record
keeps the command, so it is visible to anyone who reads it.

Scenario ids: RWT-1 and RWT-2, in the delivery approach of issue
`red-without-a-test-unlocks-edits`.
"""
from __future__ import annotations

import json

import pytest

SLUG = "silent"


def _body(tests):
    return {"assessment": {"risk": "contained", "familiarity": "greenfield",
                           "size": "small", "goal": "delivery",
                           "role": "engineer", "labels": []},
            "scenarios": [{"id": "SIL-1", "intent": "INT-1", "tests": tests}]}


@pytest.fixture
def red(make_task, run_cli, project):
    """Run tdd-red with the given command words; return the result, the
    red record if one was written, and whether `.red` exists."""
    def _run(tests, *command):
        task_dir = make_task(SLUG, _body(tests))
        result = run_cli("tdd-red", "--issue", SLUG, "--", *command, timeout=60)
        path = task_dir / "evidence" / "red.json"
        record = json.loads(path.read_text()) if path.exists() else None
        return result, record, (task_dir / ".red").exists()
    return _run


def test_rwt_1_a_silent_red_that_names_no_test_is_refused(red):
    result, record, marker = red([], "false")
    assert result.returncode != 0, result.combined
    assert record is None
    assert not marker
    assert "no test" in result.combined.lower(), result.combined


def test_rwt_2_a_runner_that_prints_its_failure_still_records(red):
    result, record, marker = red([], "sh", "-c", "echo '1 failed'; exit 1")
    assert result.returncode == 0, result.combined
    assert record["red_kind"] == "exit-code"
    assert marker


def test_rwt_2_a_silent_command_naming_a_declared_test_still_records(red, project):
    (project / "spec").mkdir()
    (project / "spec" / "thing_test.sh").write_text("exit 1\n")
    result, record, marker = red(["spec/thing_test.sh::thing"],
                                 "sh", "spec/thing_test.sh")
    assert result.returncode == 0, result.combined
    assert record["red_kind"] == "exit-code"
    assert marker
