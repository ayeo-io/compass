"""The rehearsal's token figures never reach a tracked file.

The measurements are real, but they are one run of one issue with a
rehearsal's worth of detours in it - diagnosing someone else's broken test
harness, evaluating four alternative repositories, two regression
investigations. They are an upper bound, not a benchmark.

Two reasons they stay internal. A single run is not evidence, and a number
gets quoted without its caveat: quoting "57.4M tokens" would be true and
badly misleading, because cache reads - the cheapest token class - exceed new
input by roughly 85x. And leading on efficiency undercuts the claim Compass
actually makes, which is that it deliberately does *more* work.

This guard checks the tracked surface, which is what a reader outside this
machine can see. The figures themselves live in `docs/analysis/`, which is
gitignored, so they stay private by construction - and this test keeps
working on a clean clone where those files are absent.

Scenario ids: see the issue's acceptance criteria (RR-4).
"""
from __future__ import annotations

import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent

# The distinctive measured values. Each is matched with optional thousands
# separators so a reformatted quotation cannot slip past, and the short
# rounded forms people actually write in captions are listed too.
FIGURES = (
    "661312", "57411280", "302698",          # the totals
    "241572", "6720715", "73193",            # Part 0 prep
    "419740", "50690565", "229505",          # the Compass flow
)
ROUNDED = (
    r"57\.4\s*m\s+tokens", r"57\.5\s*m\s+tokens",
    r"302,?698", r"661,?312",
)

# This file necessarily contains the figures it bans, and so does the issue's
# own acceptance criteria if it ever quotes one.
SELF = pathlib.Path(__file__).name


def _tracked_files() -> list[pathlib.Path]:
    """Every file git actually tracks.

    Deliberately not a directory walk: the point of this guard is the
    *published* surface, and gitignored planning documents are not published.
    """
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT,
        capture_output=True, text=True, check=True,
    ).stdout
    return [ROOT / p for p in out.split("\0") if p]


def _normalise(text: str) -> str:
    """Digits only, so 661,312 / 661 312 / 661312 all compare equal."""
    return re.sub(r"[,\s_]", "", text)


def test_rr_4_figures_absent_from_tracked_files():
    hits = []
    for path in _tracked_files():
        if path.name == SELF or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue                      # binary or unreadable: not prose
        flat = _normalise(text)
        for figure in FIGURES:
            if figure in flat:
                hits.append(f"{path.relative_to(ROOT)}: {figure}")
        low = text.lower()
        for pattern in ROUNDED:
            if re.search(pattern, low):
                hits.append(f"{path.relative_to(ROOT)}: /{pattern}/")

    assert not hits, (
        "the rehearsal's token measurements appear in tracked file(s), which "
        "publishes them:\n  " + "\n  ".join(sorted(set(hits)))
        + "\n\nThey are internal: one run, with a rehearsal's worth of "
          "detours, and a total dominated by cache reads. Keep them in "
          "docs/analysis/ (gitignored)."
    )
