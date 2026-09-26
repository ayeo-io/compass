"""Tests for the text utilities."""

from src.textutils import word_count


def test_word_count_simple():
    assert word_count("hello world") == 2


def test_word_count_extra_spaces():
    assert word_count("  hello   world  ") == 2


def test_word_count_empty_string():
    assert word_count("") == 0
