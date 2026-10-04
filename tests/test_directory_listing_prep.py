"""Compass meets two of the plugin directory's checks before submission.

The directory refuses a file over 5 MiB, and its security scan needs the
README to say what the plugin runs, sends and fetches. The icon was 6.6 MiB,
and no section said either.

Scenario id: DL-1 (issue `directory-listing-prep`).
"""
from __future__ import annotations

import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ICON = ROOT / "assets" / "compass-icon.png"
LIMIT = 5 * 1024 * 1024


def _png_size(path):
    with path.open("rb") as fh:
        head = fh.read(24)
    assert head[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    return struct.unpack(">II", head[16:24])


def test_dl_1_the_icon_is_under_the_limit_and_square():
    assert ICON.stat().st_size < LIMIT, ICON.stat().st_size
    width, height = _png_size(ICON)
    assert width == height >= 256


def test_dl_1_the_readme_says_what_compass_runs_sends_and_fetches():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    section = readme.split("## What Compass runs, sends and fetches", 1)[1]
    section = section.split("\n## ", 1)[0]
    for named in ("compass intent ingest", "compass record sync",
                  "compass run", "command-passes", "evals/harness.py",
                  "transcript"):
        assert named in section, named
