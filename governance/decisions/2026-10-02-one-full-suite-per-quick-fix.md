# one-full-suite-per-quick-fix

## Decided by

jed72

## Date

2026-09-25

## Supersedes

Nothing.

## Decision

A quick fix records one full-suite green before it lands. CI on the pull request covers the merged result; no second local run after landing.

## Why

The second run cost about 20 minutes per defect and added nothing CI does not check.

## Evidence

Stated in session on 2026-09-25.
