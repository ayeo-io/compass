# Run 2 of the multiagent protocol - skill-prose-pressure-tests

> **Date:** 2026-09-26 to 2026-09-27 · **Issue:** `skill-prose-pressure-tests`,
> which builds the eval harness, six scenarios and the judge (spec B4) ·
> **Protocol:** `docs/multiagent-protocol.md`

The second recorded run under the protocol: three subtasks in one wave,
then a fourth in a second wave, run by real builder and reviewer agents.

## The result

| Measure | Value |
|---|---|
| Wall-clock time | 17 h 15 min, from provisioning wave 1 (09:48) to the last integrated review (03:03 the next day) |
| Subtasks | 4, in 2 waves; wave 2 was added after the pilot was scored |
| Builder dispatches | 34 (subtask-1: 11, subtask-2: 10, subtask-3: 12, subtask-4: 1) |
| Reviews of the integrated change | 10, by reviewer agents; rounds 1 to 8 failed, 9 and 10 passed |
| Tokens, builders | 4,329,881 |
| Tokens, reviewers | 1,609,539 |
| Tokens, orchestrator | not measured - the orchestrating session's own use is not reported per step |
| Real model spend | $20.58 in reviews, which ran real sessions at a lowered budget; $6.89 for the pilot and the wording measurement |
| Merge conflicts | 0, across 12 runs of `integrate.sh` |
| Combined regression | green on the integrated tree after wave 2, except the pilot report's own test, which passed once the report was written |

All builders ran on Sonnet, each handed only its brief file's path. Budget
per dispatch: 600,000 tokens, 250,000 for subtask-4. No dispatch exceeded
it; the largest used 261,595.

## Each subtask

| Subtask | Work | Tries | Builder tokens |
|---|---|---|---|
| subtask-1 | `evals/harness.py`: runs a session under either condition and records it | 11 | 1,325,623 |
| subtask-2 | `evals/scenarios/`: the six scenarios and their seeds | 10 | 901,305 |
| subtask-3 | `evals/judge.py`: scores behaviours from actions and files | 12 | 1,965,341 |
| subtask-4 | one definition of Compass's own records, in the judge and the harness | 1 | 137,612 |

## Rework

Every integrated review from round 1 to round 8 failed on code quality
and measurement validity; acceptance passed from round 3 on. The cause was
the same each time. Every builder tested against a fake `claude`, as the
briefs required, so no builder saw what a real session writes. Each review
ran real sessions and found the next thing a fake could not show:

1. absolute paths, the installed CLI on `PATH`, no contract in five
   compass scenarios;
2. a schema passed as a path, `.pyc` files hiding the order of edits;
3. `/compass:*` commands denied, a directory name naming the scenario;
4. Compass's own red step not counted, a resume seed with no approach;
5. the reply to a stopped session missing most real questions;
6. templates unreadable, and shell spellings the command parser missed;
7. a manifest path holding a shell variable;
8. an unbound `red.json`.

From round 6 the design moved the judge from parsing commands to reading
the repository's end state, and from round 7 each brief handed the builder
the last review's real records to test against. Rounds 9 and 10 passed.

## Steps that needed improvising

- The design changed after most reviews. The protocol has no step for
  amending the contract mid-run; the orchestrator rewrote it and copied it
  into each worktree by hand.
- Each worktree was fast-forwarded to the integrated branch before a new
  try, so a builder saw the other two files. The protocol does not say to.
- Six tries were sent to a builder already running, by message, not as a
  new dispatch. Their token counts came back as the agent's running total,
  and each try's figure is that total less the last.
- A builder ran `git stash`, picked up another piece of work's stash
  shared by every worktree, and reset. Nothing was lost. Later briefs
  forbid `git stash`.
- The issue had no `devlog.md`: the assess stage did not start one, and
  the post-tool hook appends only to one that exists. The orchestrator
  wrote it late, from its notes.
- `compass issue subtask update --cost` keeps only the last try's cost,
  so the totals above are summed from the orchestrator's notes.

## Decisions taken for the user

- "With Compass" means a repository that has opted in, with `compass init`
  run and a read-only copy of this repository as its plugin. A repository
  with the plugin installed and no `.compass/` is not measured: both hooks
  do nothing there.
- The recorded Compass setup date is 30 days before the run, so the hook's
  refusal does not show it was set up minutes earlier.
- `HOME` passes through. The check whether a session authenticates without
  it was refused by the permission system as credential exploration, and
  was not run by any other route.
- The maintainer, asked, chose the reply to a session that stops with no
  code edit: one reply, "Go ahead with whichever option you recommend.",
  only in the three scenarios that score the order of work, the same under
  both conditions. That decision was the user's, not the orchestrator's.

## Found outside this issue, each recorded as a defect to fix next

- D28: the source-tree hash skips every nested `.compass/` directory.
- D29: a red from a command that runs no test unlocks code edits.
- D30: nine gaps the passing review left open in the judge and the
  scenarios.
- D31: a subtask's recorded cost keeps only the last try.

## What this run does not show

- Whether one agent building the three files in sequence, testing against
  real sessions from the start, would have cost less. No such build ran.
- That the protocol caused the rework. The rework came from tests that
  could not see real output, which a single agent would share.
