"""The monthly spending export, one CSV line per payment."""

from __future__ import annotations

from src.fmt import format_amount


def csv_row(name: str, pence: int) -> str:
    """One line of the export: the payee, then the amount."""
    return f"{name},{format_amount(pence)}"


def export(payments: list[tuple[str, int]]) -> str:
    """The whole export, a header and one line per payment."""
    lines = ["payee,amount"] + [csv_row(name, pence) for name, pence in payments]
    return "\n".join(lines) + "\n"
