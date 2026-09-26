"""Tests for the expense report helpers already built.

Nothing here covers category limits - the next piece of work the in-flight
record names.
"""

from src.report import parse_expenses, summarize


def test_parse_expenses_defaults_category():
    rows = [{"amount_cents": "500"}, {"category": "travel", "amount_cents": 1200}]
    assert parse_expenses(rows) == [
        {"category": "general", "amount_cents": 500},
        {"category": "travel", "amount_cents": 1200},
    ]


def test_summarize_totals_by_category():
    expenses = [
        {"category": "travel", "amount_cents": 1200},
        {"category": "travel", "amount_cents": 300},
        {"category": "general", "amount_cents": 500},
    ]
    assert summarize(expenses) == {"travel": 1500, "general": 500}
