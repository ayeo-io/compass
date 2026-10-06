# legacy-waivers-readable-until-7-0-0

## Decided by

jed72

## Date

2026-10-06

## Supersedes

Nothing.

## Decision

A `waived:` entry migrated from a copied policy has a reason and no approval record. Migration writes it with `approved_by: LEGACY` and no date. Lint accepts that shape until 7.0.0 and prints it as "no approval recorded" on every run.

## Why

Otherwise every migrated project would fail lint at once, and the missing approval stays visible.

## Evidence

The maintainer's approval on 6 October 2026 of the recommendations for the open questions of the configurable-framework technical specification, given with the approval to split the configuration work into epics. Question Q-11.
