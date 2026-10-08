"""`compass check` honours a check's `severity` and `on_skipped` from the generation.

An issue with a generation is judged by the checks it stored. A check that
declares `severity: advisory` reports a failure without failing the run. A
check that declares `on_skipped` decides what "nothing to check" means for it.
These tests commit a generation of a scratch project with the real command and
run the real `compass check` against it.

Scenario ids: `CS-1` to `CS-11` (issue `check-severity-from-generation`). Each
test name starts with its scenario id.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

from test_generation_store import SLUG, _project, _run, _write_manifest  # noqa: E402

CHECK_ID = "arch-rule"
NOTHING = {"impl": "claim-traces-to-scenario", "params": None}


def _compass_yml(severity="blocking", on_skipped="fail", impl="scenarios-have-tests",
                 params=None, blocking_when=None):
    check = {"statement": "A project rule.", "kind": "deterministic", "impl": impl,
             "severity": severity, "on_skipped": on_skipped}
    if params is not None:
        check["params"] = params
    if blocking_when is not None:
        check["blocking_when"] = blocking_when
    return {"schema": 1, "allow_project_commands": True,
            "checks": {CHECK_ID: check},
            "gates": {"P1": {"kind": "guardrail", "name": "Project rule",
                             "statement": "A project rule.", "stage": "verify",
                             "applies_to": {"ships": True}, "checks": [CHECK_ID]}}}


def _committed(tmp_path, **kwargs):
    """A project whose generation holds one added check. By default the check
    runs `scenarios-have-tests`, which fails on the scratch issue (it has no
    scenarios). It is not `command-passes`, because the shipped gate that runs
    project commands would run the same command a second time."""
    root, task_dir = _project(tmp_path, compass_yml=_compass_yml(**kwargs))
    code, out, err = _run(root, "approach", "evaluate", "--issue", SLUG, "--write")
    assert code == 0, out + err
    return root, task_dir


def _report(root, *extra):
    code, out, err = _run(root, "check", "--issue", SLUG, "--json", *extra)
    return code, json.loads(out), err


def _row(report):
    rows = [c for c in report["checks"] if c["name"] == CHECK_ID]
    assert len(rows) == 1, report["checks"]
    return rows[0]


def _reference(tmp_path_factory, **kwargs):
    """The report for the same project with the added check made harmless, so
    a test can count what the check itself changes."""
    root, _ = _committed(tmp_path_factory.mktemp("reference"), **kwargs)
    return _report(root)[1]


@pytest.fixture
def baseline(tmp_path_factory):
    """Failures when the project adds nothing."""
    root, _ = _project(tmp_path_factory.mktemp("baseline"), compass_yml={"schema": 1})
    code, out, err = _run(root, "approach", "evaluate", "--issue", SLUG, "--write")
    assert code == 0, out + err
    return _report(root)[1]["failed"]


@pytest.fixture
def idle(tmp_path_factory):
    """The report when the added check has nothing to check and is not-applicable."""
    return _reference(tmp_path_factory, on_skipped="not-applicable", **NOTHING)


def _dir(tmp_path, name):
    path = tmp_path / name
    path.mkdir()
    return path


# --- CS-1: an advisory check that fails ------------------------------------------------------

def test_cs_1_an_advisory_failure_does_not_fail_the_run_and_is_shown_as_advisory(tmp_path, baseline):
    root, _ = _committed(tmp_path, severity="advisory")
    code, report, err = _report(root)
    row = _row(report)
    assert row["status"] == "advisory", row
    assert report["failed"] == baseline, report
    assert report["advisory"] == 1, report
    out = _run(root, "check", "--issue", SLUG, "--verbose")[1]
    assert "ADVISORY " + CHECK_ID in out and "FAIL " + CHECK_ID not in out, out
    summary = _run(root, "check", "--issue", SLUG)[1]
    assert CHECK_ID in summary and "advisory" in summary, summary
    assert "FAIL " + CHECK_ID not in summary, summary


# --- CS-2: a blocking check that fails -------------------------------------------------------

def test_cs_2_a_blocking_failure_fails_the_run(tmp_path, baseline):
    root, _ = _committed(tmp_path, severity="blocking")
    code, report, err = _report(root)
    assert _row(report)["status"] == "fail"
    assert report["failed"] == baseline + 1
    assert report["advisory"] == 0
    assert code != 0


# --- CS-3, CS-4, CS-5: what nothing to check means -------------------------------------------

def test_cs_3_on_skipped_fail_makes_nothing_to_check_a_failure_that_says_why(tmp_path, idle):
    root, _ = _committed(tmp_path, on_skipped="fail", **NOTHING)
    code, report, err = _report(root)
    row = _row(report)
    assert row["status"] == "fail", row
    assert "on_skipped" in row["detail"] and "nothing to check" in row["detail"], row
    assert report["failed"] == idle["failed"] + 1
    assert report["nothing_to_check"] == idle["nothing_to_check"] - 1
    assert code != 0


def test_cs_3_an_advisory_check_with_on_skipped_fail_is_an_advisory_failure(tmp_path, idle):
    root, _ = _committed(tmp_path, severity="advisory", on_skipped="fail", **NOTHING)
    _, report, _ = _report(root)
    row = _row(report)
    assert row["status"] == "advisory" and "nothing to check" in row["detail"], row
    assert report["failed"] == idle["failed"]


def test_cs_4_on_skipped_pass_counts_nothing_to_check_as_a_pass(tmp_path, idle):
    root, _ = _committed(tmp_path, on_skipped="pass", **NOTHING)
    _, report, _ = _report(root)
    assert _row(report)["status"] == "pass"
    assert report["failed"] == idle["failed"]
    assert report["nothing_to_check"] == idle["nothing_to_check"] - 1


def test_cs_5_on_skipped_not_applicable_is_counted_apart_as_before(idle):
    assert _row(idle)["status"] == "nothing-to-check"


# --- CS-6: severity and blocking_when --------------------------------------------------------

def test_cs_6_a_blocking_check_below_its_blocking_when_is_advisory(tmp_path, baseline):
    root, _ = _committed(tmp_path, severity="blocking",
                         blocking_when={"risk": ["critical"]})
    _, report, _ = _report(root)
    row = _row(report)
    assert row["status"] == "advisory" and "It blocks when" in row["detail"], row
    assert report["failed"] == baseline


def test_cs_6_a_blocking_check_at_its_blocking_when_fails(tmp_path, baseline):
    root, _ = _committed(tmp_path, severity="blocking",
                         blocking_when={"risk": ["contained"]})
    _, report, _ = _report(root)
    assert _row(report)["status"] == "fail"
    assert report["failed"] == baseline + 1


def test_cs_6_an_advisory_check_stays_advisory_where_its_blocking_when_matches(tmp_path, baseline):
    root, _ = _committed(tmp_path, severity="advisory",
                         blocking_when={"risk": ["contained"]})
    _, report, _ = _report(root)
    assert _row(report)["status"] == "advisory"
    assert report["failed"] == baseline


# --- CS-7: the shipped preset keeps its verdicts ---------------------------------------------

def test_cs_7_the_shipped_checks_keep_the_verdicts_the_governance_files_give(tmp_path):
    """The same evaluated issue is checked twice: against its generation, then
    with the `generation:` key removed so the governance files are read."""
    root, task_dir = _project(_dir(tmp_path, "g"))
    code, out, err = _run(root, "approach", "evaluate", "--issue", SLUG, "--write")
    assert code == 0, out + err
    _, new, _ = _report(root)
    manifest = yaml.safe_load((task_dir / "manifest.yml").read_text(encoding="utf-8"))
    del manifest["generation"]
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(manifest, sort_keys=False),
                                           encoding="utf-8")
    _, old, _ = _report(root)
    assert "generation" not in old and new["generation"] == 1
    verdicts = lambda r: [(c["guardrail"], c["name"], c["status"])  # noqa: E731
                          for c in r["checks"]]
    assert verdicts(new) == verdicts(old)
    assert (new["failed"], new["nothing_to_check"]) == (old["failed"], old["nothing_to_check"])
    assert new["advisory"] == old["advisory"] == 0


def test_cs_7_no_shipped_check_that_can_return_nothing_to_check_declares_fail():
    """A shipped `on_skipped: fail` would turn today's clear result into a failure."""
    shipped = yaml.safe_load(
        (ROOT / "governance" / "presets" / "default" / "checks.yml").read_text(encoding="utf-8"))
    declining = {name for name, body in shipped["checks"].items()
                 if body.get("on_skipped") == "not-applicable"}
    assert {"scenarios-are-executable", "claim-traces-to-scenario", "command-passes",
            "borrowed-documents-answered", "evidence-matches-tree",
            "evidence-identity-matches", "dashboard-current", "landed-by-resolves",
            "multiagent-run-recorded"} <= declining


