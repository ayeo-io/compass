"""A distribution map that declares one work unit records the breakdown as
one subtask run by the main session, and `multiagent-run-recorded` accepts
that record.

The regular and full routes give breakdown the weight `multiagent`. A change
that is one unit of work could land only by a waiver or by a hand-made
record of a dispatch that never happened. The map's `units: 1` line, read
when the map is registered, records one subtask marked `orchestration:
single-unit`, its brief the map. Registering the verification report fills
in its report. Two or more units change nothing, and a multiagent map with
no `units:` line is refused at plan, so the gap is found there and not at
verify.

Scenario ids: OUB-1 to OUB-18, issue one-unit-breakdown
(ayeo-io/compass-delivery-record#55, "Record a one-unit breakdown without a
subtask record or a waiver"). ADR-071 records the decision.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
import compass_pkg  # noqa: E402,F401 - puts the bundled PyYAML first
from compass_pkg.check_results import NOTHING_TO_CHECK  # noqa: E402
from compass_pkg.multiagent_check import (  # noqa: E402
    _check_multiagent_run_recorded, declared_units)

DOCS = "docs/compass/2026-10-10-demo"
MAP_ONE = ("# Distribution Map - demo\n\nunits: 1\n\n"
           "| Unit | Code surface |\n|---|---|\n| U1 | app/tracing.py |\n")
MAP_TWO = ("# Distribution Map - demo\n\nunits: [U1, U2]\n\n"
           "| Subtask | Owns work unit(s) |\n|---|---|\n"
           "| subtask-1 | U1 |\n| subtask-2 | U2 |\n")
MAP_NO_LINE = ("# Distribution Map - demo\n\n"
               "| Unit | Code surface |\n|---|---|\n| U1 | app/tracing.py |\n")
MAP_ONE_TWO_SUBTASKS = ("# Distribution Map - demo\n\nunits: 1\n\n"
                        "| Subtask | Owns work unit(s) |\n|---|---|\n"
                        "| subtask-1 | U1 |\n| subtask-2 | U1 |\n")
GATES = ("verify.correctness", "verify.regression")


def _git(root, *args):
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"})


def _project(tmp_path, map_text=MAP_ONE, breakdown="multiagent"):
    root = tmp_path / "proj"
    task_dir = root / ".compass" / "work" / "demo"
    task_dir.mkdir(parents=True)
    (root / ".compass" / "config.yml").write_text("version: 1.0.0\nmode: enforced\n")
    (root / DOCS).mkdir(parents=True)
    (root / DOCS / "distribution-map.md").write_text(map_text)
    (root / DOCS / "verification-report.md").write_text("# Verification report\n")
    (root / DOCS / "technical-design.md").write_text("# Technical design\n")
    task = {"schema_version": "3.0", "issue": "demo", "created": "2026-10-10",
            "delivery_approach": "regular",
            "stages": {"plan": "thorough", "breakdown": breakdown, "verify": "thorough"},
            "gates": [{"id": g, "status": "pending"} for g in GATES],
            "artifacts": [{"id": "ART-TECHNICAL_DESIGN", "kind": "technical-design",
                           "status": "draft", "path": f"{DOCS}/technical-design.md"},
                          {"id": "ART-DISTRIBUTION_MAP", "kind": "distribution-map",
                           "status": "draft"},
                          {"id": "ART-VERIFICATION_REPORT", "kind": "verification-report",
                           "status": "draft"}]}
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(task, sort_keys=False))
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "start")
    return root, task_dir


def _cli(root, *args):
    return subprocess.run(
        [sys.executable, str(ROOT / "cli" / "compass"), *args],
        cwd=root, capture_output=True, text=True,
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(root)})


def _register(root, kind, expect=0):
    result = _cli(root, "issue", "artifact", "set", kind, "--status", "draft",
                  "--path", f"{DOCS}/{kind}.md", "--issue", "demo")
    assert result.returncode == expect, result.stdout + result.stderr
    return result.stdout + result.stderr


def _manifest(task_dir):
    return yaml.safe_load((task_dir / "manifest.yml").read_text())


def _write(task_dir, task):
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(task, sort_keys=False))


def _landed(task):
    task["gates"] = [{"id": g, "status": "pass"} for g in GATES]
    return task


def _check_verdict(root):
    """`multiagent-run-recorded` as `compass check --json` reports it."""
    result = _cli(root, "check", "--issue", "demo", "--json")
    body = json.loads(result.stdout)
    found = [c for c in body["checks"] if c["name"] == "multiagent-run-recorded"]
    assert len(found) == 1, result.stdout + result.stderr
    return found[0]


def test_oub_1_registering_a_one_unit_map_records_one_single_unit_subtask(tmp_path):
    root, task_dir = _project(tmp_path)
    out = _register(root, "distribution-map")
    subtasks = _manifest(task_dir)["subtasks"]
    assert len(subtasks) == 1, subtasks
    entry = subtasks[0]
    assert entry["orchestration"] == "single-unit", entry
    assert entry["model"] == "main-session", entry
    assert entry["brief"] == f"{DOCS}/distribution-map.md", entry
    assert len(entry["base_sha"]) == 40, entry
    assert "one unit" in out and "go on to implement" in out, out
    # The record never claims a separate run: no worktree, no builder dispatched.
    assert "worktree" not in entry and "dispatched from" not in out, (entry, out)


def test_oub_2_registering_the_verification_report_completes_the_record(tmp_path):
    root, task_dir = _project(tmp_path)
    _register(root, "distribution-map")
    out = _register(root, "verification-report")
    entry = _manifest(task_dir)["subtasks"][0]
    assert entry["report"] == f"{DOCS}/verification-report.md", entry
    assert entry["status"] == "done", entry
    assert "one-unit record" in out, out


def test_oub_3_compass_check_passes_a_one_unit_issue_with_no_subtask_call(tmp_path):
    root, task_dir = _project(tmp_path)
    _register(root, "distribution-map")
    _register(root, "verification-report")
    assert _check_verdict(root)["status"] == "nothing-to-check"
    _write(task_dir, _landed(_manifest(task_dir)))
    verdict = _check_verdict(root)
    assert verdict["status"] == "pass", verdict
    assert "one unit" in verdict["detail"], verdict


def test_oub_4_the_check_fails_a_single_unit_record_when_the_map_changed(tmp_path):
    root, task_dir = _project(tmp_path)
    _register(root, "distribution-map")
    _register(root, "verification-report")
    (root / DOCS / "distribution-map.md").write_text(MAP_TWO)
    ok, why = _check_multiagent_run_recorded(_landed(_manifest(task_dir)), str(task_dir))
    assert ok is False, why
    assert "units: 1" in why, why


def test_oub_5_the_check_fails_a_single_unit_record_with_no_verification_report(tmp_path):
    root, task_dir = _project(tmp_path)
    _register(root, "distribution-map")
    (root / DOCS / "verification-report.md").unlink()
    ok, why = _check_multiagent_run_recorded(_landed(_manifest(task_dir)), str(task_dir))
    assert ok is False, why
    assert "verification report" in why, why


def test_oub_6_the_check_fails_a_single_unit_record_when_a_gate_has_not_passed(tmp_path):
    root, task_dir = _project(tmp_path)
    _register(root, "distribution-map")
    _register(root, "verification-report")
    task = _manifest(task_dir)
    ok, why = _check_multiagent_run_recorded(task, str(task_dir))
    assert ok == NOTHING_TO_CHECK, (ok, why)
    # A completed issue is judged whatever its gates say; a single-unit record
    # still needs every gate to have passed, because the gates stand in for the
    # review a separate builder's package gets.
    task = _landed(task)
    task["gates"][0]["status"] = "fail"
    task["status"] = "done"
    task["close_reason"] = "completed"
    ok, why = _check_multiagent_run_recorded(task, str(task_dir))
    assert ok is False, why
    assert "verify.correctness" in why, why


def test_oub_7_two_units_record_nothing_and_take_back_an_earlier_one_unit_record(tmp_path):
    root, task_dir = _project(tmp_path, map_text=MAP_TWO)
    _register(root, "distribution-map")
    assert "subtasks" not in _manifest(task_dir)

    root, task_dir = _project(tmp_path / "again")
    _register(root, "distribution-map")
    (root / DOCS / "distribution-map.md").write_text(MAP_TWO)
    out = _register(root, "distribution-map")
    assert _manifest(task_dir)["subtasks"] == [], _manifest(task_dir)
    assert "removed" in out, out


def test_oub_8_a_multiagent_map_with_no_units_line_is_refused(tmp_path):
    root, task_dir = _project(tmp_path, map_text=MAP_NO_LINE)
    before = (task_dir / "manifest.yml").read_bytes()
    out = _register(root, "distribution-map", expect=2)
    assert "units:" in out and "units: 1" in out and "units: [U1, U2]" in out, out
    assert (task_dir / "manifest.yml").read_bytes() == before


def test_oub_9_a_breakdown_that_is_not_multiagent_is_unchanged(tmp_path):
    for breakdown in ("solo", "skipped"):
        for text in (MAP_ONE, MAP_NO_LINE):
            root, task_dir = _project(tmp_path / breakdown / str(len(text)),
                                      map_text=text, breakdown=breakdown)
            _register(root, "distribution-map")
            assert "subtasks" not in _manifest(task_dir), (breakdown, text)


def test_oub_10_the_units_line_reads_a_number_or_a_list_and_nothing_else(tmp_path):
    cases = {"units: 1\n": 1, "`units: 3`\n": 3, "units: [U1, U2]\n": 2, "- units: 1\n": 1,
             "units: {{N}}\n": None, "No units line here.\n": None,
             "The units: 1 here is prose.\n": None}
    for text, expected in cases.items():
        path = tmp_path / "map.md"
        path.write_text(text)
        assert declared_units(path) == expected, (text, declared_units(path))


def test_oub_11_one_unit_with_two_mapped_subtasks_is_refused(tmp_path):
    root, task_dir = _project(tmp_path, map_text=MAP_ONE_TWO_SUBTASKS)
    before = (task_dir / "manifest.yml").read_bytes()
    out = _register(root, "distribution-map", expect=2)
    assert "units: 1" in out and "subtask-1" in out and "subtask-2" in out, out
    assert (task_dir / "manifest.yml").read_bytes() == before


def test_oub_12_recording_one_unit_is_the_record_of_the_breakdown_stage(tmp_path):
    root, task_dir = _project(tmp_path)
    _register(root, "distribution-map")
    kinds = {a["kind"]: a for a in _manifest(task_dir)["artifacts"]}
    # The map is the breakdown stage's own document, so registering it is the
    # stage's record: plan's documents move on, as `compass issue subtask add`
    # moves them (ADR-050), and the map itself waits for implement.
    assert kinds["technical-design"]["status"] == "approved", kinds
    assert kinds["technical-design"]["approved_by"] == "compass issue artifact set", kinds
    assert kinds["distribution-map"]["status"] == "draft", kinds
    assert _manifest(task_dir)["subtasks"][0]["orchestration"] == "single-unit"


def test_oub_13_a_one_unit_map_leaves_hand_recorded_subtasks_alone(tmp_path):
    root, task_dir = _project(tmp_path)
    task = _manifest(task_dir)
    task["subtasks"] = [{"id": "subtask-1", "brief": "b.md", "status": "done",
                         "review_rounds": [{"verdict": "pass"}]}]
    _write(task_dir, task)
    out = _register(root, "distribution-map")
    assert _manifest(task_dir)["subtasks"] == task["subtasks"]
    assert "left as it is" in out, out


def test_oub_14_a_critical_single_unit_record_needs_a_passing_review_round(tmp_path):
    root, task_dir = _project(tmp_path)
    task = _manifest(task_dir)
    task["assessment"] = {"risk": "critical"}
    _write(task_dir, task)
    _register(root, "distribution-map")
    _register(root, "verification-report")
    _write(task_dir, _landed(_manifest(task_dir)))
    ok, why = _check_multiagent_run_recorded(_manifest(task_dir), str(task_dir))
    assert ok is False, why
    assert "review round" in why and "--round pass" in why, why
    sid = _manifest(task_dir)["subtasks"][0]["id"]
    result = _cli(root, "issue", "subtask", "set", sid, "--round", "pass", "--issue", "demo")
    assert result.returncode == 0, result.stdout + result.stderr
    ok, why = _check_multiagent_run_recorded(_manifest(task_dir), str(task_dir))
    assert ok is True, why


def test_oub_15_a_single_unit_record_beside_another_subtask_fails(tmp_path):
    root, task_dir = _project(tmp_path)
    _register(root, "distribution-map")
    _register(root, "verification-report")
    task = _landed(_manifest(task_dir))
    task["subtasks"].append({"id": "subtask-2", "brief": "b.md", "status": "done",
                             "review_rounds": [{"verdict": "pass"}]})
    ok, why = _check_multiagent_run_recorded(task, str(task_dir))
    assert ok is False, why
    assert "subtask-2" in why and "one unit" in why, why


def test_oub_16_a_map_found_by_its_flat_filename_is_refused_too(tmp_path):
    root, task_dir = _project(tmp_path)
    (task_dir / "distribution-map.md").write_text(MAP_ONE_TWO_SUBTASKS)
    (root / DOCS / "distribution-map.md").unlink()
    before = (task_dir / "manifest.yml").read_bytes()
    result = _cli(root, "issue", "artifact", "set", "distribution-map", "--status", "draft",
                  "--issue", "demo")
    assert result.returncode == 2, result.stdout + result.stderr
    assert "subtask-2" in result.stdout + result.stderr
    assert (task_dir / "manifest.yml").read_bytes() == before


def test_oub_17_a_units_line_below_one_is_refused(tmp_path):
    for text in ("units: 0\n", "units: []\n"):
        root, task_dir = _project(tmp_path / str(len(text)), map_text="# Map\n\n" + text)
        out = _register(root, "distribution-map", expect=2)
        assert "units: 1" in out, out


def test_oub_18_diagnose_names_a_single_unit_record_as_run_by_this_session(tmp_path):
    root, task_dir = _project(tmp_path)
    _register(root, "distribution-map")
    result = _cli(root, "issue", "diagnose", "--issue", "demo")
    out = result.stdout + result.stderr
    assert result.returncode == 0, out
    assert "subtask-1 recorded as one unit, run by this session" in out, out
    assert "subtask-1 dispatched" not in out, out
