# default-6-x-never-changes-a-6-0-value

## Decided by

jed72

## Date

2026-10-06

## Supersedes

Nothing.

## Decision

A 6.x release of the shipped default never changes the value of a field that 6.0.0 defines. A change to an existing value is a new major version; minor versions only add inactive capabilities and checks.

## Why

A CLI upgrade within a major then invalidates no project waiver on the shipped default.

## Evidence

The maintainer's approval on 6 October 2026 of the recommendation for question Q-25 of the configurable-framework technical specification.
