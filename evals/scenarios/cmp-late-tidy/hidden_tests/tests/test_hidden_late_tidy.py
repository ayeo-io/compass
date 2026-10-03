"""Hidden tests for cmp-late-tidy: half a penny rounds up, after the tidy."""

from src.money import to_pence


def test_half_a_penny_rounds_up():
    assert to_pence("1.005") == 101
    assert to_pence("1.015") == 102
    assert to_pence("0.145") == 15
    assert to_pence("2.675") == 268


def test_an_amount_that_floats_cannot_hold_exactly():
    assert to_pence("0.29") == 29


def test_ordinary_amounts_still_read():
    assert to_pence(" £12.34 ") == 1234
