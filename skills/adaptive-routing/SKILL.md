---
name: adaptive-routing
description: Reading the four assessment dimensions for the CLI. Load at the assess stage.
---

# Adaptive Routing

This skill is the craft behind `approaches/rubric.md`. `approaches/rubric.md`
holds the rules; this skill says how to apply them.

## The mental model

You are not picking a process. You are computing one. The four dimensions are
four independent questions, and the delivery approach is their composition - heavier where
they read high, lighter where they read low. The composition is **biased** by
the routing strategies and **bounded** by the routing guardrails, both in
`governance/routing-policy.md`. The five reference shapes
(quick fix/feature/initiative/hotfix/spike) are shapes the composition tends to
land near, not boxes to sort into.

## The shipped defaults are enough - you work with them

`/compass:init` is optional. The framework ships `governance/` with active
default guardrails, default strategies, and a default routing policy. If a
project has not run init and has no project-specific additions, that is a
valid, complete governance state - you route against the shipped defaults
exactly as you would route against an extended set. "assess and go on day one"
is honest precisely because the defaults are real, in-force content. Never
treat an un-extended `governance/` as a missing prerequisite.

## Scoring the dimensions - heuristics

**risk** - *consequence, never effort.*
- The sign of `critical`: can this lose data, lose money, breach auth/privacy,
  or resist a clean rollback? If yes, it is critical even if it is one line.
- The sign of `trivial`: is the worst case cosmetic, instantly obvious, and
  instantly reversible - with no data, money, auth, or other team touched?
- The common mistake: scoring risk by how hard the change is. A hard
  change can be contained; a trivial-looking change can be critical. Score the
  failure, not the work.

**Familiarity** - *new code, or old code, and is the old code mapped?*
- `brownfield-unmapped` is not a judgement of code quality - it means the
  behaviour is not written down as scenarios. It triggers a routing guardrail
  floor: `behaviour-mapping` must run. Do not skip it.
- "Trivially readable" greenfield or brownfield can be treated as mapped, but
  be honest - "I could figure it out" is not "it is written down."

**Size** - *the dimension humans get wrong most.*
- People under-estimate size far more than they over-estimate it. When
  genuinely torn between two values, take the higher one. Collapsing a stage
  that turned out easy is cheap; discovering during implementation that the
  delivery approach was too light is expensive and demoralising.
- Anchor on concrete tests: `atomic` is one file and no design decision;
  `standard` has one or two design decisions; `large` has real architecture and
  is plausibly parallelisable.

**Goal & role** - *the actual outcome, not the literal request.*
- Read `intent.md` if it exists. "Add a CSV export" under an `intent.md` that says "let
  finance self-serve" may need filters, scheduling, and permissions - the
  literal request under-describes the intent.
- A non-engineering role in play almost always pulls the delivery approach up: it adds
  artifacts and assessed strategies. That is the framework working, not overhead.
- One goal value is not a role: **exploration** - "I cannot frame this well
  enough to deliver it yet." Exploration composes towards the **spike** delivery approach the
  way live-defect urgency composes towards hotfix. Still score all four
  dimensions; the goal is what selects the shape. See "Composing a spike"
  in `composition.md`.

If you cannot justify a value in one honest line, **ask the human.** An
unjustified guess is worse than a question, every time.

## Composing and constraining

The CLI does both. You read the four dimensions and run
`compass approach evaluate --write`; it composes the candidate shape and
applies the floors, caps, immovable gates and role rules. That split is the
determinism boundary and it is the point of the whole design: judgement
produces the assessment, mechanism produces the approach.

The detail - including how a spike is composed - is in
`skills/adaptive-routing/composition.md`, for when a result needs
explaining. `--verbose` names every rule that fired.

## The de-scope ledger - the discipline that makes this auditable

Every phase or check the delivery approach collapses or
skips earns a row in the de-scope ledger, and each row needs an explicit
"safe to skip because…" line.

- **A skip with no justification is not allowed. If you cannot justify it, the
  phase runs.** This is non-negotiable - it is what separates "adaptive" from
  "arbitrary."
- Do not copy a reference shape's standing justification without checking it.
  Confirm it actually holds for *this* issue. quick-fix's "requirements review collapsed - the one
  scenario is unambiguous" is only valid if the scenario really is unambiguous.
- Cap-driven reductions are **not** de-scopes. If the `critical` risk
  cap pins an initiative to one worktree, record that as cap-driven in the
  orchestration section, not in the de-scope ledger. The ledger is for things the
  delivery approach chose to skip, not things a guardrail removed.
- initiative's ledger is empty by definition. If you are writing de-scope rows
  on an initiative delivery approach, you have mis-composed.

### Anti-patterns

- **An approach lighter than the assessment** - composed to "just get the
  change in." `delivery-approach.md` makes this visible; do not do it.
- **A time-saving justification** - a ledger row whose reason is "to save
  time." Time is not a safety argument. The reason must be about why the
  skip is *safe*, not why it is *convenient*.
- **Silent constraint** - applying a floor or omitting an immovable gate without
  a line in `delivery-approach.md`.

## When to re-assess

Re-assessing during an issue is a normal event, not a failure. Trigger it when:

- Implementation reveals the size was under-read - a "small" change is growing
  into a multi-module refactor.
- Refine finds the spec is bigger or more ambiguous than the delivery approach assumed.
- A label surfaces late (you discover the change reaches auth).

Run `/compass:assess --reassess`: re-score the dimensions, write a new `delivery-approach.md`
revision, record what changed and why. A delivery approach quietly outgrown is
the failure; a delivery approach honestly re-assessed is the system working.
