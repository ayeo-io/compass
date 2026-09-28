# Plan - expense limits

Done:
- parse_expenses and summarize are implemented and tested, in the report
  module's own test file.

Next:
- Implement apply_category_limits(expenses, limits) in the report module.
  It takes the totals summarize returns and a mapping of category to a
  limit in cents, and returns the categories over their limit. Write a
  test for it first.
