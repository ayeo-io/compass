---
description: Requirements review - resolve ambiguity, check the spec against governance
allowed-tools: Read, Write(./.compass/**), Write(./docs/**), Edit(./.compass/**), Edit(./docs/**), Bash(compass *), Glob, Grep
---

# /compass:refine

Refine is the requirements review: it makes the spec clear and complete
before any design uses it. It resolves ambiguities and checks
`acceptance-criteria.md` against
itself and against the governance in force - the guardrails and strategies.

## First: does the requirements review run?

Read `delivery-approach.md`. The review is **collapsed on a quick fix** (the
single scenario was certified unambiguous when it was defined), **collapsed
on a hotfix** (the reproduction *is* the clarification), and **skipped on a
spike** (there is nothing to check - the behavior is what the spike finds out). If
`delivery-approach.md` collapsed or skipped it, stop - say so, confirm the
de-scope reason still holds, and point the user to `/compass:plan`. Do not
re-add a stage the approach skipped, and do not skip one it kept.

On a collapsed- or skipped-review approach the **Definition of Ready** is
met without further work:
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
someone has just scanned spends a stage to find nothing. If you find one
that is still there, the self-review was skipped - say so, then fix it; do
not fix it without saying so, as if it were your own work.

What is left for you is everything the author could not settle alone:

- **Contradictions** between scenarios that cannot both hold.
- **Gaps** across the whole set - a stated outcome, or a `intent.md` success
  signal, with no scenario.
- **Governance conflicts** - a scenario that breaks a guardrail, or departs
  from an applicable strategy with no recorded reason.
- **Ambiguities that need a decision** rather than a correction, each
  recorded in `requirements-review.md` with its resolution and who made it.

The difference is who can settle the finding. An unfilled placeholder has
one correct answer and the author already knows it. "Which of these two
scenarios is wrong?" does not, and that is what a stage with a reviewer in it
is for. The same split is written from the spec-author's side in
`skills/bdd-specification/SKILL.md`.

## Setup

- Load `bdd-specification`; the `spec-author` agent owns this continuation.
- For a change to behavior a real client can observe, also load `atdd`:
  this stage runs its stage 1, the specification and the DSL.
- Pass the computed model and effort when you invoke the `spec-author` agent:
  `compass approach show --model refine` prints the `model`, and
  `compass approach show --effort refine` prints the `effort`. On
  `inherit`, pass the model family your session runs on (`opus`,
  `sonnet`, `haiku` or `fable`), or leave `model` out when you cannot
  tell. Exit 1 means the issue sets nothing for that value: leave it out,
  so the agent's frontmatter applies.
- Run `compass policy show` for the rules in force, and read the reasons in
  `${CLAUDE_PLUGIN_ROOT}/governance/guardrails.md` and `strategies.md` - the
  spec is checked against the guardrails and the applicable strategies. An
  unmigrated 5.x project runs on its own copied `governance/` until
  `compass policy migrate`.
- If a non-engineering role takes part, they review at this stage: invoke
  `product-owner` (intent fidelity against `intent.md`) and/or `product-marketer`
  (every planned claim has a candidate scenario).

## Procedure

1. **Check the spec against itself.** Contradictory scenarios? Undefined
   terms? Edge cases named but not specified? Failure modes missing?
2. **Check the spec against governance.** Does the spec meet the guardrails (especially
   acceptance-before-code and traceability) and respect the applicable
   strategies, including the voice strategies where claims are involved?
3. **Resolve.** For each ambiguity, either resolve it (update
   `acceptance-criteria.md`) or record it as an open question with an owner.
   An unresolved ambiguity must not pass into design unrecorded.
4. **Write `requirements-review.md`** from the output of
   `compass issue template show requirements-review`, which renders the checklist from the
   issue's entry lists: the ambiguity ledger, each entry resolved or assigned.

   **Where it goes.** `docs/compass/<created>-<issue-slug>/requirements-review.md`, where the
   date is the manifest's `created:` field - not today's. When the issue owes the
   document (regular at `lightweight`, full at `thorough`), register it:
   `compass issue artifact set requirements-review --status draft --path <that path>`. The CLI
   refuses a path outside the project, so the record is checked
   rather than claimed. A regular issue assessed before 7.0.0 does not owe it:
   write the file and leave it unregistered. `compass next`
   takes the file as refine's record. If you had to create `docs/compass/`, **say so in one
   line** - if a directory appears and nobody says so, someone can delete it
   by hand or commit it by mistake.

5. **Record the decisions you took.** Run `compass issue decision add --from-ledger`.
   It reads the ledger and records each entry whose "Decided by" names an agent, so
   the person sees those decisions at the next checkpoint. Run it again after you
   change the ledger: a reworded question is updated, and a changed resolution
   reopens the decision.

## Reassessment trigger

If the review reveals the spec is bigger or more ambiguous than the
assessment assumed, **stop and re-assess** (`/compass:assess --reassess`) - do
not use a regular-approach process on a problem that needs the full
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
waiting and name the setting, with "Next" in place of "On approval". Record
the passed hand-off with `compass issue checkpoint add refine --outcome skipped
--by spec-author`, so the person can review it later and send the issue back. If
`refine` is listed, ask with `compass evidence request --checkpoint refine` and
wait: the person types `/compass:approve` in Claude Code, or runs `compass
evidence approve --checkpoint refine --approver <name> --role <role>` at a
terminal, which records the answer. An issue assessed before outcomes were recorded is not judged: both
commands refuse it and write nothing, so say so and go on.

Before you hand off, run `compass next`. When its first line reads
`Waiting at the refine checkpoint`, the issue holds decisions that no person has
confirmed. Show the listed decisions in the hand-off and wait: the person
confirms them all by typing `/compass:approve` after you run `compass evidence
request --decisions` (or `compass evidence approve --decisions` at a terminal), or
reopens one with
`compass issue decision set`. Do not name the next stage while it waits. On
`autonomous` autonomy `compass next` lists the decisions and does not wait; show
the list in the hand-off.

## Voice

The ambiguity ledger is read by the person who has to decide, not filled
into a form. Say what was unclear, the decision, and why - never a bare
label-and-status row. See `skills/compass-runtime/writing-voice.md`.

## Gate

- `requirements-review.md` exists;
- every ambiguity is resolved or owned;
- the spec passes the check against governance;
- the **Definition of Ready** checklist at the end of
  `requirements-review.md` is fully checked - that is the entry gate into
  the plan stage, and an unchecked box stops the plan stage from starting.

Log to `devlog.md`. Next: `/compass:plan`.
