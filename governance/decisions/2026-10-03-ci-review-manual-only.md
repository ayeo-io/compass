# ci-review-manual-only

## Decided by

jed72

## Date

2026-10-03

## Supersedes

`governance/decisions/2026-10-02-ci-review-on-sonnet.md`

## Decision

The automatic Claude review no longer runs on pull requests: its workflow starts only by hand, and `main` no longer needs its `review` check. `self-check` stays required.

## Why

Not recorded.

## Evidence

The pull request that changed `.github/workflows/claude-review.yml` to `workflow_dispatch`, and the protected-main ruleset, which from 2026-10-03 needs only `self-check`.
