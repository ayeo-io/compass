---
id: ADR-004
title: Architect First Planner Second
status: accepted
date: 2026-05-23
supersedes: ''
superseded_by: ''
---

## Context

The architect perspective and the planner both produce design-decision
content. When an issue introduces a new service interaction, both need to
weigh in. The question is: who runs first, and who reads whom?
<!-- absorbed: "them), planner-first (planner writes DDs, lens annotates), and parallel (both" -->
<!-- absorbed: "run without reading each other, merged by a human)." -->
<!-- absorbed: "the planner records a \"no lens consultation applied\" note in `plan.md` -" -->
<!-- absorbed: "not a silent skip." -->

Three orderings were considered: architect-first (the architect writes notes,
planner reads them), planner-first (planner writes design decisions, the
architect annotates), and parallel (both run without reading each other,
merged by a human).

## Decision

The architect runs first; the planner reads and cites.

Order of operations:
1. The architect perspective runs at the define stage (auto-triggered) or via
   `/compass:consult architect`.  It writes `architecture-notes.md`.
2. Planner runs at plan.  It reads `architecture-notes.md` and writes
   `technical-design.md §2` design decisions that either cite an existing ADR,
   name a candidate ADR to author at implement, or explicitly justify
   divergence.
3. Planner never re-invokes the architect perspective.  If
   `architecture-notes.md` is missing, the planner records a "no architect
   consultation applied" note in `technical-design.md` - not a silent skip.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| Planner first, architect annotates | Planner already owns technical-design.md | The architect perspective would need to edit a file it doesn't own; blurs responsibility |
| Parallel, human merges | No ordering dependency | Human merge step adds process weight; ordering is cheap and makes the dependency explicit |
| Architect has authority over the plan | Strong architectural enforcement | Planner remains the single owner of technical-design.md; the architect perspective is advisory, not authoritative |

## Consequences

**Positive:**
- Clear dependency direction: architect → planner (never planner → architect).
- Planner's design decisions are always informed by architectural context.
- No recursive invocation risk.

**Negative:**
- The architect perspective must run before define finishes, which needs early consultation.

**Neutral / follow-on:**
- If `architecture-notes.md` is absent (no architecture/ in the project), the
  planner records the absence explicitly.  This is a recordable absence, not
  a silent skip (Strategy `S4` - persistence over conversation).

## References

- The requirements review, where the split between the architect perspective and the planner was settled
- The technical design's architect-first/planner-second design decision
- The invariant that there is one spec read through many role perspectives, and the architect perspective annotates rather than forks it
