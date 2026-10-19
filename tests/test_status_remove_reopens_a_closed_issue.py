"""`issue status remove` reopens a closed issue (release-7-0-0-prep, group A).

v5.6.0 `issue set-status active` reopened a closed issue. That spelling ended
at 7.0.0, and `issue status remove` does the same work.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"

# The two old status words are still read, so a close stored in them reopens too.
CLOSED = [
    pytest.param({"status": "landed"}, id="old-landed"),
    pytest.param({"status": "abandoned"}, id="old-abandoned"),
    pytest.param({"status": "done", "close_reason": "completed"}, id="completed"),
    pytest.param({"status": "done", "close_reason": "not-planned"}, id="not-planned"),
    pytest.param({"status": "done", "close_reason": "duplicate", "duplicate_of": "other"},
                 id="duplicate"),
]


def _issue(tmp_path, **fields):
    task = tmp_path / ".compass" / "work" / "the-issue"
    task.mkdir(parents=True)
    (tmp_path / ".compass" / "current-task").write_text("the-issue\n")
    (tmp_path / ".compass" / "config.yml").write_text("version: 1.0.0\n")
    data = {"schema_version": "2.0", "issue": "the-issue", "created": "2026-10-02",
            "delivery_approach": "full", "stages": {"refine": "full"},
            "land_timestamp": "2026-10-08T09:00:00Z"}
    data.update(fields)
    (task / "manifest.yml").write_text(yaml.safe_dump(data, sort_keys=False))
    (task / "delivery-approach.md").write_text("# Delivery approach\n")
    return task


@pytest.mark.parametrize("closed", CLOSED)
def test_status_remove_reopens_a_closed_issue(tmp_path, closed):
    """Scenario id: `TRC-008` in release-7-0-0-prep/acceptance-criteria.md"""
    task = _issue(tmp_path, **closed)
    env = {"PATH": os.environ["PATH"], "HOME": str(tmp_path)}
    done = subprocess.run(
        [sys.executable, str(CLI), "issue", "status", "remove", "--issue", "the-issue"],
        cwd=tmp_path, capture_output=True, text=True, env=env)
    assert done.returncode == 0, done.stderr
    saved = yaml.safe_load((task / "manifest.yml").read_text())
    assert not {"status", "close_reason", "duplicate_of"} & set(saved), saved
    assert saved["status_reason"], "the reopening leaves a reason"
