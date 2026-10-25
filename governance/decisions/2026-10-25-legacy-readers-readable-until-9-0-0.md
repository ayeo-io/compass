# legacy-readers-readable-until-9-0-0

## Decided by

jed72

## Date

2026-10-25

## Supersedes

`governance/decisions/2026-10-19-legacy-readers-readable-until-8-0-0.md`
`governance/decisions/2026-10-17-legacy-waivers-readable-until-8-0-0.md`

## Decision

Compass reads these until 9.0.0, not until 8.0.0: old words, old approach names, copied 5.x governance, the generated governance views (`governance/routing-policy.yml` and `governance/guardrails.yml`), `.compass/config.yml` when `compass.yml` is absent, and the LEGACY waivers that `compass policy migrate` writes. The role flags, `--justify role=` on `compass approach evaluate` and `compass quick-fix start --role`, stay accepted and ignored until 9.0.0, not 8.0.0 as ADR-070 set; ayeo-io/compass-delivery-record#178 [Remove the role flags from approach evaluate and quick-fix start] moves to 9.0.0. 8.0.0 ships the delegation rework (ayeo-io/compass#691) and removes no reader. Everything else in the two entries stands.

## Why

8.0.0 is a major release because of the delegation change, and it comes just before Compass is submitted to the plugin directory. Removing the readers in the same release would make it far larger and riskier than the change that needs the major. The readers serve projects still on old formats; their removal is planned as 9.0.0, with its own upgrade guide.

## Evidence

ayeo-io/compass-delivery-record#303 [Release Compass 8.0.0], which records the maintainer's decisions of 25 October 2026: the number 8.0.0, the readers kept until 9.0.0, and the role flags kept until 9.0.0.
