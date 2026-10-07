# stage-mode-ranks-cover-the-depth-ladder-only

## Decided by

The architect agent (compass:architect), on the maintainer's behalf while they were away on 6 October 2026. The maintainer can reverse it.

## Date

2026-10-06

## Supersedes

Nothing.

## Decision

A stage mode has a rank only when it sits on the depth ladder that today's lift walks: skipped, collapsed, light, full. Every other mode has no rank. A mode with no rank is incomparable, and the lift leaves it alone.

| Stage | Mode | Rank |
|---|---|---|
| `assess` | `light` | 2 |
| `assess` | `full` | 3 |
| `define` | `collapsed` | 1 |
| `define` | `light` | 2 |
| `define` | `full` | 3 |
| `define` | `reproduce-first` | none |
| `refine` | `skipped` | 0 |
| `refine` | `collapsed` | 1 |
| `refine` | `light` | 2 |
| `refine` | `full` | 3 |
| `plan` | `collapsed` | 1 |
| `plan` | `full` | 3 |
| `breakdown` | `skipped` | 0 |
| `breakdown` | `multiagent` | none |
| `implement` | `explore` | none |
| `implement` | `full` | 3 |
| `implement` | `expedited` | none |
| `verify` | `conclude` | none |
| `verify` | `light` | 2 |
| `verify` | `full` | 3 |
| `ship` | `graduate-or-discard` | none |
| `ship` | `light` | 2 |
| `ship` | `full` | 3 |
| `ship` | `full-plus-backfill` | 4 | <!-- vocabulary-scan: allow - the machine mode id the ruling ranks -->

Ranks are per stage but use one shared scale, so the same word has the same number everywhere. The only mode above `full` is the one ranked 4 in the table.

**Lift rule.** For each stage a floor names, if its mode has a rank below that of `full`, the evaluator sets it to `full`. A mode of rank 3 or more, or with no rank, stays as it is.

**What it means for the classifier.** The classifier compares stage modes by rank. A change between a ranked and an unranked mode, or between two unranked modes, is incomparable and needs a waiver. A move up the ladder, such as `light` to `full`, is a tightening. A move down, such as `full` to `light`, is a loosening. A project can add a rank to its own modes when it wants comparisons for them.

## Why

The lift in `cli/compass_pkg/routing.py` (lines 302 to 304) changes exactly `collapsed`, `skipped` and `light`, which are ranks 0, 1 and 2. It leaves `full` and every other mode untouched, so the ranked rule gives the same result for every mode in use. The floors in `governance/routing-policy.yml` name only `refine`, `verify`, `ship` and `define`, so `breakdown` is never lifted.

Four alternatives were rejected:

- **Rank every mode.** A rank below `full` for `expedited`, `reproduce-first`, `explore`, `conclude` or `graduate-or-discard` would make the lift raise them to `full` and change the hotfix and spike stages. A rank at or above `full` would claim that `expedited` is as thorough as `full`, which is false.
- **Rank the other modes equal to `full`.** An equal rank means no change in strictness, so a change such as `expedited` to `full` would pass unflagged although it changes behaviour.
- **A named list of modes to lift.** It reproduces the lift but gives the classifier nothing to compare.
- **No rank for the mode above `full`.** It also reproduces the lift, but it throws away a true ordering: the mode contains every step of `full`.

The cost is that a safe-looking move such as `expedited` to `full` needs a waiver. A false "safe" is worse than a waiver the author must write.

## Evidence

The ruling made while the maintainer was away, from reading the floors and the lift. It has not been replayed: the 1,200-assessment comparison of the ranked rule with the old rule is owed with the obligations increment (the increment that reads the stage ranks), and it must also show that a planted rank on `expedited` below `full` makes the replay report a difference.
