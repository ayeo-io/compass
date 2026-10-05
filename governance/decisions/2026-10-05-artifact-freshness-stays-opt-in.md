# artifact-freshness-stays-opt-in

## Decided by

jed72

## Date

2026-10-05

## Supersedes

Nothing.

## Decision

The `artifact-freshness` capability stays opt-in. With it on, a change to an upstream artifact marks every artifact and check result that depends on it stale, and land is refused until they are produced again. The default configuration does not turn it on until a cost-lab run has measured it on the same issues with it on and off.

## Why

Chosen from the recommendation of 5 October. Staleness blocks land, so turning it on by default changes the cost of every issue, and that cost has not been measured.

## Evidence

The design review of the configurable framework on 5 October 2026, recorded with ADR-033 in the same pull request.
