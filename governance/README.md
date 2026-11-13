# Governance - Strategies and Guardrails

Compass is governed by two kinds of thing, and keeping them separate is the
point of this directory.

- **Guardrails** - few, hard, checkable, blocking. The things that must never
  happen. A guardrail is cleared only with evidence, and a failed guardrail
  stops the work. See `guardrails.md`.
- **Strategies** - many, soft, directional, assessed. How the team tends to
  work and what it prefers. A strategy *biases* a decision. It can carry
  blocking checks that a recorded step-off makes advisory, as the four-layer
  acceptance strategy (`S17`) does. See `strategies.md`.

A third file, `routing-policy.md`, applies the same split to assessment
itself: routing rules *bound* what it may do, routing strategies *bias*
what it does by default. A fourth, `strategies-rationale.md`, holds the
incidents behind the strategies and states no rule of its own.

Guardrails and strategies are separate so a judgement is never presented as a
hard gate: a guardrail blocks and is cleared with evidence, a strategy guides
and is assessed.

---

## Why the split matters

**It is a gradient, not a threshold.** A single governing document is
all-or-nothing - you have one or you don't, and a half-written one feels
broken. Strategies and guardrails have a valid *light* state: the shipped
default guardrails, the shipped default method strategies, and zero
project-specific additions. That is a complete, usable governance state, not
a skipped step. A team starts there and adds a guardrail only when it hits
something that must never recur. This is what makes `/compass:init` optional -
see `docs/quickstart.md`. Since 6.0.0 a team makes changes to checks, gates and
rules in its `compass.yml`, which extends the shipped defaults (see
`docs/configuration.md`). `compass.yml` cannot hold strategies:
`compass policy lint` reports `L-SCHEMA` for a `strategies:` key. The shipped
strategies are the ones in force, and a rule a person has had to repeat can be
recorded as a project lesson (`compass lesson propose`), which is advice and
never a gate.

**It keeps honest things honest.** Guardrails are *checkable* - a test ran, a
scan passed, a human approved. Strategies are mostly *assessed* - is this clear,
does it fit our voice, is this the simplest thing that works - and a team can
step off one with a recorded reason. Naming them
differently stops a judgement call being presented as a hard gate. The
evidence-not-assertion guardrail (`G4`) applies cleanly to guardrails; strategies are
honestly the reviewer's judgement, and are labelled as such.

**It matches the effort to the risk.** The form of a practice can be a
strategy while its outcome is a guardrail. Compass's headline example: *being
tested before it lands* is the "tested before it lands" guardrail (`G1`) -
hard, checkable, universal. *Red-green-refactor* is a default strategy - the
strong, shipped-on way to get there, but a spike can suspend it. A
one-character typo fix still has to be tested before it lands; it does not
have to do the red-green cycle. That distinction is how Compass keeps a small
change from carrying heavy process, without dropping the guardrails.

---

## The conflict rule

When two pieces of governance disagree:

1. **A guardrail always beats a strategy.** No strategy, however sensible,
   licenses crossing a guardrail.
2. **Guardrail vs guardrail** should not happen - if it does, the guardrail
   set has a bug; fix the set, do not improvise around it.
3. **Strategy vs strategy** is resolved by context: the delivery approach
   decides, or a human picks.
   A strategy losing a context call is normal - that is what "soft" means.

There is no single supreme document; there is a small hard set that wins, and
a larger soft set that guides.

---

## Curation

Strategies are cheap to add, which is their strength and their risk. A pile of
stale, contradictory strategies is its own kind of mess. So:

- Review `strategies.md` periodically - `/compass:flow` is a natural prompt.
  Drop strategies the team no longer follows; a strategy nobody applies is
  noise.
- Be slow to add guardrails and slower to remove them. A guardrail is a
  promise the whole framework keeps; the shipped five are deliberately few.
- When a strategy keeps getting overridden the same way, that is a signal -
  either the strategy is wrong, or the thing overriding it should be written
  down. Resolve it; do not let it drift.

---

## Files

| File | Holds | Nature |
|---|---|---|
| `guardrails.md` | The 5 shipped default guardrails + a project-guardrails section | Hard, checkable, blocking |
| `strategies.md` | The shipped default method strategies (incl. BDD and TDD) + a project-strategies section | Soft, assessed, accretive |
| `routing-policy.md` | Routing guardrails (bound assessment) + routing strategies (bias it) | Both, applied to routing |
| `strategies-rationale.md` | The incidents and worked examples behind the strategies | Neither - evidence, read when a rule looks arbitrary |
| `quarantine.yml` | Records of intermittent tests explicitly quarantined with a tracking issue | Pairs with the `no-trusted-rerun` rule on evidence-not-assertion (see `strategies.md` `S5`) |

The framework ships these with sane, active defaults. A project that does
nothing runs on them as they are. A new project's
`/compass:init` copies nothing. Editing is accretion, not a precondition.

## A project that copied governance under 5.x

A 6.0.0 project does not copy governance files. It edits `compass.yml`, and the
shipped check set stays in force beneath it. A 5.x project that copied
`routing-policy.yml` or `guardrails.yml` into its own `governance/` and has no
`compass.yml` is refused by every 9.0.0 command that reads the policy
(`governance-copy-removed`, exit 2, ADR-098). It runs `compass policy migrate`
on Compass 8.x first, which writes its `compass.yml`
(`docs/upgrade-9-0-0.md`). A project's own `quarantine.yml`,
`review-rules.yml` and `architecture-sources.yml` are read by path, as before.
