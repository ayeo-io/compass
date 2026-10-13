# Autonomy and cost

Compass records what happened at each stage hand-off and what each issue cost. `compass retro --impact` and `compass issue diagnose` read those records and show how much work ran without a person and what a change cost. This document owns the record shapes, the commands that write them, the landing refusal, the session record, the definitions of every derived figure and the limits. The decision behind it is [ADR-063](../architecture/decisions/ADR-063-checkpoint-outcomes-and-session-usage-are-stored-and-the-autonomy-and-cost-figures-are-derived.md).

Four things are stored: the checkpoint outcomes, the `checkpoint-approval` records they cite, `usage.sessions` and the `usage` counts. Every other figure is derived when it is read and stored nowhere: the bands, the autonomy ratio, whether usage is complete and every median. The schema holds no key for a derived figure.

## Checkpoint outcomes

A checkpoint stage is one of `assess`, `define`, `refine` and `plan`. A listed checkpoint is a checkpoint stage in the manifest's `checkpoints:` list. It waits for a person.

The manifest's optional `checkpoint_outcomes` list holds one entry for each checkpoint stage that has an outcome:

`{stage, outcome, by, at}`, plus `evidence` on a `waited` entry.

| Key | Holds |
|---|---|
| `stage` | A checkpoint stage. |
| `outcome` | `waited` or `skipped`. |
| `by` | For `waited`, the approver of the record cited. For `skipped`, the agent that went on. |
| `at` | For `waited`, the timestamp of the record cited. For `skipped`, the time of the command. |
| `evidence` | For `waited` only: the id of the `checkpoint-approval` record. |

- `waited` means a person answered the hand-off.
- `skipped` means the autonomy setting passed the hand-off and an agent went on.
- One outcome is kept for each stage. A person's later answer replaces `skipped`, and a second answer replaces the first. A `skipped` never replaces `waited`.
- Outcomes belong to the issue, not to a generation, so an answer never changes a stored generation.

### The two commands

A person answers a hand-off at a terminal:

`compass evidence approve --checkpoint <stage> --approver <name> --role <role> [--scope <text>]`

- The command refuses the approver `agent`, and a rejected decision. It needs `--role`, and the stage must be one the route runs and must have its own record.
- Who may answer follows the rule `compass evidence approve --decisions` applies: a name in an `approvers:` list of the project file, else the project's `owner`. A project that declares neither accepts any name that is not an agent, and the command prints one line saying so.
- It writes one `checkpoint-approval` record and the `waited` outcome that cites it. `compass evidence add --type checkpoint-approval` is refused.

An agent records a hand-off that autonomy passed:

`compass issue checkpoint add <stage> --outcome skipped --by <agent>`

- It writes no evidence record and no devlog line.
- It refuses a listed checkpoint, a stage that already holds `waited`, a stage that is not a checkpoint stage, a stage the route collapses or skips, a `--by` that is not an agent, and `--outcome waited`. Each refusal exits 2 and writes nothing.
- A repeat for a stage already `skipped` exits 0 and leaves the manifest bytes unchanged.

Both commands refuse an issue that is not judged (see below) and write nothing.

### The `checkpoint-approval` record

A `checkpoint-approval` record is a person's answer to one hand-off. It holds `id`, `type`, `checkpoint`, `approver`, `role`, `scope`, `decision: approved`, `timestamp`, `issue` and `generation`, and no `check` key. It is a separate evidence type so that it never meets guardrail `G5` or a human check: `human-approval-present`, the human-check reader and the waiver check read other types and do not see it.

## The landing refusal

`compass ship-commit` runs an ordered list of landing refusals before it stages, renders, commits, derives or syncs anything. A refusal leaves every file as it was. The first entry refuses a judged issue that lists a checkpoint with no outcome, with the code `checkpoint-no-outcome`. It names each stage and the command that records it. `compass quick-fix finish` runs the same list with its other preconditions, unless `--no-commit` is given.

A later refusal is one more function appended to `manifest.LANDING_REFUSALS`, with its code in `refusals.py`. It is not a branch in the command.

### Which issues it judges

A judged issue is an issue whose manifest holds the `checkpoint_outcomes` key, an empty list included. The first assessment of every issue writes it. Nothing else adds it: a reassessment does not, and no migrate back-fills it, because nothing records what happened at the hand-offs of an older issue.

