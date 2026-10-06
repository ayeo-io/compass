# the-adoption-setting-is-adoption

## Decided by

jed72

## Date

2026-10-06

## Supersedes

Nothing.

## Decision

In `compass.yml` the adoption setting is named `adoption` (`advisory` or `enforced`). `mode` keeps one meaning there: a stage mode. A project that has not migrated keeps `mode:` in `.compass/config.yml`, read as today.

## Why

With one configuration file, a top-level `mode:` beside stage modes would give one word two unrelated meanings in the same file.

## Evidence

The maintainer's answer to question Q-4(b) of the configurable-framework technical specification, 6 October 2026.
