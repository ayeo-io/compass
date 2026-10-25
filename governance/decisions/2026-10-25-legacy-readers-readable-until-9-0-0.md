# legacy-readers-readable-until-9-0-0

## Decided by

jed72

## Date

2026-10-25

## Supersedes

`governance/decisions/2026-10-19-legacy-readers-readable-until-8-0-0.md`
`governance/decisions/2026-10-17-legacy-waivers-readable-until-8-0-0.md`

## Decision

Compass reads old words, old approach names, copied 5.x governance, the generated governance views (`governance/routing-policy.yml` and `governance/guardrails.yml`), `.compass/config.yml` and the LEGACY waivers that `compass policy migrate` writes until 9.0.0, not until 8.0.0. 8.0.0 ships the delegation rework (ayeo-io/compass#691) and removes no reader. Everything else in the two entries stands.

## Why

8.0.0 is a major release because of the delegation change, and it comes just before Compass is submitted to the plugin directory. Removing the readers in the same release would make it far larger and riskier than the change that needs the major. The readers serve projects still on old formats; their removal is planned as 9.0.0, with its own upgrade guide.

## Evidence

The maintainer's choice of option B, "ship 8.0.0 and move the reader end to 9.0.0", in the Claude Code session of 25 October 2026 that prepared the 8.0.0 release, recorded with `compass decision record`, which takes the decider from git config. The issue is `release-8-0-0`.