- An issue that is not judged is never refused. `compass check`, `compass issue lint` and `compass ci` raise no finding for it, and it lands as it did before.
- `ship-commit` takes the issue from `--issue`, then `COMPASS_ISSUE`, then the current-task pointer. It never guesses the most recently changed issue.
- The retro counts a shipped issue that lists a checkpoint with no outcome as not measurable.

## The session record

The pre-tool hook appends the session id to `usage.sessions` the first time it judges a tool call for an issue. It records on Edit, Write and Bash calls, before it classifies the target.

- It resolves the issue in shell from `COMPASS_ISSUE`, then the current-task pointer. With neither it records nothing, and it never falls back to the most recently changed issue.
- A recorded id costs one `grep`. A new id starts one Python process.
- An id that does not match `[A-Za-z0-9_-]+` is not recorded.
- When the pointer names the issue and the session table shows the session working on another issue, nothing is recorded.
- The write tries the per-issue `.manifest.lock` once, without waiting. If another process holds it, nothing is written and the id is recorded on a later call.
- It inserts the id by text, checks that the parsed result changed nothing else, and replaces the file atomically after comparing the bytes on disk with the bytes it read. If they changed, it merges again, up to three times.
- Any fault allows the edit with exit 0 and leaves the manifest as it was. The record never refuses an edit.
- `core.save_manifest` holds the same lock while it writes, so the hook never replaces a manifest a command is writing. A writer that does not take the lock is merged, not excluded.

## Usage at ship

After a landing, `ship-commit` reads the transcripts of every session in `usage.sessions`, and of the session running it, into the manifest's `usage` block. The quick fix keeps the block `quick-fix finish` wrote. An issue that is not judged gets no block.

- Transcripts are only read, line by line, and a request written over several lines is counted once. Nothing is sampled.
- The block holds numbers, booleans, model names, times, session ids and the words in `session_usage.REASONS`. No transcript text and no transcript path is stored.
- Session ids reach the delivery record inside the manifest it already copies.
- `ship-commit` never refuses for usage. When usage is not recorded it prints one line naming the reason.

### The read limit

Before it reads, `ship-commit` sums the size of every transcript file of every recorded session. Above `USAGE_READ_LIMIT_BYTES` (1 GiB) it reads none and records `recorded: false` with the reason `too-large`.

| Fault | Block holds |
|---|---|
| no session id at all | `recorded: false`, reason `not-claude-code` |
| a session id of the wrong shape | `recorded: false`, reason `bad-session-id`, the valid ids kept |
| a session with no main transcript | `recorded: false`, reason `no-transcript`, `sessions` kept |
| a transcript that cannot be read | `recorded: false`, reason `unreadable`, `sessions` kept |
| the files together over the limit | `recorded: false`, reason `too-large`, `sessions` kept |
| a model with no entry in `prices` | the counts, and `cost_usd` null where that model ran |

A block with `recorded: false` holds no count.

### Stage windows

A request counts for the issue when its time is at or after the issue's start and before the landing. The start is the latest boundary of another issue that records the same session, earlier than this issue's earliest stage end, or else the session's first request.

The stage ends are:

| Stage | Ends at |
|---|---|
| `assess`, `define`, `refine`, `plan` | the `at` of the stage's outcome |
| `breakdown` | the earliest `dispatched_at` of a subtask |
| `implement` | the latest red, green or acceptance record |
| `verify`, `ship` | no end: gates are not dated and ship runs inside the command |

An end later than the end of a later stage is dropped, because a person can answer a checkpoint after later work.

- The route's stages are walked in order from a cursor that starts before every request. A stage with an end after the cursor gets the window from the cursor to its end. A stage without one holds `measured: false` with the reason `no-window`, and its requests fall in the next window.
- Requests at or after the last end are `unattributed`. `total` is every request in the span, and the stages and `unattributed` add up to it for every count.
- A window that another issue's span overlaps, where that issue records the same session, is marked `shared: true`, and so is `total`.

## Derived figures

Every reader calls the functions of `cli/compass_pkg/autonomy_cost.py`, so the retro and `compass issue diagnose` give the same number for the same issue.

