# eval-one-reply-on-a-stop

## Decided by

jed72

## Date

2026-09-26, extended 2026-09-28

## Supersedes

Nothing.

## Decision

When an eval session stops with no edit before the run is finished, the harness sends one fixed reply. The reply is published method, and changing it needs the maintainer.

## Why

A session under `claude -p` that stops to ask gets no answer, so the scenario would have no decided result.

## Evidence

`evals/README.md`; stated in session on 2026-09-26 and 2026-09-28.
