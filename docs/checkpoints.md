# Checkpoints

A checkpoint is a stage hand-off where a session waits for a person. This
page owns the records Compass keeps of each hand-off, the commands that
write them and the refusal to land an issue with an unanswered checkpoint.
Decisions:
[ADR-063](../architecture/decisions/ADR-063-checkpoint-outcomes-and-session-usage-are-stored-and-the-autonomy-and-cost-figures-are-derived.md)
and, for what 9.0.0 removed from it,
[ADR-093](../architecture/decisions/ADR-093-compass-keeps-only-what-a-reviewer-of-one-change-needs.md).

## Checkpoint outcomes

| Issue | Checkpoint stages |
|---|---|
| A path issue: its manifest records `evidence_required` ([ADR-092](../architecture/decisions/ADR-092-compass-runs-one-path-of-four-stages.md)) | `assess`, `specify`, `build`, `ship` |
| An issue assessed before 9.0.0 | `assess`, `define`, `refine`, `plan`, `implement`, `verify` |

- `core.CHECKPOINT_STAGES` holds both sets. Each issue reads only its own
  set, and passes over an outcome in the other set's names.
- A listed checkpoint is a checkpoint stage in the manifest's `checkpoints:`
  list. It waits for a person.
- A configuration's `autonomy_checkpoints` table can name the stages of both
  sets. A path stage in the table adds no checkpoint to an issue assessed
  before 9.0.0.

`build` and `ship` (`implement` and `verify` on an older issue) end stages 2
and 3 of the four-layer acceptance strategy (`S17`). They are listed only
where the strategy applies to the issue
([ADR-083](../architecture/decisions/ADR-083-the-stage-2-and-3-reviews-are-checkpoints-listed-only-where-the-strategy-applies.md)).
For such an issue:

- A request for the `specify`, `build` or `ship` checkpoint (`refine`,
  `implement` or `verify` on an older issue) holds `review`: the stage it
  ends and that stage's questions from
  `skills/atdd/references/stage-reviews.md`.
- `compass next` reads the stage 2 and 3 hand-offs. When one is done with no
  outcome:
  - at a listed checkpoint it waits and names
    `compass evidence request --checkpoint <stage>`;
  - at a checkpoint that is not listed it goes on and names
    `compass issue checkpoint add <stage> --outcome skipped --by builder` (or
    `verifier`).
- A path issue's `ship` hand-off is due once every gate has passed.
- When a person rejects a request, `compass next` names the stage and the
  reason while the rejection is newer than the stage's outcome.
- `compass check` does not fail on a listed review with no outcome. The
  landing refusal below does.

The manifest's optional `checkpoint_outcomes` list holds one entry for each
checkpoint stage that has an outcome: `{stage, outcome, by, at}`, plus
`evidence` on a `waited` entry.

| Key | Holds |
|---|---|
| `stage` | A checkpoint stage. |
| `outcome` | `waited`: a person answered the hand-off. `skipped`: the autonomy setting passed it and an agent went on. |
| `by` | For `waited`, the approver of the record cited. For `skipped`, the agent that went on. |
| `at` | For `waited`, the timestamp of the record cited. For `skipped`, the time of the command. |
| `evidence` | For `waited` only: the id of the `checkpoint-approval` record. |

- One outcome is kept for each stage. A person's later answer replaces
  `skipped`, and a second answer replaces the first. A `skipped` never
  replaces `waited`.
- Outcomes belong to the issue, not to a generation.

### The two commands

A person answers a hand-off at a terminal:

`compass evidence approve --checkpoint <stage> --approver <name> --role <role> [--scope <text>]`

- It needs `--role`. With exit 2 and no change, it refuses:
  - the approver `agent`, or a name that may not answer;
  - a rejected decision;
  - a stage that is not a checkpoint stage of the issue;
  - a stage the approach collapses or skips;
  - a stage whose own record is not written yet.
- On a path issue, specify can be answered once each scenario has an id, an
  intent and a declared test, and ship once build is done.
- Who may answer: a name in an `approvers:` list of the project file, else
  the project's `owner`. A project that declares neither accepts any name
  that is not an agent, and the command prints one line saying so.
