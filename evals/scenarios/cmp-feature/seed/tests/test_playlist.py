from src.playlist import Track, add_track, total_duration, track_titles


def test_add_track_appends_to_the_playlist():
    playlist: list[Track] = []
    add_track(playlist, "Intro", 60)
    assert track_titles(playlist) == ["Intro"]


def test_add_track_rejects_a_non_positive_duration():
    playlist: list[Track] = []
    try:
        add_track(playlist, "Silence", 0)
    except ValueError:
        return
    raise AssertionError("expected a ValueError for a non-positive duration")


def test_total_duration_sums_every_track():
    playlist = [Track("Intro", 60), Track("Main Theme", 240)]
    assert total_duration(playlist) == 300


def test_track_titles_keeps_playlist_order():
    playlist = [Track("Intro", 60), Track("Main Theme", 240), Track("Outro", 90)]
    assert track_titles(playlist) == ["Intro", "Main Theme", "Outro"]
