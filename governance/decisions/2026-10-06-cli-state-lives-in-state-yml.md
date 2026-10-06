# cli-state-lives-in-state-yml

## Decided by

jed72

## Date

2026-10-06

## Supersedes

Nothing.

## Decision

Values the CLI writes, `initialised` and `records_signed_since`, live in `state.yml` in the `.compass/` directory. `compass init` writes that file and writes no `compass.yml`.

## Why

They are state, not configuration; dropping them would lose the signed-record cutoff and the hook's explanation of where Compass came from.

## Evidence

The maintainer's approval on 6 October 2026 of the recommendation for question Q-23 of the configurable-framework technical specification.
