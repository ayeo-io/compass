"""The one list of YAML keys `tests/test_writing_style.py`'s `_yaml_spans`
reads as prose, and `scripts/compare-behaviour.py`'s YAML reader blanks as
prose - so the two halves cannot disagree about what prose is.

Before this module existed, each file held its own copy, and the two
disagreed: this list carried `biases` and `tests/test_writing_style.py`'s
did not. `routing-policy.yml`'s `biases:` block was reworded by
this issue and no sweep read it, because the sweep's copy of this list
never named the key - found and fixed as finding 1, `review-dimensions.md`.
"""
from __future__ import annotations

PROSE_KEYS = frozenset({
    "description", "statement", "rationale", "name", "help",
    "means", "not", "context", "why", "reason", "also",
    "appears_in", "referent", "biases",
})
