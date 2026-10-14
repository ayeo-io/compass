# this-repository-declares-readiness-commands

## Decided by

jed72

## Date

2026-10-13

## Supersedes

Nothing. It amends `2026-10-06-this-repository-may-hold-a-settings-only-compass-yml`, as `2026-10-12-this-repository-names-its-owner` did: where that entry says the file holds settings keys only, it may now also hold the readiness commands and one readiness override. The rest of that entry and of the owner entry stands. Merged ledger entries are not edited, so this entry is where the amendment is recorded.

## Decision

This repository keeps `autonomy: autonomous` and meets the readiness floor by declaring the commands the floor measures. Its `compass.yml` may hold, beyond settings keys and `owner`:

- `allow_project_commands: true`;
- `project.build_command`, `project.lint_command` and `project.test_micro_command`;
- one `readiness` override, which sets the `command` parameter of `tests-declared-and-under-two-minutes` to `test_micro_command`, so the timed test command is a micro suite rather than the full suite.

It allows nothing else. It declares no other catalogue entry, no check, gate, rule, route, waiver, unlock, capability or approvers list, and `tests/test_framework_compass_yml.py` fails on any of them, or on a `readiness` value other than that one override.

## Why

From 7.0.0 an autonomous project below the readiness floor is refused at assess. Changing `autonomy` to `balanced` would put the stops at define and plan back on regular and full issues, which this repository runs autonomously at the maintainer's request of 5 October 2026. A waiver would remove the floor's signal instead of meeting it. The full suite takes about ten minutes, so it cannot be the timed test command, which must pass within two minutes. A micro suite of tests that need no ignored file meets the floor honestly, and the setting says that it is a micro suite. This repository's checks, gates and rules stay the shipped default, so its delivery record stays evidence for that default.

The record is per checkout and goes stale after seven days, 25 commits or any `compass.yml` change. Each new clone or worktree must run `compass readiness`, up to five minutes, before its first `compass approach evaluate --write`.

## Evidence

Decided by the architect for jed72 under the automation mode jed72 set on 12 October 2026, with a measured fallback to `autonomy: balanced` had the micro suite taken more than 90 seconds or the lint command failed in a clean checkout. In a clean worktree of the branch, the micro suite took 21.2, 20.4 and 19.8 seconds and passed, and `bash scripts/validate.sh --quiet` passed in 9.5 seconds.
