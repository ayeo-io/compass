# Stage entry and exit lists

This page is the owning doc for the evaluation of a stage's `entry` and `exit`
lists. It states what the capability switches, when a list is due, how each kind of
check is judged, what `on_skipped` does, where the results show, and how the
documents show the lists. The code is `cli/compass_pkg/stage_lists.py`, which
judges a list, `cli/compass_pkg/item_records.py`, which reads the manifest
records that meet an item, `cli/compass_pkg/follow_up_cmd.py`, which records a
follow-up.
`compass check` and `compass next` read the first.

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
counts only due checks.

## A path issue

A path issue is one whose manifest records `evidence_required` (ADR-092). It
runs assess, specify, build and ship, and has no stage modes, so none of its
lists is skipped. `stage_lists.path_lists` gives it its lists:

- A configuration that declares the four path stages, as the shipped default
  does since 9.0.0 (ADR-092), is read at those stages as it stands. The build
  exit list is the Definition of Done, and the ship entry list holds a check
  such as a project's `agent-review`.
- A configuration that still declares the legacy stages, as a frozen preset
  or a stored generation does, has each list moved to the path stage that shows its
  stage: define, refine and plan to specify, breakdown and implement to
  build, `verify` and ship to ship. The `verify` exit list, the Definition of
  Done, moves to the build exit.
- A path issue owes no Definition of Ready, so no `dor-*` check is listed for
  it, wherever the configuration lists one.
- It owes the Definition of Done (`verification-report`) only when its
  `evidence_required` lists `definition-of-done`. Otherwise each Definition of
  Done row is nothing to check.

The rows are labelled with the path stage, such as `stage:build:exit`. An
issue assessed before 9.0.0 keeps its legacy lists, labels and modes exactly.

## How a check is judged

