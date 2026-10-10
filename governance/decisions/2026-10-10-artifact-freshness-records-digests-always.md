# artifact-freshness-records-digests-always

## Decided by

jed72

## Date

2026-10-10

## Supersedes

Nothing.

## Decision

This entry amends `artifact-freshness-stays-opt-in` (2026-10-05) for the recording half only. Every `compass issue artifact set` registration now records the document's digest, and the digest of each artifact it depends on, whatever the `artifact-freshness` capability says. The stale-document refusals stay opt-in: with the capability off, `compass check`, `compass next` and `compass ship-commit` still name no stale document and refuse nothing for one.

The 2026-10-05 entry is not edited. A merged decision entry never changes, so this is a new entry that names it.

## Why

The 2026-10-05 reason was the unmeasured cost of refusing a land for a stale document. Recording adds one read of a file that is already being registered, and it refuses nothing. The digest is also what tells a rewrite of an approved document from a repeat registration, so 7.0.0 needs it on every issue to move a rewritten document back to `draft`.

## Evidence

The maintainer's settled decision of 10 October 2026, recorded in the requirements review of the issue `artifact-status-written-by-stages`. It follows `2026-10-06-default-6-x-never-changes-a-6-0-value`: the change lands in 7.0.0 as the shipped default, with no capability flag and no alias.
