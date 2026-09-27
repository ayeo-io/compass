from src.grades import parse_scores


def test_parses_valid_lines():
    assert parse_scores(["Ada,91", "Grace,88"]) == [("Ada", 91), ("Grace", 88)]


def test_skips_lines_without_a_comma():
    assert parse_scores(["Ada,91", "not a score line"]) == [("Ada", 91)]


def test_skips_a_non_numeric_score():
    assert parse_scores(["Ada,91", "Grace,ninety"]) == [("Ada", 91)]
