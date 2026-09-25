"""The multiagent check and `subtask next` compare the record with the map.

A subtask the distribution map names but the manifest never recorded - a
wave never dispatched - was invisible: the check passed a record of one
subtask out of three. Both now read the subtask ids from the map, found
through the artifact registry, and name any the manifest does not record.
With no map found, both behave as before.

Scenario ids: CRM-1 to CRM-3, in the delivery approach of issue
`check-does-not-compare-record-with-map`.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
import compass_pkg  # noqa: E402,F401 - puts the bundled PyYAML first
from compass_pkg.multiagent_check import _check_multiagent_run_recorded  # noqa: E402

MAP = ("# Distribution Map\n\n"
       "| Unit pair | Verdict |\n|---|---|\n| U1 and U2 | subtask-2 waits for subtask-1 |\n\n"
       "| Subtask | Owns work unit(s) | Owns scenario ids | Branch name | Wave |\n"
       "|---|---|---|---|---|\n"
       "| subtask-1 | U1 | S1 | compass/demo/subtask-1 | 1 |\n"
       "| subtask-2 | U2 | S2 | compass/demo/subtask-2 | 2 |\n"
       "| subtask-3 | U3 | S3 | compass/demo/subtask-3 | 2 |\n"
       "| verify | - | - | not a worktree | - |\n")
DONE = {"status": "done", "review_rounds": [{"round": 1, "verdict": "pass"}]}


def _task(tmp_path, recorded, *, with_map=True):
    root = tmp_path / "proj"
    task_dir = root / ".compass" / "work" / "demo"
    task_dir.mkdir(parents=True)
    (root / ".compass" / "config.yml").write_text("version: 1.0.0\nmode: enforced\n")
    if with_map:
        (task_dir / "distribution-map.md").write_text(MAP)
    task = {"schema_version": "2.0", "issue": "demo", "created": "2026-09-26",
            "status": "landed", "stages": {"breakdown": "multiagent"},
            "gates": [{"id": "verify.correctness", "status": "pass"}],
            "subtasks": [{"id": sid, **DONE} for sid in recorded]}
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(task, sort_keys=False))
    return root, task_dir, task


def test_crm_1_a_mapped_subtask_the_record_lacks_fails_the_check(tmp_path):
    _, task_dir, task = _task(tmp_path, ["subtask-1"])
    ok, why = _check_multiagent_run_recorded(task, str(task_dir))
    assert ok is False, why
    assert "subtask-2" in why and "subtask-3" in why, why
    assert "verify" not in why, why


def test_crm_1_a_record_of_every_mapped_subtask_passes(tmp_path):
    _, task_dir, task = _task(tmp_path, ["subtask-1", "subtask-2", "subtask-3"])
    ok, why = _check_multiagent_run_recorded(task, str(task_dir))
    assert ok is True, why


def test_crm_2_subtask_next_lists_a_mapped_subtask_not_yet_dispatched(tmp_path):
    root, _, _ = _task(tmp_path, ["subtask-1"])
    result = subprocess.run(
        [sys.executable, str(ROOT / "cli" / "compass"), "issue", "subtask", "next",
         "--issue", "demo"], cwd=root, capture_output=True, text=True,
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(root)})
    assert result.returncode == 0, result.stderr
    assert "subtask-2" in result.stdout and "not yet dispatched" in result.stdout, result.stdout


def test_crm_3_with_no_map_the_check_judges_the_record_as_before(tmp_path):
    _, task_dir, task = _task(tmp_path, ["subtask-1"], with_map=False)
    ok, why = _check_multiagent_run_recorded(task, str(task_dir))
    assert ok is True, why
