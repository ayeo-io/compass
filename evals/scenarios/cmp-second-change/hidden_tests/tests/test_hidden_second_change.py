"""Hidden tests for cmp-second-change: the rounding rule the first piece of
work recorded."""

from src.orders import discount


def test_half_a_penny_rounds_up():
    assert discount(1001, 50) == 501


def test_a_half_rounds_up_from_an_odd_amount_too():
    assert discount(999, 50) == 500


def test_the_result_is_whole_pence():
    assert isinstance(discount(1000, 10), int)
    assert discount(1000, 10) == 900
