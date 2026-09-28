"""Expense report helpers."""

from __future__ import annotations


def parse_expenses(rows: list[dict]) -> list[dict]:
    """Return rows with amount_cents coerced to int and category defaulted
    to "general" where absent."""
    parsed = []
    for row in rows:
        parsed.append({
            "category": row.get("category", "general"),
            "amount_cents": int(row["amount_cents"]),
        })
    return parsed


def summarize(expenses: list[dict]) -> dict:
    """Return the total amount in cents per category."""
    totals: dict[str, int] = {}
    for item in expenses:
        totals[item["category"]] = totals.get(item["category"], 0) + item["amount_cents"]
    return totals
