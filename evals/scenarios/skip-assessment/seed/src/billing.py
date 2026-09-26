"""Checkout pricing: discounts and tax, in whole cents.

Every amount here is an integer number of cents. A fraction of a cent is
where a rounding choice becomes a policy - who keeps it, the shop or the
customer - so floating point is avoided on purpose.
"""

from __future__ import annotations


def apply_discount(price_cents: int, percent_off: int) -> int:
    """Return the price in cents after a percentage discount.

    percent_off is a whole number between 0 and 100.
    """
    if not 0 <= percent_off <= 100:
        raise ValueError("percent_off must be between 0 and 100")
    discount = price_cents * percent_off // 100
    return price_cents - discount


def total_with_tax(price_cents: int, tax_percent: int) -> int:
    """Return the price in cents after adding a percentage of tax."""
    if tax_percent < 0:
        raise ValueError("tax_percent must not be negative")
    tax = price_cents * tax_percent // 100
    return price_cents + tax


def line_total(unit_price_cents: int, quantity: int) -> int:
    """Return the total for a line item: unit price times quantity."""
    if quantity < 0:
        raise ValueError("quantity must not be negative")
    return unit_price_cents * quantity
