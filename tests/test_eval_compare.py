"""`evals/compare.py` - the comparison report over run records.

CMP-4: `evals/compare.py <records...> --report <file.md>` reads the JSON run
records `evals/harness.py` writes - carrying the fields subtask-1 adds,
`framework`, `hidden: {command, exit_code, passed, failed}` and
`regressions` (the list of tests that passed at the seed and now fail) -
groups them by scenario and condition, and writes, per cell: runs, whether
each run completed (finished, with every hidden test passing), the
hidden-test pass rate, the count of regressed tests, replies sent, wall
time and tokens. A cell backed by more than one run gives the spread
(lowest and highest) of each measure; one run gives that run's own value,
marked "(one run)" so a reader never mistakes a single sample for a range.
A record that lacks a field reports that measure as "not recorded" - never
as zero, which would claim a clean run that was never actually checked. A
final summary table lists every condition's totals side by side, in the
order records first named them, never sorted by how well a condition did.

Every record here is built by hand to the field names above; none of these
tests calls a real model or reaches the network. `evals/harness.py`'s
`run_once` is the source for the fields that already existed before this
issue - `scenario`, `condition`, `finished`, `seconds`, `cost_usd`,
`replies_sent` - so `make_record` below defaults to that shape, adding only
what a cell's measures need.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import evals.compare as compare  # noqa: E402

COMPARE_SCRIPT = ROOT / "evals" / "compare.py"


# --- building blocks ---------------------------------------------------

def make_record(scenario="cmp-small-fix", condition="bare", run=1, *,
                 finished=True, seconds=12.3, cost_usd=0.42, replies_sent=0,
                 hidden=None, regressions=None, tokens=None, **extra):
    """A run record with the fields `evals/compare.py` reads. Only a field
    actually passed lands in the record - a keyword left at its default of
    `None` (`hidden`, `regressions`, `tokens`) is left off the record
    entirely, the same as a real record that never carried it, so a test
    can ask for "not recorded" by simply not passing it."""
    record = {
        "scenario": scenario,
        "condition": condition,
        "run": run,
        "finished": finished,
        "seconds": seconds,
        "cost_usd": cost_usd,
        "replies_sent": replies_sent,
    }
    if hidden is not None:
        record["hidden"] = hidden
    if regressions is not None:
        record["regressions"] = regressions
    if tokens is not None:
        record["tokens"] = tokens
    record.update(extra)
    return record


def hidden(passed, failed, command="python3 -m pytest -q hidden_tests", exit_code=0):
    return {"command": command, "exit_code": exit_code, "passed": passed, "failed": failed}


# --- CMP-4: one run per cell ------------------------------------------------

def test_one_run_per_cell_reports_that_runs_own_measures():
    """A cell with a single run shows that run's own values, not a spread -
    each measure carries "(one run)" so a reader can tell a single sample
    from a range, and "Runs" itself reads as prose, not "1 runs"."""
    record = make_record(hidden=hidden(passed=3, failed=0), regressions=[],
                          replies_sent=1, seconds=12.3, cost_usd=0.42)
    report = compare.build_report([record])

    assert "one run" in report
    assert "1/1" in report          # completed: finished, no hidden failure
    assert "100% (one run)" in report        # hidden-test pass rate
    assert "0 (one run)" in report           # regressions: none
    assert "1 (one run)" in report           # replies sent
    assert "12.3s (one run)" in report       # wall time
    assert "$0.4200 (one run)" in report     # tokens, falling back to cost_usd


def test_more_than_one_run_gives_the_spread():
    """Two runs of the same cell report the lowest and highest of each
    measure, not one value dressed up as "the" answer - a session that
    passed hidden tests once and failed them once is a real finding a
    single number would hide."""
    low = make_record(condition="compass", hidden=hidden(passed=2, failed=2),
                       regressions=["tests/test_a.py::test_one"],
                       replies_sent=0, seconds=10.0, cost_usd=0.10)
    high = make_record(condition="compass", run=2, hidden=hidden(passed=4, failed=0),
                        regressions=["tests/test_a.py::test_one",
                                     "tests/test_b.py::test_two"],
                        replies_sent=1, seconds=40.0, cost_usd=0.50)
    report = compare.build_report([low, high])

    assert "2 runs" in report
    assert "1/2" in report              # completed: only the second run
    assert "50%-100%" in report         # hidden-test pass rate
    assert "1-2" in report              # regressions
    assert "0-1" in report              # replies sent
    assert "10.0s-40.0s" in report      # wall time
    assert "$0.1000-$0.5000" in report  # tokens, falling back to cost_usd
    assert "(one run)" not in report


def test_records_lacking_a_field_show_it_as_not_recorded_never_zero():
    """A run that never reached the hidden tests, or was built without
    `cost_usd`, must not be read as a clean zero - that would claim a
    measurement that was never taken. Pins the behaviour `_measure` and the
    per-run extraction functions already give: no field on any run in the
    cell -> "not recorded", the same text regardless of which measure is
    missing."""
    record = make_record(condition="spec-kit")  # no hidden, regressions, tokens/cost
    del record["cost_usd"]
    del record["replies_sent"]
    del record["seconds"]
    report = compare.build_report([record])

    assert "0/1" in report  # completed: absent hidden, so not confirmed complete
    headers = cells = None
    for line in report.splitlines():
        if line.startswith("| Condition"):
            headers = [c.strip() for c in line.split("|")][1:-1]
        if line.startswith("| spec-kit"):
            cells = dict(zip(headers, [c.strip() for c in line.split("|")][1:-1]))
            break
    assert cells, "no spec-kit row in the report"
    # No field on the one record behind this cell was ever carried, for any
    # column - never "0", "0%" or a silently blank cell, any of which
    # would claim a clean run, or an agreed value, nobody actually checked.
    for column in ("Model", "Framework commit", "Hidden-test pass rate",
                   "Regressions", "Interventions (replies sent)",
                   "Wall time", "Tokens"):
        assert cells[column] == "not recorded", column


def test_replies_sent_column_is_named_interventions_and_explained():
    """CMP-4: the column already showing replies sent is named
    "Interventions (replies sent)", and the report says what an
    intervention is - the harness sending the scenario's own
    `continue_reply` because the session stopped to ask, the one reply a
    real user would give."""
    record = make_record(replies_sent=2)
    report = compare.build_report([record])

    assert "Interventions (replies sent)" in report
    assert "Replies sent" not in report
    assert "continue_reply" in report
    assert "intervention" in report.lower()


def test_summary_table_lists_condition_totals_side_by_side():
    """The summary pools every scenario's records by condition and reports
    each condition's own totals - it does not rank the conditions against
    one another, so no ordering word or score appears, and the condition
    columns stay in the order the records first name them. Every pooled
    measure is a total (a sum) or a pooled rate, plainly labelled as such -
    never the "lowest and highest" spread the per-cell tables use, because
    a spread there would run across different scenarios, not across
    repeated executions of the same one, and would read as the same
    statistic when it is not."""
    records = [
        make_record(scenario="cmp-small-fix", condition="bare",
                    hidden=hidden(passed=1, failed=0), regressions=[],
                    replies_sent=0, seconds=5.0, cost_usd=0.10),
        make_record(scenario="cmp-feature", condition="bare", run=2,
                    hidden=hidden(passed=0, failed=1),
                    regressions=["tests/test_x.py::test_y"],
                    replies_sent=1, seconds=15.0, cost_usd=0.30),
        make_record(scenario="cmp-small-fix", condition="compass",
                    hidden=hidden(passed=1, failed=0), regressions=[],
                    replies_sent=0, seconds=3.0, cost_usd=0.05),
    ]
    report = compare.build_report(records)

    assert "## Summary" in report
    summary = report.split("## Summary", 1)[1]
    assert "bare" in summary and "compass" in summary
    assert "2 runs" in summary   # bare: pooled across both scenarios
    assert "one run" in summary  # compass: pooled to a single run
    assert "1/2" in summary     # bare: one of its two runs completed
    assert "1/1" in summary     # compass: its one run completed

    # bare pools cmp-small-fix (1 passed, 0 failed) and cmp-feature (0
    # passed, 1 failed) into one pooled rate, not a "0%-100%" spread that
    # would read as variance across repeated runs of one scenario.
    assert "50% (pooled)" in summary
    assert "100% (pooled)" in summary    # compass: its only scenario's rate
    assert "0%-100%" not in summary

    # wall time and tokens sum across bare's two scenarios (5.0s + 15.0s,
    # $0.10 + $0.30) rather than spreading across them.
    assert "20.0s (total)" in summary
    assert "$0.4000 (total)" in summary
    assert "5.0s-15.0s" not in summary
    assert "$0.1000-$0.3000" not in summary

    assert "1 (total)" in summary   # bare: one regressed test, from cmp-feature
    for word in ("rank", "best", "winner", "worst"):
        assert word not in summary.lower()


def test_cell_shows_model_and_framework_commit():
    """A reader comparing conditions needs to know which model, and which
    framework commit, actually produced a cell's numbers - nothing else in
    the report says so."""
    record = make_record(condition="superpowers", model="claude-opus-5-5",
                          framework={"name": "superpowers",
                                     "commit": "8ca22dba9a94f28898bbce59f2537ff4d87c747d"})
    report = compare.build_report([record])

    assert "claude-opus-5-5" in report
    assert "8ca22dba9a94f28898bbce59f2537ff4d87c747d" in report


def test_cell_says_mixed_when_runs_disagree_on_model_or_commit():
    """Two runs of the same cell that used a different model, or a
    different framework commit, must not silently report only the first
    one's value - "mixed" says the cell is not the apples-to-apples
    comparison it looks like."""
    first = make_record(condition="spec-kit", model="claude-opus-5-5",
                         framework={"name": "spec-kit", "commit": "3b895d1"})
    second = make_record(condition="spec-kit", run=2, model="claude-sonnet-5",
                          framework={"name": "spec-kit", "commit": "3b895d1"})
    report = compare.build_report([first, second])

    assert "mixed" in report
    assert "claude-opus-5-5" not in report
    assert "claude-sonnet-5" not in report
    assert "3b895d1" in report  # the commit agrees, so it is not "mixed"


def test_cell_reports_no_framework_as_not_recorded():
    """`bare` and `compass` carry no framework at all -
    `evals/harness.py` writes `framework: null` for both - so the Model
    and Framework commit columns read the same "not recorded" any other
    field a record never carried does."""
    record = make_record(condition="bare", framework=None)
    report = compare.build_report([record])

    for line in report.splitlines():
        if line.startswith("| Condition"):
            headers = [c.strip() for c in line.split("|")][1:-1]
        if line.startswith("| bare"):
            cells = dict(zip(headers, [c.strip() for c in line.split("|")][1:-1]))
            break
    else:
        raise AssertionError("no bare row in the report")
    assert cells["Framework commit"] == "not recorded"


def test_tokens_prefers_an_explicit_token_count_over_cost():
    """`evals/harness.py` writes no token count today, only `cost_usd` - but
    once a run record carries one, the report must read it rather than
    silently keep reporting cost. Dollars and a token count never mix
    inside one cell's Tokens column."""
    low = make_record(tokens=1000, cost_usd=9.99)
    high = make_record(run=2, tokens=3000, cost_usd=0.01)
    report = compare.build_report([low, high])

    assert "1,000-3,000" in report
    assert "9.99" not in report and "0.01" not in report


