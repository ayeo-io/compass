"""Scenario group G of the four-layer acceptance strategy: `attempts` on outer-loop
records.

On an issue the strategy applies to, the check `outer-loop-attempts-recorded`
fails an outer-loop green with no `attempts`, or with a value that is not a
whole number of 1 or more. `no-trusted-rerun` does not change. An outer-loop
green carries the `test` field `no-trusted-rerun` reads, so a quarantine entry
can match it. Each loop keeps its own run count per scenario (ADR-084).

The specification is `acceptance-criteria.md` of the Compass issue
`atdd-strategy`, scenarios `TRC-G1` to `TRC-G6` (ayeo-io/compass-delivery#325).
Each test names the scenario it checks; `support.py` builds the projects.
"""
from __future__ import annotations

import json
import shutil

import pytest
import yaml

from tests.acceptance.atdd_strategy import support

CHECK = "outer-loop-attempts-recorded"
RERUN = "no-trusted-rerun"
FAIL = "sh", "-c", "echo 'test_place_order FAILED'; exit 1"
PASS = "sh", "-c", "echo 'test_place_order PASSED'"
GREEN = "evidence/green-TRC-1.outer.json"


def _issue(tmp_path, expected=None, setting=None):
    """A regular issue with scenario `TRC-1`, which declares the acceptance test."""
    project = support.Project(tmp_path / "repo")
    if setting is not None:
        project.setting(setting)
    support.stage_one_suite(project.root)
    issue = project.issue("orders")
    code, out, err = issue.assess(expected=expected)
    assert code == 0, out + err
    issue.must("scenario", "add", "TRC-1", "--issue", issue.slug, "--intent", "INT-1",
               "--title", "Place an order", "--test", support.SPEC_TEST)
    return project, issue


def _run(issue, verb, loop, command, scenario="TRC-1"):
    argv = [verb, "--issue", issue.slug, "--loop", loop]
    if scenario:
        argv += ["--scenario", scenario]
    if verb == "tdd-green" and loop == "outer":
        argv += support.NAMED
    return issue.run(*argv, "--", *command)


def _must(issue, verb, loop, command, scenario="TRC-1"):
    code, out, err = _run(issue, verb, loop, command, scenario)
    assert code == 0, out + err
    return out


def _record(issue, rel):
    return json.loads((issue.dir / rel).read_text(encoding="utf-8"))


def _rewrite(issue, rel, **fields):
    """Rewrite a record with `fields` set, or removed where the value is `...`, and
    stamp it again so its identity covers what it holds."""
    from compass_pkg.tdd import _stamp_identity
    record = _record(issue, rel)
    for key, value in fields.items():
        if value is ...:
            record.pop(key, None)
        else:
            record[key] = value
    record.pop("record_id", None)
    record.pop("content_digest", None)
    record_id, digest = _stamp_identity(record)
    (issue.dir / rel).write_text(json.dumps(record, indent=2), encoding="utf-8")
    body = issue.manifest()
    for entry in body.get("evidence") or []:
        if entry.get("path") == rel:
            entry["record_id"], entry["content_digest"] = record_id, digest
    issue.write_manifest(body)


def _row(document, name=CHECK):
    rows = [c for c in document["checks"] if c["name"] == name]
    assert len(rows) == 1, (name, document["checks"])
    return rows[0]


def _outer_red_and_green(issue):
    _must(issue, "tdd-red", "outer", FAIL)
    _must(issue, "tdd-green", "outer", PASS)


# --- `TRC-G1` ------------------------------------------------------------------------------

def test_trc_g1(tmp_path):
    """An outer-loop green records its run count."""
    _, issue = _issue(tmp_path)
    _must(issue, "tdd-red", "outer", FAIL)
    # The inner loop ran first, on the same tree with the same command. Its run is
    # not an outer-loop run (ADR-084).
    _must(issue, "tdd-red", "inner", FAIL)
    _must(issue, "tdd-green", "inner", PASS)
    _must(issue, "tdd-green", "outer", PASS)
    record = _record(issue, GREEN)
    assert record["loop"] == "outer"
    assert record["attempts"] == 1, record
    assert "rerun_without_change" not in record, record


