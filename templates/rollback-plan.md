<!--
TEMPLATE: rollback-plan.md
Written when the assessment carries `migrations` (RP-REQUIRE-006).

THIS IS A REHEARSAL RECORD, NOT A PLAN. Two sources agree and they are the
reason this template has the shape it has:

  SWEBOK v4 §6.3.3 - "a planned and REHEARSED rollback is done before a new
  version of the software is deployed in production."

  Dave Farley, Continuous Delivery - the answer to rollback is a mechanism
  you exercise (blue/green, canary, versioned migration scripts), not a
  document you write. Following the practice removes most of the reasons to
  roll back at all.

So the section that matters is the last one. A rollback nobody has run is a
guess, and a guess recorded as a plan is exactly the assertion the
evidence-not-assertion guardrail (`G4`) exists to reject. `compass check` reports a rollback plan whose rehearsal
section records no rehearsal.

Register the finished file as `rollback-plan` evidence:
  compass evidence add EV-RB-1 --type rollback-plan --path rollback-plan.md

Keep it under 120 lines. Delete this comment block when you fill it in.
-->

# Rollback plan - {{ISSUE_SLUG}}

<!-- compass:render document-header -->
<!-- /compass:render -->

## What breaks

<!-- What a bad deploy of THIS change looks like from the outside, and how
     you would know. An alert, a metric, a user report. If nobody would
     notice, say so - that is a finding in itself. -->

{{The failure, and the signal that shows it.}}

## How we go back

<!-- The mechanism, in the order it is run. Prefer a command over a
     description of a command.

     Say plainly whether this is a rollback or a roll-forward. Google's SRE
     workbook is blunt about it: "detect, roll back, fix, and roll forward".
     Some changes cannot be rolled back - a destructive migration, a message
     already consumed - and the honest answer there is a forward fix, named
     as one. -->

| Step | Command | Expected |
|---|---|---|
| 1 | {{`make db-rollback REV=<previous>`}} | {{schema back at <previous>}} |
| 2 | {{`kubectl rollout undo deploy/api`}} | {{previous image serving}} |

**Data:** {{what happens to rows written by the new version - preserved,
discarded, or migrated back. If any is lost, say what and how much.}}

**Point of no return:** {{the step after which rollback is no longer possible,
or "none".}}

## When this was last rehearsed

<!-- THE SECTION THIS DOCUMENT EXISTS FOR. Not "we will rehearse it" - when
     you ran it, against what, and what happened. A date, a target, an
     outcome, a duration.

     If it has not been rehearsed, write that. An honest "not yet" is a
     blocker a reviewer can act on; a plan that quietly implies rehearsal is
     one nobody can. `compass check` will report it either way, which is the
     point. -->

{{2026-08-24, against a copy of production taken that morning. Restored in
4m12s; row counts matched on every table; two rows written after the snapshot
were lost as expected.}}

**Next rehearsal:** {{when, and what would trigger one sooner.}}
