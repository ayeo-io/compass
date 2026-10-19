# legacy-readers-readable-until-8-0-0

## Decided by

jed72

## Date

2026-10-19

## Supersedes

`governance/decisions/2026-10-06-old-route-names-readable-until-7-0-0.md`
`governance/decisions/2026-10-06-legacy-governance-readable-until-7-0-0.md`
`governance/decisions/2026-10-06-the-approach-catalogue-is-approaches.md`

## Decision

Compass reads old words, old approach names, copied 5.x governance, the generated governance views (`governance/routing-policy.yml` and `governance/guardrails.yml`) and `.compass/config.yml` until 8.0.0, not until 7.0.0. This moves the date in ADR-042, ADR-043 and ADR-044. The released command spellings are not covered: they end at 7.0.0. Everything else in the three entries stands.

## Why

A project that has not migrated by 7.0.0 keeps working for one more major release. Owners get a full release line to run `compass policy migrate`.

## Evidence

The maintainer's approval, in a comment dated 19 October 2026 on GitHub issue ayeo-io/compass-delivery-record#54 (https://github.com/ayeo-io/compass-delivery-record/issues/54#issuecomment-6267435198). ADR-051 item 14 asks for the maintainer's "go" before a CLI verb is deleted. The maintainer gave it there, for the removal of the 7 alias rows, the hints and the 8 old command spellings.
