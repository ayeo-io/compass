---
name: worktree-multiagent
description: How parallel subtasks are created, isolated and integrated across git worktrees. Load at breakdown on a multiagent orchestration.
---

# Worktree Multiagent

The step-by-step run is `docs/multiagent-protocol.md`: follow it from top to
bottom. Parallelism in Compass is **decided in Plan** (the distribution map) and
**carried out in breakdown** (the worktree orchestration). This skill covers both
halves: how to decompose work correctly, and how to run and land the multiagent
orchestration
without the parallelism costing more than it saves.

## Orchestration - what runs when

| Orchestration | Subtasks | Setup | Who integrates |
|---|---|---|---|
| **Solo** | 1 | No worktree; current branch. Breakdown is a no-op. | The builder, trivially. |
| **Pair** | 2–3 | One worktree per subtask; one `builder` each; no dedicated orchestrator. | The lead builder. |
| **Multiagent** | 4+ | One worktree per subtask; one `builder` each; plus one `orchestrator`. | The orchestrator. |

The assessment's size and risk values set the default orchestration; the
distribution map sets the subtask count; `.compass/config.yml` thresholds and the
routing-guardrail caps bound it.

## The critical-risk cap

The standing cap: **`critical` risk pins `max_worktrees` to 1.** A
critical change runs solo even on initiative. This is deliberate - a multiagent buys
speed but carries coordination risk, and on a critical change the coordination
risk costs more than the speed saves. An initiative that is heavy *and* solo is
not a contradiction; it is the cap working. The initiative still writes a
`distribution-map.md` - it is the record of what could have been parallel and
why it wasn't.

## Decomposing work into independent subtasks (Plan)

A subtask is a unit of work that can run start-to-finish without waiting on,
colliding with, or reaching into another subtask. Independence has two tests,
and both must hold:

1. **Disjoint code.** The subtasks touch non-overlapping files and interfaces.
2. **Disjoint scenarios.** The subtasks satisfy non-overlapping scenario groups
   from `acceptance-criteria.md`.

Independence is *determined*, not guessed - you derive it from the scenario
file and the technical plan. The scenario grouping done at the define stage
(initiative's "group scenarios by independence") is the seed; the distribution
map is where you confirm it against the plan.

Practical decomposition heuristics:

- **Cut along boundaries the architecture already has** - module boundaries,
  service boundaries, layers. Cutting across one of them creates a shared
  surface and a guaranteed collision.
- **Shared surface = shared subtask, or sequenced subtasks.** If two units both
  need to change the same interface, either fold them into one subtask or
  sequence them (one lands, then the other branches from the result). Do not
  pretend they are parallel.
- **Pull shared foundations forward.** If three subtasks all need a new shared
  type or utility, that is a subtask-zero that lands first, not a thing three
  subtasks each invent.
- **Be honest about the count.** Four shaky subtasks are worse than two clean
  ones. The map records *what could be parallel* - if the honest answer is
  "less than it looks," that is the map's job to say.

## Git worktree mechanics

A git worktree is a second working directory backed by the same repository -
its own checked-out branch, its own files, sharing one `.git`. That isolation
is what lets a builder run a full red→green TDD cycle, including a failing
suite, without destabilising siblings.

- `scripts/multiagent.sh` creates one worktree per subtask and launches one `builder`
  agent in each. Only the `orchestrator` runs it.
- `scripts/integrate.sh` lands the worktrees back together. Only the
  `orchestrator` runs it.
- A builder lives inside exactly one worktree for the life of the subtask.

## The orchestrator / builder protocol

**The orchestrator** writes no feature code. Its job is coordination, collision
detection, and integration:

- Hands each builder an assignment as a file: its worktree, its scenario group,
  its slice of the plan, written to
  `docs/compass/<created>-<slug>/subtasks/<id>/briefing.md`. The dispatch names
  the path; a paste has no bound on what it drags in.
- States the model and the budget for each dispatch, scaled to the work, and
  records every step with `compass issue subtask` - `add` at dispatch,
  `update` for the report, the review and the cost, `package` for the review
  diff. A cost over the budget becomes a finding.
- Batches small same-shape work - five renames, three one-line guards - into
  one dispatch rather than five subtasks of setup each.
- Monitors subtasks during implementation for convergence on shared surface - shared
  files, shared interfaces, a scenario whose implementation reaches outside its
  group.
- Intervenes *before* a collision: re-sequences subtasks, re-cuts a boundary, or
  escalates to a re-assess if the distribution map was wrong.
- Is the **only** agent permitted to make a cross-subtask change.

**A builder** owns its subtask and nothing else:

- Works only inside its assigned worktree. Never touches a sibling's.
- Routes every cross-subtask need through the orchestrator - "I need to change
  an interface another subtask owns" is an orchestrator message, never a reach
  across.
- Runs full TDD inside its worktree (see `tdd-discipline`).
- Spawns no subagents, and writes its report to `result.md` beside its
  brief. Not `report.md`: Claude Code tells a subagent not to write a file
  named like a report.

**Review frequency follows the assessed risk.** `trivial` and `contained`:
one review of the integrated result. `cross-cutting`: a review of each
subtask's package before integration, and one after. `critical`: the same,
with a second reviewer on each subtask. The reviewer answers acceptance and
code quality in separate sections; see `agents/reviewer.md`.

**Resuming.** A run stopped part-way resumes from `compass issue subtask
next` alone: it names each unfinished subtask, its status (`dispatched`,
`reported`, `reviewing`, `integrating`), its files, the revision last reviewed
and its unresolved findings, and the review cadence the risk calls for. A
subtask marked `done` is never dispatched again. Where the project gitignores
`docs/compass/`, a worktree does not carry the brief: name it by its path in
the main checkout.

## Integration discipline (ship)

1. Confirm every subtask is independently green - the `verifier` has per-subtask
   evidence.
2. The orchestrator runs `scripts/integrate.sh` to merge worktrees in a
   coordinated order (foundations first, dependents after).
3. Only the orchestrator resolves a merge conflict - a builder must not.
4. **Run combined regression across the integrated result.** This is
   non-negotiable on initiative. Per-subtask green does not imply integrated
   green; proving the combination is the entire reason the orchestrator owns
   ship. Record the run and link the record.
5. Resolve every owed follow-up, update living docs, write the integration
   devlog entry.

## Never stash across a worktree hop

Never stash in one worktree and pop in another - and never stash at all
inside a temporary worktree. A stash lives in the shared repository, but
the working state it captures belongs to one checkout: a stash popped
inside a temporary worktree that is then removed
destroys the stashed work along with the worktree. A CI fix nearly lost work
this way - the change survived only because it had already been committed
elsewhere. If
work must move between worktrees, commit it (a WIP commit on the
subtask's branch is fine and can be amended); the branch is durable, the
stash is not.

## Anti-patterns

- **Optimistic decomposition** - declaring subtasks independent because you want
  parallelism, not because the code and scenarios are disjoint. The collision
  surfaces at integration, where it is most expensive.
- **The reaching builder** - a builder editing a sibling's worktree "just to
  unblock myself." It destroys the isolation guarantee for everyone.
- **The coding orchestrator** - an orchestrator writing feature code. If it is
  tempted to, the decomposition was wrong; fix the decomposition.
- **Skipping combined regression** - trusting per-subtask green. The integration
  is exactly where the untested interactions live.
- **Running a critical change as a multiagent** - ignoring the cap. The cap is a routing
  guardrail; honour it.
