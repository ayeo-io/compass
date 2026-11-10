---
description: Report on one issue, or list them all
argument-hint: "[issue-slug]"
allowed-tools: Read, Bash(compass *), Glob, Grep
---

# /compass:status

Report the state of Compass work on disk. Read-only - this changes nothing.

**Scope:** $ARGUMENTS - if an issue slug is given, report on that issue
in detail; if empty, render the board across every issue under `.compass/work/`.

`/compass:status` answers *"what should I look at?"*. For the managed
cross-issue view - triage, blockers, owed-follow-up aggregation, and the
periodic digest - use `/compass:flow`. To list every issue by state, run
`compass flow` (`docs/cli.md`).

## What this command is for

Someone asking for status wants what they would get from a quick look at
a physical board: what is blocked, what is moving, what is next, what is done.
In plain English, in a few lines, with detail available if they ask.

They do **not** want a per-issue dump of delivery approaches, stages, gate
fractions and artifact codes. Those are Compass's internal vocabulary;
making the reader decode them to find their own work is the opposite of
what the command is for.

So: **the board is the default. Everything else is detail on request.**

## Procedure - no argument (the board)

1. **Read the issues.** List `.compass/work/*/`; `manifest.yml` is each issue's
   manifest. Prefer one scripted pass over per-issue tool calls - a mature repo
   can hold hundreds, and the reader is waiting.

2. **Place each issue in exactly one column**, most urgent first:

   | column | means |
   |---|---|
   | **BLOCKED** | cannot progress without a decision or an owed follow-up being settled: `compass check` fails, an owed follow-up, a missing human approval on an irreversible change |
   | **READY TO SHIP** | all gates green and `compass check` passes, but not yet marked shipped - finished work nobody has closed |
   | **IN PROGRESS** | started, not finished: an issue whose state is in-progress or in-review. An issue in progress stores no status; `compass flow` reads its state from its records |
   | **NEXT UP** | ready to start (assessed, no work yet), or held in the backlog |
   | **DONE** | a stored status of `done`, whatever its close reason |

3. **Write each column as prose, not a table.** Name the issue and say *why
   it is in that column* - the reason is the useful part. Two or three
   sentences per column. Where a column has many members, name the ones
   needing a decision and give a count for the rest.

   For **DONE**, a count is almost always enough. Nobody scans finished
   work.

4. **Account for what cannot be placed.** An issue with no readable
   `manifest.yml` cannot honestly go in any column. Report the count on
   its own line. Do not leave it out without saying so, and do not guess: a board that
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
  import-coordinate-crs-normalization is furthest along (scenarios written
  and built, not yet reviewed). The other four are barely started.

NEXT UP
  Nothing is ready to start, and the backlog is empty.

DONE 131 shipped. 94 more issues have no readable manifest.
```

That is the whole report. It fits on a screen, every line supports a
decision, and no Compass vocabulary appears in it beyond issue names.

## Procedure - with an issue slug (drill-down)

Here the internal details *are* what the reader wants. Report:

- **Delivery approach** - from `compass approach show` / `manifest.yml`: the
  nearest reference shape, the three scored dimensions, and any policy
  rule that fired.
- **Stage** - from `compass next --issue <slug>`, which reads the records
  and names one of the four stages: assess, specify (the scenarios a
  person approves before code), build (the tests and the code) or ship (the
  record, the approval and the commit). It also prints the next step. An issue
  assessed before the path shows its old stage as the path stage it maps
  to.
- **Gates** - from `manifest.yml`'s `gates:`. Run
  `compass check --issue <slug>` for the mechanical view (read-only).
  **Say when a check passes without checking anything.** "no changed_files recorded yet"
  and "0/N pass gates" are green lines that assert nothing; reading them as
  progress is how an issue ships untraced.
- **Owed follow-ups** - scan `manifest.yml`'s `follow_ups:` and the
  approach's standing obligations. Report clearly:
  - an unsettled **defect follow-up** on a change assessed with
    `urgency: live-defect`, or a hotfix assessed before the path (the
    reproduction test not promoted to a scenario, no root cause stated);
  - an **unbacked marketing claim** - a claim in `manifest.yml`'s `claims:`
    with no passing scenario behind it;
  - any de-scoped work still marked owed.

## Note

If the manifest of a directory under `work/` has no `delivery_approach:`,
that issue was started without an assessment - flag it as a guardrail violation, not
merely an incomplete issue. On the board, that belongs in BLOCKED.
