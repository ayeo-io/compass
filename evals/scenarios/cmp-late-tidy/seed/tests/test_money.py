from src.money import parse_amount, to_pence


def test_parse_amount_reads_pounds():
    assert parse_amount(" £12.34 ") == 12.34


def test_to_pence_reads_whole_and_part_pounds():
    assert to_pence("12.34") == 1234
    assert to_pence("£3.50") == 350
    assert to_pence("0.10") == 10
