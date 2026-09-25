---
id: ADR-025
title: The printed plan and the recorded run are the multiagent interface
status: accepted
date: 2026-09-25
supersedes: ''
superseded_by: ''
---

## Context

`scripts/multiagent.sh` creates one worktree per subtask and prints a launch
plan: which builder runs where, and under which rule. It launches nothing. A
session reads the plan and starts the builders itself. Everything after that -
the briefs, the reviews, the order of integration - was prose that a session
followed or did not, and nothing could tell the two apart.

Two ways out were open:

- **Compass launches the builders.** It would own the dispatch loop.
- **The printed plan stays the interface,** with a written protocol around it
  and a record that a check can read.

## Decision

The printed plan and the recorded run are the interface. Compass provisions,
prints and records; the host launches the agents.

- `docs/multiagent-protocol.md` states every step, who does it and what the
  manifest records.
- `compass issue subtask` writes the record: each subtask's brief, base
  commit, model, budget, status, how many tries it took, review rounds and
  findings.
- The check `multiagent-run-recorded` fails a multiagent issue whose run
  left no complete record: one that records subtasks, or one created from
  2026-09-26 on.

## Alternatives considered

**Compass launches the builders.** Rejected:

- A launcher is specific to one host. Claude Code starts agents with its
  Agent tool; another host does it another way. Compass runs on the
  project's side of that boundary.
- One recorded run was the evidence when this was first asked. A launcher
  sized from one run would encode that run's accidents.
- The failure that mattered was not the manual launch. It was that a run
  which skipped the protocol looked the same as one that followed it. The
  record and the check answer that without a launcher.

## Consequences

- A run is only as good as the session that follows the protocol, and the
  check reads what was recorded, not what happened. It cannot tell a review
  round that was recorded from one that was run.
- Issues created before 2026-09-26 that record no subtasks are not checked.
  Their runs followed prose that had no record to read.
- If recorded runs show the same step improvised again and again, that step
  is the one to automate first. The run records say which.

## References

- `docs/multiagent-protocol.md` - the protocol this decision makes the
  interface.
- `cli/compass_pkg/subtasks.py` - `compass issue subtask`, which writes the
  record.
- `cli/compass_pkg/multiagent_check.py` - the check `multiagent-run-recorded`.
- `docs/compass/2026-08-27-sdd-loop-spike.md` - the spike that asked whether
  Compass should launch agents.
