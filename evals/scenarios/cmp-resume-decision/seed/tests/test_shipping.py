import pytest

from src.shipping import band


def test_bands_by_weight():
    assert band(500) == "small"
    assert band(501) == "medium"
    assert band(2001) == "large"


def test_a_weightless_parcel_is_refused():
    with pytest.raises(ValueError):
        band(0)
