#!/usr/bin/env python3
"""Group eval run records by scenario and condition and write a comparison report.

Usage:
    python3 evals/compare.py <run record ...> --report <file.md>

Each run record is the JSON `evals/harness.py` writes for one run, carrying
the fields subtask-1 adds: `framework: {name, commit}`, `hidden: {command,
exit_code, passed, failed}` and `regressions` - the tests that passed at the
seed and now fail. This groups records by `scenario` and `condition` and
writes, per cell: runs, whether each run completed (finished, with every
hidden test passing), the hidden-test pass rate, the count of regressed
tests, replies sent, wall time and tokens. A cell backed by more than one
run gives the spread (lowest and highest) of each measure; one run gives
that run's own value, marked "(one run)" so nobody reads a single sample as
a range. A record that lacks a field reports that measure as "not
recorded" - never zero, which would claim a clean run nobody checked. A
final summary table lists every condition's totals side by side, in the
order the records first name them - it ranks nothing.

A record's own `hidden.failed` undercounts when the hidden test file
failed to import: pytest's own summary then reports one error for the
whole file, not one for each test it defines. This reads `--scenarios-dir`
(default `evals/scenarios` next to this file) to find every scenario's own
`hidden_tests/` and correct for it (EGB-4), so a stored record with no raw
pytest output left to re-read still reports every test the file defines as
failed, not the fewer pytest's own summary line gave.

CMP-4.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

FRAMEWORK_ROOT = Path(__file__).resolve().parent.parent
if str(FRAMEWORK_ROOT) not in sys.path:
    sys.path.insert(0, str(FRAMEWORK_ROOT))
# `hidden_tests_defined_count` and `corrected_hidden_counts` (EGB-4) live
# once, in the harness - reused here rather than kept as a second copy, the
# same reason `evals/judge.py` imports `_is_compass_own_record` from it.
from evals import harness as _harness  # noqa: E402
from evals import quality  # noqa: E402

Cell = Tuple[str, str]  # (scenario, condition)

DEFAULT_SCENARIOS_DIR = Path(__file__).resolve().parent / "scenarios"


# --- per-run measure extraction ---------------------------------------------
# Each of these reads one run record and returns the raw number that record
# holds for a measure, or None when the record does not carry it - "not
# recorded" is a fact about the record, not a computed zero.

def _corrected_hidden(record: Dict[str, Any],
                       scenarios_dir: Path) -> Optional[Dict[str, Any]]:
    """`record["hidden"]`, corrected for a hidden test file that failed to
    import (EGB-4): pytest's own summary then reports one error for the
    whole file, not one for each test it defines, so a stored record whose
    own total falls short of what `scenarios_dir/<scenario>/hidden_tests/`
    defines is read as every one of those tests failing - there is no raw
    pytest output left in the record to re-read, so this is the only
    ground truth a re-score has for an already-recorded run. A scenario id
    `scenarios_dir` carries no `hidden_tests/` for - unknown, or one
    without any - leaves the record's own numbers untouched."""
    hidden = record.get("hidden")
    if not isinstance(hidden, dict):
        return hidden
    passed, failed = hidden.get("passed"), hidden.get("failed")
    if passed is None or failed is None:
        return hidden
    scenario = record.get("scenario")
    if not scenario:
        return hidden
    # The count the run itself recorded, when it recorded one; today's
    # hidden test file only for an older record that did not.
    defined = hidden.get("defined")
    if not isinstance(defined, int):
        defined = _harness.hidden_tests_defined_count(
            scenarios_dir / scenario / "hidden_tests")
    corrected_passed, corrected_failed = _harness.corrected_hidden_counts(
        passed, failed, defined, hidden.get("exit_code", 2))
    if (corrected_passed, corrected_failed) == (passed, failed):
        return hidden
    return {**hidden, "passed": corrected_passed, "failed": corrected_failed}


def _hidden_pass_rate(record: Dict[str, Any], scenarios_dir: Path) -> Optional[float]:
    hidden = _corrected_hidden(record, scenarios_dir)
    if not isinstance(hidden, dict):
        return None
    passed, failed = hidden.get("passed"), hidden.get("failed")
    if passed is None or failed is None:
        return None
    total = passed + failed
    if total <= 0:
        return None
    return passed / total


def _regressions_count(record: Dict[str, Any]) -> Optional[int]:
    if "regressions" not in record:
        return None
    regressions = record["regressions"]
    if isinstance(regressions, list):
        return len(regressions)
    if isinstance(regressions, (int, float)):
        return regressions
    return None


