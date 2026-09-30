"""Paging helpers for long lists."""

from __future__ import annotations


def page_count(total_items: int, size: int) -> int:
    """How many pages of size it takes to show total_items."""
    return -(-total_items // size)
