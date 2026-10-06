# the-preset-flag-is-not-on-compass-init

## Decided by

jed72

## Date

2026-10-06

## Supersedes

Nothing.

## Decision

The flag that adopts a published configuration goes on `/compass:init` or on a new `compass policy` sub-verb, not on `compass init`.

## Why

`compass init` runs from every entry point and writes no root file; adopting a configuration writes `compass.yml`.

## Evidence

The maintainer's approval on 6 October 2026 of the recommendation for question Q-28 of the configurable-framework technical specification.