def _replies_sent(record: Dict[str, Any]) -> Optional[int]:
    return record.get("replies_sent")


def _interruption_count(kind: str):
    """How many times Compass stopped the session with `kind` (`hook_blocks`
    or `check_failures`), from the record's `interruptions`. None when the
    record does not carry it: a condition with no Compass project, or a
    record from before the field existed."""
    def extract(record: Dict[str, Any]) -> Optional[int]:
        counts = record.get("interruptions")
        if not isinstance(counts, dict):
            return None
        value = counts.get(kind)
        return value if isinstance(value, int) else None
    return extract


# Static code-quality signals (evals/quality.py): the changed Python files
# outside tests/, rebuilt from the seed and the run's diff, measured with ast.
_QUALITY_MEASURES = (
    ("complexity_added", quality.complexity_added_of),
    ("duplicated_lines", quality.duplicated_lines_of),
    ("lint_findings", quality.lint_findings_of),
)


def _wall_time(record: Dict[str, Any]) -> Optional[float]:
    return record.get("seconds")


def _model(record: Dict[str, Any]) -> Optional[str]:
    return record.get("model")


def _framework_commit(record: Dict[str, Any]) -> Optional[str]:
    """The framework's pinned commit, or for the compass condition, which
    has no `framework` block, the checkout commit the harness recorded."""
    framework = record.get("framework")
    if isinstance(framework, dict) and framework.get("commit"):
        return framework["commit"]
    return record.get("compass_commit")


def _is_completed(record: Dict[str, Any], scenarios_dir: Path) -> bool:
    """Finished, with every hidden test passing. A record with no `hidden`
    at all is not counted complete - CMP-3's six scenarios all carry hidden
    tests, so an absent `hidden` on real data means the run never reached
    them, not that there were none to fail."""
    if "finished" not in record or not record["finished"]:
        return False
    hidden = _corrected_hidden(record, scenarios_dir)
    if not isinstance(hidden, dict):
        return False
    passed, failed = hidden.get("passed"), hidden.get("failed")
    if passed is None or failed is None or passed + failed <= 0:
        return False
    return failed == 0


# --- formatting one measure across a cell's runs ----------------------------

def _percentage(value: float) -> str:
    return f"{value * 100:.0f}%"


def _dollars(value: float) -> str:
    return f"${value:.4f}"


def _seconds(value: float) -> str:
    return f"{value:.1f}s"


def _plain_count(value: Any) -> str:
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return f"{value:,}" if isinstance(value, int) else str(value)


def _measure(values: List[Optional[float]], formatter) -> str:
    """`values` is one number per run in the cell, `None` where a record
    did not carry the field. With no run reporting it: "not recorded".
    With exactly one: that run's own value, marked "(one run)" - not a
    spread, because a spread of one point is not a spread, it is the point
    dressed up as a range."""
    present = [v for v in values if v is not None]
    if not present:
        return "not recorded"
    if len(present) == 1:
        return f"{formatter(present[0])} (one run)"
    return f"{formatter(min(present))}-{formatter(max(present))}"


def _column_value(records: List[Dict[str, Any]], extractor) -> str:
    """One identifying column's text for a cell: the value every run that
    reports it agrees on, "mixed" when two runs disagree - a reader must
    not read a cell as one condition's clean result when it silently
    pooled two different models or two different framework commits - and
    "not recorded" when no run in the cell reports it at all."""
    values = [extractor(r) for r in records]
    present = [v for v in values if v is not None]
    if not present:
        return "not recorded"
    if len(set(present)) > 1:
        return "mixed"
    return str(present[0])


def _tokens_values(records: List[Dict[str, Any]]) -> Tuple[List[Optional[float]], Any]:
    """An explicit token count when any run in the cell carries one -
    `evals/harness.py` writes none today, so this is for a record built by
    hand or a future harness - else the dollar cost from `cost_usd`, the
    field the harness always writes. Never mixes the two units within one
    cell."""
    token_values = [r.get("tokens") for r in records]
    if any(v is not None for v in token_values):
        return token_values, _plain_count
    return [r.get("cost_usd") for r in records], _dollars


# --- one cell's measures -----------------------------------------------------

_STAGES = ("assess", "implement", "verify", "ship")


