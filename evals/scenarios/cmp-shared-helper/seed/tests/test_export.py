from src.export import csv_row, export


def test_a_row_names_the_payee_and_the_amount():
    assert csv_row("Gas", 4250) == "Gas,£42.50"


def test_the_export_has_a_header():
    assert export([("Gas", 4250)]).splitlines()[0] == "payee,amount"
