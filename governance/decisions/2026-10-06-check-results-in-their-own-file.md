# check-results-in-their-own-file

## Decided by

jed72

## Date

2026-10-06

## Supersedes

Nothing.

## Decision

A generation's `records.yml` is fixed when the generation commits. Check results go in a separate, mutable `results.yml` beside it.

## Why

A file that changed after its `complete` marker would make the marker meaningless.

## Evidence

The maintainer's approval on 6 October 2026 of the recommendations for the open questions of the configurable-framework technical specification, given with the approval to split the configuration work into epics. Question Q-8.
