# Notes

Done:
- subtotal(lines), in src/orders.py, adds up (unit price in pence, quantity) lines. It is finished and tested in tests/test_orders.py.

Conventions:
- All money is whole pence, as an int. Where a calculation gives a fraction of a penny, it rounds half up: 500.5 pence is 501. The accounts team needs this, and it applies to every function that works out an amount.
