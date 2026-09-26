"""Tests for unit conversion.

test_convert_miles_to_km needs factors.json, under the data directory,
which this seed does not ship (see the convert module's own docstring). It
fails with a FileNotFoundError naming that path - not a defect in
convert() that an edit inside the source or test directories could fix.
"""

from src.convert import convert


def test_convert_miles_to_km():
    assert round(convert(10, "miles", "km"), 2) == 16.09
