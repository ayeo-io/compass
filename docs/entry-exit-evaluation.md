# Stage entry and exit lists

The owning doc for the evaluation of a stage's `entry` and `exit` lists, and
for the commands that record and ask for a person's approval. Code:
`cli/compass_pkg/stage_lists.py` (judges a list),
`cli/compass_pkg/item_records.py` (reads the records that meet an item) and
`cli/compass_pkg/follow_up_cmd.py` (records a follow-up). `compass check` and
`compass next` read the lists.

## Switching it on

The capability `entry-exit-evaluation` is off by default. A project turns it
on in `compass.yml`:

```yaml
capabilities:
  entry-exit-evaluation: true
```

- The shipped Definition of Done checks each say
  `requires: [entry-exit-evaluation]`. With the capability off they are
  inactive.
- A check a project adds to a list runs whatever the capability, unless it
  says `requires: [entry-exit-evaluation]`.
- A list that names a check the configuration does not define fails with
  "the check is not defined".
- An issue reads the capability from its stored generation
  (`docs/generation-store.md`). Turning it on changes nothing for an issue
  until the next `compass approach evaluate --write`.

## When a list is due

`compass next` names the current stage.

| List | Due when |
|---|---|
| entry of a stage | the stage is the current stage, or the issue is past it |
| exit of a stage | the issue is past the stage |

A closed issue has every list due, whatever its close reason. `compass check`
counts only due checks.

## A path issue

A path issue is one whose manifest records `evidence_required` (ADR-092). It
runs assess, specify, build and ship, and none of its lists is skipped.
`stage_lists.path_lists` gives it its lists:

- A configuration that declares the four path stages is read as it stands.
  The build exit list is the Definition of Done. The ship entry list holds a
  check such as `agent-review`.
- A configuration that declares the legacy stages, as a stored 8.x generation
  does, has each list moved: define, refine and plan to specify; breakdown
  and implement to build; `verify` and ship to ship. The `verify` exit list,
  the Definition of Done, moves to the build exit.
- A path issue owes no Definition of Ready, so no `dor-*` check is listed.
- It owes the Definition of Done only when its `evidence_required` lists
  `definition-of-done`. Otherwise each Definition of Done row is nothing to
  check.
- The rows carry the path stage, such as `stage:build:exit`.

An issue assessed before 9.0.0 keeps its legacy lists, labels and modes.

## How a check is judged

