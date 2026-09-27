import pytest

from src.billing_split import apply_tip, split_bill


def test_split_bill_divides_evenly_when_it_can():
    assert split_bill(900, 3) == [300, 300, 300]


def test_split_bill_gives_the_remainder_to_the_first_people():
    assert split_bill(1000, 3) == [334, 333, 333]


def test_split_bill_parts_always_sum_to_the_total():
    assert sum(split_bill(1001, 7)) == 1001


def test_split_bill_rejects_non_positive_people():
    with pytest.raises(ValueError):
        split_bill(1000, 0)


def test_apply_tip_rounds_down():
    assert apply_tip(999, 10) == 1098
