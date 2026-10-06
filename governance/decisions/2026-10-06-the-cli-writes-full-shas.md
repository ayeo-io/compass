# the-cli-writes-full-shas

## Decided by

jed72

## Date

2026-10-06

## Supersedes

Nothing.

## Decision

The CLI always writes the full 40-character sha in a pin. It accepts a hand-written sha of 7 or more characters when it names one commit, and refuses an ambiguous one.

## Why

A short sha can become ambiguous as a repository grows.

## Evidence

The maintainer's approval on 6 October 2026 of the recommendation for question Q-26 of the configurable-framework technical specification.
