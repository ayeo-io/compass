---
id: ADR-010
title: Project governance should layer over framework defaults rather than copy them
status: accepted
date: 2026-08-03
supersedes: ''
superseded_by: ''
---

## Context

`/compass:init` copies `governance/` into a project. The project then owns a
frozen snapshot. When the framework later ships a new floor or check, the
project's copy never learns about it.

This was reported from the field against 1.7.0 and reproduced against HEAD. A
project that ran init at ~1.5.0 computed **7 gates where current policy
needs 9** on a task touching auth, losing `verify.analyze` and
`verify.fitness`, while `compass policy lint` returned a clean `PASS`. Four of
the six checks it was missing belong to `G1` and `G4` - "tested before it lands"
and "evidence, not assertion".

The failure is **directional**, which is what makes it dangerous. Stale
governance never fails loudly; it produces a *lighter* route. Every artifact
looks correct. `route.md` records the guardrails that fired and says nothing
about the ones that could not, because it does not know they exist.

The detection work that shipped since addressed the *symptom*: `compass policy
lint` now names every rule a project is missing, `route evaluate` records which
policy produced the route, and a `waived:` block distinguishes a deliberate
omission from an unseen one. That makes drift **visible**. It does not make it
**impossible**, and the reporter was right that detection is the lesser fix.

This ADR records the decision about the architectural fix, which was
deliberately deferred rather than bundled into the detection work.

## Decision

**Project governance should declare what it *adds and waives*, and inherit
everything else from the framework at load time.**

```yaml
# governance/routing-policy.yml - in a project
extends: framework            # shipped defaults always apply underneath
routing_guardrails:
  floors:
    - id: PROJ-FLOOR-001      # this project's own additions
      ...
  waived:
    - id: RG-FLOOR-006        # deliberate, recorded, reviewable
      reason: "no architecture checks declared yet; revisit at Q3"
```

A new framework floor then applies to every project automatically. Drift stops
being a thing to detect and becomes structurally impossible.

**Status is `proposed`, not `accepted`.** Three things must be resolved before
it can be implemented, and they are the reason this was not done alongside the
detection work:

1. **A migration path for existing copies.** Every adopter today has a full
   copy. Turning that into a layered file is a rewrite of the file that defines
   their rules, and ADR-006 says a new mechanism must no-op for projects that
   have not adopted it. A file with no `extends:` key must keep behaving
   exactly as it does now, indefinitely.
2. **What a project may override, as opposed to add or waive.** Waiving a floor
   is a recorded decision. *Weakening* one - keeping `RG-FLOOR-003` but removing
   `migrations` from its `touches_any` - is a different act, and it is the one
   that would let a project quietly disarm a guardrail while appearing to
   declare it.
3. **Where the merged policy is visible.** Today a reader opens one file and
   sees the whole policy. Layered, they see a fragment. `compass policy show
   --merged` or equivalent is required; without it a reader cannot see the
   whole policy.

**Accepted on 2026-10-05, with ADR-033.** The three prerequisites are met by
the configurable-framework design ADR-033 records:

1. A migration converts a copied `governance/` into a layer, keeps the
   original beside it, and can be undone. A project that does not migrate
   keeps working as it does now.
2. Locks and a classifier separate adding and waiving from weakening. A
   change that weakens an obligation needs an approved waiver, and a locked
   entry refuses it.
3. A command prints the resolved configuration, with the layer each value
   came from.

The `extends: framework` example above shows the idea, not the final syntax.
A project names a versioned parent, such as `compass:default@6`.

## Consequences

**What this buys.** New framework guardrails reach existing projects without
manual action - the fifth of the field report's acceptance criteria, and the
only one detection cannot satisfy. It also matches how the framework already describes
itself: `/compass:init` is documented as the point at which a project's
governance *"extends those defaults"*. The copy-based implementation is what
breaks that description; this makes the code match the sentence.

**What it costs.** Governance stops being readable in one file. That is a real
loss for a framework whose pitch includes five-minute legibility, and point 3
above is the mitigation rather than an afterthought.

**What it does not change.** Guardrails stay hard and strategies stay soft. The
determinism boundary is untouched: the readings remain judgement, and
everything after them remains mechanism - this changes only *where the policy
is loaded from*, not who decides it.

**Relationship to the detection work.** Detection is not made redundant by
this. A layered project can still waive a rule it should not have waived, and
`policy lint` reporting waivers is how that stays visible. The two are
complementary: layering removes accidental drift, reporting keeps deliberate
divergence honest.

## Alternatives considered

- **Detection alone** (what shipped). Cheap, immediate, and it gives every
  adopter a signal today. Rejected as the *end state* because it relies on
  someone reading and acting on the report - and the field report was filed,
  and the next issue still lost two gates.
- **Version-pinning with a forced upgrade prompt.** Simpler than layering, but
  it turns every framework release into a migration event for every adopter,
  and the thing being migrated is the file that decides whether their code is
  safe to land.
- **Making `/compass:init` re-runnable as a merge.** Rejected: it puts the
  burden on remembering to re-run, which is the same class of failure as
  remembering to re-derive the living spec - a mechanism nobody invokes.

## References

- A field report against 1.7.0 reproduced the 7-gates-instead-of-9 failure and
  proposed layering as its fourth and deepest fix.
- The detection work that shipped instead made drift visible without making
  it impossible: `compass policy lint` names every rule a project is
  missing, `route evaluate` records which policy produced the route, and a
  `waived:` block distinguishes a deliberate omission from an unseen one.
- **ADR-006** (backward compat is non-negotiable) - the constraint that makes
  the migration path a prerequisite rather than a detail.
- **ADR-001** (judgement and mechanism separated) - unaffected by this; layering
  changes where policy is loaded from, not who decides it.
- `commands/init.md` - documents `/compass:init` as the point where a project's
  governance "extends those defaults", which is the sentence the copy-based
  implementation fails to honour.
