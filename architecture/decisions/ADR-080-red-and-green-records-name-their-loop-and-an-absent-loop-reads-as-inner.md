---
id: ADR-080
title: Red and green records name their loop, and an absent loop reads as inner
status: accepted
date: 2026-10-31
supersedes: ''
superseded_by: ''
---

## Context

Guardrail `G1` is met today by any test that failed and then passed, so a unit test that never leaves the process meets it for a change a client can observe. Strategy `S17`, the four-layer acceptance strategy, needs an in-scope issue to show an outer-loop red and an outer-loop green: a failure and a pass of the acceptance suite, driven through a client interface. No red or green record says which loop it came from, and records written before 8.0.0 must stay valid (ADR-006).

## Decision

1. **The field.** `compass tdd-red` and `compass tdd-green` take `--loop outer|inner` and write `loop` on every new record. Any other value is refused with exit 2 before the test runs, so no record is written.
2. **The default.** With no `--loop`, the loop is `outer` when the issue's approach is quick-fix and `acceptance_strategy.in_scope` is true, and `inner` everywhere else. A quick fix has one scenario, and its declared test is that scenario's acceptance test. `compass quick-fix finish` takes `--loop` with the same default and passes it to its green. `--loop inner` always records inner. Decided by jed72 (owner), 2026-10-31.
3. **The reader.** `acceptance_strategy.loop_of(record)` is the one reader. It returns `outer` only for a record that says `outer`. A record with no field, or with any other value, reads as `inner`.
4. **The check.** `outer-loop-recorded` is a blocking check outside every gate, in no lock, as `nfr-rows-resolved` is (ADR-064). It asks `acceptance_strategy.in_scope` (ADR-079) and declines when the strategy does not apply. On an in-scope issue it fails when there is no outer-loop red, no outer-loop green, or no outer-loop green on the current tree. One finding names the issue and each fault. `suite-passed` does not change.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| A new evidence type for outer-loop records | A type is what gates already read | The locked gates `G1` and `G4` would need to accept it, and a locked list cannot change for a strategy |
| Decide the loop from the test path | No new field | Compass would read the project's layout, and it reads records, never project code |
| Make every quick fix pass `--loop outer` | No new default rule | Every quick-fix flow and its documents would change to give the same answer |
| Keep the check advisory until #328 in ayeo-io/compass-delivery lands | No quick fix fails meanwhile | The guarantee would ship off until the last item of the strategy |
| Write the field only for `outer` | Smaller records | A reader could not tell an inner record written now from one written before the field existed |

## Consequences

- An issue assessed before the strategy, an out-of-scope issue, a spike and an opted-out project see no new finding.
- The later items of the strategy read the loop through `loop_of`: the check of `attempts`, and the candidate and client fields, read only outer-loop records.
- An in-scope quick fix records the outer loop without a flag, so `quick-fix finish` passes the check as before. A quick fix whose test is a unit test must say `--loop inner`, and then fails the check.
- A team on the regular or full approach that records its acceptance run without `--loop outer` sees the check fail with "no outer-loop green", which names the flag.

## References

- The technical design of the issue `loop-marking` (ayeo-io/compass-delivery#323), decisions `DD-1` to `DD-3`, and the plan of the issue `atdd-strategy`, decisions `DD-1` and `DD-6`. Both are issue documents kept in the delivery record.
- `cli/compass_pkg/acceptance_strategy.py` (`loop_of`), `cli/compass_pkg/outer_loop.py`, `cli/compass_pkg/tdd.py`.
- `tests/acceptance/atdd_strategy/test_loop_marking.py` (`TRC-E1` to `TRC-E6`, `TRC-A17`).
