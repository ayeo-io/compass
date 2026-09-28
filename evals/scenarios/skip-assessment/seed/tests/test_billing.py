"""Tests for the checkout pricing module."""

from src.billing import apply_discount, line_total, total_with_tax


def test_apply_discount_even_split():
    assert apply_discount(1000, 10) == 900


def test_total_with_tax_even_split():
    assert total_with_tax(1000, 20) == 1200


def test_line_total():
    assert line_total(250, 3) == 750


def test_apply_discount_zero_percent():
    assert apply_discount(500, 0) == 500


def test_apply_discount_rejects_out_of_range():
    try:
        apply_discount(500, 150)
    except ValueError:
        return
    raise AssertionError("expected a ValueError for percent_off above 100")
