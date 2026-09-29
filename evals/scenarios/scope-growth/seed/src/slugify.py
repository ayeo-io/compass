"""Turn a title into a URL slug."""

from __future__ import annotations

import re

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    """Return text lower-cased, with runs of non-alphanumeric characters
    replaced by a single hyphen."""
    return _NON_ALNUM.sub("-", text.lower())
