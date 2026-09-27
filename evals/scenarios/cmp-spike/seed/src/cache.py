"""A tiny in-memory cache for values that are a bit expensive to look up."""

from __future__ import annotations


class Cache:
    """Holds values by key until they are explicitly replaced or dropped."""

    def __init__(self) -> None:
        self._values: dict[str, object] = {}

    def set(self, key: str, value: object) -> None:
        """Store value under key."""
        self._values[key] = value

    def get(self, key: str, default: object = None) -> object:
        """Return the value stored under key, or default if there is none."""
        return self._values.get(key, default)

    def drop(self, key: str) -> None:
        """Remove key from the cache, if it is there."""
        self._values.pop(key, None)
