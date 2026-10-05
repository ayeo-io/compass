---
id: ADR-002
title: The framework grows by adding artifacts and lenses, not by adding guardrails or routing dimensions
status: superseded
date: 2026-05-24
supersedes: ''
superseded_by: 'ADR-033'
---

> **Vocabulary note (ADR-023, 2026-08-27):** this record's *lens* is now
> called a **role**; a *reading dimension* is now an **assessment
> dimension**; `touches:` is now `labels:`; the *framing step* is now the
> **assess** stage; the *route* is now the **delivery approach**. The
> record keeps the words it was decided in; only the names have moved.

## Context

As Compass matures, there are recurring pressures to add governance in the
most direct way available: a new guardrail (G6, G7...) or a new reading
dimension (e.g. `requires_architect_lens: true` as a fifth context dimension).

Both patterns have precedent in other frameworks. The appeal is that they make
desired behaviour mandatory rather than advisory. A team that keeps forgetting
to invoke the architect-lens might prefer "a routing guardrail fires if the
task touches a boundary surface and the lens wasn't invoked" over "please
remember to invoke the lens".

The question is whether mandatory-via-guardrail is the right growth model for
a framework that is also used by teams with very different risk tolerances and
domain contexts.

## Decision

We grow the framework by adding artifacts (new files the mechanism produces or
consumes) and lenses (new agents that read the existing artifacts and annotate
them), not by adding guardrails or routing dimensions.

The five guardrails (`G1`–`G5`) are fixed. Any new check that an adopter or the
framework maintainer wants to enforce registers as a `CHECK_FN` entry under an
existing guardrail (typically `G4` - evidence not assertion), not as a new
G-letter. The guardrail count in `governance/guardrails.md` must remain five.

The four reading dimensions (blast radius, terrain, magnitude, intent + role)
are fixed. The routing policy may evolve the values within each dimension
(e.g. adding a new route shape), but it may not add a fifth dimension. New
concerns are expressed as `touches:` tags - an open-ended list on the existing
`intent + role` dimension - not as new dimension slots.

New capabilities are introduced as lenses (agents that read artifacts and
produce annotated artifacts) or as new artifact types that Frame loads. The
architect-lens is the canonical example: it reads `architecture/` and produces
`architecture-notes.md`. It does not add a guardrail or a reading dimension.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| Add a sixth guardrail (G6) for architectural integrity | Makes architectural review mandatory on boundary-crossing tasks; no "forgetting" | Guardrails are supposed to be few and irreversible-severity. Architectural review is important but not on the same severity level as "tested before it lands" (G1) or "human signs off on data loss" (G5). A G6 would dilute the guardrail concept. |
| Add `requires_architect_lens` as a fifth reading dimension | Explicit, discoverable, mechanical trigger for lens invocation | Adding a dimension changes the routing policy schema, the `compass route evaluate` logic, all the regression fixtures, and CLAUDE.md. The cost of the change far exceeds the value; `touches:` tags already serve the trigger function via the lens's auto-trigger logic. |
| Allow projects to define custom guardrails in `governance/guardrails.yml` | Projects with stricter requirements could add their own G6+ | Adopter-defined guardrails that block the same CLI as the framework guardrails create a compatibility surface. When Compass upgrades, it must not break any adopter's custom guardrail. This creates a versioning obligation the framework cannot now honour. |

## Consequences

**Positive:**
- The framework's rule surface stays small. Adopters learn five guardrails and
  four dimensions; they do not need to track which version added G7 or the
  sixth reading.
- Lenses are cheaper to add than guardrails. A lens is a markdown file with
  instructions; a guardrail needs CLI changes, schema changes, regression
  fixtures, and documentation updates.
- The `touches:` tag mechanism allows projects to express domain-specific
  triggers (e.g. `touches: [billing, pii]`) without changing the framework
  schema.

**Negative:**
- Advisory lenses can be ignored. A team that consistently ignores the
  architect-lens does not face a blocking gate - only a missing evidence
  artifact. The framework accepts this gap deliberately: it cannot police
  human attention, only make the information visible.
- The `CHECK_FN` mechanism for extending `G4` is less discoverable than "add a
  new G6 guardrail". Teams who need stronger enforcement may feel
  under-served until they understand the `CHECK_FN` pattern.

**Neutral / follow-on:**
- The `governance/signals.yml` file was introduced using this pattern: it is
  a new artifact type the CLI consumes, not a new guardrail or dimension.
- The architect-lens was introduced using this pattern.
- Future capabilities (behaviour mapping, review automation) should follow the same
  pattern.

## References

- The invariant that there are five guardrails, not more (Inv-2), and the invariant that adaptive routing is untouched, with no new routes or dimensions (Inv-3), both defined in `architecture/decisions/README.md`
- `governance/guardrails.md` (the five guardrails)
- `governance/routing-policy.yml` (the routing dimensions and route shapes)
- `agents/architect.md` (canonical lens example)
- `governance/strategies.md` (S3 - simplest thing)
