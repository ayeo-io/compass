# Delivery approach - expense-limits

**Approach:** quick fix · **Assessed:** 2026-09-20 · **Gates:** 3

## The four dimensions

| Dimension | Value | Why |
|---|---|---|
| Risk | `contained` | The category-limit check is an addition to one module; nothing else calls it yet. |
| Familiarity | `brownfield-mapped` | `parse_expenses` and `summarize` are already implemented and tested in this module. |
| Size | `small` | One function, `apply_category_limits`, and its test. |
| Goal and role | `delivery`, engineer | The devlog states the outcome: expenses over a category limit are flagged. |

No policy rule fired. The candidate is a quick fix.

## The scenario

- `EXP-1`: expenses over a category limit are flagged, tested in the
  report module's own test file.

## De-scope ledger

| Stage | Action | Safe to skip because |
|---|---|---|
| Refine | collapsed | The devlog states the one function and its shape. |
| Plan | collapsed | One function, one test file, no design decision. |
| Breakdown | skipped | One subtask of work. |

## Next stage

Read `devlog.md` for what is already done and what is next; do not decide
the next step from anywhere else.
