"""The comparison report shows how often each condition was stopped.

Compass counts each hook block and each failing `compass check` in
`.compass/interruptions.log`. The eval harness now reads that log at the end
of a session and records the counts as `interruptions`; `evals/compare.py`
shows them per cell and in the summary as "Hook blocks" and "Check
failures". A condition with no Compass project, or a record from before
this field, shows "not recorded", never zero (B21).

Scenario id: SC-1 (issue `stops-and-cost-per-condition`).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
import evals.compare as compare  # noqa: E402
import evals.harness as harness  # noqa: E402
from test_eval_compare import make_record  # noqa: E402


def test_sc_1_the_harness_counts_the_sessions_interruptions(tmp_path):
    (tmp_path / ".compass").mkdir()
    (tmp_path / ".compass" / "interruptions.log").write_text(
        "2026-10-03T10:00:00Z\tfix\thook_blocks\n"
        "2026-10-03T10:01:00Z\tfix\thook_blocks\n"
        "2026-10-03T10:02:00Z\tfix\tcheck_failures\n"
        "not a line\n")
    assert harness._interruptions(tmp_path) == {
        "hook_blocks": 2, "check_failures": 1}


def test_sc_1_a_compass_project_with_no_log_counts_zero(tmp_path):
    (tmp_path / ".compass").mkdir()
    assert harness._interruptions(tmp_path) == {
        "hook_blocks": 0, "check_failures": 0}


def test_sc_1_no_compass_project_is_not_recorded(tmp_path):
    assert harness._interruptions(tmp_path) is None


def test_sc_1_the_report_shows_blocks_and_failures_per_condition():
    a = make_record(condition="compass", run=1,
                    interruptions={"hook_blocks": 2, "check_failures": 1})
    b = make_record(condition="compass", run=2,
                    interruptions={"hook_blocks": 0, "check_failures": 3})
    bare = make_record(condition="bare")
    report = compare.build_report([a, b, bare])
    assert "Hook blocks" in report and "Check failures" in report
    assert "0-2" in report and "1-3" in report          # per-cell spread
    assert "2 (total)" in report and "4 (total)" in report  # summary
    summary = report.split("## Summary", 1)[1]
    for measure in ("Hook blocks", "Check failures"):
        row = next(l for l in summary.splitlines() if l.startswith(f"| {measure} "))
        # Columns: measure, compass, bare. The bare condition has no
        # Compass project, so its count is not recorded, never zero.
        assert row.split("|")[3].strip() == "not recorded", row
