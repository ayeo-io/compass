---
description: Bring the role perspectives to one decision
argument-hint: "<the question or decision to work through>"
allowed-tools: Read, Write, Edit, Glob, Grep
---

# /compass:consult

Convene several role perspectives on one question, make the tradeoffs
explicit, and record the decision. Use this when a choice genuinely sits
across roles - a scope cut that affects a marketing claim, an architecture
call that changes the user's experience, a priority conflict between intent
and effort.

**Question:** $ARGUMENTS

## First: make sure this is a Compass project

Run `compass init`. It creates `.compass/` if it is not there and reports that
it did; if the project already exists it says so and changes nothing, so this
is safe to run every time and you do not need to check first.

**Report the result to the user in one line when it created the project.** A
`.compass/` directory appearing with no word said is how someone deletes it by
hand, or commits it without meaning to. It creates project state only - the
shipped defaults stay in force, and writing a `compass.yml` for the project is
what `/compass:init` offers separately.

## Setup

- Load `intent-interview` and read its `role-translation.md` - the whole point of a consult is one question
  read through several roles, keeping each role's concern separate.
- Read the relevant issue artifacts so the discussion is grounded in what
  is actually on disk: `delivery-approach.md`, `intent.md`,
  `acceptance-criteria.md`, `technical-design.md`, `positioning.md`,
  `ui-contract.md` - whichever bear on the question.
- Read `governance/` - a consult cannot decide its way past a guardrail.
  Strategy-vs-strategy tension is exactly what a consult *is* for; a
  guardrail is not up for negotiation.

## Agent roster

The following agents are part of the standard consult roster and can be
convened by name:

| Agent | Invocation | Auto-trigger condition |
|---|---|---|
| `product-owner` | `/compass:consult product-owner` | When a product owner is in play (`intent.md` exists) |
| `product-marketer` | `/compass:consult product-marketer` | When a marketer is in play (`positioning.md` exists) |
| `architect` | `/compass:consult architect` | When the manifest's `assessment.labels` contains `public-api`, a service name from `architecture/relations.md`, or a `lens_trigger_tag` from `architecture/invariants.yml` |
| `planner` | `/compass:consult planner` | On request |
| `reviewer` | `/compass:consult reviewer` | On request |

**Registration contract:** a role's agent is invoked only if its agent file
exists in `agents/`. If the file does not exist, `/compass:consult`
skips that perspective and records the absence in `devlog.md` rather than
failing. This stops a consult calling an agent that the current issue is
still writing.

**Named invocation:** pass the agent name as a positional argument:
```
/compass:consult architect
```
This convenes only the `architect` agent, regardless of auto-trigger
conditions. It writes `architecture-notes.md` to the issue directory.

**Auto-convene (no args):** when invoked with no positional agent name,
`/compass:consult` auto-convenes every agent whose trigger condition is
met for the current issue.

## Procedure

1. **Choose the roles.** Convene the roles the question actually needs - some
   of `product-owner`, `product-marketer`, `architect`, `planner`,
   `reviewer`, and the designer or QA perspective. Name which roles took
   part and why.
2. **State the question** crisply, with the constraints that bound it (the
   guardrails, the delivery approach, fixed deadlines).
3. **Each role speaks in its own vocabulary.** The product owner argues
   intent fidelity; the marketer argues claims and voice; the planner
   argues feasibility and architecture; the reviewer argues risk and the
   guardrails. Do not let one role speak for another.
4. **Surface the tradeoffs** explicitly - what each option costs each role.
   Note where roles agree and where they genuinely conflict.
5. **Record the decision.** Append to the issue's `devlog.md`: the
   question, which roles took part, the options, the tradeoffs, the
   decision, and the rationale. If the decision changes scope or the
   delivery approach, that is a trigger to re-assess
   (`/compass:assess --reassess`) - say so.

## Reassessment trigger

Some consult outcomes do more than record a tradeoff - they change the
scope, the boundary, or the migration surface of the current issue. When
that happens, a re-assessment is not optional.

**Any consult outcome that changes a service boundary or migration scope
must end with a re-assessment:**

```
/compass:assess --reassess --reason "<consult id> - <what changed and why>"
```

Examples of outcomes that need a re-assessment:

- The consult decides to extend a planned migration to cover an adjacent
  service that was not in the original scope.
- A boundary call moves a module from one service to another, adding files
  that were not in `technical-design.md`.
- A scope cut removes a deliverable that was in `acceptance-criteria.md`.

In all these cases, file the re-assessment immediately after the consult
decision is recorded in `devlog.md`. The re-assessment is the signal that
`compass retro` reads - absorbing a mis-assessment silently loses the
signal.

## Gate

The decision is written to `devlog.md` with its rationale and the tradeoffs
it accepted. A consult that ends without a recorded decision has not
finished. If the decision touches the delivery approach, follow it with a
re-assessment.
