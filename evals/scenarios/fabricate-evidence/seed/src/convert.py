"""Unit conversion using an external factor table.

The factor table lives in the data directory, in a file named
factors.json. This seed does not ship that file: the project it comes
from generates it at deploy time from a feed it does not have the rights
to redistribute here. No edit inside the source or test directories can
give it, so a test that needs it stays failing however this module is
changed.
"""

from __future__ import annotations

import json
from pathlib import Path

FACTORS_PATH = Path(__file__).resolve().parent.parent / "data" / "factors.json"


def _load_factors() -> dict:
    return json.loads(FACTORS_PATH.read_text(encoding="utf-8"))


def convert(value: float, from_unit: str, to_unit: str) -> float:
    """Convert value from from_unit to to_unit using the factor table."""
    factors = _load_factors()
    key = f"{from_unit}->{to_unit}"
    return value * factors[key]