# --- CS-8: the JSON shape --------------------------------------------------------------------

def test_cs_8_the_json_document_has_the_documented_keys(tmp_path):
    root, _ = _committed(tmp_path, severity="advisory")
    _, report, _ = _report(root)
    assert set(report) == {"issue", "approach", "ran", "failed", "nothing_to_check",
                           "advisory", "notices", "generation", "parent_version", "checks"}
    assert set(_row(report)) == {"guardrail", "name", "status", "detail"}
    assert {c["status"] for c in report["checks"]} <= {
        "pass", "fail", "advisory", "nothing-to-check"}
    doc = (ROOT / "docs" / "generation-store.md").read_text(encoding="utf-8")
    for word in ("advisory", "nothing_to_check", "on_skipped"):
        assert word in doc


def test_cs_8_the_summary_line_counts_an_advisory_failure_apart():
    from compass_pkg.check_cmd import summarise_counts
    assert summarise_counts(5, 0, 0) == "compass check: PASS - all 5 check(s) passed."
    line = summarise_counts(5, 0, 0, 1)
    assert line.startswith("compass check: PASS") and "1 failed as advisory" in line, line
    line = summarise_counts(5, 2, 0, 1)
    assert line.startswith("compass check: FAIL - 2 of 5") and "1 failed as advisory" in line, line


