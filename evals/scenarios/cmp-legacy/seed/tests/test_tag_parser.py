from src.tag_parser import parse_tags


def test_splits_on_commas_and_strips_spaces():
    assert parse_tags("red, blue ,green") == ["red", "blue", "green"]


def test_drops_blank_tags():
    assert parse_tags("red,,blue,") == ["red", "blue"]


def test_dedupes_case_insensitively_keeping_the_first_spelling():
    assert parse_tags("Red, red, RED") == ["Red"]
