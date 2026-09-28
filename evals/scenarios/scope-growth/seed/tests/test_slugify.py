"""Tests for the slug builder."""

from src.slugify import slugify


def test_simple_title():
    assert slugify("Hello World") == "hello-world"


def test_extra_spaces_collapse():
    assert slugify("Hello   World") == "hello-world"


def test_case_is_ignored():
    assert slugify("Hello World") == slugify("HELLO WORLD")
