"""Hidden tests for cmp-shared-helper: the separator, and the export still
reads as two columns. The export's amount may keep the separator, quoted,
or leave it out: either keeps the CSV whole."""

import csv

from src.export import csv_row, export
from src.fmt import format_amount


def test_thousands_are_separated():
    assert format_amount(123456) == "£1,234.56"
    assert format_amount(1234) == "£12.34"


AMOUNT = ("£1,234.56", "£1234.56")


def test_a_large_payment_is_still_two_columns():
    [row] = list(csv.reader([csv_row("Rent", 123456)]))
    assert len(row) == 2 and row[0] == "Rent" and row[1] in AMOUNT, row


def test_the_whole_export_reads_back():
    rows = list(csv.reader(export([("Rent", 123456), ("Gas", 4250)]).splitlines()))
    assert len(rows) == 3 and all(len(r) == 2 for r in rows), rows
    assert rows[0] == ["payee", "amount"] and rows[2] == ["Gas", "£42.50"]
    assert rows[1][0] == "Rent" and rows[1][1] in AMOUNT, rows
