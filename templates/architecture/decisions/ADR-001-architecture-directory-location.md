---
id: ADR-001
title: Architecture Directory Location
status: accepted
date: 2026-05-23
supersedes: ''
superseded_by: ''
---

## Context

The project needed a canonical location for architecture artifacts
(system-context.md, relations.md, ownership.md, invariants.yml, and ADRs).
Two candidates were considered: nesting under `governance/` (alongside
`guardrails.yml` and `routing-policy.yml`) and a top-level `architecture/`
directory as a sibling to `governance/`.

## Decision

We place `architecture/` at the project root as a sibling to `governance/`.

`governance/` describes *how we work* (delivery process, routing rules,
guardrails).  `architecture/` describes *what we built* (system structure,
relations, ownership, decisions).  These are separate concerns that do not
overlap; nesting one inside the other blurs the distinction.

A top-level location is also more adoption-friendly: many projects already
have a top-level `architecture/` or `docs/architecture/` directory, reducing
migration cost.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| `governance/architecture/` | Keeps all Compass-related artifacts under one top-level dir | Mixes "process" (governance) with "structure" (architecture); makes `governance/` heavier |
| `docs/architecture/` | Common convention in many projects | `docs/` is for human documentation; architecture artifacts are also machine-read by the assess stage |

## Consequences

**Positive:**
- Clean separation of governance (process) and architecture (structure).
- The assess stage's load contract is symmetric: reads `governance/` for policy, reads `architecture/` for structure.
- Low adoption barrier for projects with existing `architecture/` directories.

**Negative:**
- One more top-level directory in the repository root.

**Neutral / follow-on:**
- The `compass-self-architecture` follow-on issue will populate Compass's own `architecture/` using this location.

## References

- The requirements review, where the location of `architecture-notes.md` was settled
- The technical design's foundation-first subtask ordering decision
