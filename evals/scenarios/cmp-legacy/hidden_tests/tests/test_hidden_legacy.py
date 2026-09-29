"""Hidden tests for cmp-legacy: semicolon support, plus the dedupe rule the
seed's tests already pin, now checked with both separators mixed."""

from src.tag_parser import parse_tags


def test_accepts_semicolons_as_well_as_commas():
    assert parse_tags("red; blue, green") == ["red", "blue", "green"]


def test_mixed_separators_still_dedupe_case_insensitively_keeping_first_spelling():
    assert parse_tags("Red; red, RED") == ["Red"]


def test_blank_tags_from_either_separator_are_dropped():
    assert parse_tags("red;;blue,,green;") == ["red", "blue", "green"]
