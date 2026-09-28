"""Hidden tests for cmp-small-fix: the century exception to the leap-year
rule, which the seed's own tests never exercised."""

from src.calendar_utils import is_leap_year


def test_century_years_are_only_leap_when_divisible_by_400():
    assert is_leap_year(1900) is False
    assert is_leap_year(2000) is True
    assert is_leap_year(2100) is False
    assert is_leap_year(2400) is True


def test_ordinary_years_are_unaffected():
    assert is_leap_year(2023) is False
    assert is_leap_year(2024) is True
