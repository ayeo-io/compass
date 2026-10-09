---
description: Report on one issue, or list them all
argument-hint: "[issue-slug]"
allowed-tools: Read, Bash, Glob, Grep
---

# /compass:status

Report the state of Compass work on disk. Read-only - this changes nothing.

**Scope:** $ARGUMENTS - if an issue slug is given, drill into just that
issue; if empty, render the board across every issue under `.compass/work/`.

`/compass:status` answers *"what should I look at?"*. For the managed
cross-issue view - triage, blockers, owed-follow-up aggregation, and the
periodic digest - use `/compass:flow`.

## What this command is for

Someone asking for status wants what they would get from glancing at a
physical board: what is blocked, what is moving, what is next, what is done.
In plain English, in a few lines, with detail available if they ask.

They do **not** want a per-issue dump of delivery approaches, stages, gate
fractions and artifact codes. Those are Compass's internal vocabulary;
making the reader decode them to find their own work inverts what the
command is for.

So: **the board is the default. Everything else is drill-down.**

## Procedure - no argument (the board)

1. **Read the issues.** List `.compass/work/*/`; `manifest.yml` is each issue's
   manifest. Prefer one scripted pass over per-issue tool calls - a mature repo
   can hold hundreds, and the reader is waiting.

2. **Place each issue in exactly one column**, most urgent first:

   | column | means |
   |---|---|
   | **BLOCKED** | cannot progress without a decision or an owed follow-up being settled: `compass check` fails, an owed follow-up, a missing human approval on an irreversible change |
   | **READY TO SHIP** | all gates green and `compass check` passes, but not yet marked shipped - finished work nobody has closed |
   | **IN PROGRESS** | started, not finished: an issue whose state is in-progress or in-review. An issue in flight stores no status; `compass flow` reads its state from its records |
   | **NEXT UP** | ready to start (defined and refined, no work yet), or held in the backlog |
   | **DONE** | a stored status of `done`, whatever its close reason |

3. **Write each column as prose, not a table.** Name the issue and say *why
   it is in that column* - the reason is the useful part. Two or three
   sentences per column. Where a column has many members, name the ones
   needing a decision and give a count for the rest.

   For **DONE**, a count is almost always enough. Nobody scans finished
   work.

4. **Account for what cannot be placed.** An issue with no readable
   `manifest.yml` cannot honestly go in any column. Report the count on
   its own line. Do not quietly drop it and do not guess: a board that
   silently omits part of the work looks complete when it is not.

5. **Lead with anything blocking a ship**, and keep the whole thing to one
   screen. If the reader wants the delivery approach, stage, gates or
   evidence they will ask - or run `/compass:status <issue-slug>`.

### Shape of a good answer

```
BLOCKED (2)
  gcp-internal-test-env-apply owes BF-POSTAPPLY, and it is the terraform-apply
  issue, so it needs a human sign-off to move. address-comprehensive-review's
  follow-up is actually done - recorded as `paid: true` where the check wants
  `status: paid`, so it is a one-word fix rather than real work.

READY TO SHIP (1)
  pypsa-api-v020-extensions - all six gates green, check passes. Just needs
  its commit made.

IN PROGRESS (5)
  import-coordinate-crs-normalisation is furthest along (criteria defined and
  designed, not verified). The other four are barely started.

NEXT UP
  Nothing is ready to start, and the backlog is empty.

DONE 131 shipped. 94 more issues have no readable manifest.
```

That is the whole report. It fits on a screen, every line supports a
decision, and no Compass vocabulary appears in it beyond issue names.

## Procedure - with an issue slug (drill-down)

Here the internals *are* the point. Report:

- **Delivery approach** - from `delivery-approach.md` / `manifest.yml`: the
  nearest reference shape, the four assessment dimensions, and any policy
  rule that fired.
- **Stage** - inferred from which artifacts exist: `delivery-approach.md`
  -> assessed; `acceptance-criteria.md` -> criteria defined;
  `requirements-review.md` -> requirements reviewed; `technical-design.md` ->
  designed; `distribution-map.md` -> broken down;
  `verification-report.md` -> verified. Cross-check the approach's
  de-scope ledger so a *collapsed* stage is not reported as *missing*.
- **Gates** - from `verification-report.md` and `manifest.yml`'s `gates:`. Run
  `compass check --issue <slug>` for the mechanical view (read-only).
  **Say when a check passes without checking anything.** "no changed_files recorded yet"
  and "0/N pass gates" are green lines that assert nothing; reading them as
  progress is how an issue ships untraced.
- **Owed follow-ups** - scan `delivery-approach.md`'s de-scope ledger and
  the approach's standing obligations. Flag loudly:
  - an unsettled **hotfix follow-up** (the approach record not completed,
    reproduction test not promoted to a scenario, no root-cause devlog
    line);
  - an **unbacked marketing claim** - a claim in `positioning.md` with no
    passing scenario behind it;
  - any de-scoped artifact still marked owed.

## Note

If `delivery-approach.md` is missing for a directory under `work/`, that
issue was started without an assessment - flag it as a guardrail violation, not
merely an incomplete issue. On the board, that belongs in BLOCKED.
