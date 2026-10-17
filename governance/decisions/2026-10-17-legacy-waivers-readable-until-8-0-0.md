# legacy-waivers-readable-until-8-0-0

## Decided by

jed72

## Date

2026-10-17

## Supersedes

`governance/decisions/2026-10-06-legacy-waivers-readable-until-7-0-0.md`

## Decision

Lint accepts a project waiver with `approved_by: LEGACY`, a reason and no date until 8.0.0, not until 7.0.0. Through every 7.x release it prints the waiver as "no approval recorded" with a warning, and the waiver still excuses its departure. From 8.0.0 the same waiver is an error. Everything else in the entry this replaces stands.

## Why

From 7.0.0, `compass policy migrate` writes a LEGACY waiver for each rule a project recorded under `waived:`. If lint stopped accepting the shape at 7.0.0, an upgraded project would fail lint straight after the upgrade. Owners get a full release line to replace each LEGACY waiver with a dated approval.

## Evidence

The maintainer's answer, in a session on 17 October 2026, to the question of how long lint accepts LEGACY waivers after 7.0.0 (GitHub issue ayeo-io/compass-delivery-record#195, "Decide how long lint accepts LEGACY waivers after 7.0.0").
