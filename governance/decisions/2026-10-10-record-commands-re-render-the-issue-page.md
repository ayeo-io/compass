# record-commands-re-render-the-issue-page

## Decided by

jed72

## Date

2026-10-10

## Supersedes

remind-when-the-review-page-goes-stale

## Decision

The commands that change an issue's records re-render the issue's documents and its issue page instead of printing a reminder. After a command exits 0, the step `render_after` rewrites the rendered blocks of the issue and of the issues its manifest links to. A command that exits non-zero renders nothing. A failed render prints one line on standard error with a count and never fails the command.

Compass 7.0.0 removes `compass issue dashboard render` and the check `dashboard-current` together with the reminder. The check `rendered-blocks-current` replaces `dashboard-current`.

## Why

The 2026-10-05 decision chose a reminder because regenerating would have left `dashboard-current` able to catch only a hand-edited page. Rendered blocks change that. Text a person did not write is now confined between markers, every digest and reader ignores the interior of a block, and a check compares each block with a fresh render. A render after each command keeps the documents current without a person running a verb, and the check stays as the backstop for an edit made by hand or a render that failed.

Two earlier decisions bound this change:

- `default-6-x-never-changes-a-6-0-value`: 7.0.0 is the release that may change a default, so the render is the shipped default with no flag, alias or until clause.
- `keep-the-stop-before-a-breaking-change`: the work stops and asks the maintainer at the moment `compass issue dashboard render` is deleted.

## Evidence

Issue `documents-carry-judgement`, scenarios DCJ-18 to DCJ-22 and DCJ-75.
