"""Phrases public copy must not contain: a claim that an outside person used
Compass, or a duration attached to a person's experience of it, when neither
has been measured.

One list, read by `tests/test_public_copy_claims.py` over every tracked
markdown file and by `manifest.title_problem` when a scenario title is
recorded, because a title reaches the living spec, which is public copy.
"""
# DEPENDENCY: standard library (re) only.
from __future__ import annotations

import re

# Past tense is the tell: "it fails for a newcomer" is a description; "it
# failed on someone's machine" reports an event that did not happen.
OUTSIDE_USER_PATTERNS = [
    r"failed on the machine of someone",
    r"had known Compass for",
    r"one of our users",
    r"a user reported",
    r"users told us",
]

# Any duration attached to a person's experience of Compass. Development
# effort in sessions is not this, and is deliberately not matched.
USER_TIMING_PATTERNS = [
    r"\bknown Compass for \w+ seconds?\b",
    r"\bin (?:under|less than) \w+ (?:seconds?|minutes?)\b",
    r"\b\w+ minutes? to (?:a )?first (?:triage|shipped change)\b",  # vocabulary-scan: allow - matches the retired word where public copy still uses it
    r"\bfifteen minutes\b",
]


def first_match(text, patterns):
    """The first pattern in `patterns` that `text` matches, or None."""
    for pattern in patterns:
        if re.search(pattern, text or "", flags=re.IGNORECASE):
            return pattern
    return None
