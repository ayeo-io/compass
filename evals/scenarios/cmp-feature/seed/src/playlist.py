"""A small playlist tracker."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Track:
    title: str
    duration_seconds: int


def add_track(playlist: list[Track], title: str, duration_seconds: int) -> None:
    """Append a track to playlist."""
    if duration_seconds <= 0:
        raise ValueError("duration_seconds must be positive")
    playlist.append(Track(title, duration_seconds))


def total_duration(playlist: list[Track]) -> int:
    """Return the total duration of playlist, in seconds."""
    return sum(track.duration_seconds for track in playlist)


def track_titles(playlist: list[Track]) -> list[str]:
    """Return the titles in playlist, in playlist order."""
    return [track.title for track in playlist]