def test_grouping_keeps_each_scenario_and_condition_cell_separate():
    """Two scenarios and two conditions must not blend into one cell - a
    condition's records for one scenario must never count towards another
    scenario's row."""
    records = [
        make_record(scenario="cmp-small-fix", condition="bare", replies_sent=0),
        make_record(scenario="cmp-small-fix", condition="compass", replies_sent=5),
        make_record(scenario="cmp-feature", condition="bare", replies_sent=9),
    ]
    report = compare.build_report(records)

    assert "## cmp-small-fix" in report and "## cmp-feature" in report
    small_fix_section = report.split("## cmp-small-fix", 1)[1].split("## cmp-feature")[0]
    feature_section = report.split("## cmp-feature", 1)[1].split("## Summary")[0]
    assert "0 (one run)" in small_fix_section   # bare's own replies_sent
    assert "5 (one run)" in small_fix_section   # compass's own replies_sent
    assert "9 (one run)" not in small_fix_section
    assert "9 (one run)" in feature_section
    assert "compass" not in feature_section  # cmp-feature has no compass row


def test_cli_writes_the_report_file():
    """The literal command line CMP-4 names: run record paths, then
    `--report <file>`."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        record_path = Path(tmp) / "cmp-small-fix-bare-1.json"
        record_path.write_text(json.dumps(make_record()), encoding="utf-8")
        report_path = Path(tmp) / "report.md"

        result = subprocess.run(
            [sys.executable, str(COMPARE_SCRIPT), str(record_path),
             "--report", str(report_path)],
            capture_output=True, text=True)

        assert result.returncode == 0, result.stderr
        assert report_path.is_file()
        assert "# Comparison report" in report_path.read_text(encoding="utf-8")
