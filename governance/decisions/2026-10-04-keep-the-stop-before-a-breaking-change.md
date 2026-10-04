# keep-the-stop-before-a-breaking-change

## Decided by

jed72

## Date

2026-10-04

## Supersedes

Nothing.

## Decision

Compass keeps stopping to ask before a change that would break a consumer the request did not mention, at its measured cost. In the comparison scenario where a shared helper's change breaks a hidden consumer, both Compass sessions stopped to say the change would break the CSV export, went ahead after one reply, and passed every hidden test; the decision rule counted the two replies against Compass. No spec removes or softens that stop.

## Why

The stop named the real risk the scenario hides. Chosen from the recommendations after the 4 October comparison run, alongside specs for the other three scenarios with no edge.

## Evidence

`docs/compass/2026-10-04-eval-comparison-premium.md` (pull request #380), the section "What the sessions did".
