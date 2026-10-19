# compass_pkg.classify_lists - read two trigger lists as sets of entries
"""Read the two sides of a list parameter as sets of exact entries (ADR-073)."""
# DEPENDENCY: standard library only. compass_pkg.classify imports `entry_sets`.
from __future__ import annotations


def _entry(item):
    """One entry of a trigger list as a hashable value, or None when its shape
    is not one the check reads: a non-empty string, or a pair with exactly the
    keys `path` and `contains`, both non-empty strings."""
    if isinstance(item, str):
        return item or None
    if isinstance(item, dict) and set(item) == {"path", "contains"}:
        pair = (item["path"], item["contains"])
        if all(isinstance(part, str) and part for part in pair):
            return pair
    return None


def _entries(value):
    """A list as the set of its exact entries, so order and repeats do not
    matter. None when the value is not a list or holds an entry the check
    cannot read (an empty string, or a mapping without exactly the keys `path`
    and `contains`): the check skips such an entry silently, and the
    classifier does not call it safe."""
    if not isinstance(value, (list, tuple)):
        return None
    found = {_entry(item) for item in value}
    return None if None in found else found


def entry_sets(p, c):
    """The two sides as sets of entries, or None when either side is absent or
    malformed."""
    p, c = _entries(p), _entries(c)
    return None if p is None or c is None else (p, c)
