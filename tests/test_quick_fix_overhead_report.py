"""The quick-fix cost is on record, measured, with its limits.

The report gives every session's tokens, before and after, for the two
B6 scenarios a quick fix serves, and the calls by step. This test reads
the report's own table, so a figure changed in one place and not the
other fails here, and it holds the claim the report makes: each
scenario's Compass mean after the change is at most twice Superpowers'.

Scenario ids: QFO-7 and QFO-8, in acceptance-criteria.md of issue
quick-fix-overhead.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "docs" / "compass" / "2026-09-28-quick-fix-overhead.md"

# | scenario | condition | session | tokens | calls | hidden | gates |
ROW = re.compile(
    r"^\| `(cmp-[a-z-]+)` \| ([a-z -]+?) \| (\d) \| ([\d,]+) \| (\d+) \| "
    r"(\d+/\d+) \| ([a-z-]+) \|$")


def _rows():
    rows = []
    for line in REPORT.read_text(encoding="utf-8").splitlines():
        m = ROW.match(line.strip())
        if m:
            scenario, condition, _run, tokens, calls, hidden, gates = m.groups()
            rows.append(dict(scenario=scenario, condition=condition.strip(),
                             tokens=int(tokens.replace(",", "")),
                             calls=int(calls), hidden=hidden, gates=gates))
    return rows


def _mean(rows, scenario, condition):
    got = [r["tokens"] for r in rows
           if r["scenario"] == scenario and r["condition"] == condition]
    assert got, f"no {condition} row for {scenario}"
    return sum(got) / len(got)


def test_qfo_7_each_scenario_mean_is_within_twice_superpowers():
    rows = _rows()
    for scenario in ("cmp-small-fix", "cmp-feature"):
        after = _mean(rows, scenario, "compass after")
        rival = _mean(rows, scenario, "superpowers")
        assert after <= 2 * rival, (scenario, after, rival)


def test_qfo_7_every_session_after_held_the_guardrails_and_the_result():
    after = [r for r in _rows() if r["condition"] == "compass after"]
    assert len(after) == 4
    for r in after:
        passed, total = r["hidden"].split("/")
        assert passed == total, r
        assert r["gates"] == "pass", r


def test_qfo_8_the_breakdown_gives_calls_before_and_after_with_its_limits():
    raw = REPORT.read_text(encoding="utf-8")
    rows = _rows()
    for condition in ("compass before", "compass after", "superpowers",
                      "no framework"):
        assert any(r["condition"] == condition for r in rows), condition
    assert "## Calls by step" in raw
    assert "## What this does not show" in raw
    for placeholder in ("TODO", "TBD", "{{"):
        assert placeholder not in raw, placeholder


STEP_ROW = re.compile(
    r"^\| ([A-Za-z ,]+?) \| (\d+(?: to \d+)?) \| ([\d,]+) \| "
    r"(\d+(?: to \d+)?) \| ([\d,]+) \|$")


def test_qfo_8_the_steps_add_up_to_each_condition_mean():
    """Calls and tokens by step, and the tokens in each column sum to the
    mean of that condition's four sessions in the results table."""
    steps = [STEP_ROW.match(l.strip()) for l in
             REPORT.read_text(encoding="utf-8").splitlines()]
    steps = [m for m in steps if m]
    assert len(steps) >= 5, "the calls-by-step table gives no tokens"
    before = sum(int(m.group(3).replace(",", "")) for m in steps)
    after = sum(int(m.group(5).replace(",", "")) for m in steps)
    rows = _rows()
    for condition, total in (("compass before", before),
                             ("compass after", after)):
        got = [r["tokens"] for r in rows if r["condition"] == condition]
        mean = sum(got) / len(got)
        assert abs(total - mean) <= len(steps), (condition, total, mean)
