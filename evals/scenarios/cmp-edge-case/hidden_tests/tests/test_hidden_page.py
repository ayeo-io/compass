"""Hidden tests for cmp-edge-case: every rule the prompt states."""

import pytest

from src.paging import page

ITEMS = list(range(10))


def test_the_first_page():
    assert page(ITEMS, 1, 3) == [0, 1, 2]


def test_the_last_page_can_be_short():
    assert page(ITEMS, 4, 3) == [9]


def test_a_page_past_the_end_is_empty():
    assert page(ITEMS, 5, 3) == []


@pytest.mark.parametrize("number", [0, -1])
def test_a_number_below_one_raises(number):
    with pytest.raises(ValueError):
        page(ITEMS, number, 3)


@pytest.mark.parametrize("size", [0, -2])
def test_a_size_below_one_raises(size):
    with pytest.raises(ValueError):
        page(ITEMS, 1, size)