| Kind | Judged by |
|---|---|
| `human` | A record in the manifest (see [Item records](#item-records)): evidence that meets the check, a person's approval, or a follow-up that carries it to ship. A tick on a page counts for nothing, and the page is never read. With `approvers:` the check needs a current approval by a listed approver (see [Approvers on a human check](#approvers-on-a-human-check)). |
| `deterministic` | Its registered implementation runs. |
| `judged` | A review record: the newest registered `manual-review` record by a listed reviewer must say `pass` and match the check's inputs, definition, issue and generation. The cause of a failure is the first words of the detail. See [judged-checks.md](judged-checks.md). |
| `evidence` | Not evaluated by this version. A blocking check of this kind fails, so a list cannot pass by naming a check nothing reads. This holds whatever the capability, for a check a project adds, and `compass policy lint` warns (`M-LIST-KIND-UNEVALUATED`, exit code unchanged). The shipped default names none. |

A row passes with the record's name in its detail: `met by EV-T`, `ticked by
jed72`, `carried to ship, FU-3`, `met, FU-3 resolved`. An item with no record
fails as `not recorded` and names the commands that record it. `dod-evidence-typed`
reads the same records, so an item has one state whoever asks.

## Item records

An item is a check id in the issue's Definition of Done or `plan` entry list
(the Definition of Ready), whatever the capability says: the page shows both
lists, and the capability only decides whether the stage lists run. The
Definition of Done is the build exit list, or the `verify` exit list of a
configuration that declares a `verify` stage, as every stored generation and
the shipped default do now. A path issue has only the Definition of Done: a
command refuses to record a `dor-*` item or a `plan` or `breakdown` exit item
for it. One of four records meets an item, and a command writes each:

| Record | Written by | The item reads |
|---|---|---|
| `evidence[].meets: [item]` on an entry of an accepted type | `compass gate pass ... --meets ITEM`, `compass evidence add ... --meets ITEM` | `met by EV-id` |
| a `human-approval` record with `check: item` | `compass evidence approve --check ITEM` | `ticked by <approver>` |
| `follow_ups[].defers: item` with `github: {repo, number}`, on a path issue | `compass follow-up add FU-id --defers ITEM --github owner/repo#N --summary TEXT` | `carried to a GitHub issue, FU-id`, whether or not it is resolved |
| `follow_ups[].defers: item`, on an issue assessed before 9.0.0 | `compass follow-up add FU-id --defers ITEM --summary TEXT` | `carried to ship, FU-id`, then `met, FU-id resolved` once `compass follow-up resolve` resolves it |
| a `page_ticks` entry | `compass issue migrate`, from a tick on an archived page | `ticked on the page before 7.0.0` |

An item with none of them is open. `--meets` and `--defers` refuse, with exit 2
and no change, an item the issue does not list, and `--meets` refuses evidence
of a type the lists do not accept.

A path issue has one follow-up rule (ADR-093): an open Definition of Done item
is met only by a follow-up that links to a GitHub issue. So on a path issue:

- `compass follow-up add` refuses, with exit 2 and no change, a follow-up with
  no `--github`, and a `--defers` item that is not in the build exit list;
- `--github` takes `owner/repo#N` or the issue's URL, parsed as `compass issue
  link set` parses a target; nothing is written to GitHub;
- a follow-up with no `github` field meets nothing, and the open item's hint
  names it;
- the check that every follow-up is resolved has nothing to check, because
  the linked issue tracks the work.

An issue assessed before 9.0.0 keeps every older rule: an outstanding
follow-up fails `compass check` until `compass follow-up resolve` resolves it,
and a `target_task` entry that an older `--target` wrote blocks that issue's
`dod-evidence-typed` while it is outstanding. `--target` was removed in 9.0.0
and fails to parse with a line naming ADR-093.

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
declares none. Both are read from `compass.yml` as settings
(`project_settings.project_file`): a catalog key in the same file is a removed
setting and does not stop them being read (ADR-094). Any other entry is read as a person id, a role included, until
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
| `--checkpoint` | Answer the hand-off of a checkpoint stage: a path stage on a path issue, a legacy stage such as `define` on an older one (below) |
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

#### Approving a document: `--artifact` (removed in 9.0.0)

9.0.0 keeps no document status (ADR-091), so the document form of
`compass evidence approve` and `compass evidence request` is removed. A pending
request for a document, written before 9.0.0, closes with nothing written. An
`artifact-approval` record an older issue holds stays valid: it meets the human
check it names, and `human-approval-present`, the check of guardrail `G5`,
still reads only `human-approval` records.

#### Confirming decisions: `--decisions`

An agent that resolves a requirement question for the person records the
decision in the manifest's `decisions_taken` (ADR-050). `compass evidence
approve --decisions` confirms them as one set.

- **Which decisions.** At a checkpoint (`compass next` reports `Waiting at the
  <stage> checkpoint`), every unconfirmed decision taken at that stage or
  earlier. Away from a checkpoint, every unconfirmed decision. On a path issue
  the stages are assess, specify, build and ship: a decision taken at a legacy
  stage counts at the path stage that shows it, such as refine at specify, and
  the decisions wait at a listed `specify` checkpoint once the scenarios are
  written.
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

A checkpoint is a stage hand-off that can wait for a person. On a path issue
it is `assess`, `specify`, `build` or `ship`. On an issue assessed before 9.0.0
it is `assess`, `define`, `refine`, `plan`, `implement` or `verify`, and an
outcome or request in a path stage name is refused, as before.
`compass evidence approve --checkpoint <stage>` records a person's answer to
one. ADR-063 owns the decision.

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
  name that may not answer. On a path issue the specify hand-off can be answered
  once each scenario has an id, an intent and a declared test, and the ship
  hand-off once build is done, because those two stages count as done only after
  their answer or the landing.
- **What it never clears.** No check reads `checkpoint-approval`:
  `human-approval-present`, the check of guardrail `G5`, reads only
  `human-approval`, a human check reads `human-approval` and
  `artifact-approval`, and a waiver's approval needs `human-approval`. Answering
  a hand-off is therefore never the sign-off on an irreversible change.
  `compass evidence add --type checkpoint-approval` is refused, so the type is
  written only by this command.
  `compass evidence add` refuses the types `isolation-proof` and `layering`
  in the same way: only `compass isolation record` and `compass layering
  record` write them (ADR-086).

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

#### Approving a waiver: `--waiver`

`compass evidence approve --waiver W-<n>` approves one waiver of the issue
(`cli/compass_pkg/waiver_records.py`, ADR-094). It writes one
`human-approval` record with `waiver: W-<n>`, the `waived_check` and the
`waiver_reason` the waiver names, `approver`, `role`, `scope`,
`decision: approved`, `timestamp`, `issue` and `generation`. The record names
a subject, so it never clears guardrail `G5`, and it counts only at the
generation it holds. It refuses a withdrawn waiver,
one already approved, one with no reason, one of a check the check set never
waives, `--decision rejected` and a name that is not in `approvers.waiver`
(else the project's owner). The waiver and what `compass check` shows are in
`docs/waivers.md`.

### Approving in Claude Code, and delegated approvals

In Claude Code a person answers a request by typing `/compass:approve [n]` or
`/compass:reject [n] <reason>`. The `UserPromptExpansion` hook
(`hooks/prompt-approval.sh`, `cli/compass_pkg/prompt_approval.py`) records
the answer through `approvals.record`, with `via: prompt`, the session id,
the prompt id, the request number and its nonce. It records only one pending
request of the session's issue that Compass has shown and that has not
changed since, and blocks with the reason otherwise. `/compass:approve waiver W-<n>`
answers the pending request for that waiver, and only while the waiver names
the check and reason the request showed. A rejected check gets a
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

`g5` is covered only with `--for g5`, and a waiver only with `--for waivers`,
after the person types back a code the hook shows them. The code is
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
approve`, cut at the first shell operator, comment or redirect such as `2>&1`.
The hook writes one only when `compass` stands in command position, never when it
is an argument of `echo`, `printf` or `xargs`. The CLI takes the matching ticket
under the store lock and reads the session from it, never from the environment.
A ticket is deleted when its call finishes, fails or has its permission denied
(the post-tool hook, registered for `PostToolUse`, `PostToolUseFailure` and
`PermissionDenied`), and every unused ticket of a session is deleted at its
Stop and at its next prompt; an untaken ticket expires after 10 minutes. The
verb refuses, writing
nothing, when it has no ticket, no `--issue`, or an issue that two worktrees
hold; or when no delegation in force names the agent or covers its session, or
the one that does has ended, was revoked, reached its `max`, was not written by
a typed command, or does not cover the issue, its generation, the form or the
labels of a 7.0.0 file. The refusal tells the agent to ask with `compass
evidence request` and stop, and says the person must type `/compass:approve`. A delegation file in a linked worktree's own folder
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
issue in any worktree. With more than one matching request, the two commands
refuse and list the `--issue` forms. When two worktrees hold the slug named
after `--issue`, the copy in the worktree the person types in wins; typed in a
worktree that holds no copy, the command is refused
(`governance/decisions/2026-10-29-a-persons-approval-takes-the-issue-in-its-own-worktree.md`).
An agent's delegated approval and `--on` still refuse a slug two worktrees
hold. The approver is read from the folder that holds the chosen
request, after the choice. The session-start hook lists each delegation with no
end time (`delegations.session_start_lines`) on a new session, after `/clear`
and after compaction, but not on a resumed session.

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
- **A stage review.** A request for the `refine`, `implement` or `verify`
  checkpoint (`specify`, `build` or `ship` on a path issue) of an issue the
  four-layer acceptance strategy (`S17`) applies to also holds `review`: the stage of the `atdd` skill it ends and that
  stage's questions from `skills/atdd/references/stage-reviews.md`. The
  command prints the questions, the person sees them with the request, and
  the request's digest covers them (ADR-083).
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
approach does not owe that list, the row is nothing to check, for example
"quick-fix owes no verification-report". Since 9.0.0 (ADR-091) the stage modes
decide what is owed:

- the Definition of Ready (`requirements-review`) where the issue's `refine`
  mode is `lightweight` or `thorough`;
- the Definition of Done (`verification-report`) where its `verify` mode is
  `thorough`.

So the 8.x regular and full approaches owe both, hotfix owes only the
Definition of Done, and quick fix and spike owe neither. An issue assessed
before 9.0.0 names an approach the shipped default no longer declares
(ADR-092); it owes by its own stage modes in the same way. A stored generation or
a frozen preset whose approach still declares an `artifacts:` map is read by
that map, as before 9.0.0. An issue assessed before 7.0.0 keeps a stored
generation whose regular approach does not list `requirements-review`, so it
has nothing to check for the Definition of Ready.

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

## Where a list shows

`compass check` lists each item of the `plan` entry list and the `verify` exit
list with its state, under `stage:<stage>:<entry|exit>`. A tick written on a page
counts for nothing. Before 9.0.0 a rendered block showed each list in the
requirements review and the verification report (ADR-091 removed the render).

## Limits

- A role in `approvers:` other than `owner` is read as a person id. An
  approval record is not authenticated (see [Approvers on a human
  check](#approvers-on-a-human-check)).
- `evidence` checks are not evaluated.
- A list on a stage other than `plan` and `verify` is judged from the records but
  has no block in a document.
