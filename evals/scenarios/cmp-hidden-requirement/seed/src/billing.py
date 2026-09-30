"""Bill helpers for splitting costs between friends."""

from __future__ import annotations


def format_pence(amount: int) -> str:
    """Show an amount of pence as pounds, e.g. 1234 -> '£12.34'."""
    pounds, pence = divmod(amount, 100)
    return f"£{pounds}.{pence:02d}"


def add_tip(total: int, percent: int) -> int:
    """Return total plus a tip of percent, rounded down to whole pence."""
    return total + total * percent // 100
