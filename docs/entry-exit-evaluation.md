# Stage entry and exit lists

This page is the owning doc for the evaluation of a stage's `entry` and `exit`
lists. It states what the capability switches, when a list is due, how each kind of
check is judged, what `on_skipped` does, where the results show, and how the
documents show the lists. The code is `cli/compass_pkg/stage_lists.py`, which
judges a list, `cli/compass_pkg/item_records.py`, which reads the manifest
records that meet an item, `cli/compass_pkg/follow_up_cmd.py`, which records a
follow-up, and `cli/compass_pkg/template_lists.py`, which prints a template.
`compass check`, `compass next` and `compass issue receipt` read the first.

## Switching it on

The capability `entry-exit-evaluation` is off in the shipped default. A
project turns it on in `compass.yml`:

```yaml
capabilities:
  entry-exit-evaluation: true
```

The capability switches the shipped checks. The shipped default lists the seven
Definition of Ready checks as the `plan` entry and the seven Definition of Done
checks as the `verify` exit, and each says `requires: [entry-exit-evaluation]`.
With the capability off those fourteen are inactive, and the output of a
project that has added nothing is the same as before the capability existed.

A check a project adds to a list runs whatever the capability. A project that
wants its own check to wait for the capability writes
`requires: [entry-exit-evaluation]` on it. A list that names a check the
configuration does not define fails with "the check is not defined".

An issue reads the capability from its stored generation (see
`docs/generation-store.md`). Turning it on changes nothing for an issue until
the next `compass approach evaluate --write`.

## When a list is due

`compass next` names the current stage. A list is due by its position:

| List | Due when |
|---|---|
| entry of a stage | the stage is the current stage, or the issue is past it |
| exit of a stage | the issue is past the stage |

A closed issue has every list due, whatever its close reason. `compass check`
counts only due checks. The
receipt shows every list, and says which are not yet due.

## How a check is judged

