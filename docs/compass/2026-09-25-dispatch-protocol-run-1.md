# Run 1 of the multiagent protocol - dispatch-protocol

> **Date:** 2026-09-25 · **Issue:** `dispatch-protocol`, which writes the
> protocol and fixes the two multiagent scripts · **Protocol:**
> `docs/multiagent-protocol.md`, corrected during the run

The first recorded run under the protocol: the issue's own build, four
subtasks in three waves, run by real builder and reviewer agents.

## The result

| Measure | Value |
|---|---|
| Wall-clock time | 4 h 4 min, from provisioning wave 1 (10:43) to the last subtask review (14:47) |
| Subtasks | 4, in 3 waves; the third wave was added during `/compass:verify` |
| Builder dispatches | 13 (subtask-1: 4, subtask-2: 4, subtask-3: 3, subtask-4: 2) |
| Subtask review rounds | 13: 5 by reviewer agents, 8 by the orchestrator |
| Reviews of the integrated change | 2 reviewer agents: security; clarity and claims |
| Tokens, builders | 2,166,238 |
| Tokens, reviewers | 632,850 (350,554 on subtasks, 282,296 on the integrated change) |
| Tokens, orchestrator | not measured - the orchestrating session's own use is not reported per step |
| Merge conflicts | 0, across four runs of `integrate.sh` |
| Combined regression | the full suite on the final integrated tree is the issue's recorded green run |

All builders ran on Sonnet, each handed only its brief file's path. Budget
per dispatch: 600,000 tokens. No dispatch exceeded it.

## Each subtask

| Subtask | Work | Tries | Rounds | Tokens (build + review) | Build time |
|---|---|---|---|---|---|
| subtask-1 | `multiagent.sh`: registry, seeding, waves | 4 | fail, fail, pass, pass | 814,354 + 176,386 | 95 min |
| subtask-2 | the check `multiagent-run-recorded` | 4 | fail, pass, pass, pass | 499,954 + 114,864 | 55 min |
| subtask-3 | `integrate.sh`: registry, record conflicts | 3 | fail, pass, pass | 541,462 + 59,304 | 61 min |
| subtask-4 | `ship-commit` lands and derives the spec | 2 | fail, pass | 310,468 + 0 | 32 min |

A try after a passing round came from a later review: the review of the
integrated change, or a decision at integration.

## Rework

Every subtask failed its first review, and every failure was in code
quality. Acceptance passed every time.

- **subtask-1** behaved differently under bash 3.2 and bash 5 on an empty
  wave, and dropped a subtask with a blank wave number. In round 2 a map lost
  its waves when an earlier table mentioned a subtask id. The security review
  of the integrated change then found that seeding followed a symlink out of
  the worktree, and that a huge wave number hung the script.
- **subtask-2** passed a malformed manifest it had to fail. Its fourth try
  came from integration: the check failed a landed issue, `evidence-binding`,
  because the start rule in the requirements review was wrong. That was the
  orchestrator's error, not the builder's.
- **subtask-3** left a merge half done when the base branch had deleted a
  record file. The security review found that a file moved into the records
  could drop a builder's code.
- **subtask-4** did not exist at the start. It was added during
  `/compass:verify`, when the maintainer decided that `ship-commit`, not
  `integrate.sh`, lands an issue (ADR-026). Its first try passed its own tests and broke four others
  that assumed the land commit is HEAD.

Each of these passed its own tests. The code-quality and security reviews
found them by running cases the tests did not cover.

## Steps that needed improvising

1. `multiagent.sh` could not find the map, registered under `docs/compass/`.
   It was copied to `.compass/work/<slug>/`, the workaround in the issue
   `multiagent-does-not-ask-where-documents-live`. Fixed by subtask-1.
2. `multiagent.sh` read no waves, so the copy held wave 1 only. Fixed by
   subtask-1; waves 2 and 3 were provisioned with the fixed script.
3. `multiagent.sh` seeded none of the issue's documents, so wave 1's briefs
   named the documents in the main checkout. Fixed by subtask-1; later waves
   received all five.
4. The first briefs told builders to commit `result.md`, which would merge it
   into the codebase. The protocol now says the builder leaves it
   uncommitted and the orchestrator copies it.
5. A builder deleted its own records to clear `no-trusted-rerun`. Recorded as
   a finding; the protocol now says to record each green once and never
   delete a record.
6. `integrate.sh` refused to start because an untracked directory existed.
   `.claude/` was excluded locally, and that exclusion made a citation check
   fail in the combined regression. Fixed by subtask-3.
7. The combined regression failed twice, and the protocol had no step for
   that. The orchestrator fixed its own files, sent the rest back as new
   tries, and re-ran. The protocol now has that step.
8. The map copy was replaced with the full map before the final integration
   of waves 1 and 2, because the old `integrate.sh` still read the copy.
9. After subtask-1's and subtask-3's fixes merged, the combined regression
   was stopped at 3%: it was failing on tests subtask-4 was about to replace,
   and on this record's unfilled figures.
10. The orchestrator reviewed eight rounds itself, by replaying the previous
    reviewer's cases, and wrote no package for those tries. The protocol now
    allows this and says how to record it.
11. Wave 1's briefs were written to `briefs/<id>.md` and results to
    `results/`; the skill already named `subtasks/<id>/briefing.md`. Wave 3
    used the skill's path, which the protocol now gives.
12. The builders' own reds and greens lived in their worktrees, and
    `integrate.sh` removed the worktrees at the end, so those records are
    gone. Each builder's result states the commands and output. The
    protocol now says to copy a builder's records with its result.

Steps 1 to 3, 6 and 8 are defects this issue fixes. Steps 4, 5, 7, 10, 11
and 12 were gaps in the protocol, corrected during the run.

## Decisions taken for the user

- A shared date helper between the new check and `red_first.py` was not
  built: it would have touched a file no subtask owned.
- `import compass_pkg` was kept in `multiagent.sh`'s manifest reader against
  a reviewer's suggestion, because `scripts/lib/compass-python.sh` needs it
  to put the bundled PyYAML first.
- The spec-derivation helper in `ship-commit` finds the project root from
  the current directory, which is the directory `ship-commit` runs in. A test
  that calls it directly must change directory first.
- The maintainer, asked, decided that `ship-commit` lands every issue and
  derives the living spec (ADR-026). That decision was the user's, not the
  orchestrator's.

## Found outside this issue, filed as their own specs

- `compass changed-file add` keeps only the last `--scenario` when the flag is
  repeated.
- A map's subtask ids and branch cells reach paths and git unchecked.
- A merge can overwrite an ignored record in the main checkout.
- The check and `subtask next` do not compare the recorded subtasks with the
  map.

## What this run does not show

- One run, on one kind of work: scripts, a check and a CLI command, in this
  repository. Two more runs, on later work, are to follow.
- Whether the same work done by one agent in sequence would cost more or
  less. No single-agent build of the same issue was run to compare.