| Kind | Judged by |
|---|---|
| `human` | A record in the manifest (see [Item records](#item-records)). A tick on a page counts for nothing, and the page is never read. With `approvers:` the check needs a current approval by a listed approver (see [Approvers on a human check](#approvers-on-a-human-check)). |
| `deterministic` | Its registered implementation runs. |
| `judged` | A review record: the newest registered `manual-review` record by a listed reviewer must say `pass` and match the check's inputs, definition, issue and generation. See [judged-checks.md](judged-checks.md). |
| `evidence` | Not evaluated. A blocking check of this kind fails, whatever the capability. The shipped default names none. |

- A row that passes names the record in its detail: `met by EV-T`, `ticked
  by jed72`, `carried to ship, FU-3`, `met, FU-3 resolved`.
- An item with no record fails as `not recorded` and names the commands that
  record it. `dod-evidence-typed` reads the same records.
- Each result gets the judgement `compass check` gives a gate check. A
  failing check with `severity: advisory`, or with a `blocking_when` that
  does not match the assessment, shows as ADVISORY and does not fail the
  run. In `--json` its status is `advisory`, and `results.yml` records
  `advisory`.

## Item records

An item is a check id in the issue's Definition of Done (the build exit
list, or the `verify` exit list of a configuration with a `verify` stage) or
its Definition of Ready (the `plan` entry list), whatever the capability. A
path issue has only the Definition of Done. A command refuses to record a
`dor-*` item or a `plan` or `breakdown` exit item for it.

| Record | Written by | The item reads |
|---|---|---|
| `evidence[].meets: [item]` on an entry of an accepted type | `compass gate pass ... --meets ITEM`, `compass evidence add ... --meets ITEM` | `met by EV-id` |
| a `human-approval` record with `check: item` | `compass evidence approve --check ITEM` | `ticked by <approver>` |
| `follow_ups[].defers: item` with `github: {repo, number}`, on a path issue | `compass follow-up add FU-id --defers ITEM --github owner/repo#N --summary TEXT` | `carried to a GitHub issue, FU-id`, whether or not it is resolved |
| `follow_ups[].defers: item`, on an issue assessed before 9.0.0 | `compass follow-up add FU-id --defers ITEM --summary TEXT` | `carried to ship, FU-id`, then `met, FU-id resolved` once `compass follow-up resolve` resolves it |
| a `page_ticks` entry | `compass issue migrate`, from a tick on an archived page | `ticked on the page before 7.0.0` |

An item with none of them is open. With exit 2 and no change:

- `--meets` and `--defers` refuse an item the issue does not list;
- `--meets` refuses evidence of a type the lists do not accept.

On a path issue only a follow-up that links to a GitHub issue meets an open
Definition of Done item (ADR-093):

- `compass follow-up add` refuses, with exit 2 and no change, a follow-up
  with no `--github`, and a `--defers` item that is not in the build exit
  list.
- `--github` takes `owner/repo#N` or the issue's URL. Nothing is written to
  GitHub.
- A follow-up with no `github` field meets nothing.
- The check that every follow-up is resolved has nothing to check.

On an issue assessed before 9.0.0:

- an outstanding follow-up fails `compass check` until `compass follow-up
  resolve` resolves it;
- a `target_task` entry blocks `dod-evidence-typed` while it is outstanding.
  `--target` is removed and fails to parse with a line that names ADR-093.

`compass evidence approve --check` accepts an item whose check lists no
`approvers`. The approver must be a name in an `approvers:` list of the
project file, or the project's owner when it declares none. Only the item
reader counts a page tick: `human-approval-present` never does.

## Approvers on a human check

A `human` check can declare `approvers:`, a list of names. Then evidence or
a deferral does not clear it. It needs a `human-approval` entry in the
issue's evidence registry that:

- names the check (`check: <id>`) and holds a decision, `approved` or
  `rejected`;
- holds `approver`, `role`, `scope` and `timestamp`;
- is by a listed approver;
- names this issue (`issue: <slug>`);
- names the issue's current generation (`generation: <n>`; both are none
  when the issue has none, and generation 0 is not none).

A record that fails any of these is set aside. Of the rest, the newest
decides: a later rejection by a listed approver withdraws an approval, and a
later approval restores it. The row fails when no record remains. Its detail
starts with the cause: `no approval record`, `approver not listed`,
`approval is for another issue`, `approval is for another generation` or
`approval withdrawn`. It also shows the values read and who may approve.