| Term | Meaning |
|---|---|
| shipped issue | An issue `status_words.is_completed` accepts. |
| measurable | A shipped issue whose manifest holds `checkpoints:` as a list and an outcome for every listed checkpoint. |
| autonomous issue | A measurable issue with no `waited` outcome. |
| human judgement count | The `waited` outcomes plus the human checks whose approval `approval_records.judge` passes. The unit is checkpoints and human checks. |
| guardrailed count | The gates with status `pass` and at least one evidence id that names a typed record in `evidence:`. The unit is gates. |
| autonomous count | The stages the route ran (weight not `skipped`, `collapsed` or `none`) with no `waited` outcome and no passed gate. A gate belongs to the stage its id starts with, such as `verify.` for `verify.correctness`. The unit is stages. |
| complete usage | A `usage` block with `recorded` not false, a numeric `total.cost_usd` and no stage marked `shared`. A quick fix's block has no total: every measured stage needs a numeric `cost_usd`, none may be shared, and the cost is their sum. |

The three bands count unlike things, so each is printed with its unit and they are never added together. When the issue's configuration cannot be read, its bands are not counted: the issue is left out of the band totals and counted as not measurable for them.

- The autonomy ratio is the autonomous issues over the measurable issues, both shipped. A shipped issue that is not measurable is counted and reported, and is never treated as autonomous or as not.
- The cost per change is the median cost of the issues with complete usage, for each delivery approach, and the median of each cost divided by the issue's scenario count. An issue without complete usage is counted as unmeasured, never as zero. An issue with no scenarios is left out of the per-scenario figure and counted.

## The retro rows

`compass retro --impact` prints four rows after its by-approach block. Every other line keeps its text and its place. The command is advisory: it exits 0 and writes nothing.

| Row | Rests on |
|---|---|
| `autonomy` | the measurable shipped issues, with the shipped issues not measurable |
| `bands` | the measurable shipped issues whose bands could be counted |
| `cost` | the shipped issues with complete usage, with the shipped issues unmeasured |
| `decisions` | the issues that hold decisions, from the numbers `compass retro --decisions` prints |

Each row says how many issues it rests on. A row below its floor says `unmeasurable` with its count and the floor, and prints no `0%`, no `$0` and no median:

- `IMPACT_SAMPLE_FLOOR` (20) is the floor of each row: 20 measurable shipped issues for the ratio and the bands, 20 shipped issues with complete usage for the cost, and 20 issues with decisions for the decisions row.
- `IMPACT_GROUP_FLOOR` (3) is the floor of each approach group in the cost row. A smaller group is shown with its count and `under 3 - not summarised`.
- A cost prints to four decimal places.

`compass retro --impact --json` and `compass retro --impact --format json` print one identical object. It holds the numbers `compute_impact` returns, with its sets as sorted lists, and the four rows `autonomy_ratio`, `band_split`, `cost_per_change` and `decisions_confirmed`. Each row holds `value`, `issues`, `not_measurable` and `withheld`. An unmeasurable value is `null` with a `withheld` reason, never 0.

`compass issue diagnose` has a Checkpoints and cost section for one issue: each outcome with its stage, outcome, by and at, the three band counts with their units, and the total and per-stage cost and requests, or `cost: not recorded (<reason>)`. Each outcome is also an event in its timeline. Its last line of what the records cannot show is the token use of a session the hook did not record.

## The delivery record

`compass record sync` copies the configured paths file by file. Where `.compass/work` is listed, the record holds each manifest with its `usage` block and `checkpoint_outcomes`, and the `approver` of every `checkpoint-approval` record. A record that does not list `.compass/work` holds neither, and no summary file is added.

## Limits

- A session the hook never saw, and that is not the session running `ship-commit`, is not counted. A session that only reads, with no Edit, Write or Bash call, is not recorded.
- A session recorded only in a linked worktree's copy of the manifest is not read, because `ship-commit` reads the main checkout's manifest. Subagent requests are counted through the parent session's subagents folder.
- No usage is recorded for an issue landed before this change, and no migrate reads a transcript after the fact.
- A session id that appears as a list item elsewhere in the manifest is taken as already recorded. Today no other list holds session ids.
