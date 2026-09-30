from src.pricing import format_price


def test_format_price_shows_pounds_and_pence():
    assert format_price(1234) == "£12.34"
    assert format_price(5) == "£0.05"
