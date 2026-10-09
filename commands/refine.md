---
description: Requirements review - resolve ambiguity, check the spec against governance
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
---

# /compass:refine

Refine is the requirements review: it hardens the spec before any design is
built on it. It resolves ambiguities and QAs `acceptance-criteria.md` against
itself and against the governance in force - the guardrails and strategies.

## First: is the requirements review in play?

Read `delivery-approach.md`. The review is **collapsed on a quick fix** (the
single scenario was certified unambiguous when it was defined), **collapsed
on a hotfix** (the reproduction *is* the clarification), and **skipped on a
spike** (there is nothing to QA - the behaviour is the unknown). If
`delivery-approach.md` collapsed or skipped it, stop - say so, confirm the
de-scope reason still holds, and point the user to `/compass:plan`. Do not
re-add a stage the approach skipped, and do not skip one it kept.

On a collapsed- or skipped-review approach the **Definition of Ready** is
satisfied by construction:
- a quick fix, by the assess stage certifying the single scenario
  unambiguous;
- a hotfix, by the reproduction test being the spec;
- a spike, by having no acceptance criteria to be ready against.

So there is no separate checklist to fill. On the regular and full approaches
it is the explicit gate below.

On the regular approach, the review is a lightweight-to-thorough pass - lightweight, never
absent. On the full approach it is a thorough pass with an explicit ambiguity ledger and
non-engineering role review.

## What the define stage already did - and what is left for you

The spec-author ran a four-scan self-review inline at the end of the define
stage, before handing the spec over: a **placeholder** scan, an
**orphan**-intent scan, an **untestable**-`Then` scan, and an
**ambiguous**-quantifier scan. The spec-author fixed those in place. The
self-review runs on every approach, including a quick fix.

**Refine does not repeat them.** Re-running four mechanical scans over a file
someone has just scanned spends a stage to find nothing. If you do hit one
still outstanding, that means the self-review was skipped - say so, then fix
it; do not quietly absorb it as your own work.

What is left for you is everything the author could not settle alone:

- **Contradictions** between scenarios that cannot both hold.
- **Gaps** across the whole set - a stated outcome, or a `intent.md` success
  signal, with no scenario.
- **Governance conflicts** - a scenario that crosses a guardrail, or departs
  from an applicable strategy with no recorded reason.
- **Ambiguities that need a decision** rather than a correction, each
  recorded in `requirements-review.md` with its resolution and who made it.

The dividing line is who can close the finding. An unfilled placeholder has
one correct answer and the author already knows it. "Which of these two
scenarios is wrong?" does not, and that is what a stage with a reviewer in it
is for. The same split is written from the other side in
`skills/bdd-specification/SKILL.md`.

## Setup

- Load `bdd-specification`; the `spec-author` agent owns this continuation.
- Run `compass policy show` for the rules in force, and read the reasons in
  `${CLAUDE_PLUGIN_ROOT}/governance/guardrails.md` and `strategies.md` - the
  spec is QA'd against the guardrails and the applicable strategies. An
  unmigrated 5.x project runs on its own copied `governance/` until
  `compass policy migrate`.
- If a non-engineering role is in play, this is where they review: invoke
  `product-owner` (intent fidelity against `intent.md`) and/or `product-marketer`
  (every planned claim has a candidate scenario).

## Procedure

1. **Self-QA the spec.** Contradictory scenarios? Undefined terms? Edges
   named but not specified? Failure modes missing?
2. **Governance QA.** Does the spec meet the guardrails (especially
   acceptance-before-code and traceability) and respect the applicable
   strategies, including the voice strategies where claims are involved?
3. **Resolve.** For each ambiguity, either resolve it (update
   `acceptance-criteria.md`) or record it as an open question with an owner.
   An unresolved ambiguity is not allowed to silently pass into design.
4. **Write `requirements-review.md`** from the output of
   `compass issue template show requirements-review`, which renders the checklist from the
   issue's entry lists: the ambiguity ledger, each entry resolved or assigned.

   **Where it goes.** `docs/compass/<created>-<issue-slug>/requirements-review.md`, where the
   date is the manifest's `created:` field - not today's. On an approach that
   earns the document (the full approach), register it:
   `compass issue artifact set requirements-review --status draft --path <that path>`. The CLI
   refuses a path that climbs out of the project, so the record is checked
   rather than claimed. The regular approach does not earn it, and the CLI refuses to
   register it there: write the file and leave it unregistered. `compass next`
   takes the file as refine's record. If you had to create `docs/compass/`, **say so in one
   line** - a directory appearing with nothing said is how it gets deleted by
   hand or committed by accident.

## Reassessment trigger

If the review reveals the spec is bigger or more ambiguous than the
assessment assumed, **stop and re-assess** (`/compass:assess --reassess`) - do
not push a regular-approach process through a problem that needs the full
approach.

## Hand-off

Close the review by handing the ambiguity ledger to a human. This is the last
review before work is designed against the spec, so the questions here are
about decisions, not wording.

> I have written the ambiguity ledger to
> `docs/compass/<created>-<issue-slug>/requirements-review.md`, and updated
> `acceptance-criteria.md` where a resolution changed it.
>
> I found and resolved N ambiguities. The ones that changed what gets
> built are: <short list>.
>
> Worth a read before the plan stage. Specifically, look for:
> - **Decisions you disagree with** - each entry records what was decided and
>   by whom; a resolution recorded is not the same as a resolution you would
>   make.
> - **Resolutions that quietly widened scope** - a question answered by
>   adding work should be visible as such.
> - **The Definition of Ready** - every box is checked, and each one is meant
>   to be true rather than ticked.
>
> On approval this goes to the plan stage, which turns the spec into a
> technical approach and runs the governance check against it.

Wait for approval only if `refine` is in the manifest's `checkpoints:`.
The project's `autonomy` setting, read from `compass.yml` (or from
`.compass/config.yml` in a project without one), decides that list,
and `compass approach show` shows it. If `refine` is not listed, still
write the ambiguity ledger and show this hand-off, then say you are going on without
waiting and name the setting, with "Next" in place of "On approval". Log
the skipped checkpoint to `devlog.md`, so the person can review it later and
send the issue back.

## Voice

The ambiguity ledger is read by the person who has to decide, not filled
into a form. Say what was unclear, the call, and why - never a bare
label-and-status row. See `skills/compass-runtime/writing-voice.md`.

## Gate

- `requirements-review.md` exists;
- every ambiguity is resolved or owned;
- the spec passes governance QA;
- the **Definition of Ready** checklist at the foot of
  `requirements-review.md` is fully checked - that is the entry gate into
  the plan stage, and an unchecked box stops the plan stage from starting.

Log to `devlog.md`. Next: `/compass:plan`.