def _stage_totals(record: Dict[str, Any]) -> Optional[Dict[str, int]]:
    """Each stage's tokens from the `usage` block a quick fix records in its
    manifest (#375), summed over every manifest the run left, or None when
    no manifest recorded any."""
    from compass_pkg import core as _core  # the bundled YAML, as harness does
    found: Dict[str, Any] = {}
    for text in (record.get("manifests") or {}).values():
        try:
            data = _core.yaml.safe_load(text) or {}
        except _core.yaml.YAMLError:
            continue
        stages = ((data.get("usage") or {}).get("stages") or {}) \
            if isinstance(data, dict) else {}
        for stage in _STAGES:
            counts = stages.get(stage) or {}
            if counts.get("measured") is False:
                found.setdefault(stage, "not measured")
                continue
            values = [counts.get(k) for k in ("input", "output", "cache_write",
                                              "cache_read")]
            if any(isinstance(v, int) for v in values):
                previous = found.get(stage)
                found[stage] = (previous if isinstance(previous, int) else 0) + sum(
                    v for v in values if isinstance(v, int))
    return found or None


def _tokens_by_stage(records: List[Dict[str, Any]]) -> str:
    """The mean tokens per stage across the runs that recorded them."""
    totals = [t for t in (_stage_totals(r) for r in records) if t]
    if not totals:
        return "not recorded"
    parts = []
    for stage in _STAGES:
        values = [t[stage] for t in totals if isinstance(t.get(stage), int)]
        if values:
            parts.append(f"{stage} {round(sum(values) / len(values)):,}")
        elif any(t.get(stage) == "not measured" for t in totals):
            parts.append(f"{stage} not measured")
        else:
            parts.append(f"{stage} not recorded")
    return ", ".join(parts) + f" (mean of {len(totals)})"


def _runs_label(n: int) -> str:
    return "one run" if n == 1 else f"{n} runs"


def _completed_fraction(records: List[Dict[str, Any]], scenarios_dir: Path) -> str:
    completed = sum(1 for r in records if _is_completed(r, scenarios_dir))
    return f"{completed}/{len(records)}"


# Which run made a cell's numbers - shown only on the per-scenario tables,
# never pooled into the summary, which already pools deliberately and says
# so; a "mixed" model or commit there would tell a reader nothing they
# could act on.
IDENTITY_COLUMNS = (
    ("model", "Model"),
    ("framework_commit", "Framework commit"),
)

MEASURE_COLUMNS = (
    ("runs", "Runs"),
    ("completed", "Completed"),
    ("hidden_pass_rate", "Hidden-test pass rate"),
    ("regressions", "Regressions"),
    ("replies_sent", "Interventions (replies sent)"),
    ("hook_blocks", "Hook blocks"),
    ("check_failures", "Check failures"),
    ("complexity_added", "Complexity added"),
    ("duplicated_lines", "Duplicated lines"),
    ("lint_findings", "Lint findings"),
    ("wall_time", "Wall time"),
    ("tokens", "Tokens"),
    ("tokens_by_stage", "Tokens by stage"),
)


def cell_identity(records: List[Dict[str, Any]]) -> Dict[str, str]:
    """Which model ran a cell's sessions, and which framework commit they
    loaded - "mixed" if the runs in the cell disagree, "not recorded" for
    a condition with no framework at all (`bare`, `compass`)."""
    return {
        "model": _column_value(records, _model),
        "framework_commit": _column_value(records, _framework_commit),
    }


def cell_measures(records: List[Dict[str, Any]], scenarios_dir: Path) -> Dict[str, str]:
    """The seven measures CMP-4 asks for, for one (scenario, condition)
    cell's worth of run records - every run in the list is a repeat
    execution of the same scenario under the same condition, so a spread
    across them is a spread across executions."""
    token_values, token_formatter = _tokens_values(records)
    return {
        "runs": _runs_label(len(records)),
        "completed": _completed_fraction(records, scenarios_dir),
        "hidden_pass_rate": _measure(
            [_hidden_pass_rate(r, scenarios_dir) for r in records], _percentage),
        "regressions": _measure([_regressions_count(r) for r in records], _plain_count),
        "replies_sent": _measure([_replies_sent(r) for r in records], _plain_count),
        "hook_blocks": _measure([_interruption_count("hook_blocks")(r) for r in records],
                                _plain_count),
        "check_failures": _measure(
            [_interruption_count("check_failures")(r) for r in records], _plain_count),
        **{key: _measure([of(r, scenarios_dir) for r in records], _plain_count)
           for key, of in _QUALITY_MEASURES},
        "wall_time": _measure([_wall_time(r) for r in records], _seconds),
        "tokens": _measure(token_values, token_formatter),
        "tokens_by_stage": _tokens_by_stage(records),
    }


