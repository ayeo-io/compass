from src.invoice import invoice_line


def test_invoice_line_names_the_item_and_its_price():
    assert invoice_line("Tea", 250) == "Tea: £2.50"
