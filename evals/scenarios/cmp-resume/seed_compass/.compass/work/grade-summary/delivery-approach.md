# Delivery approach - grade-summary

**Approach:** quick fix · **Assessed:** 2026-09-27 · **Gates:** 3

## The four dimensions

| Dimension | Value | Why |
|---|---|---|
| Risk | `contained` | summarize is an addition to one module; nothing else calls it yet. |
| Familiarity | `brownfield-mapped` | parse_scores is already implemented and tested in this module. |
| Size | `small` | One function, summarize, and its test. |
| Goal and role | `delivery`, engineer | The devlog states the outcome: a report of the average score and the top and bottom scorer. |

No policy rule fired. The candidate is a quick fix.

## The intent

- `INT-1`: the issue description - summarize should return a dict with
  the average score, and the top and bottom scorer by name.

## The scenario

- `TRC-A1`: summarize returns a dict with the average score, and the
  top and bottom scorer, tested in the grades module's own test file.

## De-scope ledger

| Stage | Action | Safe to skip because |
|---|---|---|
| Refine | collapsed | The devlog states the one function and its shape. |
| Plan | collapsed | One function, one test file, no design decision. |
| Breakdown | skipped | One subtask of work. |

## Next stage

Read `devlog.md` for what is already done and what is next; do not
decide the next step from anywhere else.