Without `approvers:`, or with an empty list, any record in
[Item records](#item-records) meets the check.

**Who is listed.**

- `owner` names the project's owner (the `owner:` of `compass.yml`), and
  nobody when the project declares none.
- A `compass.yml` with a settings lint error names no owner, and
  `/compass:approve` names the error.
- Any other entry is read as a person id, a role included.
- The approver `agent` never matches.

**What is not protected.** An approver's name is not authenticated. Anyone
who can write `manifest.yml`, an agent included, can add a record that names
a listed person. `compass evidence approve` needs a terminal and refuses the
approver `agent`. That stops an agent session that calls the command, not
one that edits the manifest.

### `compass evidence approve`

```
compass evidence approve (--check ID | --guardrail G5 | --decisions
                          | --checkpoint STAGE | --waiver W-N | --ship)
                         --approver NAME --role ROLE [--scope TEXT]
                         [--decision approved|rejected] [--issue SLUG]
```

| Option | Meaning |
|---|---|
| `--check` | The id of a human check that lists approvers |
| `--guardrail` | `G5`: sign off guardrail `G5`, the only guardrail with a sign-off |
| `--decisions` | Confirm the decisions an agent took for the person |
| `--checkpoint` | Answer the hand-off of a checkpoint stage: a path stage on a path issue, a legacy stage such as `define` on an older one |
| `--waiver` | Approve one waiver of the issue |
| `--ship` | Approve the change of the issue at ship |
| `--approver` | The person's id. It must be listed by the check |
| `--role` | The role the person acts in |
| `--scope` | What the approval covers. Required with `--check` and `--guardrail`; with `--checkpoint` it defaults to `the <stage> hand-off` |
| `--decision` | `approved` (the default) or `rejected` |

Exactly one form is given. Every form needs a terminal and refuses the
approver `agent`. Every approval is written by one function,
`approvals.record` (`cli/compass_pkg/approvals.py`). A record from this
command holds `via: terminal`. No verdict reads `via`.

With `--check`, the command stamps the issue, its generation and the time,
and registers the record as `EV-APPROVAL-<check>-<n>`. It exits 0 when it
wrote the record. It exits 2 and writes nothing for:

- no terminal on standard input. The refusal tells an agent to ask with
  `compass evidence request`;
- the approver `agent` (or `agent:<id>`), or an empty approver, role or scope;
- a check that does not exist, is not `human`, or lists no approvers and is not
  an item of the Definition of Ready or Done;
- an approver the check does not list;
- a decision other than `approved` or `rejected`.

The `--json` document of `--check` is a public contract: a change to a key or
its order is a breaking change. `at` varies and is shown as `...`. The key
`answer` holds the decision.

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

#### Approving a document: `--artifact` (removed in 9.0.0)

9.0.0 keeps no document status (ADR-091), so `--artifact` is removed from
`compass evidence approve` and `compass evidence request`. A pending request
for a document closes with nothing written. An `artifact-approval` record an
older issue holds stays valid: it meets the human check it names.

#### Confirming decisions: `--decisions`

An agent that resolves a requirement question for the person records the
decision in the manifest's `decisions_taken` (ADR-050). `compass evidence
approve --decisions` confirms them as one set.

- **Which decisions.** At a checkpoint (`compass next` reports `Waiting at the
  <stage> checkpoint`), every unconfirmed decision taken at that stage or
  earlier. Away from a checkpoint, every unconfirmed decision. On a path
  issue a decision taken at a legacy stage counts at the path stage that
  shows it, such as refine at specify.
- **Who may confirm.** A name in any `approvers:` list of the project file,
  with `owner` read as the project's owner. With no `approvers:`, only the
  `owner`.
- **What it writes.** One `artifact-approval` record,
  `EV-APPROVAL-DECISIONS-<n>`, with `decisions` (the ids), `stage`,
  `approver`, `role`, `decision`, `timestamp`, `issue` and `generation`, and
  `scope` when given. It sets each decision to `confirmed`. It never clears
  a sign-off.
- **When it refuses.** Exit 2 with no change when the approver is not
  allowed, when nothing is unconfirmed, or when the decision is `rejected`.
  Send a decision back with `compass issue decision set <id> --status
  reopened --reason "<why>"`, which needs a terminal.

#### Answering a checkpoint: `--checkpoint`

`compass evidence approve --checkpoint <stage>` records a person's answer to
a stage hand-off. `docs/checkpoints.md` owns it: the stages, the
`checkpoint-approval` record, who may answer and when the command refuses
(ADR-063, ADR-095). No check reads `checkpoint-approval`, so an answer is
never the sign-off on an irreversible change.

#### Signing off guardrail `G5`: `--guardrail`

`human-approval-present`, the check of guardrail `G5`, counts only a
`human-approval` record given for guardrail `G5` (ADR-066):

- A record that holds a `check`, `waiver`, `checkpoint`, `artifact`,
  `decisions` or `ship` key, whatever the value, was given for that subject
  and is set aside (`approval_records.SUBJECT_KEYS`).
- A record whose `guardrail` is anything but the exact string `G5` is set
  aside.
- A record with none of these keys counts (`approval_records.gives_g5`).

A person records the sign-off with:

```
compass evidence approve --guardrail G5 --approver <name> --role <role> --scope <text>
```

- **What it writes.** One `human-approval` record whose `guardrail` key
  holds `G5`, with `approver`, `role`, `scope`, `decision: approved`,
  `timestamp`, `issue` and `generation`, and no `check` key. No human check,
  item or waiver reads it.
- **Who may sign off.** Any person who is not an agent. Guardrail `G5` lists
  no approvers.
- **When it refuses.** Exit 2 with no change for a value other than `G5`,
  the decision `rejected`, an empty scope, a second form, the approver
  `agent` and no terminal.
- **What the check reports.** It cites the first approved record that
  counts. When none counts, it names the first record set aside, its
  subject and this command. On a landed issue that passed the earlier rule,
  the check passes and says it is reported only.

#### Approving a waiver: `--waiver`

`compass evidence approve --waiver W-<n>` approves one waiver of the issue
(`cli/compass_pkg/waiver_records.py`, ADR-094). `docs/waivers.md` owns the
record and what `compass check` shows. The record counts only at the
generation it holds, and never clears guardrail `G5`. The command refuses:

- a withdrawn waiver, or one already approved;
- a waiver with no reason;
- a waiver of a check the check set never waives;
- `--decision rejected`;
- a name that is not in `approvers.waiver` (else the project's owner).

#### The typed ship approval: `--ship`

`compass evidence approve --ship` approves the change of the issue at ship.
It is for an issue that owes `ship-approval` and whose merged pull request
has no approving review by a person other than its author, such as a project
not on GitHub or with one person.

- **What it writes.** One `human-approval` record with `ship: <slug>`,
  `head` (the `HEAD` commit, or none outside git), `approver`, `role`,
  `scope`, `decision: approved`, `timestamp`, `issue` and `generation`.
  `ship-approval-present` (`cli/compass_pkg/ship_approval.py`) counts it at
  the generation it holds while no `approval-withdrawal` names it. It never
  clears guardrail `G5` (ADR-095).
- **Who may approve.** A name in any `approvers:` list of `compass.yml`, else
  the project's owner. Any person who is not an agent when the project
  declares neither.
- **When it refuses.** An issue whose `evidence_required` does not list
  `ship-approval`, a second approval while one stands, `--decision
  rejected`, the approver `agent` and no terminal.
- **The other paths.** The agent asks with `compass evidence request --ship`
  and the person types `/compass:approve <n>`. An agent records it under a
  delegation only when the person typed `--for ship` and the code.
  `/compass:reject <record id>` withdraws a delegated one.

### Approving in Claude Code, and delegated approvals

A person answers a request by typing `/compass:approve [n]` or
`/compass:reject [n] <reason>`. The `UserPromptExpansion` hook
(`hooks/prompt-approval.sh`, `cli/compass_pkg/prompt_approval.py`) records
the answer through `approvals.record`, with `via: prompt`, the session id,
the prompt id, the request number and its nonce.

- It records only a pending request of the session's issue that Compass has
  shown and that has not changed since. Otherwise it blocks and gives the
  reason.
- `/compass:approve waiver W-<n>` answers the pending request for that
  waiver, only while the waiver names the check and reason the request
  showed.
- A rejected check gets a `rejected` record. A rejected guardrail 5,
  checkpoint or decisions request writes no record.
- `/compass:approve <n>` and `/compass:reject <n> <reason>` search the
  current issue of each worktree for pending request n. `--issue <slug>`
  reaches any issue in any worktree. With more than one match, they refuse
  and list the `--issue` forms.
- When two worktrees hold the slug named after `--issue`, the copy in the
  worktree the person types in wins. Typed in a worktree that holds no
  copy, the command is refused
  (`governance/decisions/2026-10-29-a-persons-approval-takes-the-issue-in-its-own-worktree.md`).
  The approver is read from the folder that holds the chosen request.

#### Delegating

A person lets agents approve for them with `/compass:delegate [--agent <name>]
[--until <time>] [--on <issues>] [--for <forms>] [--max <n>]`
(ADR-069 as amended by ADR-077). Code: `cli/compass_pkg/delegations.py`,
`cli/compass_pkg/worktree_lookup.py` and
`cli/compass_pkg/delegation_tickets.py`. Every flag
is optional, in any order. The old positional form and `--labels` are
refused. Compass sets no limit on how long a delegation lasts or on how many
are in force.

| Flag | Without it | With it |
|---|---|---|
| `--agent` | Covers the session's main agent and its subagents (`covers_session`) | Covers that agent in any session. `any` is refused |
| `--until` | Lasts until `/compass:revoke` | Ends at that time |
| `--on` | Covers every issue in the repository's worktrees, at any generation | Covers the named issues. A name that no worktree holds, or that two hold, is refused |
| `--for` | Covers `checks`, `documents`, `checkpoints` and `decisions` | Covers the named forms. `g5`, `waivers` or `ship` is covered only when named here, after the person types back a code the hook shows |
| `--max` | No limit on the number of approvals | A whole number of approvals, at least 1 |

- The code is 16 hex characters in four groups, such as
  `1a2b-3c4d-5e6f-7a8b`, typed with or without the hyphens.
- The file is kept in `.compass/delegations/` in the main checkout, which
  every worktree reads. A delegation file in a linked worktree's own folder
  gives no approval, and the refusal names it.
- A new file has `format: 2`. A file with no `format` is read by the 7.0.0
  rules.
- `/compass:delegate` and `/compass:revoke` need no current issue.
- A `/compass:approve`, `/compass:reject` or `/compass:delegate` whose input
  has no prompt id is refused. So is a `/compass:delegate` whose prompt id a
  delegation already holds. A confirmed g5 delegation keeps the first
  command's prompt id as `requested_prompt_id`.
- `/compass:revoke [DL-n]` ends delegations early and names what each
  covered.
- The session-start hook lists each delegation with no end time on a new
  session, after `/clear` and after compaction, but not on a resumed
  session.

The agent records with:

```
compass evidence approve (--check ID | --guardrail G5 | --decisions
                          | --checkpoint STAGE | --waiver W-N | --ship)
                         [--scope TEXT] --issue SLUG --delegated --as AGENT
```

It needs no terminal, `--approver` or `--role`. The record names the person
who delegated as `approver`, with `approved_by_agent`, `delegation` and
`via: delegation`. The issue's devlog gets no line.

The manifest's `delegations_used:` gets a copy of the delegation under its
id, in the same save (ADR-095 decision 12):

- The copy keeps who delegated, to whom, until when, for which issues and
  forms, and how it was typed, with the `sha256` of those fields.
- It leaves out the nonce, the use count, the index of other issues' records
  and the session ids. `covers_session` is kept as `true`.
- A second use of the same delegation adds nothing. A delegation whose kept
  fields changed is added again, as `DL-1@2`. A revocation does not change
  the copy.

The command must be a plain command that the pre-tool hook reads. The hook
writes a call ticket into the common store:

- The ticket holds the session and the caller that Claude Code reported, and
  a digest of the words after `evidence approve`, cut at the first shell
  operator, comment or redirect.
- The hook writes one only when `compass` stands in command position, never
  as an argument of `echo`, `printf` or `xargs`.
- The CLI reads the session from the ticket, never from the environment.
- A ticket is deleted when its call finishes, fails or has its permission
  denied (the post-tool hook, on `PostToolUse`, `PostToolUseFailure` and
  `PermissionDenied`). Every unused ticket of a session is deleted at its Stop and at its
  next prompt. An untaken ticket expires after 10 minutes.

The command refuses, and writes nothing, when:

- it has no ticket, no `--issue`, or an issue that two worktrees hold;
- no delegation in force names the agent or covers its session;
- the delegation has ended, was revoked, reached its `max`, or was not
  written by a typed command;
- the delegation does not cover the issue, its generation, the form, or the
  labels of a 7.0.0 file;
- `--as` is not exactly the agent Claude Code reports (the pre-tool hook
  refuses).

The refusal tells the agent to ask with `compass evidence request` and stop.

#### Reviewing delegated approvals

The person sees each delegated approval, from any worktree, in a summary
until they mark it reviewed. `/compass:approve` with nothing pending marks
reviewed only the approvals the session was shown: the rows of the latest
summary shown in the same session before the command, whose digest still
matches. A summary shown for the `/compass:approve` prompt itself does not
count. An approval recorded after the summary stays unmarked and appears in
the next summary.

- Each delegation file indexes its records (`records`), so the summary reads
  only the issue folders that hold one.
- The summary hooks write the rows they show into the store's
  `shown/<session>.json`.
- The prompt hook takes the approval lock of each shown issue in one sorted
  order before it marks anything (`approvals.lock_all`).

### `compass evidence request`

An agent asks a person for an approval with this command. It never records
one. With no form, it asks for the approval the issue waits for next.

```
compass evidence request [--check ID | --guardrail G5 | --decisions
                          | --checkpoint STAGE | --waiver W-N | --ship]
                         [--scope TEXT] [--issue SLUG]
```

- **What it writes.** One file,
  `.compass/work/<slug>/approval-requests/pending/<n>.yml`, with the facts
  the command derives (issue, generation, labels, subject), the agent's
  `--scope`, the time and a single-use `nonce`. A pending request for the
  same subject closes as `replaced`. A request is not evidence, and no check
  reads it (`cli/compass_pkg/approval_requests.py`).
- **A stage review.** A request for the `specify`, `build` or `ship`
  checkpoint of an issue the four-layer acceptance strategy (`S17`) applies
  to also holds `review`, and prints its questions (`docs/checkpoints.md`,
  ADR-083). The request's digest covers them.
- **When it refuses.** It gives every refusal `compass evidence approve`
  gives for the subject, except those that depend on who answers. It exits
  2 and writes nothing.
- **What it prints.** The line to say to the person: type `/compass:approve`
  or `/compass:reject`. Where an adapter sets
  `COMPASS_APPROVAL_CHANNEL=terminal`, it prints the exact `compass evidence
  approve` command for the person's own terminal.

## When a list is skipped, and `on_skipped`

A skipped check does not run. It gives the verdict its `on_skipped` names:

| `on_skipped` | Verdict |
|---|---|
| `fail` | fail |
| `not-applicable` | nothing to check |
| `pass` | pass |

A check is skipped in two cases:

- A `human` check: the stage that produces its document is `skipped` or
  `collapsed`, or the document is recorded as deliberately omitted. That
  stage is the one before the listed stage for an entry list, and the listed
  stage for an exit list.
- Any other kind: the listed stage is `skipped` or `collapsed`.

A list does not depend on the stage's mode. A deterministic check that has
nothing to inspect also follows its `on_skipped`.

A third case is not a skip. When a `human` check's document is missing and
the issue does not owe that list, the row is nothing to check. On an issue
assessed before 9.0.0, the stage modes decide what is owed (ADR-091):

- the Definition of Ready (`requirements-review`) where the `refine` mode is
  `lightweight` or `thorough`;
- the Definition of Done (`verification-report`) where the `verify` mode is
  `thorough`.

So the 8.x regular and full approaches owe both, hotfix owes only the
Definition of Done, and quick fix and spike owe neither.

A stored generation whose approach declares an `artifacts:` map is read by
that map.

## A check that an approach does not owe

A `when` on a check reads the assessment. Evaluation adds one derived key,
`ships`: whether the issue's approach ships.

- Each Definition of Done check says `when: {ships: true}`, so a spike owes
  none of them.
- A delivery issue owes them only where it owes `definition-of-done`.
- The `when` of a `project_checks` setting takes the keys of the assessment,
  `labels_any` and `any_of`, and not `ships` (`docs/configuration.md`).

## Where results show

`compass check` adds one result for each due check, under a guardrail
named `stage:<stage>:<entry|exit>`. The results count in `ran`, `failed`
and `nothing_to_check`, and a failure fails the run. In `--json`, a row of
`checks` has the same four keys as every other row: `guardrail`, `name`,
`status` (`pass`, `fail` or `nothing-to-check`) and `detail`.

`compass next` appends `entry not met: <check ids>` to its line when the
current stage has failing entry checks.

## Limits

- A role in `approvers:` other than `owner` is read as a person id. An
  approval record is not authenticated.
- `evidence` checks are not evaluated.
- A tick written on a page counts for nothing.
