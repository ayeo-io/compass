---
description: Cross-issue view - blockers, owed follow-ups, the digest
argument-hint: "[--digest | --html <file>]"
allowed-tools: Read, Write, Bash, Glob, Grep
---

# /compass:flow

`/compass:status` looks *down* into one issue. `/compass:flow` looks
*across* every issue - it is the delivery-management function as a
capability, not a persona. Anyone can run it; it is not a role entry point.

Compass is issue-centric by design: each issue carries its own delivery
approach, artifacts, and gates. But a team runs many issues at once, and
nothing in the per-issue pipeline answers "what is the state of
*everything*, and what needs a human's attention first?" That is this
command.

**Mode:** $ARGUMENTS - default is the live flow board; `--digest` writes a
dated digest file (see below).

## Setup

- Load the `flow-management` skill - it carries the triage heuristics, the
  blocker protocol, and the digest format.
- This command reads broadly and writes only the digest, or the board page
  `compass flow --html <file>` names (never inside `.compass/` or
  `docs/compass/`). It never edits an
  issue's artifacts - issue state is inferred from artifacts on disk, never
  set by a label.

## Procedure

1. **Enumerate.** List every issue directory under `.compass/work/`. For
   each, read `delivery-approach.md`, `manifest.yml` (the machine-readable
   manifest), and whichever stage artifacts exist. To report an issue's
   *mechanical* gate status you can run `compass check --issue <slug>` - it
   is read-only and changes nothing.

2. **Assess each issue.** Apply the `flow-management` heuristics:
   - **No `delivery-approach.md`** -> a guardrail violation (work started
     without an assessment). Surface this above everything else.
   - **Stalled** -> an in-progress stage with no `devlog.md` movement for
     longer than the approach's expected cadence. Flag it and name the
     likely blocker.
   - **Approach outgrown** -> signs in the devlog that the issue no longer
     fits its delivery approach. Recommend `/compass:assess --reassess`.
   - **Healthy** -> progressing in line with its approach.

3. **Build the board.** Start from `compass flow`: it lists each issue in
   progress or in review with its approach, stage, gates passed and whether
   its newest test record still matches its files, and marks a blocked issue
   with its reason; sets stale evidence apart; lists ready issues; shows the
   backlog with its age, what was done this week and the most common
   friction. Add the health and owner the heuristics above
   give. `compass flow --html <file>` writes the same board as one page.

4. **Surface blockers.** For every blocked or stalled issue, state what it
   is blocked on and who or what can unblock it. Anything needing a human
   decision goes to the top.

5. **Aggregate owed follow-ups.** `/compass:status` flags follow-ups per
   issue; `/compass:flow` collects them all into one list - every unsettled
   hotfix follow-up, every unbacked marketing claim, every de-scoped
   artifact still owed, across all issues.

6. **Read the retrospective signal.** Run `compass retro` - it reads
   the `reassessments:` log across every issue and reports whether the
   assess stage is systematically over- or under-sizing the process (a run
   of "up" re-assessments means the assess stage keeps rating work lighter
   than it is).
   This is the framework's own feedback loop: a framework about
   right-sizing process has to be able to tell whether the right-sizing is
   any good. Report the signal; if most re-assessments go the same way, the
   fix is in the project's `compass.yml` (a reviewed change to the routing
   rules) or the delivery-approach rubric, not in any one issue.

7. **Run rework-scan.** Run `compass rework-scan --format markdown` and
   embed the output in the report as a "Rework scan" section. This surfaces
   cross-issue add-then-delete patterns within the configured window
   (`rework_scan.window_days` in `${CLAUDE_PLUGIN_ROOT}/governance/signals.yml`,
   or in the project's own copy of that file, which the scan reads first; an
   unmigrated 5.x project runs on its own copied `governance/` until
   `compass policy migrate`). The
   scan is a signal - it never gates, never changes issue state, and always exits 0
   on detection (Flow advises, never gates). If the section is empty,
   record "0 rework instances detected" to confirm the scan ran.

8. **Report**, ordering by what needs attention first: human decisions ->
   guardrail violations -> blockers -> owed follow-ups -> rework signals ->
   retrospective signal -> healthy in progress -> shipped.

## `--digest`

With `--digest`, also write a dated digest to
`.compass/flow/digest-{{DATE}}.md` using the format in the
`flow-management` skill: shipped since the last digest, in flight, blocked,
owed follow-ups, rework signals, and next up. The digest is the artifact a
team reviews on a cadence - and `/compass:flow --digest` is a natural fit
for a scheduled run (e.g. weekly). It is append-only history: never
overwrite a prior digest.

The digest must include a **Rework scan** section produced by
`compass rework-scan --format markdown`. This section is informational - it
does not change any issue's state, and a non-empty rework report does not
block or gate anything.

## Note

`/compass:flow` advises; it does not gate. The gates live in the per-issue
pipeline where the evidence is. Flow's job is to make sure no issue is
quietly stuck, off-approach, or owing a follow-up - not to add
another gate.
