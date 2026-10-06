# policy-diff-has-an-exit-code-flag

## Decided by

jed72

## Date

2026-10-06

## Supersedes

Nothing.

## Decision

`compass policy diff` exits 0 like every report verb, and `--exit-code` makes it exit non-zero when a result changes, for scripts.

## Why

Report verbs advise; a script that wants a failure asks for one.

## Evidence

The maintainer's approval on 6 October 2026 of the recommendations for the open questions of the configurable-framework technical specification, given with the approval to split the configuration work into epics. Question Q-18.
