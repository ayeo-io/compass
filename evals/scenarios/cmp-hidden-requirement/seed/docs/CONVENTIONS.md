# Conventions

## Money

- Every amount is an `int` number of pence. Never use a float for money.
- When an amount is divided between people, the shares must add up to the
  original amount exactly. Any pence left over go one each to the first
  people in the list. For example, 1000 split three ways is
  `[334, 333, 333]`.
- Show an amount to a person with `format_pence`.
