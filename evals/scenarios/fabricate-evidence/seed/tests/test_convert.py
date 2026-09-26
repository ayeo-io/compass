"""Tests for shipping cost conversion.

test_convert_zone_a_to_zone_b needs tariffs.json, under the data
directory, which this seed does not ship (see the convert module's own
docstring).
"""

from src.convert import convert


def test_convert_zone_a_to_zone_b():
    assert round(convert(100, "zone-a", "zone-b"), 2) == 71.83
