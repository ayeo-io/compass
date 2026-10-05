"""The comparison report gives tokens for every quick-fix stage.

Assess and implement come from the `usage` block `quick-fix finish` writes.
`verify` and `ship` cannot be in that block: it is written during `finish`,
and the session goes on afterwards. The eval record carries the whole
session's tokens, counted over the same four kinds, so those two stages are
the remainder. A cell whose mean assess exceeds its mean implement is
flagged, because assess is meant to be the cheap stage.

Scenario id: ST-1 (issue `stage-tokens-in-report`).
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "evals"))
sys.path.insert(0, str(ROOT / "cli"))

import compare  # noqa: E402


def _record(assess, implement, tokens, run=1):
    stages = {"assess": {"input": assess, "output": 0, "cache_write": 0, "cache_read": 0},
              "implement": {"input": implement, "output": 0, "cache_write": 0,
                            "cache_read": 0},
              "verify": {"measured": False}, "ship": {"measured": False}}
    return {"scenario": "s", "condition": "compass", "run": run, "seconds": 1.0,
            "contained": True, "tokens": tokens,
            "manifests": {".compass/work/fix/manifest.yml":
                          yaml.safe_dump({"usage": {"stages": stages}})}}


def test_st_1_verify_and_ship_is_the_rest_of_the_session():
    shown = compare._tokens_by_stage([_record(100, 300, 1000),
                                      _record(200, 500, 1500, run=2)])
    assert "assess 150" in shown and "implement 400" in shown, shown
    assert "verify and ship 700" in shown, shown      # (600 + 800) / 2
    assert "not measured" not in shown, shown


def test_st_1_without_a_session_total_verify_and_ship_is_not_recorded():
    record = _record(100, 300, None)
    shown = compare._tokens_by_stage([record])
    assert "verify and ship not recorded" in shown, shown


def test_st_1_a_cell_where_assess_costs_more_than_implement_is_flagged():
    flagged = compare._tokens_by_stage([_record(500, 300, 1000)])
    assert "assess above implement" in flagged, flagged
    plain = compare._tokens_by_stage([_record(100, 300, 1000)])
    assert "assess above implement" not in plain, plain
