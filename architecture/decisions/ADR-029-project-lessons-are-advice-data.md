---
id: ADR-029
title: Project lessons are advice kept as data, injected under their own cap and never read by a check
status: accepted
date: 2026-10-02
supersedes: ''
superseded_by: ''
---

## Context

A person who corrects Compass in one issue has to make the same correction
in the next session in that repository. `compass retro --friction`
aggregates friction and feeds nothing forward, and Claude Code's own memory
holds general preferences rather than how governance applies in one
repository. Issue #257 asks for project lessons: rules the next session reads.

Two limits shape the design. In a Claude Code session the model runs every
command, so the CLI cannot tell whether the person or the model typed a
lesson's words. And whether a sentence agrees with a guardrail is a question
of meaning, which a pattern cannot answer without refusing good sentences
and missing reworded ones.

The design follows rulings the compass:architect agent made on the
maintainer's behalf while the maintainer was offline.

## Decision

- Lessons live in `lessons.yml` in the project's `.compass` folder, each
  with an `LS-` id, a one-sentence `rule`, a `category`, `applies` (`always`
  or `on_topic`), a `source`, the `issue`, `created`, `added_by`, and
  `superseded` when it replaced another.
- `compass lesson add` records a lesson now, with `added_by` from
  `git config compass.decidedBy`, else `user.name`, and no option to set it.
  The CLI does not claim the person typed the words. `compass lesson propose`
  holds a lesson in `lessons-pending.yml`, in the same folder, and only
  `compass lesson accept` turns it into a lesson. The model is told to
  propose, and `compass retro --lessons` proposes friction seen in three or
  more issues.
- The session-start hook injects the `always` lessons after the operating
  contract, under a 150-word cap that is separate from the 900-word resident
  ceiling, oldest first, whole lessons only, with a line naming how many were
  omitted. `on_topic` lessons are stored and listed, not yet surfaced.
- The CLI cannot tell whether the person or the model typed the words, so
  `source` records the route a lesson came by, not who typed it. The model
  is told, in the `compass-runtime` skill, `/compass:ship` and the injected
  block, to propose and never add. The operating contract does not say so,
  because the resident text is at 892 of its 900 words.
- Lessons are advice. No check reads them, and the injected block says a
  guardrail always wins. Compass does not check that a lesson agrees with
  the guardrails. It refuses a lesson that names a guardrail id, read from
  `governance/guardrails.yml`, and one matching a short list of model names
  and tool-version shapes. That second check is a pattern, not a proof:
  some names pass it and some ordinary words are refused.
- `compass retro --lessons` matches friction text exactly, after case and
  spacing; a row reworded by another issue does not match.

## Alternatives considered

- **Record only what the person typed.** Rejected: the CLI cannot see who
  typed a command, so the claim could not be true. A pending list with an
  accept step is a real gate the model's output must pass.
- **Refuse a lesson that contradicts a guardrail.** Rejected for now: a
  keyword rule refuses "never skip the review" and misses "do not bother
  with red tests". Stated as a limit instead.
- **A subcommand of an existing group.** No group fits: `decision` records
  settled outcomes, `retro` aggregates, `policy` checks the governance YAML.
- **Count lessons in the resident ceiling.** Rejected: that test counts
  static files and cannot see a block built at session start; the cap is
  tested at the hook instead.

## Consequences

- A project's repeated corrections reach later sessions without being
  repeated, within 150 words.
- Lessons cannot clear a gate or relax a guardrail, because nothing that
  judges an issue reads them.
- This adds a verb but no guardrail and no `CHECK_FN`, so it stays within
  ADR-002, which grows the framework by artifacts. The verb is additive
  under ADR-006.
- `on_topic` surfacing and the reserved third `source` value are left for later.

## References

- Issue #257, project lessons.
- ADR-027, where the decider also comes from git config.
- ADR-002, the framework grows by artifacts and lenses, not guardrails.
- ADR-006, backward compatibility within a major version.
- `cli/compass_pkg/lessons.py`, `hooks/session-start.sh`.