| Kind | Judged by |
|---|---|
| `human` | A record in the manifest (see [Item records](#item-records)): evidence that meets the check, a person's approval, or a follow-up that carries it to ship. A tick on a page counts for nothing, and the page is never read. With `approvers:` the check needs a current approval by a listed approver (see [Approvers on a human check](#approvers-on-a-human-check)). |
| `deterministic` | Its registered implementation runs. The receipt does not run it and shows `pending`. |
| `judged` | A review record: the newest registered `manual-review` record by a listed reviewer must say `pass` and match the check's inputs, definition, issue and generation. The cause of a failure is the first words of the detail. See [judged-checks.md](judged-checks.md). The receipt reads the record and shows the real verdict. |
| `evidence` | Not evaluated by this version. A blocking check of this kind fails, so a list cannot pass by naming a check nothing reads. This holds whatever the capability, for a check a project adds, and `compass policy lint` warns (`M-LIST-KIND-UNEVALUATED`, exit code unchanged). The shipped default names none. |

A row passes with the record's name in its detail: `met by EV-T`, `ticked by
jed72`, `carried to ship, FU-3`, `met, FU-3 resolved`. An item with no record
fails as `not recorded` and names the commands that record it. `dod-evidence-typed`
reads the same records, so an item has one state whoever asks.

## Item records

An item is a check id in the issue's `verify` exit list (the Definition of
Done) or `plan` entry list (the Definition of Ready), whatever the capability
says: the page shows both lists, and the capability only decides whether the
stage lists run. One of four records meets an item, and a command writes each:

| Record | Written by | The item reads |
|---|---|---|
| `evidence[].meets: [item]` on an entry of an accepted type | `compass gate pass ... --meets ITEM`, `compass evidence add ... --meets ITEM` | `met by EV-id` |
| a `human-approval` record with `check: item` | `compass evidence approve --check ITEM` | `ticked by <approver>` |
| `follow_ups[].defers: item` | `compass follow-up add FU-id --defers ITEM --summary TEXT` | `carried to ship, FU-id`, then `met, FU-id resolved` once `compass follow-up resolve` resolves it |
| a `page_ticks` entry | `compass issue migrate`, from a tick on an archived page | `ticked on the page before 7.0.0` |

An item with none of them is open. `--meets` and `--defers` refuse, with exit 2
and no change, an item the issue does not list, and `--meets` refuses evidence
of a type the lists do not accept. `compass follow-up add` also takes
`--target SLUG`, which blocks that issue's `dod-evidence-typed` while the
follow-up is outstanding.

`compass evidence approve --check` accepts an item whose check lists no
`approvers`. The approver must be a name in an `approvers:` list of the project
file, or the project's owner when it declares none. Only that item reader counts a
page tick: `human-approval-present` and the approval check never do.

Each result goes through the judgement `compass check` gives a gate check, so
one check id has one verdict. A deterministic check that has nothing to inspect
follows its `on_skipped`. A check with `severity: advisory`, or a
`blocking_when` that does not match the issue's assessment, that fails is shown
as ADVISORY (status `advisory` in `--json`, counted in `advisory`, recorded as
`advisory` in `results.yml`) and does not fail the run.

## Approvers on a human check

A `human` check can declare `approvers:`, a list of names. Then evidence or a
deferral alone does not clear it. It also needs a `human-approval` entry in
the issue's evidence registry that:

- names the check (`check: <id>`) and holds a decision, `approved` or
  `rejected`;
- holds `approver`, `role`, `scope` and `timestamp`;
- is by a listed approver (below);
- names this issue (`issue: <slug>`);
- names the issue's current generation (`generation: <n>`; both are none when
  the issue has none, and generation 0 is not none).

A record that fails any of these is set aside, so a record by someone else
cannot clear the check or block it. Of the records that remain, the newest
decides: a later rejection by a listed approver withdraws an approval, and a
later approval restores it. The row fails when no record remains. Its detail
starts with the cause (`no approval record`, `approver not listed`, `approval
is for another issue`, `approval is for another generation`, `approval
withdrawn`), shows the values it read and names the approvers who may approve.

Evidence and a deferral do not excuse a check that lists approvers, so it
needs a current approval. Without `approvers:`, or with an empty list, any
record in [Item records](#item-records) meets it.

Who is listed. `owner` names the project's owner (the `owner:` of
`compass.yml`, the same name waivers use), and names nobody when the project
declares none. Any other entry is read as a person id, a role included, until
roles are resolved. The approver `agent` never matches.

What is not protected. An approver's name is not authenticated, the same limit
as every `human-approval` record. Anyone who can write `manifest.yml`, an
agent included, can add a record that names a listed person. Two guards exist:
`compass evidence approve` needs a terminal and refuses the approver `agent`.
They stop an agent session that calls the verb. They do not stop one that
edits the manifest.

### `compass evidence approve`

```
compass evidence approve (--check ID | --guardrail G5 | --artifact KIND | --decisions
                          | --checkpoint STAGE)
                         --approver NAME --role ROLE [--scope TEXT]
                         [--decision approved|rejected] [--issue SLUG]
```

| Option | Meaning |
|---|---|
| `--check` | The id of a human check that lists approvers |
| `--guardrail` | `G5`: sign off guardrail `G5`, the only guardrail with a sign-off (below) |
| `--artifact` | The kind of a document that reads `awaiting-approval` (below) |
| `--decisions` | Confirm the decisions an agent took for the person |
| `--checkpoint` | Answer the hand-off of a checkpoint stage: `assess`, `define`, `refine` or `plan` (below) |
| `--approver` | The person's id. It must be listed by the check |
| `--role` | The role the person acts in |
| `--scope` | What the approval covers. Required with `--check` and `--guardrail`; with `--checkpoint` it defaults to `the <stage> hand-off` |
| `--decision` | `approved` (the default) or `rejected` |

Exactly one of `--check`, `--guardrail`, `--artifact`, `--decisions` and
`--checkpoint` is given. The terminal requirement and the refusal of the
approver `agent` apply to all five. The rest of this section describes
`--check`.

Every path that records an approval writes it through one function,
`approvals.record` (`cli/compass_pkg/approvals.py`): this command, and in
Claude Code the hook that records a typed `/compass:approve`. A record
from this command also holds `via: terminal`. No verdict reads `via`, and a
record without it still counts.

The command stamps the issue, the issue's generation and the time, and
registers the record as `EV-APPROVAL-<check>-<n>`. It exits 0 when it wrote the
record and 2 when it did not. In the second case it writes nothing. It exits 2
for:

- no terminal on standard input, because an approval is a person's act and an
  agent session has no terminal; the refusal tells an agent to ask with
  `compass evidence request`;
- the approver `agent` (or `agent:<id>`), or an empty approver, role or scope;
- a check that does not exist, is not `human`, or lists no approvers and is not
  an item of the Definition of Ready or Done;
- an approver the check does not list, because the record would not count;
- a decision other than `approved` or `rejected`.

#### Approving a document: `--artifact`

A stage command moves a document with a human check to `awaiting-approval`
when the stage after it records its work (see ADR-050). `compass evidence
approve --artifact <kind>` approves it. The command refuses, with exit 2 and
no change, when:

- the entry does not read `awaiting-approval`, naming the status it reads;
- a human check on the document lists approvers and the approver is not one of
  them. A human check with no `approvers:` takes any person other than
  `agent`;
- the decision is `rejected`. Send a document back with `compass issue
  artifact set <kind> --status draft`.

It writes one record of the type `artifact-approval` for each human check on
the document, as `EV-APPROVAL-ARTIFACT-<kind>-<n>`, each holding `artifact`,
`check`, `approver`, `role`, `decision`, `timestamp`, `issue` and `generation`
(and `scope` when it is given). A document set to `awaiting-approval` by hand
with no human check gets one record with no `check`. It then sets the
entry's `approved_by` to the person and `approved_at` to the record's time.

An `artifact-approval` record meets the human check it names, under every rule
above except that it needs no `scope`. It is read nowhere else:
`human-approval-present`, the check of guardrail `G5`, reads only
`human-approval` records, and a waiver's approval needs one too. A document
approval therefore never clears a sign-off.

`compass issue artifact set <kind> --status approved` refuses a document with
a human check and names this command. For a document with none it stays
allowed and records `approved_by: compass issue artifact set`.

#### Confirming decisions: `--decisions`

An agent that resolves a requirement question for the person records the
decision in the manifest's `decisions_taken` (ADR-050). `compass evidence
approve --decisions` confirms them as one set.

- **Which decisions.** At a checkpoint (`compass next` reports `Waiting at the
  <stage> checkpoint`), every unconfirmed decision taken at that stage or
  earlier. Away from a checkpoint, every unconfirmed decision.
- **Who may confirm.** A name in any `approvers:` list of the project file, with
  `owner` read as the project's owner. When the project file declares no
  `approvers:`, only its `owner` may confirm.
- **What it writes.** One record of the type `artifact-approval`, as
  `EV-APPROVAL-DECISIONS-<n>`, holding `decisions` (the ids), `stage`,
  `approver`, `role`, `decision`, `timestamp`, `issue` and `generation` (and
  `scope` when it is given). It sets each decision to `confirmed`. Like a
  document approval, it is never a `human-approval` record and never clears a
  sign-off.
- **When it refuses.** It exits 2 with no change when the approver is not
  allowed, when nothing is unconfirmed, or when the decision is `rejected`.
  Send a decision back with `compass issue decision set <id> --status reopened
  --reason "<why>"`, which needs a terminal and accepts no other status.

#### Answering a checkpoint: `--checkpoint`

A checkpoint is a stage hand-off that can wait for a person: `assess`,
`define`, `refine` or `plan`. `compass evidence approve --checkpoint <stage>`
records a person's answer to one. ADR-063 owns the decision.

- **What it writes.** One record of the type `checkpoint-approval`, as
  `EV-CHECKPOINT-<stage>-<n>`, holding `checkpoint` (the stage), `approver`,
  `role`, `scope`, `decision: approved`, `timestamp`, `issue` and
  `generation`. The record has no `check` key. It also sets the stage's entry
  in the manifest's `checkpoint_outcomes` to `{stage, outcome: waited, by, at,
  evidence}`, where `by` is the approver, `at` the record's timestamp and
  `evidence` the record's id. The entry replaces a `skipped` outcome an agent
  recorded with `compass issue checkpoint add`. A second answer for the same
  stage writes a new record and the outcome then cites it; both records stay.
- **Who may answer.** A name in any `approvers:` list of the project file, with
  `owner` read as the project's owner; when the file declares no `approvers:`,
  only its `owner`. When the project declares neither, any name that is not an
  agent is accepted, and the command prints one line saying so.
- **When it refuses.** It exits 2 with no change for an issue whose manifest
  holds no `checkpoint_outcomes` key (it was assessed before outcomes were
  recorded, so it is not judged), a stage that is not a checkpoint stage, a
  stage the approach collapses or skips, a stage whose own record is not written
  yet (`compass next` does not count it done), the decision `rejected`, and a
  name that may not answer.
- **What it never clears.** No check reads `checkpoint-approval`:
  `human-approval-present`, the check of guardrail `G5`, reads only
  `human-approval`, a human check reads `human-approval` and
  `artifact-approval`, and a waiver's approval needs `human-approval`. Answering
  a hand-off is therefore never the sign-off on an irreversible change.
  `compass evidence add --type checkpoint-approval` is refused, so the type is
  written only by this command.

#### Signing off guardrail `G5`: `--guardrail`

`human-approval-present`, the check of guardrail `G5`, counts only a
`human-approval` record given for guardrail `G5` (ADR-066). A record names
its subject: one that holds a `check`, `waiver`, `checkpoint`, `artifact` or
`decisions` key, whatever the value, was given for that subject and is set
aside. So is one whose `guardrail` is anything but the exact string `G5`. A
record with none of these keys counts, which is the form every earlier
sign-off uses. `approval_records.SUBJECT_KEYS` holds the keys and
`approval_records.gives_g5` applies the rule; the check and this command both
import them.

A person records the sign-off with this command:

```
compass evidence approve --guardrail G5 --approver <name> --role <role> --scope <text>
```

- **What it writes.** One `human-approval` record, numbered in sequence,
  whose `guardrail` key holds `G5`, with `approver`, `role`, `scope`,
  `decision: approved`, `timestamp`, `issue` and `generation`, and no `check` key. No human check,
  item or waiver reads it, because each of those readers matches on `check`
  or `waiver`.
- **Who may sign off.** Any person who is not an agent: guardrail `G5` lists
  no approvers.
- **When it refuses.** It exits 2 with no change for a value other than `G5`,
  the decision `rejected` (a rejected record would not withdraw an earlier
  sign-off), an empty scope, a second form, the approver `agent` and no
  terminal.
- **What the check reports.** It cites the first approved record that counts.
  When none counts, it names the first record set aside and the subject it
  was given for, and names this command. On a landed issue that the earlier
  rule passes (the first approved `human-approval` record, whatever it names,
  holds all four fields) the check passes and says it is reported only.

The `--json` document of `--check` is a public contract. A change to a key or its order is
a breaking change. This is the real output for the example above; `at` varies
and is shown as `...`. The key `answer` holds the decision.

```json
{
  "outcome": "compass evidence approve: sign-off - approved by jed72 recorded as EV-APPROVAL-sign-off-1.",
  "check": "sign-off",
  "answer": "approved",
  "evidence_id": "EV-APPROVAL-sign-off-1",
  "approver": "jed72",
  "role": "owner",
  "scope": "the plan",
  "issue": "feature",
  "generation": 1,
  "at": "...",
  "detail": [
    "record     : EV-APPROVAL-sign-off-1 in manifest.yml evidence",
    "issue      : feature",
    "generation : 1"
  ]
}
```

### Approving in Claude Code, and delegated approvals

In Claude Code a person answers a request by typing `/compass:approve [n]` or
`/compass:reject [n] <reason>`. The `UserPromptExpansion` hook
(`hooks/prompt-approval.sh`, `cli/compass_pkg/prompt_approval.py`) records
the answer through `approvals.record`, with `via: prompt`, the session id,
the prompt id, the request number and its nonce. It records only one pending
request of the session's issue that Compass has shown and that has not
changed since, and blocks with the reason otherwise. A rejected check gets a
`rejected` record; a rejected document returns to draft and stays there while
its file is unchanged; a rejected guardrail 5, checkpoint or decisions request
writes no record.

A person can let agents approve for them with `/compass:delegate [--agent <name>]
[--until <time>] [--on <issues>] [--for <forms>] [--max <n>]`
(`cli/compass_pkg/delegations.py`, ADR-069 as amended by ADR-077). Every flag
is optional and the flags come in any order; `delegations.parse_flags` reads
them. The old positional form and `--labels` are refused with the flag form.
The person sets the bounds, and no limit is put on how long a delegation lasts
or on how many are in force:

- with no `--agent`, the file names the session (`covers_session`) and covers its
  main agent and its subagents; with `--agent <name>` it covers that agent in
  any session, and `any` is refused;
- with no `--until`, it lasts until `/compass:revoke`;
- with no `--on`, it covers every issue in the repository's worktrees at any
  generation; `--on` looks each issue up in every worktree
  (`cli/compass_pkg/worktree_lookup.py`) and refuses a name that no worktree
  holds, or that two hold;
- a new file has `format: 2`; a file with no `format` is read by the 7.0.0 rules;
- the file is kept in the common store, `.compass/delegations/` in the main
  checkout, which every worktree reads. `/compass:delegate` and `/compass:revoke`
  take the approver from the folder that holds it and need no current issue.

`g5` is covered only with `--for g5`, after the person types back a code the
hook shows them. The code is
16 hex characters in four groups, such as `1a2b-3c4d-5e6f-7a8b`, typed with
or without the hyphens. A `/compass:approve`, `/compass:reject` or
`/compass:delegate` whose input has no prompt id is refused, and so is a
`/compass:delegate` whose prompt id a delegation already holds; a confirmed
g5 delegation keeps the first command's prompt id as `requested_prompt_id`.
`/compass:revoke [DL-n]` ends delegations early and names what each covered.
The agent records with:

```
compass evidence approve (--check ID | --guardrail G5 | --artifact KIND | --decisions
                          | --checkpoint STAGE) [--scope TEXT] --issue SLUG --delegated --as AGENT
```

It needs no terminal and no `--approver` or `--role`: the record names the
person who delegated as `approver`, with `approved_by_agent`, `delegation` and
`via: delegation`, and a line goes to the issue's devlog. The command must be
a plain command that the pre-tool hook reads. The hook writes a call ticket into
the common store (`cli/compass_pkg/delegation_tickets.py`): the session and the
caller that Claude Code reported, and a digest of the words after `evidence
approve`. The CLI takes the matching ticket under the store lock and reads the
session from it, never from the environment. The verb refuses, writing
nothing, when it has no ticket, no `--issue`, or an issue that two worktrees
hold; or when no delegation in force names the agent or covers its session, or
the one that does has ended, was revoked, reached its `max`, was not written by
a typed command, or does not cover the issue, its generation, the form or the
labels of a 7.0.0 file. A delegation file in a linked worktree's own folder
gives no approval, and the refusal names it. The
pre-tool hook also refuses the call when `--as` is not exactly the agent
Claude Code reports.

The person sees each delegated approval, from any worktree, in a summary until
they mark it reviewed. Each delegation file indexes its records
(`records`), so the summary reads only the issue folders that hold one. Both
summary hooks write the rows they show into the store's
`shown/<session>.json`. `/compass:approve` with nothing pending marks reviewed
only the approvals the session was shown: the rows of the latest summary shown
in the same session before the command, whose digest still matches. A summary
shown for the `/compass:approve` prompt itself does not count. The prompt hook
takes the approval lock of each shown issue, with the session's own, in one
sorted order before it marks anything (`approvals.lock_all`). So two sessions
that type it on two issues at once never each hold one lock while waiting for
the other's. An approval recorded after the summary stays unmarked and appears
in the next summary.

`/compass:approve <n>` and `/compass:reject <n> <reason>` search the current
issue of each worktree for pending request n, and `--issue <slug>` reaches any
issue in any worktree. With more than one match they refuse and list the
`--issue` forms. The approver is read from the folder that holds the chosen
request, after the choice. Session start lists each delegation with no end time
(`delegations.session_start_lines`).

### `compass evidence request`

An agent asks a person for an approval with this command. It never records
one.

```
compass evidence request (--check ID | --guardrail G5 | --artifact KIND | --decisions
                          | --checkpoint STAGE) [--scope TEXT] [--issue SLUG]
```

- **What it writes.** One file,
  `.compass/work/<slug>/approval-requests/pending/<n>.yml`, with facts the
  command derives (issue, generation, labels, subject, and a document's
  digest), the agent's `--scope`, the time and a single-use `nonce`. A
  pending request for the same subject closes as `replaced`. A request is not
  evidence, and no check reads it. The code is
  `cli/compass_pkg/approval_requests.py`.
- **When it refuses.** It runs every refusal `compass evidence approve` gives
  for the subject, with the same words, except those that depend on who
  answers. It exits 2 and writes nothing.
- **What it prints.** The line to say to the person: type `/compass:approve`
  or `/compass:reject`. Where an adapter sets
  `COMPASS_APPROVAL_CHANNEL=terminal`, because its host has no event only a
  person can raise, it prints the exact `compass evidence approve` command
  for the person's own terminal instead.

## When a list is skipped, and `on_skipped`

A skipped check does not run. It gives the verdict its `on_skipped` names:

| `on_skipped` | Verdict |
|---|---|
| `fail` | fail |
| `not-applicable` | nothing to check |
| `pass` | pass |

A check is skipped in two cases:

- For a `human` check, the stage that produces its document is `skipped` or
  `collapsed`, or the document is recorded as deliberately omitted. That stage
  is the one before the listed stage for an entry list (refine, for the
  `plan` entry) and the listed stage for an exit list. This is why a collapsed
  refine makes the Definition of Ready not applicable.
- For any other kind, the listed stage is `skipped` or `collapsed`.

`on_skipped` answers "the stage was skipped". It does not say that a list does
not apply to an approach. A list does not depend on the stage's mode.

A third case is not a skip. When a `human` check's document is missing and the
approach the issue was given does not list that document kind among its
artifacts, the approach owes no such document, and the row is nothing to check,
for example "quick-fix owes no verification-report". The artifact set is read
from the configuration, so a project that adds `verification-report` to an
approach makes the Definition of Done owed there. The shipped regular approach
lists `requirements-review` from 7.0.0, so with this capability on, a regular
issue assessed from 7.0.0 owes the seven Definition of Ready records at plan
entry. An issue assessed earlier keeps its stored generation, which does not
list the kind, so it has nothing to check for the Definition of Ready.

## A check that an approach does not owe

A `when` on a check reads the assessment. Evaluation adds one derived key,
`ships`, whether the approach the issue was given ships. Each Definition of
Done check in the shipped default says `when: {ships: true}`, so a spike, which
does not ship, owes none of them and a delivery owes all seven. A project can
use `ships` in the `when` or `blocking_when` of its own checks and in the
`when` of a guardrail gate. The key adds no field to the
configuration, so the classifier compares it as it compares any `when`.

## Where results show

`compass check` adds one result for each due check, under a guardrail labelled
`stage:<stage>:<entry|exit>`. The results count in `ran`, `failed` and
`nothing_to_check` like any other, and a failure fails the run. In `--json`, a
row of `checks` has the same four keys as every other row: `guardrail`,
`name`, `status` (`pass`, `fail` or `nothing-to-check`) and `detail`. No key
is added to the output.

`compass next` appends `entry not met: <check ids>` to its line when the
current stage has failing entry checks.

`compass issue receipt` adds a "Stage lists" section before the verdict. Each
list is headed with its stage, its side and whether it is due. Each check shows
its id, its state (`pass`, `fail`, `nothing-to-check` or `pending`) and its
detail.

## Where a list shows in a document

The requirements review shows the plan entry list and the verification report
shows the `verify` exit list, each as a rendered block that `compass issue render`
writes from the issue's configured list (`docs/rendered-blocks.md`):

| List | Block | Under the heading |
|---|---|---|
| `plan` entry | `dor` | `Definition of Ready` |
| `verify` exit | `dod` | `Definition of Done` |

The first line of a block reads `Definition of Done: 5 of 7 met, 2 carried to
ship (FU-3, FU-4)`, then one line gives each item's statement and its state.
A tick written on the page counts for nothing. A list on another stage has no
block yet; its checks are judged from the same records and are not written into
a document.

## Printing a template

`compass issue template show <kind> [--depth D] [--issue SLUG] [--json]` prints
the skeleton of that kind, which [the artifact catalogue](artifact-catalog.md)
describes. The requirements review and the verification report hold an empty
rendered block for each list, and the skeleton keeps each block marker as the
template holds it: the blocks fill when the document is registered and
`compass issue render` runs. `/compass:refine` and `/compass:verify` write
their documents from this output. `--json` prints one object with the keys
`kind`, `issue`, `depth`, `source` and `text`. `source` is `generation`, `live`
or `none`.

## Limits

- A role in `approvers:` other than `owner` is read as a person id. An
  approval record is not authenticated (see [Approvers on a human
  check](#approvers-on-a-human-check)).
- `evidence` checks are not evaluated.
- A list on a stage other than `plan` and `verify` is judged from the records but
  has no block in a document.
