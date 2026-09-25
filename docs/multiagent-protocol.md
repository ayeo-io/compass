# The multiagent protocol

How an issue whose breakdown stage is `multiagent` is run, step by step. A
session that has never run one follows this document from top to bottom.
Every step names who does it, what they write, and what the manifest records.

## The interface

Compass does not launch agents. The host does - in Claude Code, the Agent
tool. Compass provisions the worktrees, prints the launch plan, records each
subtask in the manifest, and `compass check` reads that record: the check
`multiagent-run-recorded` fails an issue whose run left no complete record.
The printed plan plus the recorded run is the interface (ADR-025).

## The roles

- **Orchestrator** - the session that owns the issue. It writes the briefs,
  records every step, reviews or dispatches reviewers, integrates, and
  resolves any conflict between subtasks. It writes no subtask's code.
- **Builder** - one agent per subtask, inside one worktree.
- **Reviewer** - one agent per review, handed a brief file and a package.

## Before the run

1. The distribution map exists and is registered. Its subtask table has one
   row per subtask. For a staged run it has a `Wave` column: a whole number
   per row, starting at 1.
2. Every document a builder needs is registered in the manifest
   (`compass issue artifact <kind> --path <path>`), so `multiagent.sh` can
   seed it into each worktree.

## Step 1 - provision a wave

```
scripts/multiagent.sh <slug>             # wave 1, or the only wave
scripts/multiagent.sh <slug> --wave 2    # a later wave
```

It creates one worktree and branch per subtask in the wave, seeds each with
`.compass/work/<slug>/` and every registered document at the same relative
path, and prints the launch plan. The worktree ceiling applies to each wave.

## Step 2 - write each brief, then record it

The orchestrator writes one brief file per subtask, in the issue's documents
directory in the main checkout: `docs/compass/<created>-<slug>/briefs/<id>.md`.
A brief states:

- the subtask's scenarios, by id, and the files it owns;
- the worktree path, and that the builder works only there;
- the CLI to run, as a full path: the project's own `bin/compass` or
  `cli/compass` inside the worktree when the project pins one, never a bare
  `compass` that may resolve to an installed plugin;
- where to write the result: `result.md` at the worktree root, **not**
  committed - a committed result would merge into the codebase;
- what not to touch: another subtask's files, and the shared fixtures the map
  names as the orchestrator's.

A brief never tells a builder or a reviewer what not to flag.

Then, before launching anything:

```
compass issue subtask add <id> --brief <brief path> --model <model> --budget <tokens>
```

This records the base commit (HEAD), the model, the budget and status
`dispatched`.

## Step 3 - launch the builders

One builder per subtask, handed only the brief file's path. Builders in the
same wave run at once. A builder spawns no subagents. It runs the red-green
cycle through the CLI its brief names, commits its work on its branch, and
writes `result.md` without committing it. It records each scenario's green once,
after its last edit: a second green on an unchanged tree fails
`no-trusted-rerun`. A builder never deletes or edits a record to clear a
check; it says in `result.md` what the check reported.

## Step 4 - take the result

A builder's `result.md` is in its worktree, not in the main checkout. The
orchestrator copies it, and records the tokens the dispatch used:

```
cp <worktree>/result.md docs/compass/<created>-<slug>/results/<id>.md
compass issue subtask update <id> --status reported --report <that path> --cost <tokens>
```

## Step 5 - review

Review frequency follows the issue's risk, as `compass issue subtask next`
prints it:

| Risk | Review |
|---|---|
| critical | each subtask's package before integration, with a second reviewer, and the integrated result after |
| cross-cutting | each subtask's package before integration, and the integrated result after |
| contained, trivial | the integrated result, once |

A subtask reviewed only as part of the integrated result still has its round
recorded against it, so `multiagent-run-recorded` can read it.

For each review:

```
compass issue subtask package <id> --head <branch>
compass issue subtask update <id> --status reviewing --review-brief <reviewer brief path>
```

The reviewer gets the reviewer brief's path and the package's path, and
reports acceptance and code quality in separate sections. The orchestrator
records the round and every finding:

```
compass issue subtask update <id> --reviewed <commit> --round pass|fail --finding "<text>"
```

A failed round goes back to the builder for another try, with the findings
in a new brief. The earlier brief is kept, and the manifest counts the try:

```
compass issue subtask update <id> --brief <new brief> --attempt --status dispatched
```
 A finding the orchestrator
decides not to act on is resolved with `--resolve <n>`, and its reason is
listed at the end of the run as a decision taken for the user.

## Step 6 - integrate

```
compass issue subtask update <id> --status integrating
scripts/integrate.sh <slug>
compass issue subtask update <id> --status done
```

`integrate.sh` merges the subtasks in the map's order, so a later wave lands
on a base that holds the earlier one. Then it runs the combined regression.

## When a merge conflicts

- **Only Compass's records conflict** - files under `.compass/` or
  `docs/compass/`, which every builder writes. `integrate.sh` keeps the base
  branch's copy, completes the merge and says which files it kept. The
  builder's records stay on its branch.
- **Anything else conflicts.** `integrate.sh` aborts the merge and names the
  subtask and the files. The orchestrator resolves a conflict between
  subtasks. A conflict inside one subtask's own work goes back to its builder.

## What the manifest records, step by step

| Step | Command | Recorded |
|---|---|---|
| 2 | `subtask add` | brief, model, budget, base commit, status `dispatched`, `attempts: 1` |
| 4 | `subtask update --report` | result file, status `reported` |
| 5 | `subtask package` | the review package's path |
| 5 | `subtask update --round --finding` | each round's verdict, each finding |
| 5 | `subtask update --brief` | another try, counted; the earlier brief is kept |
| 6 | `subtask update --status done` | status `done` |

An interrupted run resumes from `compass issue subtask next`, which names
what to dispatch, what is in review and what is left, with each finding.

## At the end of the run

- Every subtask is `done` with a passing last review round; otherwise
  `compass check` fails `multiagent-run-recorded`.
- The run record, `docs/compass/<created>-<slug>-run-<n>.md`, states the
  wall-clock time, tokens per agent, conflicts, rework rounds, and each step
  that needed improvising. It sits beside the issue's documents directory, not
  in it, so a project that keeps issue directories private can publish it.
- The verification report lists the decisions taken for the user.

## Issues this protocol closes

| Queued issue | Closed by |
|---|---|
| `swarm-dispatch-is-a-protocol-not-a-script` | this document and ADR-025, which decide the interface, and the check `multiagent-run-recorded`, which tells a run that followed it from one that did not | <!-- vocabulary-scan: allow - the queued issue's slug, which a reader must be able to find, keeps the retired word -->
| `multiagent-does-not-ask-where-documents-live` | `multiagent.sh` and `integrate.sh` read documents through `compass issue artifact-path`, and seed every registered document into each worktree |
| `multiagent-cannot-stage-a-map-in-waves` | the `Wave` column and `multiagent.sh --wave` |
