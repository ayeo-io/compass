"""Invoice lines."""

from __future__ import annotations

from src.pricing import format_price


def invoice_line(item: str, amount: int) -> str:
    """One line of an invoice, e.g. 'Tea: £2.50'."""
    return f"{item}: {format_price(amount)}"
