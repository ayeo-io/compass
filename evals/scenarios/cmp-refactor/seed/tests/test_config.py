from src.config import parse_config


def test_reads_key_value_pairs():
    assert parse_config("host = example.org\nport=8080\n") == {
        "host": "example.org", "port": "8080"}


def test_skips_blank_lines_and_comment_lines():
    text = "# settings\n\nhost = example.org\n   # indented comment\n"
    assert parse_config(text) == {"host": "example.org"}
