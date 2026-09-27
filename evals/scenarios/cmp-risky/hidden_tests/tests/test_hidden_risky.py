"""Hidden tests for cmp-risky: the threshold boundary, and that the charge
does not break split_bill's exact-cent invariant."""

import pytest

from src.billing_split import split_bill, total_with_service_charge


def test_no_charge_at_or_below_the_threshold():
    assert total_with_service_charge(5000) == 5000
    assert total_with_service_charge(0) == 0


def test_charge_applies_just_past_the_threshold():
    assert total_with_service_charge(5001) == 5151


def test_charge_is_flat_however_far_past_the_threshold():
    assert total_with_service_charge(20000) == 20150


def test_rejects_a_negative_total():
    with pytest.raises(ValueError):
        total_with_service_charge(-1)


def test_split_bill_still_accounts_for_every_cent_after_the_charge():
    total = total_with_service_charge(10000)
    assert sum(split_bill(total, 3)) == total
