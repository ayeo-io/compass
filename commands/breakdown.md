---
description: Order the units of the distribution map for this session to build
allowed-tools: Read, Write(./.compass/**), Write(./docs/**), Edit(./.compass/**), Edit(./docs/**), Bash(compass *), Glob
---

# /compass:breakdown

Breakdown orders the units the plan decided. Compass runs each issue in one
session (ADR-090), so breakdown creates no worktree and starts no agent: this
session builds the units itself, one after another.

## First: does breakdown run?

Read `delivery-approach.md`. Breakdown is **skipped on solo work** - quick
fixes, hotfixes, spikes, and most regular-approach issues. If
`delivery-approach.md` says solo, stop: confirm the de-scope reason, and
point the user to `/compass:implement`. Breakdown does nothing there; do not
invent work for it.

## Procedure

1. **Read the map.** `distribution-map.md` names the units and the
   scenarios each one owns. A map that declares one unit needs no order: go
   on to `/compass:implement`.
2. **Order the units.** A unit that another unit depends on comes first. A
   map with a Wave column gives the order. Record the order in the map if it
   is not already there.

## Gate

Every unit of the distribution map has a place in the order. Next:
`/compass:implement`, which builds the units in that order.
