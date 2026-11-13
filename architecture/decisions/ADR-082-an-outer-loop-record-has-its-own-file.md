---
id: ADR-082
title: An outer-loop record has its own file
status: accepted
date: 2026-11-02
supersedes: ''
superseded_by: ''
---

## Context

A red or green record's file name came from its binding only: `red-<id>.json` for `--scenario <id>`, `red.json` with none. Strategy `S17` records an outer-loop red at the end of stage 1 (ADR-081), bound to each scenario. At implement, the inner-loop red bound to the same scenario wrote the same file and replaced the outer-loop red. `outer-loop-recorded` then reported "no outer-loop red" for work that had recorded one. A green had the same fault, in the file and in the registry entry, which was keyed by scenario.

## Decision

1. **The file.** An outer-loop record's file name ends `.outer.json`. `compass tdd-red --loop outer --scenario <id>` writes `evidence/red-<id>.outer.json` and `compass tdd-green --loop outer --scenario <id>` writes `evidence/green-<id>.outer.json`. With no `--scenario` they write `red.outer.json` and `green.outer.json`. An inner-loop record keeps `red-<id>.json`, `green-<id>.json`, `red.json` and `green.json`. Decided by jed72 (owner), 2026-11-02.
2. **The registry.** An outer-loop green has its own `test-run` entry, with id `EV-T-<id>-outer` (`EV-T-outer` unbound). A green updates only the entry of its own binding and loop.
3. **The readers.** `red_first.record_stem`, `record_paths` and `is_record_name` name the files. Every reader of red and green files sees both loops: `red_first.red_verdict` (which the pre-tool hook runs), `acceptance_strategy.red_records`, `next_cmd`, the status line, `compass run`, `compass diagnose`, and the red a bound green needs (`tdd._red_record_for`). A bound green takes the red of its own loop first and the other loop's red when its own is absent.
4. **Old records.** A record is never moved or renamed. A record with no `loop` field is inner where it is. An outer-loop record written to `red-<id>.json` before this decision still reads as outer, because the loop comes from the record (`acceptance_strategy.loop_of`, ADR-080), not from the file name.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| Refuse an inner red whose binding already holds an outer red | No new file name | The inner loop is the normal work of implement and must not be refused |
| Name the loop in a folder, such as `evidence/outer/` | Groups the records | Every reader that lists `evidence/` would need a second folder walk |
| Keep one file and append runs to it | One record per binding | Every reader of a record reads one run, and the identity stamps cover one run |

## Consequences

- An inner-loop red or green bound to a scenario keeps the stage 1 red and every outer-loop green of that scenario.
- The registry can hold two `test-run` entries for one scenario. Readers that key entries by scenario see both; `suite-passed` reads each.
- The `attempts` counter of `compass tdd-green` is still kept per scenario, across both loops.

## References

- ADR-080 (the `loop` field) and ADR-081 (the stage 1 red).
- `cli/compass_pkg/red_first.py`, `cli/compass_pkg/tdd.py`, `cli/compass_pkg/acceptance_strategy.py`, `cli/compass_pkg/statusline.py`, `cli/compass_pkg/run_cmd.py`, `cli/compass_pkg/diagnose.py`.
- `tests/acceptance/atdd_strategy/test_outer_loop_files.py`.