def _total(values: List[Optional[float]], formatter) -> str:
    """The sum of whatever a record actually carried - "not recorded" when
    none did. A sum, unlike `_measure`'s spread, says the same thing
    whatever the records underneath it span: scenarios, executions, or
    both - it never implies a range some later reader could mistake for
    variance across repeats of one thing."""
    present = [v for v in values if v is not None]
    if not present:
        return "not recorded"
    return f"{formatter(sum(present))} (total)"


def _pooled_hidden_pass_rate(records: List[Dict[str, Any]], scenarios_dir: Path) -> str:
    """The pass rate over every hidden test counted across the pool, not
    the mean of each run's own rate - two records with 1/1 and 0/3 pool to
    1/4, not to the average of 100% and 0%."""
    totals = [_corrected_hidden(r, scenarios_dir) for r in records
              if isinstance(r.get("hidden"), dict)]
    passed = failed = 0
    counted = False
    for hidden in totals:
        p, f = hidden.get("passed"), hidden.get("failed")
        if p is None or f is None:
            continue
        passed += p
        failed += f
        counted = True
    if not counted or passed + failed <= 0:
        return "not recorded"
    return f"{_percentage(passed / (passed + failed))} (pooled)"


def summary_measures(records: List[Dict[str, Any]], scenarios_dir: Path) -> Dict[str, str]:
    """A condition's own totals, pooled across every scenario it ran. Runs
    and Completed already say the same thing regardless of what they pool
    across, so they are unchanged; every other measure is a sum or a
    pooled rate, plainly labelled, in place of `cell_measures`'s spread -
    a "lowest and highest" here would run across different scenarios, not
    across repeated executions of one, and would read as the same
    statistic the per-cell tables give when it is not."""
    token_values, token_formatter = _tokens_values(records)
    return {
        "runs": _runs_label(len(records)),
        "completed": _completed_fraction(records, scenarios_dir),
        "hidden_pass_rate": _pooled_hidden_pass_rate(records, scenarios_dir),
        "regressions": _total([_regressions_count(r) for r in records], _plain_count),
        "replies_sent": _total([_replies_sent(r) for r in records], _plain_count),
        "hook_blocks": _total([_interruption_count("hook_blocks")(r) for r in records],
                              _plain_count),
        "check_failures": _total(
            [_interruption_count("check_failures")(r) for r in records], _plain_count),
        **{key: _total([of(r, scenarios_dir) for r in records], _plain_count)
           for key, of in _QUALITY_MEASURES},
        "wall_time": _total([_wall_time(r) for r in records], _seconds),
        "tokens": _total(token_values, token_formatter),
        "tokens_by_stage": _tokens_by_stage(records),
    }


# --- grouping and the report -------------------------------------------------

def group_by_scenario_and_condition(
        records: List[Dict[str, Any]]
        ) -> Tuple[Dict[Cell, List[Dict[str, Any]]], List[str], List[str]]:
    """Every record filed under its `(scenario, condition)` cell, plus the
    scenario and condition orders as the records first name them - the
    order the report renders in, and the order the summary table's columns
    take. Never sorted by any measure: the summary "ranks nothing"."""
    cells: Dict[Cell, List[Dict[str, Any]]] = {}
    scenario_order: List[str] = []
    condition_order: List[str] = []
    for record in records:
        scenario, condition = record["scenario"], record["condition"]
        if scenario not in scenario_order:
            scenario_order.append(scenario)
        if condition not in condition_order:
            condition_order.append(condition)
        cells.setdefault((scenario, condition), []).append(record)
    return cells, scenario_order, condition_order


