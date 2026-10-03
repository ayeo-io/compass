"""Order totals."""

from __future__ import annotations


def subtotal(lines: list[tuple[int, int]]) -> int:
    """The subtotal of (unit price in pence, quantity) lines, in pence."""
    return sum(price * quantity for price, quantity in lines)
