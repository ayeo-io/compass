# new-flag-means-minor

## Decided by

jed72

## Date

2026-10-02

## Supersedes

Nothing.

## Decision

The release that added `compass ci --since` is 5.2.0, not 5.1.1. A new flag is new capability, which `docs/releasing.md` calls a minor.

## Why

The version number states the compatibility promise, not the size of the change.

## Evidence

#251, the pull request that bumped the version to 5.2.0; `docs/releasing.md`, "The release procedure".
