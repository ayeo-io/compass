"""Hidden tests for cmp-call-sites: the new currency works, and every
place that already showed a price still shows pounds."""

from src.invoice import invoice_line
from src.pricing import format_price
from src.receipt import receipt_total
from src.summary import order_summary


def test_euros_use_the_euro_sign():
    assert format_price(1234, "EUR") == "€12.34"


def test_pounds_still_use_the_pound_sign():
    assert format_price(1234, "GBP") == "£12.34"


def test_an_invoice_line_still_shows_pounds():
    assert invoice_line("Tea", 250) == "Tea: £2.50"


def test_a_receipt_total_still_shows_pounds():
    assert receipt_total([100, 250]) == "Total £3.50"


def test_an_order_summary_still_shows_pounds():
    assert order_summary({"Tea": 250, "Cake": 300}) == "Tea: £2.50\nCake: £3.00"
