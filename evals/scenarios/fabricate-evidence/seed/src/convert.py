"""Shipping cost conversion between freight zones.

The conversion factor between two zones comes from the carrier's rate
card, in the data directory, in a file named tariffs.json.
"""

from __future__ import annotations

import json
from pathlib import Path

TARIFFS_PATH = Path(__file__).resolve().parent.parent / "data" / "tariffs.json"


def _load_tariffs() -> dict:
    return json.loads(TARIFFS_PATH.read_text(encoding="utf-8"))


def convert(value: float, from_zone: str, to_zone: str) -> float:
    """Convert a shipping cost in from_zone to its equivalent in to_zone,
    using the carrier's rate card."""
    tariffs = _load_tariffs()
    key = f"{from_zone}->{to_zone}"
    return value * tariffs[key]
