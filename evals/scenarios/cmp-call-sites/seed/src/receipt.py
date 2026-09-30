"""Till receipts."""

from __future__ import annotations

from src.pricing import format_price


def receipt_total(amounts: list[int]) -> str:
    """The total line at the foot of a receipt."""
    return f"Total {format_price(sum(amounts))}"
