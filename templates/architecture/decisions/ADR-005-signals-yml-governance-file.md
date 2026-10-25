---
id: ADR-005
title: Signals Yml Governance File
status: accepted
date: 2026-05-23
supersedes: ''
superseded_by: ''
---

## Context

Three framework mechanisms needed configurable patterns:
- The stop-hook's scope-bloat phrase detector (re-assessment prompt).
- The rework scanner's time window and public-surface patterns.
- Eventually, the architect's trigger tags.

The patterns needed to be project-overridable (different projects have
different migration path conventions, public surface patterns, etc.) and
loaded at run time so the CLI is not hard-coded with opinions about any one
project's conventions.

Two locations were considered: folding the patterns into `governance/guardrails.yml`
alongside the hard checks, and a new sibling file `governance/signals.yml`.

## Decision

A new file `governance/signals.yml` ships alongside `guardrails.yml` and
`routing-policy.yml`.  It holds all *advisory signal* configurations.

Default content:
```yaml
version: 1.0.0
scope_bloat_phrases:
  - "more files than Plan estimated"
  - "narrow scope and spawn sibling"
  - ...
rework_scan:
  window_days: 14
  public_surface_patterns:
    - "/api/v[0-9]+/"
    - "pb\\."
  migration_paths:
    - "migrations/*.sql"
    - "**/migrations/*.sql"
```

Projects override by editing their own `governance/signals.yml`.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| Fold into `guardrails.yml` | One fewer file | Guardrails are hard and blocking; signals are soft and advisory - mixing dilutes both |
| Put in `.compass/config.yml` | Config is already project-scoped | Config holds project settings (test command, worktree root); governance content belongs in `governance/` |
| Hard-code in the CLI | Simplest implementation | Non-overridable; defeats the "adaptive" principle for project-specific conventions |

## Consequences

**Positive:**
- Clean three-file governance model: routing-policy.yml (delivery approaches), guardrails.yml (hard checks), signals.yml (advisory patterns).
- Projects can tune scope-bloat phrases and rework windows without forking the framework.
- `compass policy lint` checks signals.yml structure.

**Negative:**
- A third file for new adopters to become aware of.

**Neutral / follow-on:**
- Architect trigger tags (when the architect becomes more sophisticated) will be added as a new key in `signals.yml`, not a new file.

## References

- The requirements review, where the question of where advisory patterns live was settled
- The technical design's decision to keep signals.yml a separate file
<!-- absorbed: "- Plan DD-1 (signals.yml as a separate file)" -->
- The invariant that the framework holds five guardrails, not six
