# money-rounding

## Decided by

The accounts team

## Date

2026-09-29

## Supersedes

Nothing.

## Decision

All money is whole pence, as an int. Where a calculation gives a fraction of a penny, it rounds half up: 500.5 pence is 501. The accounts team needs this, and it applies to every function that works out an amount.

## Why

The accounts team reconciles every order to the penny, and rounds half up.

## Evidence

The order-subtotal work, which added subtotal in src/orders.py.
