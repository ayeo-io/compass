"""Stock levels for a small shop."""

from __future__ import annotations


class Inventory:
    """Tracks items on hand, each with a quantity and a unit price."""

    def __init__(self) -> None:
        self._items: dict[str, tuple[int, int]] = {}

    def add_item(self, name: str, quantity: int, unit_price_cents: int) -> None:
        """Record quantity units of name at unit_price_cents each."""
        if quantity < 0:
            raise ValueError("quantity must not be negative")
        self._items[name] = (quantity, unit_price_cents)

    def remove_item(self, name: str) -> None:
        """Drop name from the inventory."""
        self._items.pop(name, None)

    def quantity_of(self, name: str) -> int:
        """Return how many units of name are on hand, or zero."""
        return self._items.get(name, (0, 0))[0]
