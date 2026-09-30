from src.billing import add_tip, format_pence


def test_format_pence_shows_pounds_and_pence():
    assert format_pence(1234) == "£12.34"
    assert format_pence(5) == "£0.05"


def test_add_tip_rounds_down_to_whole_pence():
    assert add_tip(1000, 12) == 1120
    assert add_tip(999, 10) == 1098
