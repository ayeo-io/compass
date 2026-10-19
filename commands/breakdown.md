---
description: Split the work into independent subtasks, one worktree each
allowed-tools: Read, Write, Edit, Bash, Glob
---

# /compass:breakdown

Breakdown carries out the orchestration that the plan decided. It creates the
worktrees and assigns one builder agent to each worktree.

## First: is breakdown in play?

If the distribution map says `units: 1`, registering it already recorded the
breakdown as one subtask this session runs itself (`orchestration:
single-unit`). Create no worktree and launch no builder: go on to
`/compass:implement`. Registering `verification-report` in `/compass:verify`
completes the record, and `multiagent-run-recorded` accepts it. No waiver is
needed. On a critical-risk issue the check also needs a passing review round
from a second reviewer: `compass issue subtask set <id> --round pass`.

Read `delivery-approach.md`. Breakdown is **skipped on solo work** - quick
fixes, hotfixes, spikes, and most regular-approach issues work on the current branch with no
worktree. If `delivery-approach.md` says solo, stop: confirm the de-scope
reason, and point the user to `/compass:implement`. Breakdown is a no-op
there, not a stage to invent.

It runs when the distribution map shows genuinely independent units. The
pair/multiagent boundaries are framework constants (`docs/methodology.md` §9); the orchestration
and the worktree cap come from `delivery-approach.md` - which the CLI
computed from `governance/routing-policy.yml` (the shapes' `orchestration`, the
policy `caps`):
- **pair** (2-3 subtasks) - larger regular-approach issues. One worktree per subtask, one
  `builder` agent each, no dedicated orchestrator - the lead builder
  integrates.
- **multiagent** (4+ subtasks) - the full approach. One worktree per subtask, one
  `builder` per worktree, plus an `orchestrator` agent that writes no
  feature code.

## Setup

- Read `distribution-map.md` - it is the source of truth for subtask count
  and which scenarios each subtask owns.
- Load the `worktree-multiagent` skill.
- Pass the computed model and effort when you invoke the `orchestrator` agent:
  `compass approach show --model breakdown` prints the `model`, and
  `compass approach show --effort breakdown` prints the `effort`. On
  `inherit`, pass the model family your session runs on (`opus`,
  `sonnet`, `haiku` or `fable`), or leave `model` out when you cannot
  tell. Exit 1 means the issue sets nothing for that value: leave it out,
  so the agent's frontmatter applies.
- Invoke the `orchestrator` agent. **Only the orchestrator** creates
  worktrees and integrates them.

## Procedure

1. **Check the count.** Cross-check the map's subtask count against the
   orchestration and any policy `cap` recorded in `delivery-approach.md` (the CLI
   computed both from `routing-policy.yml`). Note: `critical` risk caps
   worktrees at 1 - the full approach can be heavy *and* solo. If the cap and
   the map disagree, the cap wins; record it as cap-driven.
2. **Create the worktrees.** Run `scripts/multiagent.sh` - it creates one git
   worktree per subtask under the configured `worktree_root`. Each worktree
   is an isolated checkout so a builder can run a full red-to-green cycle
   without destabilising siblings.
3. **Assign by file.** Write each builder's assignment - its worktree, its
   scenario set from the distribution map, its slice of the plan - to
   `docs/compass/<created>-<slug>/subtasks/<id>/briefing.md`. A builder works
   *only* inside its assigned worktree and never touches a sibling's.
4. **Record, then launch.** Record each dispatch with `compass issue subtask
   add <id> --brief <path> --budget <tokens>`. Without `--model` it takes the
   tier the manifest records for the implement seat, and records both;
   `compass approach show --model implement` prints the same model. Then
   launch one `builder` agent per worktree, naming only its brief file and
   passing the recorded model as `model` (on `inherit`, your session's model
   family) and the recorded effort as `effort`;
   `compass approach show --effort implement` prints the effort. A second try, recorded with `compass issue subtask set`, is
   dispatched one tier up, and the command prints the new model.

## Gate

Worktrees exist and match the distribution map; every subtask has a builder
and an assigned scenario set; the orchestrator is in place (multiagent). Next:
`/compass:implement`.
