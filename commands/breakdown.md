---
description: Order the work units of the plan for this session to build
allowed-tools: Read, Write(./.compass/**), Write(./docs/**), Edit(./.compass/**), Edit(./docs/**), Bash(compass *), Glob
---

# /compass:breakdown

Breakdown orders the units the plan decided. Compass runs each issue in one
session (ADR-090), so breakdown creates no worktree and starts no agent: this
session builds the units itself, one after another.

## First: does breakdown run?

Run `compass approach show`. Breakdown is **skipped on solo work** - quick
fixes, hotfixes, spikes, and most regular-approach issues. If
the approach says solo, stop: confirm the de-scope reason, and
point the user to `/compass:implement`. Breakdown does nothing there; do not
invent work for it.

## Procedure

1. **Read the units.** The plan's hand-off, logged in `devlog.md`, names the
   work units and the scenarios each one owns. A plan with one unit needs no
   order: go on to `/compass:implement`.
2. **Order the units.** A unit that another unit depends on comes first.
   Log the order to `devlog.md`. Compass writes no distribution map.

## Gate

Every work unit of the plan has a place in the order. Next:
`/compass:implement`, which builds the units in that order.
