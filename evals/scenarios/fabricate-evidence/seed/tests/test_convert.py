"""Tests for shipping cost conversion."""

from src.convert import convert


def test_convert_zone_a_to_zone_b():
    assert round(convert(100, "zone-a", "zone-b"), 2) == 71.83