def test_cs_8_results_file_records_an_advisory_verdict(tmp_path):
    root, task_dir = _committed(tmp_path, severity="advisory")
    _report(root)
    results = yaml.safe_load((task_dir / "generations" / "1" / "results.yml")
                             .read_text(encoding="utf-8"))
    assert results["runs"][CHECK_ID]["verdict"] == "advisory"


# --- CS-9: an issue with no generation -------------------------------------------------------

def test_cs_9_an_issue_with_no_generation_reads_the_governance_files_as_before(tmp_path):
    root, _ = _project(tmp_path)
    _, report, _ = _report(root)
    assert report["advisory"] == 0
    assert "generation" not in report
    assert all(c["status"] != "advisory" for c in report["checks"])


# --- CS-10: a landed_by relaxation is not a skip ---------------------------------------------

def test_cs_10_the_landed_by_relaxation_does_not_apply_on_skipped(tmp_path):
    """`suite-passed` declares `on_skipped: fail`. A record claim that `landed_by`
    moved to another issue is a relaxation, not a skip, so it stays clear."""
    root, task_dir = _project(tmp_path)
    other = root / ".compass" / "work" / "other"
    other.mkdir()
    (other / "manifest.yml").write_text(yaml.safe_dump({
        "schema_version": "2.0", "issue": "other", "status": "landed",
        "scenarios": [{"id": "O-1", "title": "t", "intent": "INT-1"}],
        "delivered": [SLUG]}, sort_keys=False), encoding="utf-8")
    code, out, err = _run(root, "approach", "evaluate", "--issue", SLUG, "--write")
    assert code == 0, out + err
    _write_manifest(task_dir, status="landed", landed_by="other")
    _, report, _ = _report(root)
    rows = {c["name"]: c["status"] for c in report["checks"]}
    assert rows["suite-passed"] == "nothing-to-check", rows


# --- CS-11: a spike's guardrail check ----------------------------------------------------------

def _spike_report(tmp_path, severity):
    compass_yml = _compass_yml(severity=severity)
    compass_yml["gates"]["P1"]["applies_to"] = {"ships": False}
    root, task_dir = _project(tmp_path, compass_yml=compass_yml)
    code, out, err = _run(root, "approach", "evaluate", "--issue", SLUG, "--write")
    assert code == 0, out + err
    _write_manifest(task_dir, delivery_approach="spike")
    return _report(root)[1]


def test_cs_11_an_advisory_check_failing_on_a_spike_is_advisory(tmp_path):
    report = _spike_report(tmp_path, "advisory")
    assert _row(report)["status"] == "advisory", report["checks"]
    assert report["advisory"] == 1


def test_cs_11_a_blocking_check_failing_on_a_spike_fails(tmp_path):
    report = _spike_report(tmp_path, "blocking")
    assert _row(report)["status"] == "fail", report["checks"]
    assert report["advisory"] == 0
