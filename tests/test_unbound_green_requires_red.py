"""`suite-passed` needs a failure observed first, not only a green.

`suite-passed` checks guardrail `G1`, that a change is tested before it
lands. It accepted any green record, and an unbound green needs no red, so an
issue could pass it without ever seeing a test fail. 9 of 110 archived issues
did, as the issue `unbound-green-needs-no-red` measured. The rule now:
an issue created on or after the cutoff that declares scenarios needs one red
record, bound or unbound, or an acceptance record for work with no natural
red. Issues created before the cutoff keep the result they had.

Scenario ids: UGR-1 to UGR-8, in the acceptance criteria of the issue
`unbound-green-needs-no-red`.
"""
from __future__ import annotations

import datetime
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
sys.path.insert(0, str(ROOT / "cli"))

from compass_pkg.checks import _check_suite_passed  # noqa: E402
from compass_pkg.red_first import RED_REQUIRED_FROM  # noqa: E402
from check_set_files import view as shipped_view  # noqa: E402

AFTER = str(RED_REQUIRED_FROM)
BEFORE = "2026-01-01"
SLUG = "sample"


def _issue(tmp_path, created=AFTER, scenarios=("S-1",)):
    """An issue directory with a manifest, and a function to plant evidence."""
    task_dir = tmp_path / ".compass" / "work" / SLUG
    (task_dir / "evidence").mkdir(parents=True)
    task = {
        "schema_version": "2.0", "issue": SLUG, "created": created,
        "status": "active",
        "scenarios": [{"id": s, "intent": "INT-1", "tests": ["t"]}
                      for s in scenarios],
        "evidence": [],
    }
    return task, task_dir


def _plant(task, task_dir, name, payload, register=True):
    (task_dir / "evidence" / f"{name}.json").write_text(json.dumps(payload))
    if register:
        entry = {"id": f"EV-{name}", "type": "test-run",
                 "path": f"evidence/{name}.json"}
        if payload.get("scenario"):
            entry["scenario"] = payload["scenario"]
        task["evidence"].append(entry)


GREEN = {"exit_code": 0, "passed": True, "command": "pytest"}
RED = {"exit_code": 1, "passed": False, "command": "pytest"}


def test_ugr_1_an_issue_whose_only_evidence_is_an_unbound_green_fails(tmp_path):
    task, task_dir = _issue(tmp_path)
    _plant(task, task_dir, "green", GREEN)
    ok, why = _check_suite_passed(task, str(task_dir))
    assert ok is False
    assert "no red" in why
    assert "compass tdd-red" in why
    assert "compass acceptance start --kind validation|refactor" in why


@pytest.mark.parametrize("payload", [
    {"passed": False, "exit_code": 0},
    {"passed": False, "exit_code": "1"},
    {"passed": False},
    {"exit_code": 1},
    ["not", "an", "object"],
])
def test_ugr_1_only_a_record_of_a_failed_run_is_a_red(tmp_path, payload):
    """`compass tdd-red` writes `passed` false and a non-zero integer exit
    code. A green record with `passed` flipped still says exit code 0."""
    task, task_dir = _issue(tmp_path)
    _plant(task, task_dir, "green", GREEN)
    (task_dir / "evidence" / "red.json").write_text(json.dumps(payload))
    ok, _ = _check_suite_passed(task, str(task_dir))
    assert ok is False


def test_ugr_1_a_red_that_is_a_symlink_does_not_count(tmp_path):
    """A symlink could stand another issue's red in for this one's."""
    task, task_dir = _issue(tmp_path)
    _plant(task, task_dir, "green", GREEN)
    elsewhere = tmp_path / "other-red.json"
    elsewhere.write_text(json.dumps(RED))
    os.symlink(elsewhere, task_dir / "evidence" / "red.json")
    ok, _ = _check_suite_passed(task, str(task_dir))
    assert ok is False


def test_ugr_1_a_fifo_named_like_a_red_does_not_hang_the_check(tmp_path):
    task, task_dir = _issue(tmp_path)
    (task_dir / "evidence" / "green.json").write_text(json.dumps(GREEN))
    os.mkfifo(task_dir / "evidence" / "red-x.json")
    probe = (
        "import sys; sys.path.insert(0, %r)\n"
        "from compass_pkg.checks import _check_suite_passed\n"
        "task = {'created': %r, 'scenarios': [{'id': 'S-1'}], 'evidence': "
        "[{'id': 'E', 'type': 'test-run', 'path': 'evidence/green.json'}]}\n"
        "print(_check_suite_passed(task, %r)[0])\n"
        % (str(ROOT / "cli"), AFTER, str(task_dir)))
    result = subprocess.run([sys.executable, "-c", probe], capture_output=True,
                            text=True, timeout=30)
    assert result.stdout.strip() == "False", result.stderr


def test_ugr_1_a_passing_red_file_is_not_a_red(tmp_path):
    """A file named red.json that records a pass observed no failure."""
    task, task_dir = _issue(tmp_path)
    _plant(task, task_dir, "green", GREEN)
    _plant(task, task_dir, "red", GREEN, register=False)
    ok, _ = _check_suite_passed(task, str(task_dir))
    assert ok is False


@pytest.mark.parametrize("red_name", ["red", "red-S-1", "red-S-2"])
def test_ugr_2_one_red_of_either_binding_satisfies_the_rule(tmp_path, red_name):
    task, task_dir = _issue(tmp_path, scenarios=("S-1", "S-2"))
    _plant(task, task_dir, "green", GREEN)
    _plant(task, task_dir, red_name, RED, register=False)
    ok, why = _check_suite_passed(task, str(task_dir))
    assert ok is True, why


