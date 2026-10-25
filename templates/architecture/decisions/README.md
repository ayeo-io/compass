# Architecture Decision Records

This directory contains the project's Architecture Decision Records (ADRs).

Each ADR captures one significant architectural decision: its context, the
choice made, the alternatives considered, and the consequences.

## Why ADRs

Architectural decisions tend to be made once and then forgotten.  Six months
later, a new team member asks "why do we do it this way?" and no one remembers.
ADRs make the *why* a searchable record.  They also give the
`architect` agent a corpus to cite rather than reopening decisions
that were already made deliberately.

## Numbering

ADRs are numbered sequentially (`ADR-001`, `ADR-002`, ...).  Use
`compass adr new <slug>` to create the next ADR - it counts the existing
`ADR-*.md` files, assigns `N+1`, and registers the new file in this README.

**Concurrency note:** if two worktrees both call `compass adr new` at the same
time they may each produce an `ADR-NNN` with the same number.  This surfaces
as a normal git merge conflict on this README at integration.  The orchestrator
resolves it by renumbering one side.  This is deliberate - sequential numbers
matter more than collision-freedom.

## Supersession

When a decision is reversed or replaced:

1. Update the old ADR: set `status: superseded` and `superseded_by: ADR-NNN`.
2. Create the new ADR with `supersedes: ADR-MMM` in its frontmatter.

The chain is navigable: `superseded_by` and `supersedes` form a linked list.

## Index

| ID | Title | Status |
|---|---|---|
| [ADR-001](ADR-001-architecture-directory-location.md) | Architecture Directory Location | accepted |
| [ADR-002](ADR-002-architecture-loaded-yml-schema.md) | Architecture-Loaded Yml Schema | accepted |
| [ADR-003](ADR-003-inline-tag-dod-syntax.md) | Inline Tag Dod Syntax | accepted |
| [ADR-004](ADR-004-lens-first-planner-second.md) | Architect First Planner Second | accepted |
| [ADR-005](ADR-005-signals-yml-governance-file.md) | Signals Yml Governance File | accepted |
