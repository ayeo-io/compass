---
id: ADR-079
title: The acceptance strategy block is stored once and replaced only by a re-assess
status: accepted
date: 2026-10-31
supersedes: ''
superseded_by: ''
---

## Context

Strategy `S17`, the four-layer acceptance strategy, ships in the default preset from 8.0.0. Its later checks (#323, #325 and #328 in ayeo-io/compass-delivery) must know whether the strategy applies to an issue. An issue created before 8.0.0 must keep the checks it had. A project can turn the strategy off with `acceptance_strategy` in `compass.yml`, and that setting can change while an issue is open.

Two questions follow:

- Where does an issue keep whether the strategy applies, and when does that change?
- What happens when the stored answer and the issue's records disagree?

## Decision

1. **The block.** `compass approach evaluate --write` stores an `acceptance_strategy` block in the manifest: `{state, reason, routing, expected_acceptance, applies, why}`. It writes the block only when the configuration being committed declares the check `acceptance-applicability-agrees`, and not for a project pinned to a default major before the strategy.
2. **Stored once.** The first assess adds the block. A re-assess replaces it only when the manifest already holds one. A re-assess of an issue without a block adds none, so an issue created before the strategy never gains one.
3. **One scope rule.** `acceptance_strategy.in_scope` decides whether the strategy applies now. It is true when the block exists, its state is `on`, its routing is not `suspended`, and either a red record exists or no acceptance of kind `validation` or `refactor` does. Every check of the strategy calls it and adds no scope rule of its own.
4. **The advisory check.** `acceptance-applicability-agrees` compares the stored block with the project setting and with what the records decide:
   - with no block, or with the block and the setting both off, it has nothing to check;
   - when the setting changed since assess, or the stored applicability differs from the records, it fails as advice and names `compass approach evaluate --write --reason "..."`;
   - when they agree, it passes.

   It never blocks. A project waiver cannot make it blocking.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| A creation-date cutoff, as the check `suite-passed` uses 2026-09-24 | No stored state | The release date was not known when the strategy was planned, and a date reads wrong in a back-dated fixture |
| A new assessment dimension | Assess would score the strategy directly | It would change the routing of every issue |

## Consequences

- An issue created before 8.0.0 keeps today's checks, and `compass check` adds a notice that says so.
- A change to the project setting takes effect on an open issue only at its next re-assess. Until then the advisory check reports the difference.
- The later check items read one function, so a change to the scope rule changes every check together.

## References

- The technical design of ayeo-io/compass-delivery#321, decisions `DD-1` and `DD-2`, and the parent plan of the ATDD strategy, decision `DD-3`. Both are issue documents kept in the delivery record.
- `governance/decisions/2026-10-29-a-strategy-can-carry-checks-a-step-off-makes-advisory.md` and `governance/decisions/2026-10-30-the-strategy-follows-the-pinned-major-and-the-settings-key.md`.
- `cli/compass_pkg/acceptance_strategy.py` (`stored`, `in_scope`, `records_say`, `_check_applicability_agrees`) and `cli/compass_pkg/routing.py` (`_acceptance_block`).
- `governance/strategies.md` (`S17`), `docs/rendered-blocks.md` (the `acceptance-strategy` block).
- `tests/acceptance/atdd_strategy/test_strategy_routing.py` (`TRC-A2`, `TRC-A5`, `TRC-A14`, `TRC-A23`) and `test_cross_cutting.py` (`TRC-X2`).
