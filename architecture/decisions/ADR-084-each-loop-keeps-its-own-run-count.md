---
id: ADR-084
title: Each loop keeps its own run count
status: accepted
date: 2026-11-02
supersedes: ''
superseded_by: ''
---

## Context

`compass tdd-green` writes `attempts` and, past the first run, `rerun_without_change` on a green record. `no-trusted-rerun` reads them for strategy `S5`: a pass on the same tree with the same command is a rerun, and a rerun of a test that is not in `governance/quarantine.yml` fails. The count lived in `evidence/.tdd-state.json`, one entry per scenario, across both loops (ADR-082, consequences). So an outer-loop green that followed an inner-loop green of the same scenario, on the same tree with the same command, read as a second run and a rerun.

`no-trusted-rerun` is locked and passes a record with no `attempts`, for records written before the field. Strategy `S17`, the four-layer acceptance strategy, needs the outer loop to show intermittency, so an outer-loop green must carry the count and the test a quarantine entry names.

## Decision

1. **A count per loop.** Each loop keeps its own count per scenario. The inner loop keeps the key it had, the scenario id (`""` unbound). The outer loop keys the scenario id with `.outer` after it, as its record's file name does (ADR-082). An outer-loop green's `attempts` counts outer-loop runs only. Decided by jed72 (owner), 2026-11-02.
2. **A failed outer-loop run counts.** An outer-loop `compass tdd-green` whose command fails, or exits 0 with a failure token in its output, adds one to the outer-loop count and writes no record. A pass on the same tree with the same command that follows it has `attempts` 2 and `rerun_without_change: true`. The inner loop counts passes only, as before.
3. **The test.** An outer-loop green bound to a scenario writes `test`, the first test the scenario declares, which `no-trusted-rerun` looks up in `governance/quarantine.yml`. A green holds one exit code for the suite, so it cannot say which of several tests was flaky; a quarantine entry must name the first declared test. An inner-loop green writes no `test`.
4. **The `attempts` check.** `outer-loop-attempts-recorded` is blocking, unlocked, outside every gate and in no lock, as `outer-loop-recorded` is (ADR-080). On an in-scope issue it fails each registered outer-loop green with no `attempts`, or with a value that is not a whole number of 1 or more. It declines for an issue the strategy does not apply to, and for an issue with no outer-loop green, which `outer-loop-recorded` reports. `no-trusted-rerun` does not change.
5. **Old records.** A record is read as it is. A count written before this decision is the inner loop's, so the next outer-loop green of that scenario starts at 1.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| Keep one count per scenario across both loops | No change to the sidecar | An outer-loop green after an inner-loop green of the same command reads as a rerun, and fails `no-trusted-rerun` for work that ran once |
| Count failed runs in both loops | One rule for every green | It changes the inner-loop records of every issue, in and out of the strategy's scope; the strategy needs the outer loop only |
| Write every declared test as a list in `test` | Names all of a scenario's tests | `no-trusted-rerun` is locked and looks up one test id; a list cannot match a quarantine entry |
| Make `attempts` mandatory in `no-trusted-rerun` | One check | It is locked, and it would fail every record written before the field |

## Consequences

- An outer-loop green after inner-loop work on the same tree has `attempts` 1.
- An acceptance test that fails and then passes with no source change fails `no-trusted-rerun` at the verify stage and at ship, unless its first declared test is in `governance/quarantine.yml` with a tracking issue.
- The sidecar can hold two entries for one scenario, `<id>` and `<id>.outer`.

## References

- ADR-080 (the `loop` field), ADR-082 (the outer-loop file and registry entry).
- `cli/compass_pkg/green_attempts.py`, `cli/compass_pkg/tdd.py`, `cli/compass_pkg/outer_loop.py`.
- `tests/acceptance/atdd_strategy/test_attempts.py`.
