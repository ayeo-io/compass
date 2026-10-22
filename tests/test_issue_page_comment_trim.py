"""A line that is only an HTML comment is dropped from an issue page ask, whichever
way the comment ends (code scanning alert py/bad-tag-filter). HTML also closes a
comment with `--!>`."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "cli"))
from compass_pkg import issue_page  # noqa: E402


def test_a_line_holding_only_a_comment_is_dropped_whichever_way_it_ends():
    lines = ["<!-- the template's instruction -->", "<!-- the other ending --!>", "The ask."]
    assert issue_page._trim(lines) == ["The ask."]


def test_a_comment_that_holds_a_newline_is_dropped():
    # Code scanning alert py/bad-tag-filter: the pattern must not stop at a newline.
    assert issue_page._trim(["<!-- one\nline -->", "The ask."]) == ["The ask."]


def test_a_quoted_marker_and_the_render_marker_stay():
    lines = ["text <!-- not alone --> more", "<!-- compass:render coverage -->"]
    assert issue_page._trim(lines) == lines
