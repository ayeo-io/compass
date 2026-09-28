"""Hidden tests for cmp-resume: summarize does not exist on the seed."""

import pytest

from src.grades import parse_scores, summarize


def test_summarize_reports_average_highest_and_lowest():
    scores = parse_scores(["Ada,91", "Grace,88", "Linus,75"])
    result = summarize(scores)
    assert result["average"] == pytest.approx((91 + 88 + 75) / 3)
    assert result["highest"] == "Ada"
    assert result["lowest"] == "Linus"


def test_a_tie_goes_to_whichever_student_comes_first():
    result = summarize([("Ada", 90), ("Grace", 90)])
    assert result["highest"] == "Ada"
    assert result["lowest"] == "Ada"


def test_empty_scores_raises_value_error():
    with pytest.raises(ValueError):
        summarize([])
