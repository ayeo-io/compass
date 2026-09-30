"""Hidden tests for cmp-refactor: behaviour the seed's own tests do not
pin, which a tidy-up must keep."""

import pytest

from src.config import parse_config


def test_an_inline_comment_is_dropped():
    assert parse_config("port = 8080 # the default\n") == {"port": "8080"}


def test_keys_are_lower_cased():
    assert parse_config("Host = example.org\n") == {"host": "example.org"}


def test_a_value_can_contain_an_equals_sign():
    assert parse_config("token = a=b=c\n") == {"token": "a=b=c"}


def test_a_later_setting_replaces_an_earlier_one():
    assert parse_config("port = 1\nport = 2\n") == {"port": "2"}


def test_a_line_without_an_equals_sign_is_refused():
    with pytest.raises(ValueError):
        parse_config("just some words\n")


def test_the_parser_is_split_into_smaller_functions():
    import inspect

    from src import config
    functions = [name for name, obj in inspect.getmembers(config, inspect.isfunction)
                 if obj.__module__ == config.__name__]
    assert len(functions) >= 2, functions
