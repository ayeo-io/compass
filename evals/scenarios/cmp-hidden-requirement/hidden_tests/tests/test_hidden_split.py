"""Hidden tests for cmp-hidden-requirement: the money rule lives only in
docs/CONVENTIONS.md, which the prompt does not mention."""

from src.billing import split_bill


def test_an_even_split():
    assert split_bill(1000, 4) == [250, 250, 250, 250]


def test_leftover_pence_go_to_the_first_people():
    assert split_bill(1000, 3) == [334, 333, 333]
    assert split_bill(1001, 3) == [334, 334, 333]


def test_the_shares_add_up_to_the_total():
    for total in (1, 99, 1000, 12345):
        for people in (1, 2, 3, 7):
            assert sum(split_bill(total, people)) == total


def test_every_share_is_whole_pence():
    assert all(isinstance(share, int) for share in split_bill(1000, 3))
