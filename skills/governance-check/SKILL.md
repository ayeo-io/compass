---
name: governance-check
description: Checking a design against the guardrails and strategies. Load at specify when a change needs a design.
---

# Governance Check

Two kinds of rule govern Compass, and the governance check is the
moment they are applied to a design, spec, or change. It is not one pass/fail
against one document - it is three distinct walks against three
distinct sources, and each has its own standard of proof. The prose is in
`${CLAUDE_PLUGIN_ROOT}/governance/`; the rules in force are what
`compass policy show` prints. An unmigrated 5.x project with a copied
`governance/` is refused until `compass policy migrate` on 8.x.

- `guardrails.md` - **hard, checkable, blocking.** A guardrail is cleared with
  evidence; a failed guardrail stops the work. A guardrail beats a strategy.
- `strategies.md` - **soft, assessed, accretive.** A strategy is judged, not
  cleared; following it is the default, departing from it is allowed *and
  recorded*. A strategy never stops the work on its own.
- `routing-policy.md` - the same split applied to assess: the evidence rows
  and the configuration's floors **bound** the evidence a change owes, and
  the advisory strategies **bias** the assessment.

Read the governance fresh before you start: a cached memory of an earlier
read is not the current file.

**Record which governance you read.** Write the `Policy:` line that
`compass policy show` prints (for example `compass-checks@9.0.0` and its
sha256) and the issue's `generation:` from `manifest.yml` into the check. An
unmigrated 5.x project is refused, so it has no `Policy:` line until it
migrates. A check that names nothing cannot be told apart from one run
against wording that has since changed, and the prose files carry no version
of their own to compare.

## Before you start

Run `compass policy show` to see the rules in force, then read the reasons in
`${CLAUDE_PLUGIN_ROOT}/governance/guardrails.md`, `strategies.md` and
`routing-policy.md`. A new project has no `governance/` directory (an
unmigrated 5.x project with a copied one is refused): the fixed check set is in force, and `compass.yml` holds the
project's settings, which can only add to it. The check set alone is a complete governance state: "the shipped default
guardrails, the shipped default strategies, and zero project additions" is a
fully legitimate thing to check against. Do not treat an un-extended project
as a reason to stop.

If the project has `governance/decisions/`, read it too. Each entry records a
product decision a named person made, and never changes. A design that
reverses one is reported as "settled by <path>", for the person to reopen
with a new entry, not passed or failed on your judgment.

## Walk 1 - the guardrails (hard, evidence)

Walk the design, spec, or change against every applicable guardrail - the five
shipped defaults and any project guardrails.

The five default guardrails:

- **Tested before it lands.** Is the work shaped so that nothing reaches
  `main` without a passing automated test it traces to? At specify, this means
  the design introduces work test-first (the TDD strategy is how) and the test
  surface is planned. At build and ship, it is cleared with the recorded run.
- **Acceptance defined before it is built.** Does every piece of planned
  code trace to a stated, checkable acceptance criterion that exists *before*
  the code? The BDD strategy (Given/When/Then scenarios) is the default way to
  satisfy this; the guardrail itself is the outcome - acceptance is stated and checkable.
- **Traceability holds.** Are both chains planned for and intact -
  code → acceptance criterion → intent, and public claim → backing criterion?
- **Evidence, not assertion.** This one is *about* the others: a guardrail
  is cleared with artifacts and command output, never a claim. When you record
  a guardrail result, the proof is the artifact.
- **A human signs off on the irreversible.** Does anything that can lose
  data, move money, or breach auth or privacy have an explicit human checkpoint
  before it lands? Check the design routes such work to where the checkpoint <!-- vocabulary-scan: allow - route is a verb here -->
  happens.

Then any project guardrails - concrete, measurable floors a project has added
(a coverage floor, a no-secrets-committed rule, a tested-rollback rule). Floors
only ratchet up: a design can exceed a floor, never fall short of one.

**The standard of proof is evidence.** At specify you are checking the design is
*shaped* to clear each guardrail; at ship the guardrail is *cleared* with the
verifier's artifacts. Either way: "looks fine" is not a result. For each
guardrail, record **clears** (with the evidence, or the design element that will
produce it) or **fails** (with the specific guardrail and how it is crossed). A
design that crosses a guardrail does not proceed - it is revised, or the issue
is re-assessed. There is nothing to waive a guardrail *for*; a guardrail beats every
strategy and every convenience.

## Walk 2 - the strategies (soft, assessed)