- It writes one `checkpoint-approval` record, `EV-CHECKPOINT-<stage>-<n>`,
  and the `waited` outcome that cites it. A second answer writes a new
  record, and both stay.
- `compass evidence add --type checkpoint-approval` is refused. It also
  refuses the types `isolation-proof` and `layering`: only `compass
  isolation record` and `compass layering record` write them (ADR-086).

An agent records a hand-off that autonomy passed:

`compass issue checkpoint add <stage> --outcome skipped --by <agent>`

- It writes no evidence record and no devlog line.
- It refuses, with exit 2 and no write:
  - a listed checkpoint;
  - a stage that already holds `waited`;
  - a stage that is not a checkpoint stage of the issue;
  - a stage the approach collapses or skips;
  - a `--by` that is not an agent;
  - `--outcome waited`.
- A repeat for a stage already `skipped` exits 0 and leaves the manifest
  bytes unchanged.

Both commands refuse an issue that is not judged (see below) and write
nothing.

### The `checkpoint-approval` record

A person's answer to one hand-off. It holds `id`, `type`, `checkpoint`,
`approver`, `role`, `scope`, `decision: approved`, `timestamp`, `issue` and
`generation`, and no `check` key.

- On a path issue the record for `specify` also holds `spec`, the spec's
  path relative to the project, and `spec_sha256`, the `sha256sum` digest of
  its bytes
  ([ADR-095](../architecture/decisions/ADR-095-compass-reads-the-ship-approval-from-the-merged-pull-request.md)).
- It is its own evidence type, so it never meets guardrail `G5` or a human
  check. `human-approval-present`, the human-check reader and the waiver
  check do not read it.

## The scenario sign-off before code

A path issue owes `scenario-approval` when it has a `G5` label, a
`signoff_labels` label or critical risk (ADR-099). While its `specify`
checkpoint has no `waited` outcome:

| What | Refuses with |
|---|---|
| The pre-tool hook, on a code edit | `code-before-approval` |
| `compass tdd-red`, before the test runs. It writes no red record and no `.red` marker. | `scenarios-not-approved` |
| `compass quick-fix finish`, before it writes the record | a `next:` line that names the request |

- A `skipped` outcome does not count.
- The fix is `compass evidence request --checkpoint specify`. The person
  answers with `/compass:approve`.
- An issue that does not owe `scenario-approval` is not refused. `controlled`
  autonomy still waits at specify on every change.
- The request holds `spec` and `spec_sha256`, and Compass shows the person
  the first 12 characters of the digest. When the spec's digest changes after
  the request, the prompt hook refuses to record the answer and closes the
  request as stale.

## The landing refusal

`compass ship-commit` runs an ordered list of landing refusals before it
stages, renders, commits, derives or syncs anything. A refusal leaves every
file as it was.

- The first entry refuses a judged issue that lists a checkpoint with no
  outcome (`checkpoint-no-outcome`). It names each stage and
  `compass evidence request --checkpoint <stage>`, then stops. An agent does
  not approve.
- `compass quick-fix finish` runs the same list, unless `--no-commit` is
  given.
- A new refusal is one more function in `manifest.LANDING_REFUSALS`, with its
  code in `refusals.py`.

### Which issues it judges

A judged issue is one whose manifest holds the `checkpoint_outcomes` key, an
empty list included. The first assessment of every issue writes it. A
reassessment does not add it, and no migration back-fills it.

- An issue that is not judged is never refused. `compass check`, `compass
  issue lint` and `compass ci` raise no finding for it.
- `ship-commit` takes the issue from `--issue`, then `COMPASS_ISSUE`, then
  the current-task pointer. It never guesses the most recently changed issue.

## Where the outcomes are read

- `compass issue diagnose` has a Checkpoints section: each outcome with its
  stage, outcome, by and at, or `no checkpoint outcomes recorded`. Each
  outcome is also an event in its timeline.
- `compass record sync` copies the configured paths. Where `.compass/work`
  is listed, the record holds each manifest with its `checkpoint_outcomes`,
  and the `approver` of every `checkpoint-approval` record.

## What 9.0.0 no longer writes

9.0.0 does not write the manifest's `usage` block or the quick fix's
`started_at`, `finish_started_at` and `committed_at`. The schema still reads
each as valid. The pre-tool hook writes no manifest.