def test_trc_g1_each_loop_keeps_its_own_count(tmp_path):
    """Each loop counts only its own runs of a scenario (ADR-084)."""
    _, issue = _issue(tmp_path)
    _outer_red_and_green(issue)
    _must(issue, "tdd-red", "inner", FAIL)
    _must(issue, "tdd-green", "inner", PASS)
    _must(issue, "tdd-green", "outer", PASS)
    assert _record(issue, "evidence/green-TRC-1.json")["attempts"] == 1
    outer = _record(issue, GREEN)
    assert (outer["attempts"], outer["rerun_without_change"]) == (2, True), outer


def test_trc_g1_old_shared_count_is_read_as_inner(tmp_path):
    """A count written before ADR-084 keys a scenario with no loop, and stays the
    inner loop's: the next outer-loop green starts at 1."""
    _, issue = _issue(tmp_path)
    _must(issue, "tdd-red", "outer", FAIL)
    state = issue.dir / "evidence" / ".tdd-state.json"
    state.write_text(json.dumps({"TRC-1": {"tree_hash": "older", "attempts": 3,
                                           "command": "older"}}), encoding="utf-8")
    _must(issue, "tdd-green", "outer", PASS)
    assert _record(issue, GREEN)["attempts"] == 1
    assert json.loads(state.read_text(encoding="utf-8"))["TRC-1"]["attempts"] == 3


# --- `TRC-G2` ------------------------------------------------------------------------------

def test_trc_g2(tmp_path):
    """An in-scope outer-loop record with no `attempts` fails."""
    _, issue = _issue(tmp_path)
    assert issue.manifest()["created"] == support.CREATED
    _outer_red_and_green(issue)
    _rewrite(issue, GREEN, attempts=...)
    code, document = issue.check()
    assert code == 1
    row = _row(document)
    assert row["status"] == "fail", row
    assert GREEN in row["detail"], row
    assert "attempts is required on an in-scope outer-loop record" in row["detail"], row


def test_trc_g2_restored(tmp_path):
    """The same issue with the `attempts` tdd-green wrote passes the `attempts` check."""
    _, issue = _issue(tmp_path)
    _outer_red_and_green(issue)
    code, document = issue.check()
    row = _row(document)
    assert row["status"] == "pass", row
    assert GREEN in row["detail"], row


# --- `TRC-G3` ------------------------------------------------------------------------------

def test_trc_g3(tmp_path):
    """A rerun is a failure."""
    project, issue = _issue(tmp_path)
    _must(issue, "tdd-red", "outer", FAIL)
    # The first outer-loop run of the green fails, and a rerun passes with no source
    # change: the same command, and a test that passes on its second run.
    flaky = ("sh", "-c", "if [ -f .first ]; then echo 'test_place_order PASSED'; "
             "else touch .first; echo 'test_place_order FAILED'; exit 1; fi")
    (project.root / ".gitignore").write_text(".first\n", encoding="utf-8")
    support.git(project.root, "add", ".gitignore")
    support.git(project.root, "commit", "-q", "-m", "ignore the flaky marker")
    code, out, err = _run(issue, "tdd-green", "outer", flaky)
    assert code != 0, out + err
    _must(issue, "tdd-green", "outer", flaky)
    record = _record(issue, GREEN)
    assert (record["attempts"], record["rerun_without_change"]) == (2, True), record
    assert record["test"] == support.SPEC_TEST, record
    code, document = issue.check()
    assert code == 1
    row = _row(document, RERUN)
    assert row["status"] == "fail", row
    assert f"test '{support.SPEC_TEST}' ran 2 time(s)" in row["detail"], row
    assert "not in governance/quarantine.yml" in row["detail"], row
    assert _row(document)["status"] == "pass"
    body = issue.manifest()
    body["current_phase"] = "ship"
    issue.write_manifest(body)
    code, at_ship = issue.check()
    assert code == 1
    assert _row(at_ship, RERUN) == row


