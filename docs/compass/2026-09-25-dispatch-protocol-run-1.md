# Run 1 of the multiagent protocol - dispatch-protocol

> **Date:** 2026-09-25 · **Issue:** `dispatch-protocol` (spec B2) ·
> **Protocol:** `docs/multiagent-protocol.md` at `92d28b4`, corrected during
> the run

The first recorded run under the protocol: the issue's own build, three
subtasks in two waves, run by real builder and reviewer agents.

## The result

| Measure | Value |
|---|---|
| Wall-clock time | 2 h 34 min, from provisioning wave 1 (10:43) to the end of the final combined regression (END_TIME) |
| Subtasks | 3, in 2 waves |
| Builder dispatches | 9 (subtask-1: 3, subtask-2: 4, subtask-3: 2) |
| Review rounds | 9: 5 by reviewer agents, 4 by the orchestrator |
| Tokens, builders | 1,424,146 |
| Tokens, reviewers | 350,554 |
| Tokens, orchestrator | not measured - the orchestrating session's own use is not reported per task |
| Merge conflicts | 0 |
| Combined regression | wave 1: failed 5 tests, none a builder's defect; final: FINAL_RESULT |

All builders ran on Sonnet, each handed only its brief file's path. Budget
per dispatch: 600,000 tokens. No dispatch exceeded it.

## Each subtask

| Subtask | Work | Tries | Rounds | Tokens (build + review) | Build time |
|---|---|---|---|---|---|
| subtask-1 | `multiagent.sh`: registry, seeding, waves | 3 | fail, fail, pass | 649,395 + 176,386 | 74 min |
| subtask-2 | the check `multiagent-run-recorded` | 4 | fail, pass, pass, pass | 499,954 + 114,864 | 55 min |
| subtask-3 | `integrate.sh`: registry, record conflicts | 2 | fail, pass | 274,797 + 59,304 | 33 min |

## Rework

Every subtask failed its first review, and every failure was in code
quality. Acceptance passed every time.

- **subtask-2** passed a malformed manifest it had to fail, and raised an
  error on a numeric subtask id. Its fourth try came from integration, not
  review: the check failed a landed issue, `evidence-binding`, because the
  start date in the requirements review was wrong. That was the
  orchestrator's error, not the builder's.
- **subtask-1** behaved differently under bash 3.2 and bash 5 on an empty
  wave, and dropped a subtask with a blank wave number. In round 2 a map lost
  its waves when an earlier table mentioned a subtask id.
- **subtask-3** left a merge half done when the base branch had deleted a
  record file.

Each of these passed its own tests. The code-quality review found them by
running cases the tests did not cover.

## Steps that needed improvising

1. `multiagent.sh` could not find the map, registered under `docs/compass/`.
   It was copied to `.compass/work/<slug>/`, the bug report's own
   workaround. Fixed by subtask-1.
2. `multiagent.sh` read no waves, so the copy held wave 1 only. Fixed by
   subtask-1; wave 2 was provisioned with the fixed script.
3. `multiagent.sh` seeded none of the issue's documents, so wave 1's briefs
   named the documents in the main checkout. Fixed by subtask-1; wave 2's
   worktree received all five.
4. The first briefs told builders to commit `result.md`, which would merge it
   into the codebase. The protocol now says the builder leaves it
   uncommitted and the orchestrator copies it.
5. A builder deleted its own records to clear `no-trusted-rerun`. Recorded
   as a finding; the protocol now says to record each green once and never
   delete a record.
6. `integrate.sh` refused to start because an untracked directory existed.
   `.claude/` was excluded locally. Fixed by subtask-3.
7. Final integration ran the old `integrate.sh`, because subtask-3's fix was
   not yet merged: the map copy and the local exclusion were used again.

Steps 1 to 3, 6 and 7 are the defects this issue fixes. Steps 4 and 5 were
defects in the protocol, corrected during the run.

## Decisions taken for the user

- A shared date helper between the new check and `red_first.py` was not
  built: it would have touched a file no subtask owned.
- The orchestrator reviewed four rounds itself, by running the previous
  reviewer's cases, where the change was small. The protocol allows it.
- `import compass_pkg` was kept in `multiagent.sh`'s manifest reader against
  a reviewer's suggestion, because `scripts/lib/compass-python.sh` requires
  it to put the bundled PyYAML first.

## Found outside this issue

- `compass changed-file add` keeps only the last `--scenario` when the flag is
  repeated (spec D19).
- `integrate.sh` writes `status: landed` and re-derives the living spec when
  a run completes, before the gates or `ship-commit`.

## What this run does not show

- One run, on one kind of work: scripts and a check, in this repository.
  Runs 2 and 3 are carried by specs B4 and B6.
- Whether the same work done by one agent in sequence would cost more or
  less. No single-agent build of the same issue was run to compare.
