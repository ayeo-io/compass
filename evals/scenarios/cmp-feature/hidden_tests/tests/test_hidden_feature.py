"""Hidden tests for cmp-feature: longest_track does not exist on the seed."""

import pytest

from src.playlist import Track, longest_track


def test_returns_the_title_of_the_longest_track():
    playlist = [Track("Intro", 60), Track("Main Theme", 240), Track("Outro", 90)]
    assert longest_track(playlist) == "Main Theme"


def test_a_tie_goes_to_the_track_added_first():
    playlist = [Track("First", 200), Track("Second", 200)]
    assert longest_track(playlist) == "First"


def test_an_empty_playlist_raises_value_error():
    with pytest.raises(ValueError):
        longest_track([])
