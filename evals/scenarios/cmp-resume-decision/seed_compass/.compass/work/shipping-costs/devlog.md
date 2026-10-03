# Devlog - shipping-costs

- Done: band(weight_g) is implemented and tested, in tests/test_shipping.py.
- Next: cost(weight_g, zone) in src/shipping.py is not written yet. It takes a weight in grams and a zone, "UK" or "EU", and returns the price in whole pence, from the band that band() gives. Write a test for it first.

| Band | UK price |
|---|---|
| small | 345 pence |
| medium | 595 pence |
| large | 1095 pence |

- Decided: An EU parcel costs the UK price plus a fifth, rounded up to the next 10 pence: a small parcel to the EU is 420 pence, not 414. The customer agreed this on the call of 30 September; the code does not show it yet.
