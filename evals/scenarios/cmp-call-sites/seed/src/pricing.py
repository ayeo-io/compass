"""Price formatting."""

from __future__ import annotations


def format_price(amount: int) -> str:
    """Show amount pence as pounds, e.g. 1234 -> '£12.34'."""
    pounds, pence = divmod(amount, 100)
    return f"£{pounds}.{pence:02d}"
