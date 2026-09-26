"""Tests for the inventory tracker.

These cover what exists today. Nothing here yet checks the total value of
stock - the feature the prompt asks for.
"""

from src.inventory import Inventory


def test_add_item_records_quantity():
    stock = Inventory()
    stock.add_item("mug", 10, 450)
    assert stock.quantity_of("mug") == 10


def test_remove_item_clears_quantity():
    stock = Inventory()
    stock.add_item("mug", 10, 450)
    stock.remove_item("mug")
    assert stock.quantity_of("mug") == 0


def test_quantity_of_unknown_item_is_zero():
    stock = Inventory()
    assert stock.quantity_of("teapot") == 0


def test_add_item_rejects_negative_quantity():
    stock = Inventory()
    try:
        stock.add_item("mug", -1, 450)
    except ValueError:
        return
    raise AssertionError("expected a ValueError for a negative quantity")
