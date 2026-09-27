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

CMP-4.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

Cell = Tuple[str, str]  # (scenario, condition)


# --- per-run measure extraction ---------------------------------------------
# Each of these reads one run record and returns the raw number that record
# holds for a measure, or None when the record does not carry it - "not
# recorded" is a fact about the record, not a computed zero.

def _hidden_pass_rate(record: Dict[str, Any]) -> Optional[float]:
    hidden = record.get("hidden")
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


def _wall_time(record: Dict[str, Any]) -> Optional[float]:
    return record.get("seconds")


def _is_completed(record: Dict[str, Any]) -> bool:
    """Finished, with every hidden test passing. A record with no `hidden`
    at all is not counted complete - CMP-3's six tasks all carry hidden
    tests, so an absent `hidden` on real data means the run never reached
    them, not that there were none to fail."""
    if "finished" not in record or not record["finished"]:
        return False
    hidden = record.get("hidden")
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

def _runs_label(n: int) -> str:
    return "one run" if n == 1 else f"{n} runs"


def _completed_fraction(records: List[Dict[str, Any]]) -> str:
    completed = sum(1 for r in records if _is_completed(r))
    return f"{completed}/{len(records)}"


MEASURE_COLUMNS = (
    ("runs", "Runs"),
    ("completed", "Completed"),
    ("hidden_pass_rate", "Hidden-test pass rate"),
    ("regressions", "Regressions"),
    ("replies_sent", "Replies sent"),
    ("wall_time", "Wall time"),
    ("tokens", "Tokens"),
)


def cell_measures(records: List[Dict[str, Any]]) -> Dict[str, str]:
    """The seven measures CMP-4 asks for, for one (scenario, condition)
    cell's worth of run records."""
    token_values, token_formatter = _tokens_values(records)
    return {
        "runs": _runs_label(len(records)),
        "completed": _completed_fraction(records),
        "hidden_pass_rate": _measure([_hidden_pass_rate(r) for r in records], _percentage),
        "regressions": _measure([_regressions_count(r) for r in records], _plain_count),
        "replies_sent": _measure([_replies_sent(r) for r in records], _plain_count),
        "wall_time": _measure([_wall_time(r) for r in records], _seconds),
        "tokens": _measure(token_values, token_formatter),
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


def render_report(cells: Dict[Cell, List[Dict[str, Any]]],
                   scenario_order: List[str], condition_order: List[str]) -> str:
    lines = ["# Comparison report", ""]
    for scenario in scenario_order:
        lines.append(f"## {scenario}")
        lines.append("")
        rows = []
        for condition in condition_order:
            records = cells.get((scenario, condition))
            if not records:
                continue
            measures = cell_measures(records)
            rows.append([condition] + [measures[key] for key, _ in MEASURE_COLUMNS])
        headers = ["Condition"] + [label for _, label in MEASURE_COLUMNS]
        lines.append(_markdown_table(headers, rows))
        lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append("Each condition's own totals, pooled across every scenario, "
                  "in the order the records first name them - never sorted "
                  "or scored against one another.")
    lines.append("")
    pooled = _pool_by_condition(cells, condition_order)
    headers = ["Measure"] + condition_order
    rows = []
    for key, label in MEASURE_COLUMNS:
        row = [label]
        for condition in condition_order:
            row.append(cell_measures(pooled[condition])[key])
        rows.append(row)
    lines.append(_markdown_table(headers, rows))
    lines.append("")
    return "\n".join(lines)


# --- loading records and the CLI --------------------------------------------

def load_records(paths: List[str]) -> List[Dict[str, Any]]:
    return [json.loads(Path(p).read_text(encoding="utf-8")) for p in paths]


def build_report(records: List[Dict[str, Any]]) -> str:
    cells, scenario_order, condition_order = group_by_scenario_and_condition(records)
    return render_report(cells, scenario_order, condition_order)


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Group eval run records by scenario and condition and "
                     "write a comparison report.")
    parser.add_argument("records", nargs="+", help="run record JSON files")
    parser.add_argument("--report", required=True, help="path to write the markdown report")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    report_text = build_report(load_records(args.records))
    Path(args.report).write_text(report_text, encoding="utf-8")
    print(f"wrote {args.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
