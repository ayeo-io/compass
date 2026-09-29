"""Splitting a shared bill in whole cents, with no floating point."""

from __future__ import annotations


def split_bill(total_cents: int, n_people: int) -> list[int]:
    """Split total_cents as evenly as possible across n_people.

    Every person gets total_cents // n_people, and the first
    total_cents % n_people people get one extra cent, so the parts
    always add up to exactly total_cents.
    """
    if n_people <= 0:
        raise ValueError("n_people must be positive")
    if total_cents < 0:
        raise ValueError("total_cents must not be negative")
    base, remainder = divmod(total_cents, n_people)
    return [base + 1 if i < remainder else base for i in range(n_people)]


def apply_tip(total_cents: int, tip_percent: int) -> int:
    """Return total_cents plus a tip_percent percentage, rounded down."""
    if tip_percent < 0:
        raise ValueError("tip_percent must not be negative")
    return total_cents + total_cents * tip_percent // 100
