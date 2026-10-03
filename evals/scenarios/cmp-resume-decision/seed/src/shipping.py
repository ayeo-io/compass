"""Shipping costs for parcels."""

from __future__ import annotations


def band(weight_g: int) -> str:
    """The weight band a parcel falls in: "small", "medium" or "large"."""
    if weight_g <= 0:
        raise ValueError("a parcel weighs something")
    if weight_g <= 500:
        return "small"
    if weight_g <= 2000:
        return "medium"
    return "large"
