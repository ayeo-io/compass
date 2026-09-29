---
description: Pick up an issue with state on disk
argument-hint: "<issue-slug>"
allowed-tools: Read, Write, Glob, Grep
---

# /compass:resume

Resume an issue that already has state on disk - a later session, or a
different agent, picking up where the work was left. The artifacts were
written precisely so the process never has to be re-derived.

**Issue:** $ARGUMENTS

## Procedure

1. **Locate the issue.** Find `.compass/work/<issue-slug>/`. If the slug is
   ambiguous or missing, list the available issues and ask. Once found,
   write the slug into `.compass/current-task` - that pointer is how every
   `compass` call (and a later session) resolves to *this* issue without a
   `--issue` flag.
2. **Read `delivery-approach.md` and `manifest.yml` first.**
   `delivery-approach.md` is the human-readable contract for this issue -
   the delivery approach, the per-stage weight, the gate set, the orchestration,
   the de-scope ledger; `manifest.yml` is its machine-readable manifest, what the
   CLI reads. Everything else is read in light of them. If
   `delivery-approach.md` carries a re-assessment revision, read the latest
   revision.
3. **Read the artifacts in pipeline order** - `intent.md`,
   `acceptance-criteria.md`, `requirements-review.md`, `technical-design.md`,
   `distribution-map.md`, role artifacts, `verification-report.md` - and
   the `devlog.md` for the running narrative.
4. **Determine where things stand.** Which stage is complete, which is
   next. Cross-check against the de-scope ledger so a collapsed stage
   counts as handled, not pending. Note any owed follow-up.
5. **Report, then continue.** State plainly: the delivery approach, the
   last completed stage, the next command to run, and any blocker or owed
   follow-up. Then continue from that stage - invoke the matching
   `/compass:*` command's procedure.

## When the artifacts do not answer the question

If `delivery-approach.md` does not explain the process from here, the
assessment under-sized it. Say so and re-assess (`/compass:assess --reassess`) rather
than improvising a process. A guessed process is not a resumed issue.