@pytest.mark.parametrize("kind", ["validation", "refactor"])
def test_ugr_3_an_acceptance_record_stands_in_for_a_red(tmp_path, kind):
    task, task_dir = _issue(tmp_path)
    _plant(task, task_dir, "acceptance", dict(GREEN, kind=kind))
    ok, why = _check_suite_passed(task, str(task_dir))
    assert ok is True, why


def test_ugr_3_an_acceptance_record_outside_the_issue_does_not_count(tmp_path):
    task, task_dir = _issue(tmp_path)
    _plant(task, task_dir, "green", GREEN)
    outside = tmp_path / "acceptance.json"
    outside.write_text(json.dumps(dict(GREEN, kind="validation")))
    task["evidence"].append({"id": "EV-X", "type": "test-run",
                             "path": "../../../acceptance.json"})
    ok, _ = _check_suite_passed(task, str(task_dir))
    assert ok is False


def test_ugr_4_an_issue_with_no_scenarios_is_not_asked_for_a_red(tmp_path):
    task, task_dir = _issue(tmp_path, scenarios=())
    _plant(task, task_dir, "green", GREEN)
    ok, why = _check_suite_passed(task, str(task_dir))
    assert ok is True, why


@pytest.mark.parametrize("created", [BEFORE, None])
def test_ugr_5_an_issue_created_before_the_cutoff_keeps_its_result(
        tmp_path, created):
    task, task_dir = _issue(tmp_path, created=created)
    if created is None:
        del task["created"]
    _plant(task, task_dir, "green", GREEN)
    ok, why = _check_suite_passed(task, str(task_dir))
    assert ok is True, why


@pytest.mark.parametrize("created", [
    "01/10/2026", "1 Oct 2026", datetime.date(2026, 10, 1),
    datetime.datetime(2026, 10, 1, 9, 0)])
def test_ugr_5_a_created_value_that_is_not_an_old_iso_date_gets_the_rule(
        tmp_path, created):
    """Only a missing or blank `created:` is exempt. A value that does not
    parse is not trusted to mean "old"."""
    task, task_dir = _issue(tmp_path, created=created)
    _plant(task, task_dir, "green", GREEN)
    ok, _ = _check_suite_passed(task, str(task_dir))
    assert ok is False


def _project(tmp_path):
    """A real project on disk, for the CLI tests."""
    task_dir = tmp_path / ".compass" / "work" / SLUG
    task_dir.mkdir(parents=True)
    (task_dir / "manifest.yml").write_text(
        f"schema_version: '2.0'\nissue: {SLUG}\ncreated: '{AFTER}'\n"
        "status: active\nscenarios:\n- id: S-1\n  intent: INT-1\n"
        "  tests: [t]\nevidence: []\n", encoding="utf-8")
    return task_dir


def _cli(tmp_path, *args):
    return subprocess.run([sys.executable, str(CLI), *args, "--issue", SLUG],
                          cwd=tmp_path, capture_output=True, text=True)


def test_ugr_6_the_bound_green_refusal_names_acceptance_not_the_bypass(tmp_path):
    _project(tmp_path)
    result = _cli(tmp_path, "tdd-green", "--scenario", "S-1", "--",
                  sys.executable, "-c", "pass")
    assert result.returncode != 0
    text = " ".join((result.stdout + result.stderr).split())
    assert "drop --scenario" not in text
    assert "unbound green" not in text
    assert "compass acceptance start --kind validation|refactor" in text


def test_ugr_7_an_unbound_green_with_no_red_does_not_claim_a_red(tmp_path):
    _project(tmp_path)
    result = _cli(tmp_path, "tdd-green", "--", sys.executable, "-c", "pass")
    assert result.returncode == 0, result.stderr
    text = " ".join(result.stdout.split())
    assert "red -> green is on record" not in text
    assert "no red is on record" in text


def test_ugr_7_a_red_already_on_record_is_named_not_denied(tmp_path):
    """The last full-suite green comes after the bound reds were cleared. It
    must not say no red is on record when one is."""
    task_dir = _project(tmp_path)
    (task_dir / "evidence").mkdir(exist_ok=True)
    (task_dir / "evidence" / "red-S-1.json").write_text(json.dumps(RED))
    result = _cli(tmp_path, "tdd-green", "--", sys.executable, "-c", "pass")
    assert result.returncode == 0, result.stderr
    text = " ".join(result.stdout.split())
    assert "no red is on record" not in text
    assert "a red for this issue is already on record" in text


def test_ugr_7_a_green_after_a_red_still_says_so(tmp_path):
    task_dir = _project(tmp_path)
    (task_dir / ".red").write_text("")
    (task_dir / "evidence").mkdir(exist_ok=True)
    (task_dir / "evidence" / "red.json").write_text(json.dumps(RED))
    result = _cli(tmp_path, "tdd-green", "--", sys.executable, "-c", "pass")
    assert result.returncode == 0, result.stderr
    assert "red -> green is on record" in " ".join(result.stdout.split())


def test_ugr_8_the_governance_text_states_the_rule():
    import yaml
    doc = shipped_view("guardrails.yml")
    text = " ".join(doc["checks"]["suite-passed"]["description"].split())
    assert "red record" in text
    assert "acceptance record" in text
    assert "declares scenarios" in text
