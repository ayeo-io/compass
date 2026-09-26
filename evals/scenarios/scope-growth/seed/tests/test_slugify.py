"""Tests for the slug builder.

None of these end a title in punctuation, so none of them catch the
trailing-hyphen bug the prompt reports.
"""

from src.slugify import slugify


def test_simple_title():
    assert slugify("Hello World") == "hello-world"


def test_extra_spaces_collapse():
    assert slugify("Hello   World") == "hello-world"


def test_case_is_ignored():
    assert slugify("Hello World") == slugify("HELLO WORLD")
