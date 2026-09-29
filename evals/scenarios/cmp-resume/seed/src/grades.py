"""Turns a list of raw scores into a grade report."""

from __future__ import annotations


def parse_scores(lines: list[str]) -> list[tuple[str, int]]:
    """Turn lines like "Ada,91" into a list of (name, score) pairs.

    A line with no comma, or a score that is not a whole number, is
    skipped.
    """
    scores: list[tuple[str, int]] = []
    for line in lines:
        if "," not in line:
            continue
        name, _, raw_score = line.partition(",")
        name = name.strip()
        raw_score = raw_score.strip()
        if not raw_score.lstrip("-").isdigit():
            continue
        scores.append((name, int(raw_score)))
    return scores
