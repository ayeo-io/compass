from src.fmt import format_amount


def test_format_amount_shows_pounds_and_pence():
    assert format_amount(1234) == "£12.34"
    assert format_amount(5) == "£0.05"