# --- `TRC-G4` ------------------------------------------------------------------------------

def _quarantine(project, test):
    """Give the project its own governance, with `test` in `quarantine.yml`."""
    gov = project.root / "governance"
    gov.mkdir()
    for name in ("routing-policy.yml", "guardrails.yml"):
        shutil.copy(support.ROOT / "governance" / name, gov / name)
    (gov / "quarantine.yml").write_text(yaml.safe_dump({
        "version": "1.0.0",
        "quarantined": [{"test": test, "tracking_task": "fix-flaky-orders",
                         "reason": "Race in the driver set-up", "added": "2026-10-29"}],
    }), encoding="utf-8")


def test_trc_g4(tmp_path):
    """A quarantined rerun passes as it does today."""
    project, issue = _issue(tmp_path)
    _outer_red_and_green(issue)
    _must(issue, "tdd-green", "outer", PASS)
    record = _record(issue, GREEN)
    assert (record["attempts"], record["rerun_without_change"]) == (2, True), record
    _quarantine(project, support.SPEC_TEST)
    code, document = issue.check()
    row = _row(document, RERUN)
    assert row["status"] == "pass", row
    assert row["detail"] == "no trusted-rerun violations (quarantine notes: 1)", row


def test_trc_g4_first_declared_test(tmp_path):
    """A scenario that declares more than one test: the green names the first."""
    _, issue = _issue(tmp_path)
    body = issue.manifest()
    second = support.SPEC + "::test_cancel_order"
    for scenario in body["scenarios"]:
        scenario["tests"] = [support.SPEC_TEST, second]
    issue.write_manifest(body)
    _outer_red_and_green(issue)
    assert _record(issue, GREEN)["test"] == support.SPEC_TEST
    _must(issue, "tdd-green", "inner", PASS)
    assert "test" not in _record(issue, "evidence/green-TRC-1.json")


# --- `TRC-G5` ------------------------------------------------------------------------------

@pytest.mark.parametrize("issue_is", [
    "an in-scope issue whose record has loop inner",
    "an issue whose acceptance is of kind validation",
    "an in-scope issue on a project with the strategy off",
])
def test_trc_g5(tmp_path, issue_is):
    """The `no-attempts` exemption stays where the strategy does not reach."""
    if issue_is.startswith("an issue whose acceptance"):
        _, issue = _issue(tmp_path, expected="validation")
        issue.acceptance_start("validation")
        _must(issue, "tdd-green", "outer", PASS, scenario=None)
        rel = "evidence/green.outer.json"
    elif issue_is.endswith("strategy off"):
        _, issue = _issue(tmp_path, setting={"state": "off", "reason": "a CLI with no client"})
        _outer_red_and_green(issue)
        rel = GREEN
    else:
        _, issue = _issue(tmp_path)
        _outer_red_and_green(issue)
        _must(issue, "tdd-red", "inner", FAIL)
        _must(issue, "tdd-green", "inner", PASS)
        rel = "evidence/green-TRC-1.json"
    _rewrite(issue, rel, attempts=...)
    assert "attempts" not in _record(issue, rel)
    code, document = issue.check()
    assert _row(document, RERUN)["status"] == "pass", _row(document, RERUN)
    row = _row(document)
    if issue_is.endswith("loop inner"):
        assert row["status"] == "pass", row
        assert rel not in row["detail"], row
    else:
        assert row["status"] == "nothing-to-check", row
        assert "not required: the strategy does not apply" in row["detail"], row


# --- `TRC-G6` ------------------------------------------------------------------------------

@pytest.mark.parametrize("value", [0, -1, "two", True, 1.0])
def test_trc_g6(tmp_path, value):
    """An `attempts` value that is not a positive whole number fails."""
    _, issue = _issue(tmp_path)
    _outer_red_and_green(issue)
    _rewrite(issue, GREEN, attempts=value)
    code, document = issue.check()
    assert code == 1
    row = _row(document)
    assert row["status"] == "fail", row
    assert GREEN in row["detail"], row
    assert f"attempts {json.dumps(value)}" in row["detail"], row