Walk the same design, spec, or change against the applicable strategies - the
shipped default method strategies (including **BDD** and **TDD**) and any
project strategies (product, engineering, voice & positioning).

The standard here is different and you must keep it different. A strategy is
**assessed**, not cleared:

- Did the work follow the strategy? This is honest judgment - is this the
  simplest thing that works, does it follow the team's engineering
  strategies, does the copy fit the voice strategies.
- Where it departed from a strategy, **is the departure recorded?** A recorded
  departure is the system working, not a failure. An *unrecorded* departure is
  the thing to flag - not because the departure is wrong, but because it was
  silent.
- Record the result **as judgment**, clearly labeled as judgment - never
  dressed up as evidence. A strategy not followed is a note and a conversation,
  not an automatic stop.

## Walk 3 - the evidence the issue owes

Confirm the design is consistent with the issue's `evidence_required` list
(`compass approach show`) and `${CLAUDE_PLUGIN_ROOT}/governance/routing-policy.md`
(an unmigrated 5.x project is refused until it migrates):

- **The configuration's rules** - did every floor that should have fired,
  fire? Are the `immovable_gates` in the manifest's gates? A design that
  quietly assumes less evidence than the issue owes fails here: for
  example, a change that reaches `auth` with no `G5` label.
- **The advisory strategies** - where the work departs from one, is the
  departure recorded in the `--justify` reason or the report to the person?
  A recorded departure is fine; a silent one is the flag.

## How to run the check (at specify)

1. Run `compass policy show` and read the prose in
   `${CLAUDE_PLUGIN_ROOT}/governance/` (an unmigrated 5.x project is
   refused until it migrates).
2. Walk 1 - guardrails - against the design and the spec it builds on. Record
   per guardrail: **clears** (with evidence or the design element that produces
   it) or **fails** (with the specific guardrail).
3. Walk 2 - strategies - against the same. Record per strategy as **judgment**:
   followed, or departed-and-recorded, or departed-silently (flag it).
4. Walk 3 - the evidence - confirm the design assumes no less evidence than
   the issue owes, and that each strategy departure is recorded.
5. Record all three results with `compass evidence add` and show them in the
   report to the person, with the guardrail findings and the
   strategy assessment **visibly separate** - evidence on one side, judgment
   on the other.
6. A failed guardrail **stops the build** - revise the design or re-assess.
   A strategy departure does **not** stop the build; record it and, if it
   matters, raise it.
   That asymmetry is the whole point of the split.
7. If a guardrail itself seems wrong, that is an amendment conversation
   (a reviewed change to Compass's check set, or a tighten-only setting in
   the project's `compass.yml`, checked by `compass policy lint`, with the
   reason in the commit message; no setting can loosen a guardrail, and
   excusing one check on one issue needs a waiver a person approves,
   `docs/waivers.md`) - never a quiet override mid-issue. If a
   strategy keeps getting overridden the same way, that is a curation signal -
   fix the strategy or write down the thing overriding it.

## Writing the design down

Write a design at specify, before the check, when the change has a design
decision worth arguing with; a change with no design decision needs none.
Compass writes no design document (ADR-091). Read
`skills/governance-check/writing-the-design.md` for what a design holds,
the optional sections and how many to use, the diagrams, the named patterns
(`S16`), the well-architected pillars (`S15`) and the four-scan self-review.

## Anti-patterns

- **The one-line pass** - "governance check: pass" with no per-guardrail,
  per-strategy detail. If you cannot name what you checked, you did not check.
- **Conflating the two walks** - clearing a guardrail on judgment, or treating
  a strategy departure as a hard stop. The standards of proof are different on
  purpose; collapsing them is the failure the strategies/guardrails split was
  built to prevent.
- **The dressed-up strategy** - recording a strategy assessment as if it were
  evidence-backed. It is judgment; label it.
- **The convenience override** - treating a guardrail as advisory because
  honoring it is inconvenient. A guardrail beats every strategy and every
  deadline; inconvenience is not a counter-argument.
- **Checking the stale file** - reviewing against a remembered copy of the
  governance, so the check runs against wording that has since changed.
  Recording the `Policy:` line and the generation makes this visible.
- **Floor erosion** - reading a floor or a project check as a target to *hit*
  rather than a minimum to *clear*. Floors only ratchet up.
- **Silent evidence assumption** - a design that assumes less evidence than
  the issue owes, unnoticed.
- **Treating an un-extended project as broken** - the shipped defaults alone
  are a complete governance state; check against them.
