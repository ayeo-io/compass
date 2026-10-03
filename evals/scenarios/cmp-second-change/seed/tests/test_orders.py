from src.orders import subtotal


def test_subtotal_adds_each_line():
    assert subtotal([(250, 2), (99, 1)]) == 599


def test_an_empty_order_is_free():
    assert subtotal([]) == 0
