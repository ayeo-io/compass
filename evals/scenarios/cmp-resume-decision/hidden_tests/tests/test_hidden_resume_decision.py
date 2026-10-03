"""Hidden tests for cmp-resume-decision: the price table, and the EU rule
the record holds."""

from src.shipping import cost


def test_uk_prices_follow_the_table():
    assert cost(400, "UK") == 345
    assert cost(1500, "UK") == 595
    assert cost(3000, "UK") == 1095


def test_eu_prices_add_a_fifth_rounded_up_to_the_next_ten_pence():
    assert cost(400, "EU") == 420
    assert cost(1500, "EU") == 720
    assert cost(3000, "EU") == 1320
