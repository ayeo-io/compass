"""Money helpers for the shop's price list."""

from __future__ import annotations


def parse_amount(text: str) -> float:
    """Read an amount of pounds, such as "12.34" or " £12.34 ", as a number."""
    return float(text.strip().lstrip("£"))


def to_pence(text: str) -> int:
    """Read an amount of pounds as whole pence."""
    cleaned = text.strip().lstrip("£")
    return int(float(cleaned) * 100)
