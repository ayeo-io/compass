---
description: Cross-issue view - blockers, owed follow-ups, the digest
argument-hint: "[--digest | --html <file>]"
allowed-tools: Read, Write(./.compass/**), Write(./docs/**), Bash(compass *), Glob, Grep
---

# /compass:flow

`/compass:status` reports on one issue. `/compass:flow` reports on
every issue - it does the work of delivery management as a command, not
as a role. Anyone can run it; it is not a role entry point.

Compass is issue-centric by design: each issue carries its own delivery
approach, artifacts, and gates. But a team runs many issues at once, and
nothing in the per-issue pipeline answers "what is the state of
*everything*, and what needs a human's attention first?" That is this
command.

**Mode:** $ARGUMENTS - default is the live flow board; `--digest` writes a
dated digest file (see below).

## Setup

- Load the `flow-management` skill - it holds the triage heuristics, the
  blocker protocol, and the digest format.
- This command reads broadly and writes only the digest, or the board page
  `compass flow --html <file>` names (never inside `.compass/` or
  `docs/compass/`). It never edits an
  issue's artifacts - issue state is inferred from artifacts on disk, never
  set by a label.

## Procedure

1. **Enumerate.** List every issue directory under `.compass/work/`. For
   each, read `manifest.yml` (the machine-readable manifest, which holds the
   delivery approach) and, on an issue assessed before the path,
   `devlog.md`. To report an issue's
   *mechanical* gate status you can run `compass check --issue <slug>` - it
   is read-only and changes nothing.

2. **Assess each issue.** Apply the `flow-management` heuristics:
   - **No `delivery_approach:` in the manifest** -> a guardrail violation (work started
     without an assessment). Report this above everything else.
   - **Stalled** -> an in-progress stage with no new record (evidence, or a
     `devlog.md` entry on an older issue) for longer than the approach's
     expected cadence. Flag it and name the likely blocker.
   - **Approach outgrown** -> signs in the records that the issue no longer
     fits its assessment. Recommend `/compass:assess --reassess`.
   - **Healthy** -> progressing in line with its approach.

3. **Build the board.** Start from `compass flow`: it lists each issue in
   progress or in review with its approach, stage, gates passed and whether
   its newest test record still matches its files, and marks a blocked issue
   with its reason; sets stale evidence apart; lists ready issues; shows the
   backlog with its age, what was done this week and the most common
   friction. Add the health and owner the heuristics above
   give. `compass flow --html <file>` writes the board page: the same page
   `compass board render --out <file>` writes, with a lane for each stage and
   a panel for each open issue that says why it has its delivery approach.
   `compass board render` writes that page to one file per checkout and opens
   it; `docs/board.md` describes it.

4. **Report blockers.** For every blocked or stalled issue, state what it
   is blocked on and who or what can unblock it. Anything needing a human
   decision goes to the top.

5. **Aggregate owed follow-ups.** `/compass:status` flags follow-ups per
   issue; `/compass:flow` collects them all into one list - every unsettled
   defect follow-up, every unbacked marketing claim, every de-scoped
   artifact still owed, across all issues.

6. **Report**, ordering by what needs attention first: human decisions ->
   guardrail violations -> blockers -> owed follow-ups -> healthy in
   progress -> shipped.

## `--digest`

With `--digest`, also write a dated digest to
`.compass/flow/digest-{{DATE}}.md` using the format in the
`flow-management` skill: shipped since the last digest, in flight, blocked,
owed follow-ups, and next up. The digest is the artifact a
team reviews on a cadence - and `/compass:flow --digest` suits a
scheduled run (e.g. weekly). It is append-only history: never
overwrite a prior digest.

## Note

`/compass:flow` advises; it does not gate. The gates are in the per-issue
pipeline, where the evidence is. Flow makes sure no issue is stuck without
anyone noticing, off-approach, or owing a follow-up. It does not add
another gate.
