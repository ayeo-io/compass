<!--
TEMPLATE: review.md
Role in the pipeline: one round of review by a reviewer who did not write the
work. Each round is its own file, review-<n>.md, registered with
`compass issue artifact set review --path <file>`; a later round adds a file
and leaves the earlier ones as they are.

Findings are written as a colleague would say them: what is wrong, where, and
what would fix it. Mark each finding blocking or not blocking, and give the
file and line it rests on.

Fill every {{PLACEHOLDER}}.
-->

# Review - {{ISSUE_SLUG}}

> **Date:** {{DATE}} · **Reviewer:** {{AGENT OR PERSON}} (not the author)
> **Round:** {{N}} · **Head reviewed:** {{COMMIT}}

## Scope

{{What was reviewed: the commits, the files and the scenarios. Name what was left out and why.}}

## Verdict

{{Pass, pass with conditions, or no pass - and the one reason that decides it.}}

## Blocking

{{Each finding that must change before the work passes: what is wrong, where (file and line) and what would fix it. Write "None" when there is none.}}

## Not blocking

{{Each finding that can wait: a question, a nitpick or an item for a follow-up. Name which.}}

## Security

{{What an attacker could gain from this change and what stops them - or "no new surface".}}

## Probes

{{Each check the reviewer ran, the command and what it printed. A probe with no output is a claim.}}
