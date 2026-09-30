"""Order summaries sent by email."""

from __future__ import annotations

from src.pricing import format_price


def order_summary(order: dict[str, int]) -> str:
    """One line per item, in the order given."""
    return "\n".join(f"{item}: {format_price(amount)}"
                     for item, amount in order.items())
