"""Tests for the date helpers, written before the century bug was found."""

from src.calendar_utils import day_of_year, days_in_month, is_leap_year


def test_is_leap_year_simple_cases():
    assert is_leap_year(2024) is True
    assert is_leap_year(2023) is False


def test_days_in_month_handles_february_in_a_leap_year():
    assert days_in_month(2024, 2) == 29


def test_days_in_month_rejects_a_bad_month():
    try:
        days_in_month(2024, 13)
    except ValueError:
        return
    raise AssertionError("expected a ValueError for month 13")


def test_day_of_year_counts_from_january_first():
    assert day_of_year(2023, 1, 1) == 1
    assert day_of_year(2023, 3, 1) == 60
