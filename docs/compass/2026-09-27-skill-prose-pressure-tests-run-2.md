# Run 2 of the multiagent protocol - skill-prose-pressure-tests

> **Date:** 2026-09-26 to 2026-09-27 · **Issue:** `skill-prose-pressure-tests`,
> which builds the eval harness, six scenarios and the judge ·
> **Protocol:** `docs/multiagent-protocol.md`

The second recorded run under the protocol; the first is
`docs/compass/2026-09-25-dispatch-protocol-run-1.md`. Three subtasks ran in
one wave, a fourth in a second wave and a fifth in a third, by real
builder and reviewer agents.

## The result

| Measure | Value |
|---|---|
| Wall-clock time | 23 h 21 min, from provisioning wave 1 (09:48) to the last review at `/compass:verify` (09:09 the next day) |
| Subtasks | 5, in 3 waves; wave 2 was added after the pilot was scored, wave 3 after the security review at `/compass:verify` |
| Builder tries | 38 (subtask-1: 11, subtask-2: 10, subtask-3: 12, subtask-4: 1, subtask-5: 4), from 32 new dispatches and 6 messages to a builder already running |
| Reviews of the integrated change | 10, by reviewer agents; rounds 1 to 8 failed, 9 and 10 passed |
| Reviews at `/compass:verify` | 9, by reviewer agents: security three times, clarity three times, claims once, and two final checks of wave 3 |
| Tokens, builders | 5,603,063 |
| Tokens, reviewers | 2,449,891: 1,609,539 on the ten integrated reviews, 840,352 at `/compass:verify` |
| Tokens, orchestrator | not measured - the orchestrating session's own use is not reported per step |
| Real model spend | about $20.58 in reviews, nine of which ran real sessions at a lowered budget; $6.89 for the pilot and the wording measurement, plus scoring calls that were not recorded |
| Merge conflicts | 0, across 16 runs of `integrate.sh` |
| Combined regression | green on the integrated tree after wave 3's last try |

All builders ran on Sonnet, each handed only its brief file's path. Budget
per dispatch: 600,000 tokens, 250,000 for subtask-4 and 400,000 for
subtask-5. No dispatch exceeded it; the largest used 358,410.

## Each subtask

| Subtask | Work | Tries | Builder tokens |
|---|---|---|---|
| subtask-1 | `evals/harness.py`: runs a session under either condition and records it | 11 | 1,325,623 |
| subtask-2 | `evals/scenarios/`: the six scenarios and their seeds | 10 | 901,305 |
| subtask-3 | `evals/judge.py`: scores behaviours from actions and files | 12 | 1,965,341 |
| subtask-4 | one definition of Compass's own records, in the judge and the harness | 1 | 137,612 |
| subtask-5 | the security fixes and the citation guard from `/compass:verify` | 4 | 1,273,182 |

## Rework

Every integrated review from round 1 to round 8 failed on code quality
and measurement validity; acceptance passed from round 3 on. The cause was
the same each time. Every builder tested against a fake `claude`, as the
briefs required, so no builder saw what a real session writes. Each review
ran real sessions and found the next thing a fake could not show:

1. Real sessions write absolute paths, which the judge did not match.
   Both conditions could run the installed Compass CLI. In five of six
   scenarios the compass session never received Compass's injected
   instructions, because its repository had not opted in.
2. The judge handed the model a file path where it needed the JSON schema
   itself, so model judging never ran. Compiled `.pyc` files from test
   runs looked like code edits and hid their order.
3. The compass sessions were refused every `/compass:*` command, and the
   working directory's name told the session which scenario it was in.
4. The judge did not count Compass's own red step, `compass tdd-red`, as
   a failing test, and the resume scenario's record had no delivery
   approach, so the hook refused its edits.
5. The reply to a session that stopped to ask fired only when its last
   message ended with a question mark, and most real questions did not.
6. Compass sessions could not read the plugin's templates, and the judge
   missed shell commands spelt in ways its parser did not list.
7. The judge missed a manifest written to a path holding a shell
   variable, such as `.compass/work/$S/manifest.yml`.
8. The judge did not count a red record written without a scenario name,
   `red.json`, as a failing test.

From round 6 the design moved the judge from parsing commands to reading
the repository's end state, and from round 7 each brief handed the builder
the last review's real records to test against. Rounds 9 and 10 passed.
At `/compass:verify`, the security review then found that the harness ran
session-written code with its own environment, and that its containment
check could not see ignored files or `.git/`. Wave 3 took four tries. Its
first closed the named cases and left others of the same kind open, so
the second review failed on members of the same class. The later tries
fixed each class: one helper for every git call, with a test that no
other process start exists, and a citation guard that names what it
catches and lists what it does not. The last try closed a regression the
third try had introduced. The design now states where the security
requirement stops: nothing a session controls may run with more than the
session's own minimal environment, and a further route that stays within
it is recorded for later, not a blocker.

## Steps that needed improvising

- The design changed after most reviews. The protocol has no step for
  amending the shared design mid-run; the orchestrator rewrote it and copied it
  into each worktree by hand.
- Each worktree was fast-forwarded to the integrated branch before a new
  try, so a builder saw the other two files. The protocol does not say to.
- Six tries were sent to a builder already running, by message, not as a
  new dispatch. Their token counts came back as the agent's running total,
  and each try's figure is that total less the last.
- A builder ran `git stash`, picked up another piece of work's stash
  shared by every worktree, and reset its own worktree to its last commit.
  Nothing was lost. Later briefs
  forbid `git stash`.
- The issue had no `devlog.md`: the assess stage did not start one, and
  the post-tool hook appends only to one that exists. The orchestrator
  wrote it late, from its notes.
- Builders broke three rules and each disclosed it. One rewrote comments
  through a Bash script before recording a red; the hook stopped its next
  edit. One ran `git stash` against its brief and popped it at once; the
  shared stash was intact. Twice a builder started a red after editing;
  the CLI refused each, and the builder redid it. For one red, a builder
  reverted to its own draft to make a test fail.
- `compass issue subtask update --cost` keeps only the last try's cost,
  so the totals above are summed by hand from each agent's reported
  tokens, in the orchestrator's notes and its session transcript. Neither
  is published.

## Decisions about how the runs were set up

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

- The CLI's source-tree hash skips every nested `.compass/` directory, so
  an edit under one looks like no change.
- A red from a command that runs no test, such as
  `compass tdd-red -- false`, unlocks code edits.
- Nine known gaps remain in the judge, the harness and the scenarios'
  rubrics; none changed a pilot result.
- A subtask's recorded cost keeps only the last try.

## What this run does not show

- Whether one agent building the three files in sequence, testing against
  real sessions from the start, would have cost less. No such build ran.
- That the protocol caused the rework. In the orchestrator's judgement,
  the rework came from tests that could not see real output, which a
  single agent would share; no build ran to test that.