def _markdown_table(headers: List[str], rows: List[List[str]]) -> str:
    lines = ["| " + " | ".join(headers) + " |",
             "|" + "|".join(" --- " for _ in headers) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _pool_by_condition(cells: Dict[Cell, List[Dict[str, Any]]],
                        condition_order: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    """Every record for a condition, across every scenario - what the
    summary's totals are computed from."""
    pooled: Dict[str, List[Dict[str, Any]]] = {c: [] for c in condition_order}
    for (_, condition), records in cells.items():
        pooled[condition].extend(records)
    return pooled


def _how_it_ran(records: List[Dict[str, Any]]) -> List[str]:
    """The uid and Python version the runs used, and how many runs were
    not contained and why. A run that escaped its sandbox has undecided
    rule-judged behaviours, so a reader must see it before the numbers."""
    lines: List[str] = []
    uids = sorted({r["uid"] for r in records if r.get("uid") is not None})
    pythons = sorted({r["python_version"] for r in records
                      if r.get("python_version")})
    if uids or pythons:
        lines += [f"Method: ran as uid {', '.join(map(str, uids)) or 'not recorded'}, "
                  f"Python {', '.join(pythons) or 'not recorded'}.", ""]
    escaped = [r for r in records if r.get("contained") is False]
    if escaped:
        paths = sorted({p for r in escaped for p in r.get("escaped_paths") or []})
        shown = ", ".join(f"`{p}`" for p in paths[:5])
        more = f" and {len(paths) - 5} more" if len(paths) > 5 else ""
        lines += [f"{len(escaped)} of {len(records)} runs were not contained, "
                  f"so their rule-judged behaviours are undecided. They wrote "
                  f"outside their sandbox: {shown or 'no path recorded'}{more}.",
                  ""]
    return lines


def render_report(cells: Dict[Cell, List[Dict[str, Any]]],
                   scenario_order: List[str], condition_order: List[str],
                   scenarios_dir: Path) -> str:
    lines = ["# Comparison report", ""]
    lines.append(
        "An intervention is the harness sending the scenario's own "
        "`continue_reply` because the session stopped to ask - the one "
        "reply a real user would give, not a step the condition took on "
        "its own. \"Interventions (replies sent)\" below counts how many "
        "a condition needed.")
    lines.append("")
    lines.extend(_how_it_ran([r for rs in cells.values() for r in rs]))
    for scenario in scenario_order:
        lines.append(f"## {scenario}")
        lines.append("")
        rows = []
        for condition in condition_order:
            records = cells.get((scenario, condition))
            if not records:
                continue
            row_values = {**cell_identity(records),
                          **cell_measures(records, scenarios_dir)}
            columns = IDENTITY_COLUMNS + MEASURE_COLUMNS
            rows.append([condition] + [row_values[key] for key, _ in columns])
        headers = ["Condition"] + [label for _, label in IDENTITY_COLUMNS + MEASURE_COLUMNS]
        lines.append(_markdown_table(headers, rows))
        lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append("Each condition's own totals, pooled across every scenario, "
                  "in the order the records first name them - never sorted "
                  "or scored against one another. Runs and Completed are "
                  "counts either way; every other measure is a sum "
                  "\"(total)\" or a pooled rate \"(pooled)\" across every "
                  "scenario the condition ran, not a spread across "
                  "repeated executions of one.")
    lines.append("")
    pooled = _pool_by_condition(cells, condition_order)
    headers = ["Measure"] + condition_order
    rows = []
    for key, label in MEASURE_COLUMNS:
        row = [label]
        for condition in condition_order:
            row.append(summary_measures(pooled[condition], scenarios_dir)[key])
        rows.append(row)
    lines.append(_markdown_table(headers, rows))
    lines.append("")
    return "\n".join(lines)


# --- loading records and the CLI --------------------------------------------

def load_records(paths: List[str]) -> List[Dict[str, Any]]:
    return [json.loads(Path(p).read_text(encoding="utf-8")) for p in paths]


def build_report(records: List[Dict[str, Any]],
                  scenarios_dir: Optional[Path] = None) -> str:
    cells, scenario_order, condition_order = group_by_scenario_and_condition(records)
    return render_report(cells, scenario_order, condition_order,
                          scenarios_dir or DEFAULT_SCENARIOS_DIR)


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Group eval run records by scenario and condition and "
                     "write a comparison report.")
    parser.add_argument("records", nargs="+", help="run record JSON files")
    parser.add_argument("--report", required=True, help="path to write the markdown report")
    parser.add_argument("--scenarios-dir", default=None,
                         help="directory holding <scenario id>/hidden_tests/, "
                              "read to correct a hidden test file that failed "
                              "to import (EGB-4) - default: evals/scenarios "
                              "next to this file")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    scenarios_dir = Path(args.scenarios_dir) if args.scenarios_dir else None
    report_text = build_report(load_records(args.records), scenarios_dir)
    Path(args.report).write_text(report_text, encoding="utf-8")
    print(f"wrote {args.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
