# a-strategy-can-carry-checks-a-step-off-makes-advisory

## Decided by

jed72

## Date

2026-10-29

## Supersedes

Nothing.

## Decision

A strategy can carry blocking checks that a recorded step-off makes advisory. Such checks are unlocked, sit outside every gate and every lock, and do not run on a spike, as `nfr-rows-resolved` does (ADR-064); guardrails `G1` and `G4` keep their checks. The first is the four-layer acceptance strategy (`S17`), shipped in the 8.0.0 default preset. Whether it applies to an issue is stored at the issue's first assessment and decided from the records: an issue is in scope unless it holds an acceptance of kind `validation` or `refactor` and no red record, and an issue assessed before the strategy shipped holds no stored applicability, so the strategy never applies to it. A project turns it off with the settings key `acceptance_strategy: {state: off, reason: <text>}`, with no owner's approval; one issue steps off through an approved issue waiver (ADR-039).

## Why

A team must be able to step off the strategy with a recorded reason, so it is a strategy and not a guardrail; a locked guardrail check cannot be waived. Its checks still have to block, so the definition of a strategy changes in `governance/strategies.md`, `governance/terminology.yml` and the generated header of `governance/guardrails.yml`. Storing applicability at assess keeps issues in flight at the upgrade on the checks they started with (ADR-006). One settings key, visible in the delivery-approach record and in `compass retro --acceptance`, is lighter than five waivers for one choice.

## Evidence

ayeo-io/compass-delivery#307 [Make the four-layer acceptance test model a Compass strategy for client-observable behavior]: the requirements review of its issue `atdd-strategy` records jed72's answers of 2026-10-29 to questions Q1 (applicability from the kind plus the records), Q8 (checks outside the locked guardrails) and Q9 (one issue steps off through an issue waiver), and decision 14 of the strategy's product requirements (one settings key with a reason and no owner's approval). ayeo-io/compass-delivery#321 [Add the four-layer acceptance strategy with applicability and opt-out] builds it.
