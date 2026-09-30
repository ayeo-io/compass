# Routing Policy - How the Delivery Approach Is Bounded and Biased

Assess (see `approaches/rubric.md` for the sizing rubric) reads the four
assessment dimensions and computes the delivery approach. This file
governs that computation, using
the same split as the rest of `governance/`:

- **Routing rules** - hard. They *bound* what assess may do. A
  routing rule can force a delivery approach to be at least a certain weight,
  cap how far it may scale up, or add a gate that no delivery approach may
  remove. Assess cannot bypass these, and a human cannot override them
  per-issue - changing one means amending this file.
- **Routing strategies** - soft. They *bias* what assess does by default -
  the delivery-approach shapes it reaches for, the way it breaks ties. A
  routing strategy is the starting point; assess (or a human) can depart from
  it for a given issue, and that departure is just recorded in
  `delivery-approach.md`.

This is the answer to the obvious objection to any adaptive framework - *"if
the process can flex, what stops it flexing to nothing?"* The routing
rules are what stop it. The flex is real, and it is bounded by this file.

Assess applies this policy after reading the four dimensions
and composing a candidate delivery approach, before writing `delivery-approach.md`. Every routing
rule that fires is recorded in `delivery-approach.md` with its rationale - so any
`delivery-approach.md` shows not just the delivery approach, but which bounds were active and why.

**This document explains; `routing-policy.yml` enforces.** The companion
`governance/routing-policy.yml` is the machine-readable, authoritative policy -
it has the live floors, caps, immovable gates, role rules, and default shapes,
each with a stable id, and `compass approach evaluate` runs it deterministically.
The YAML excerpts below are *illustrative*; where this prose and that file
could be read to differ, the `.yml` wins. The crucial boundary: the
four-dimension *assessment* is judgement (assess produces it, and that
judgement is the adaptivity); this policy governs only what happens *after* -
composing and constraining the delivery approach from the assessment, which is deterministic.

---

## Routing rules (hard - they bound assess)

### `floors` - an assessment value forces *at least* a given approach

A floor says: "when the context looks like X, the delivery approach may not
be lighter than Y." Floors are how domain risk overrides the raw dimension
assessment - the canonical case is that size reads a one-line auth change as
`atomic`, but a floor forces it heavier because the risk of auth is not a
function of line count.

### `caps` - limits on scaling up

The mirror of floors. Where a floor stops the delivery approach going too
light, a cap stops it going too heavy in a way that adds risk. The default
cap - critical risk caps worktrees at 1 - encodes a real tradeoff: multiagent
orchestration is faster, but it is also coordination risk, and on a critical
change the coordination risk costs more than the speed saves.

### `immovable_gates` - gates no delivery approach may remove

Delivery approaches adapt *which* review dimensions apply. Immovable gates
are the floor under that adaptation: no assessment value, and no delivery
approach, can drop one.

### blocking `role_rules` - a role's involvement enforces a gate

When a role's involvement makes a gate non-negotiable, that is a routing
rule. The two defaults wire the non-engineering roles in as enforced
participants, not optional consultees.

The shipped defaults (see `routing-policy.yml` for the live, id-tagged set):

- **floors** - `RP-FLOOR-001` critical risk → at least initiative,
  never skip refine/verify/ship; `RP-FLOOR-002` brownfield-unmapped familiarity →
  define runs full-weight with `behaviour-mapping`; `RP-FLOOR-003`
  touching auth/payments/personal-data/migrations → at least initiative.
- **caps** - `RP-CAP-001` critical risk caps worktrees at 1.
- **immovable_gates** - `RP-GATE-001..003`: `verify.correctness`,
  `verify.governance`, `verify.traceability`. Deliberately not here:
  `verify.regression` is scoped by the delivery approach and
  `verify.claims` by the role in play, so neither is immovable.
- **role_rules** - `RP-ROLE-001` the product-marketer's involvement blocks shipping
  until claims trace to scenarios; `RP-ROLE-002` the product-owner's involvement
  gates Plan on the spec being checked against `intent.md`.

The `verify.governance` immovable gate is what makes `G5` (a human signs off
on the irreversible) hold: a change labelled with an irreversible surface is
floored to initiative, where the human checkpoint is part of the gate set.

---

## Routing strategies (soft - they bias assess)

These are the assess stage's defaults: the delivery-approach shapes it
reaches for, and how it breaks ties. Assess starts here and tunes; a
departure is normal and is recorded in `delivery-approach.md`, not punished.

```yaml
routing_strategies:
  # The reference shapes triage composes toward. See approaches/.
  # These mirror governance/routing-policy.yml; the live file also carries an
  # `id:` and a `rationale:` per entry, which the evaluator reports when a
  # shape fires.
  default_shapes:
    - when: { size: [atomic, small], risk: [trivial, contained], familiarity: [greenfield, brownfield-mapped] }
      lean_toward: express
    - when: { size: standard }
      lean_toward: standard
    - when: { size: [large, product] }
      lean_toward: expedition
    - when: { urgency: live-defect, size: [atomic, small] }
      lean_toward: hotfix
    - when: { goal: exploration }      # "I need to understand this before I can scope it"
      lean_toward: spike

  # Tie-breaking biases.
  biases:
    - "When size is genuinely unclear, estimate up - it is cheaper to
       collapse a stage that turned out easy than to discover mid-implementation
       that the approach was too light."
    - "A non-engineering role in play usually pulls the route heavier, because
       it adds artifacts and assessed strategies - but this is a bias, not a
       floor. A marketer glancing at a tiny change need not trigger an initiative."
    - "Prefer the lightest route that still clears the routing guardrails and
       the applicable gates. Process weight is a cost; spend it where it buys safety."

  # Advisory role defaults (the blocking versions are routing guardrails above).
  role_defaults:
    - when: { role: designer }
      suggest_artifact: ui-contract.md
      rationale: "A new user-facing surface usually wants a UI contract; advisory."
```

---

## Schema reference

The authoritative structure is `routing-policy.yml`, validated by `compass
policy lint` - against the executable `schemas/routing-policy.schema.json`
(when `jsonschema` is installed) and the CLI's built-in linter. The
human-readable field-by-field companion is `schemas/routing-policy.reference.yml`.
In brief:

`when` conditions match against the assessment - `risk`, `familiarity`,
`size`, `goal`, `role`, `urgency` - or `labels_any` (a domain-tag list:
`auth`, `payments`, `personal-data`, `migrations`, `public-api`, …). A list
value means "any of".

A policy written before the v2 freeze keeps working: the evaluator maps the
retired dimension names on read, so an unmigrated project file still
matches. Write the current names in anything new.

Routing-rule keys: `force_minimum_route`, `require_phase`,
`require_skill`, `never_skip`, `max_worktrees`, `forbid_route`,
`block_phase` + `until`, `require_artifact`, `add_gate`, `gate`. Every rule
carries a stable `id` (e.g. `RP-FLOOR-001`) so `delivery-approach.md` can
name exactly which one fired.

Routing-strategy keys: `lean_toward`, `suggest_artifact`, free-text `biases`.

---

## Amending this file

- **Loosening a routing rule weakens the framework for everyone,
  quietly.** It should be deliberate, logged, ideally reviewed - not a
  convenience edit mid-issue. If a rule keeps being painful, fix the delivery
  approach that makes it painful; do not remove the rule.
- **Routing strategies are meant to be tuned.** Adjust `default_shapes` and
  `biases` freely as the team learns how its work actually distributes. That
  is the soft layer doing its job.
