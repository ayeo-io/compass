# the-migration-marker-records-what-an-undo-needs

## Decided by

jed72

## Date

2026-10-19

## Supersedes

Nothing.

## Decision

The marker, `migration.yml` in the project's `.compass` folder, gains two keys after `created_state`. `written` maps `compass.yml`, and `.compass/state.yml` when `created_state` is true, to the sha256 digest of the text the migration wrote. `migrated_at` is a UTC time with seconds. The marker stays at schema 1. A marker without `written` is one that `compass policy migrate --undo` refuses, and it answers with the manual steps.

## Why

The undo must tell an edited file from an unedited one, and a record written after the migration from an older one. A marker with extra keys breaks nothing that reads it, because `pending_removal` reads only `sources`.

## Evidence

Two comments on GitHub issue ayeo-io/compass-delivery-record#35 ("Add compass policy migrate --undo"), both dated 19 October 2026:

- the architect's six design decisions, https://github.com/ayeo-io/compass-delivery-record/issues/35#issuecomment-6264810979
- the comment that brought the issue back into 7.0.0 at jed72's request, https://github.com/ayeo-io/compass-delivery-record/issues/35#issuecomment-6270991586
