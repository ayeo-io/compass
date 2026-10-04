# Feature Specification: Shipping Costs

**Feature Branch**: `001-shipping-costs`

**Created**: 2026-09-30

**Status**: In progress

## User Scenarios & Testing

### User Story 1 - Price a parcel (Priority: P1)

A shop owner wants the shipping price of a parcel from its weight and
where it is going.

## Requirements

- **FR-001**: band(weight_g) puts a parcel in the small, medium or large band.
- **FR-002**: cost(weight_g, zone) in src/shipping.py is not written yet. It takes a weight in grams and a zone, "UK" or "EU", and returns the price in whole pence, from the band that band() gives.
- **FR-003**: UK prices follow this table:

| Band | UK price |
|---|---|
| small | 345 pence |
| medium | 595 pence |
| large | 1095 pence |

- **FR-004**: An EU parcel costs the UK price plus a fifth, rounded up to the next 10 pence: a small parcel to the EU is 420 pence, not 414. The customer agreed this on the call of 30 September; the code does not show it yet.
