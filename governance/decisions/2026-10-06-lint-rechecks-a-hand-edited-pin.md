# lint-rechecks-a-hand-edited-pin

## Decided by

jed72

## Date

2026-10-06

## Supersedes

Nothing.

## Decision

`compass policy lint` compares the pin on `extends:` in the working file with the pin at git HEAD. When they differ, it runs the same waiver re-check `compass policy update` runs. A fresh clone or a project outside git prints "pin history unknown".

## Why

A hand edit of the pin would otherwise move a parent with no waiver re-check.

## Evidence

The maintainer's approval on 6 October 2026 of the recommendation for question Q-22 of the configurable-framework technical specification.
