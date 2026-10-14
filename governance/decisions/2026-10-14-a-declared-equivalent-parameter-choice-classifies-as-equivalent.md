# a-declared-equivalent-parameter-choice-classifies-as-equivalent

## Decided by

jed72

## Date

2026-10-14

## Supersedes

Nothing. This entry amends no entry. `2026-10-13-this-repository-declares-readiness-commands` still holds: this repository's one readiness override still sets only the `command` parameter of `tests-declared-and-under-two-minutes`, now written in map form (`set: {params: {set: {command: test_micro_command}}}`) so the shipped `limit_seconds` is kept.

## Decision

A registry entry can declare a fourth direction for a parameter, `equivalent`, beside `higher`, `lower` and `none`. The classifier compares a parameter whose direction is `equivalent` as follows.

- Only the readiness registry and the check registry, which ship with the CLI, can declare the direction `equivalent`. The readiness registry declares it on `tests-under-limit.command` only.
- A registry refuses `equivalent` on a parameter that has no `choices` entry. A check parameter has no `choices`, so the check registry refuses it on every parameter.
- A catalogue or a preset cannot declare `equivalent`: a dimension's direction stays `higher` or `lower`, and the catalogue check refuses any other value.
- A changed value is equivalent only when both sides name the same implementation, both values are present and both are in that implementation's `choices` for the parameter. An unchanged value is equal, as for every other direction.
- A value missing on either side, or a value outside `choices`, is incomparable, and so is a change across two implementations. The classifier fills in no runtime default, so a readiness parameter one side leaves out is incomparable whatever its direction.
- An `equivalent` parameter is never tighter or looser: it has no stricter value.
- `compass policy diff` names the swap on its own line, outside the classification, for example `changes readiness tests-declared-and-under-two-minutes command: test_command -> test_micro_command`. The swap stays visible without a waiver.

The classifier version is 5, so no classification stored under version 4 is served again. No stored generation is rewritten.

## Why

Swapping the timed test command between `test_command` and `test_micro_command` changes which declared suite the readiness floor times, not the floor: both run under the same limit, and the project declares both. Before this rule the classifier could compare a changed string parameter only as incomparable, so the override this repository needs to meet the readiness floor refused every `compass approach evaluate --write` and `compass quick-fix start` here.

Equivalence is declared per parameter, not inferred from `choices`. `project-command-succeeds.key` (lint, format check, build, typecheck) and `project-declaration.key` (secret scan, structured logging) also have `choices`, but each choice names a different floor, so those changes stay incomparable. A catalogue cannot declare an equivalence, so an adopter cannot declare any swap equal and skip the waiver; a further equivalence needs a registry change and a CLI release.

A missing value stays incomparable because filling in the runtime default would hide a dropped parameter: a plain map under `set:` replaces the whole `params` map and drops `limit_seconds`, and a later change to the default would then move verdicts silently.

## Evidence

Decided by the architect for jed72 under the automation mode jed72 set on 12 October 2026, for issue `readiness-override-assess`. That issue's tests in `tests/test_classifier.py` and `tests/test_readiness_override_assess.py` cover each point, and each regression test was shown failing on a planted fault. In this repository the map-form override passes the write-time lint, and the plain-map form fails it with `C-INCOMPARABLE`.
