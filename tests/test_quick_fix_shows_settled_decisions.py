"""A quick fix sees the project's settled decisions before it changes code.

A project recorded in its decisions ledger that money rounds half up. A
Compass quick fix never read the ledger, rounded halves to even and failed
a hidden test that sessions with no framework passed (#385).

Scenario id: SD-1 (issue `quick-fix-shows-settled-decisions`).
"""
from __future__ import annotations

from test_quick_fix_verbs import _start, repo  # noqa: F401

LEDGER = "governance/decisions"


def _entry(root, date, slug, decision, supersedes="Nothing."):
    d = root / LEDGER
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{date}-{slug}.md").write_text(
        f"# {slug}\n\n## Decided by\n\nsomeone\n\n## Date\n\n{date}\n\n"
        f"## Supersedes\n\n{supersedes}\n\n## Decision\n\n{decision}\n\n"
        f"## Why\n\nNot recorded.\n\n## Evidence\n\nA test.\n",
        encoding="utf-8")


def test_sd_1_start_lists_the_live_decisions_newest_first(repo):
    _entry(repo, "2026-09-01", "old-rounding", "Money rounds half to even.")
    _entry(repo, "2026-09-29", "money-rounding", "Money rounds half up. Always.",
           supersedes=f"`{LEDGER}/2026-09-01-old-rounding.md`")
    _entry(repo, "2026-09-30", "dates-in-utc", "Dates are stored in UTC.")
    out = _start(repo, "fix").stdout
    assert "money-rounding: Money rounds half up." in out
    assert "dates-in-utc: Dates are stored in UTC." in out
    assert out.index("dates-in-utc") < out.index("money-rounding")
    assert "old-rounding" not in out


def test_sd_1_the_list_is_capped_with_a_count_of_the_rest(repo):
    for n in range(1, 9):
        _entry(repo, f"2026-09-0{n}", f"rule-{n}", f"Rule {n} holds.")
    out = _start(repo, "fix").stdout
    assert "rule-8" in out and "rule-1:" not in out
    assert "3 more" in out and "compass decision list" in out


def test_sd_1_an_empty_ledger_adds_nothing(repo):
    out = _start(repo, "fix").stdout
    assert "decision" not in out.lower()
