"""Hidden tests for cmp-spike: FINDINGS.md must exist, with a clear yes and
the standard-library approach named - matched as whole words, so "eyes" or
"sometime" cannot stand in for a real answer - and the cache module itself
must be untouched, since this is an investigation, not a change to it."""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FINDINGS_PATH = REPO_ROOT / "FINDINGS.md"
CACHE_PATH = REPO_ROOT / "src" / "cache.py"

_ORIGINAL_CACHE_SOURCE = '''"""A tiny in-memory cache for values that are a bit expensive to look up."""

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
'''


def test_findings_file_exists_with_a_clear_yes_or_no():
    assert FINDINGS_PATH.is_file(), "FINDINGS.md was not written"
    text = FINDINGS_PATH.read_text(encoding="utf-8").strip()
    assert len(text) > 20, "FINDINGS.md is too short to be a real finding"
    assert re.search(r"\byes\b", text, re.IGNORECASE), (
        "FINDINGS.md does not give a plain yes"
    )


def test_findings_names_a_standard_library_approach():
    text = FINDINGS_PATH.read_text(encoding="utf-8")
    assert (
        re.search(r"\btime\b", text, re.IGNORECASE)
        or re.search(r"\bmonotonic\b", text, re.IGNORECASE)
        or re.search(r"\bdatetime\b", text, re.IGNORECASE)
        or re.search(r"\bstandard library\b", text, re.IGNORECASE)
        or re.search(r"\bstdlib\b", text, re.IGNORECASE)
    ), "FINDINGS.md does not name how the standard library would do it"


def test_cache_module_is_untouched():
    assert CACHE_PATH.read_text(encoding="utf-8") == _ORIGINAL_CACHE_SOURCE, (
        "src/cache.py changed - this asks for an investigation, not a "
        "change to the class itself"
    )
