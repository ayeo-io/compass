# Checkpoints

Compass records what happened at each stage hand-off. A person's answer to a hand-off is a `checkpoint-approval` record, and the outcome of each hand-off is kept in the manifest's `checkpoint_outcomes`. `compass ship-commit` refuses to land an issue that lists a checkpoint with no outcome. This document owns the record shapes, the commands that write them and the landing refusal. The decision behind them is [ADR-063](../architecture/decisions/ADR-063-checkpoint-outcomes-and-session-usage-are-stored-and-the-autonomy-and-cost-figures-are-derived.md); 9.0.0 removed its usage record and its autonomy and cost figures ([ADR-093](../architecture/decisions/ADR-093-compass-keeps-only-what-a-reviewer-of-one-change-needs.md)).

## Checkpoint outcomes

A checkpoint stage of a path issue (one whose manifest records `evidence_required`, [ADR-092](../architecture/decisions/ADR-092-compass-runs-one-path-of-four-stages.md)) is one of `assess`, `specify`, `build` and `ship`. A checkpoint stage of an issue assessed before 9.0.0 is one of `assess`, `define`, `refine`, `plan`, `implement` and `verify`. `core.CHECKPOINT_STAGES` holds both sets, and each issue reads only its own, so an old outcome keeps its meaning and an outcome in the other set's names is passed over. A listed checkpoint is a checkpoint stage of the issue in the manifest's `checkpoints:` list. It waits for a person. A configuration's `autonomy_checkpoints` table can name the stages of both sets. The routing gives an issue assessed before 9.0.0 only the legacy hand-offs, so a path stage in the table adds no checkpoint to it.

`implement` and `verify` (`build` and `ship` on a path issue) end stages 2 and 3 of the four-layer acceptance strategy (`S17`), and are listed only where the strategy applies to the issue ([ADR-083](../architecture/decisions/ADR-083-the-stage-2-and-3-reviews-are-checkpoints-listed-only-where-the-strategy-applies.md)). For an in-scope issue:

- A request for the `refine`, `implement` or `verify` checkpoint (`specify`, `build` or `ship` on a path issue) holds `review`: the stage it ends and the questions of that stage from `skills/atdd/references/stage-reviews.md` (`checkpoint_outcomes.review`). The skill's headings name the path stages; an old issue's `refine`, `implement` and `verify` checkpoints read the `specify`, `build` and `ship` headings.
- `compass next` reads the stage 2 and 3 hand-offs (`checkpoint_outcomes.next_review`). When the records show one done with no outcome, it waits at a listed checkpoint and names `compass evidence request --checkpoint <stage>`. At a checkpoint that is not listed it goes on and names `compass issue checkpoint add <stage> --outcome skipped --by builder` (or `verifier`). A path issue's `ship` stage is done only once the issue is closed, so its hand-off is due once every gate has passed (`checkpoint_outcomes.reached`), where an old issue's `verify` hand-off is due.
- A request for either that a person rejects sends the issue back: while the rejection is newer than the stage's outcome, `compass next` names the stage and the reason.
- `compass check` does not fail on a listed review with no outcome. The landing refusal below refuses it.

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

- The command refuses the approver `agent`, and a rejected decision. It needs `--role`, and the stage must be one the approach runs and must have its own record.
- Who may answer follows the rule `compass evidence approve --decisions` applies: a name in an `approvers:` list of the project file, else the project's `owner`. A project that declares neither accepts any name that is not an agent, and the command prints one line saying so.
- It writes one `checkpoint-approval` record and the `waited` outcome that cites it. `compass evidence add --type checkpoint-approval` is refused.

An agent records a hand-off that autonomy passed:

`compass issue checkpoint add <stage> --outcome skipped --by <agent>`

