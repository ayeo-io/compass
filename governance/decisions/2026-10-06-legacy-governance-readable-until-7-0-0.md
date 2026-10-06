# legacy-governance-readable-until-7-0-0

## Decided by

jed72

## Date

2026-10-06

## Supersedes

Nothing.

## Decision

The generated legacy views of the shipped policy and the reads of the old `.compass/config.yml` stay through every 6.x release and are removed at 7.0.0.

## Why

Projects that copied governance, the drift report and the existing tests keep working, and the break is paid once with the other legacy removals.

## Evidence

The maintainer's approval on 6 October 2026 of the recommendations for the open questions of the configurable-framework technical specification, given with the approval to split the configuration work into epics. Question Q-12.
