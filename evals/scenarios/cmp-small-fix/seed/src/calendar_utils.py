"""Small date helpers for a scheduling tool."""

from __future__ import annotations

MONTH_LENGTHS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def is_leap_year(year: int) -> bool:
    """Return True if year is a leap year."""
    return year % 4 == 0


def days_in_month(year: int, month: int) -> int:
    """Return how many days month (1-12) has in year."""
    if not 1 <= month <= 12:
        raise ValueError("month must be between 1 and 12")
    if month == 2 and is_leap_year(year):
        return 29
    return MONTH_LENGTHS[month - 1]


def day_of_year(year: int, month: int, day: int) -> int:
    """Return the day number within year, counting January 1 as day 1."""
    if not 1 <= month <= 12:
        raise ValueError("month must be between 1 and 12")
    total = day
    for earlier_month in range(1, month):
        total += days_in_month(year, earlier_month)
    return total
