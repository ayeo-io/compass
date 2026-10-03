# Feature Specification: Order Subtotal

**Feature Branch**: `001-order-subtotal`

**Created**: 2026-09-29

**Status**: Complete

## User Scenarios & Testing

### User Story 1 - Total an order (Priority: P1)

A shop owner wants an order's subtotal from its lines.

## Requirements

- **FR-001**: subtotal(lines), in src/orders.py, adds up (unit price in pence, quantity) lines. It is finished and tested in tests/test_orders.py.
- **FR-002**: All money is whole pence, as an int. Where a calculation gives a fraction of a penny, it rounds half up: 500.5 pence is 501. The accounts team needs this, and it applies to every function that works out an amount.