- It writes no evidence record and no devlog line.
- It refuses a listed checkpoint, a stage that already holds `waited`, a stage that is not a checkpoint stage of the issue (a legacy stage on a path issue, or a path stage on an older one), a stage the approach collapses or skips, a `--by` that is not an agent, and `--outcome waited`. Each refusal exits 2 and writes nothing.
- A repeat for a stage already `skipped` exits 0 and leaves the manifest bytes unchanged.

Both commands refuse an issue that is not judged (see below) and write nothing.

### The `checkpoint-approval` record

A `checkpoint-approval` record is a person's answer to one hand-off. It holds `id`, `type`, `checkpoint`, `approver`, `role`, `scope`, `decision: approved`, `timestamp`, `issue` and `generation`, and no `check` key. On a path issue the record for `specify` also holds `spec`, the spec's path relative to the project, and `spec_sha256`, the `sha256sum` digest of its bytes, so the record names the scenarios the person approved ([ADR-095](../architecture/decisions/ADR-095-compass-reads-the-ship-approval-from-the-merged-pull-request.md)). It is a separate evidence type so that it never meets guardrail `G5` or a human check: `human-approval-present`, the human-check reader and the waiver check read other types and do not see it.

## The scenario sign-off before code

On a path issue that owes `scenario-approval` (a `G5` label, a `signoff_labels` label or critical risk), `compass tdd-red` refuses while the `specify` checkpoint has no `waited` outcome, with the code `scenarios-not-approved`. A `skipped` outcome does not count. It refuses before the test runs, so it writes no red record and no `.red` marker, and code edits stay refused. The fix names `compass evidence request --checkpoint specify`; the person answers with `/compass:approve`. The landing refusal below stays. An issue that does not owe `scenario-approval` is not refused, and `controlled` autonomy still waits at specify on every change, because that wait is the project's choice and not this rule (`scenario_freeze.refusal`).

A request for the `specify` checkpoint of a path issue holds `spec` and `spec_sha256`, and Compass shows the person the first 12 characters of the digest. The prompt hook refuses to record the answer, and closes the request as stale, when the spec's digest changed after the request was written.

## The landing refusal

`compass ship-commit` runs an ordered list of landing refusals before it stages, renders, commits, derives or syncs anything. A refusal leaves every file as it was. The first entry refuses a judged issue that lists a checkpoint with no outcome, with the code `checkpoint-no-outcome`. It names each stage and the command that asks the person for an answer, `compass evidence request --checkpoint <stage>`, then stops: an agent does not approve. `compass quick-fix finish` runs the same list with its other preconditions, unless `--no-commit` is given.

A later refusal is one more function appended to `manifest.LANDING_REFUSALS`, with its code in `refusals.py`. It is not a branch in the command.

### Which issues it judges

A judged issue is an issue whose manifest holds the `checkpoint_outcomes` key, an empty list included. The first assessment of every issue writes it. Nothing else adds it: a reassessment does not, and no migrate back-fills it, because nothing records what happened at the hand-offs of an older issue.

- An issue that is not judged is never refused. `compass check`, `compass issue lint` and `compass ci` raise no finding for it, and it lands as it did before.
- `ship-commit` takes the issue from `--issue`, then `COMPASS_ISSUE`, then the current-task pointer. It never guesses the most recently changed issue.

## Where the outcomes are read

- `compass issue diagnose` has a Checkpoints section for one issue: each outcome with its stage, outcome, by and at, or `no checkpoint outcomes recorded`. Each outcome is also an event in its timeline.
- `compass record sync` copies the configured paths file by file. Where `.compass/work` is listed, the record holds each manifest with its `checkpoint_outcomes`, and the `approver` of every `checkpoint-approval` record.

## What 9.0.0 no longer writes

A manifest written before 9.0.0 can hold a `usage` block: the session ids the pre-tool hook recorded and the tokens and cost read from their transcripts. The quick fix also wrote `started_at`, `finish_started_at` and `committed_at` as the ends of its stages. 9.0.0 writes none of these, and the schema still reads each as valid. The pre-tool hook writes no manifest.
