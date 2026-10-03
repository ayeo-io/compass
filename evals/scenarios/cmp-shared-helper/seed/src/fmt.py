"""How amounts of money are shown."""

from __future__ import annotations


def format_amount(pence: int) -> str:
    """Show pence as pounds, for example 123456 -> "£1234.56"."""
    pounds, rest = divmod(pence, 100)
    return f"£{pounds}.{rest:02d}"
