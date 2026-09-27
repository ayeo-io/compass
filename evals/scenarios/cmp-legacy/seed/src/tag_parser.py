"""Turns a raw tag string from an import file into a clean tag list."""

from __future__ import annotations


def parse_tags(raw: str) -> list[str]:
    """Split raw on commas into a clean list of tags."""
    seen_lower: set[str] = set()
    tags: list[str] = []
    for chunk in raw.split(","):
        tag = chunk.strip()
        if not tag:
            continue
        key = tag.lower()
        if key in seen_lower:
            continue
        seen_lower.add(key)
        tags.append(tag)
    return tags
