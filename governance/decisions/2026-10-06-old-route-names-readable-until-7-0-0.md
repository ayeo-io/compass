# old-route-names-readable-until-7-0-0

## Decided by

jed72

## Date

2026-10-06

## Supersedes

`governance/decisions/2026-10-05-routes-are-quick-fix-regular-full.md`

## Decision

The delivery approach names stay `quick-fix`, `regular`, `full`, `hotfix` and `spike`. The old names (`express`, `standard` and `expedition` as policy keys, `feature` and `initiative` as approach names) stay readable, with a warning, through every 6.x release, and are removed at 7.0.0, not 6.0.0. Everything else in the entry this replaces stands.

## Why

Chosen from the recommendation of 6 October. The configurable framework keeps every legacy reader until 7.0.0, so a project's copied policy keeps working through 6.x and the break is paid once, alongside the other legacy removals (ADR-006). Removing the old names at 6.0.0 would have broken those copies one major release early.

## Evidence

The maintainer's answer to question Q-9 of the configurable-framework technical specification, 6 October 2026.
