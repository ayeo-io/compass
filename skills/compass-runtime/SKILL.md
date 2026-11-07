---
name: compass-runtime
description: What runs each stage of the path, which skill it loads, where issue state lives. Load when an issue begins.
---

# Compass - the stage map

The rules of behavior are in `compass-contract.md`, and the SessionStart hook
puts them in every session before you read this. They are not repeated here,
so the two cannot disagree.

What this file carries is the mapping a session needs once it is already
following the contract - what runs each stage, what each writes,
which skill it loads, and where the result lands on disk.

If anything here conflicts with `docs/methodology.md`, the methodology doc
wins. First Compass session? `docs/five-minutes.md` has the mental model and a
worked example; `docs/safety-contract.md` says what Compass guarantees and
what it explicitly does not.

## The stages and their commands

A delivery issue runs one path of four stages (ADR-092,
`approaches/path.md`). The stages have no commands of their own: one
command runs the path, and the `next:` line names each step.

| Stage | What runs it | What it writes |
|---|---|---|
| Assess | `compass quick-fix start`, or `/compass:assess` for the full procedure, `--reassess` and the spike | the assessment, `evidence_required`, the pending gates, the `S17` block and the checkpoints |
| Specify | the `next:` line: `compass scenario add`, `compass scenario tests set` | the scenarios in `acceptance-criteria.md`, the test each one declares, and the `specify` checkpoint's outcome where `scenario-approval` is owed |
| Build | the `next:` line: `compass tdd-red`, then the code, then `compass tdd-green` | the red and green records (named by binding), and the outer-loop, isolation and layering records where `S17` applies |
| Ship | the `next:` line: `compass evidence add`, `compass gate pass`, `compass check`; `/compass:ship` or `compass quick-fix finish` for the commit | the gate evidence and the Definition of Done items as records, the sign-offs, and the commit |

- `/compass:go` runs the whole path in one session: it assesses with
  `compass quick-fix start`, shows `compass approach show`, then follows
  the `next:` line until `compass check` passes. It stops only where a
  `next:` line says to wait for a person.
- `/compass:quick-fix` is its short form, for a change the person already
  knows is small: start, red, finish. It is read alone.
- `/compass:assess` carries the light path. The full assess procedure -
  setup, `--reassess`, steps 1 to 7 and the gate - is in
  `approaches/assess-procedure.md`, which assess names for a change that is
  not small, for a spike and for `--reassess`.
- `/compass:ship` lands the change once every gate passes.
- `compass next` prints the issue's stage and the one command to run next,
  and every verb that writes a record of a path issue ends its text output
  with the same `next: <command>` line. Run that command. When you are not
  sure what comes next, run `compass next`.

A spike runs assess, build (explore) and ship (conclude); `approaches/spike.md`
describes it.

Cross-issue: `/compass:status` (one issue or a flat list) and `/compass:flow`
(the managed cross-issue view - advisory, never gating; `compass flow` and
`docs/cli.md`). `/compass:init` is optional, and it is not what creates
the project: `/compass:go`, `/compass:quick-fix` and `/compass:assess` run
`compass init` for you.

A command spelling that a release held and 6.0.0 renamed worked through an
alias in 6.x. The aliases were removed at 7.0.0, so the old spelling now exits 2
with the parser's usual error. That error names no new spelling, except for
two removed verbs that add one line. `docs/upgrade-7-0-0.md` names them and lists
each removed spelling beside its new one. `governance/terminology.yml` names each retired word beside the
one that replaced it, and `docs/glossary.md` says the same in prose; the
current verbs are whatever `compass --help` lists.

**The binding decides the filename.** `compass tdd-red --scenario <id>` and
`compass tdd-green --scenario <id>` write `evidence/red-<id>.json` and
`evidence/green-<id>.json`; a run with no `--scenario` writes
`evidence/red.json` and `evidence/green.json` instead. With `--loop outer` the
name ends `.outer.json`, so an inner-loop record does not replace it (ADR-082).
Nothing else is touched, so one scenario's record cannot overwrite another's.

## Which skill, per stage

This session runs every stage; Compass starts no stage agent (ADR-090).

- **Assess** - load the `adaptive-routing` skill.
- **Specify** - load `bdd-specification`; on brownfield work whose
  behavior is not yet written down, also load `behavior-mapping`. When the
  change needs a design a reviewer can argue with, load `governance-check`
  (how to write the design down and check it against the governance in
  force).
- **Build** - load `tdd-discipline`; build the units in turn.
- **Ship** - load `evidence-gates`, and `receiving-code-review`
  when answering a review's comments.
- **A change to behavior a real client can observe** - also load `atdd`:
  stage 1 at specify, stage 2 at build and stage 3 at ship. Each ends at
  that stage's checkpoint, whose request lists the stage's review questions.
  No stage or gate moves. Not for a refactor.
- **An unexpected test failure while building** - load `systematic-debugging`,
  and after three failed fixes re-assess rather than try a fourth.
- **A brief or an idea with no acceptance criteria yet** - load
  `intent-interview`, which draws the intent out before any scenario.
- `evidence-gates` carries `traceability.md`, read whenever an artifact is
  written.

No session edits `manifest.yml` by hand: a `compass` verb writes it.

## Never stash across a worktree hop

Compass starts no worktree (ADR-090), but a person or a delegated agent can
work in one; the hook judges an edit there by that worktree's own pointer
(ADR-078). Never stash in one worktree and pop in another, and never stash
inside a temporary worktree: a stash lives in the shared repository, but the
state it captures belongs to one checkout, so removing a temporary worktree
destroys the stashed work along with the worktree. A CI fix nearly lost work
this way. To move work between worktrees, commit it: the branch is durable.

## Where state lives

```
compass.yml                     The one file a person edits: settings, and the tighten-only settings that add to the check set (written by /compass:init)
.compass/
├── state.yml                   What the CLI wrote: what initialized the project, and when
├── config.yml                  Projects from 5.x only: read until the project moves its settings with compass policy migrate on 8.x; no 6.0.0 command writes it
├── legacy/, migration.yml      Written by compass policy migrate on 8.x: the superseded files, and the digests of them
├── current-task                One-line pointer to the active issue
├── work/
│   └── <issue-slug>/            One directory per issue: its machine state
│       ├── manifest.yml         The manifest
│       ├── generations/<n>/     The configuration the issue runs against (written by compass approach evaluate --write)
│       ├── evidence/            red/green records + typed gate evidence
│       ├── .red, .spike, ...    The markers the hook reads
│       └── devlog.md            An archived issue's running log; a new issue has none (ADR-092)
└── flow/
    └── digest-<date>.md         Periodic cross-issue digest

docs/compass/
└── <created>-<issue-slug>/      One directory per issue: its documents
    ├── acceptance-criteria.md   The one document Compass needs and checks
    └── ...                      Any note the team keeps, such as ui-contract.md
                                 or positioning.md; Compass does not read it
```

An issue's acceptance criteria are at
`docs/compass/<created>-<issue-slug>/acceptance-criteria.md`, where `<created>`
is the manifest's `created:` date. Compass 9.0.0 registers no document and
keeps no document status (ADR-091). An archived issue's manifest can still hold
an `artifacts:` list and its folder the documents it names; they stay valid
and are not read.

The intent opens the acceptance criteria: their Summary and Intent links,
written at specify before any scenario. A delivery issue owes a release
line when its stored configuration sets `release_line: true` on any approach
that ships, as the shipped default does; an issue assessed before the path
owes one when its own approach sets it. The line is the manifest's
`release_note` (`schemas/manifest.schema.json`). Give it with
`--release-note "<text written for a user>"` on `compass ship-commit`,
`compass quick-fix finish` or `compass acceptance record`; a landing refuses
the issue without one (`docs/release-line.md`).

On a delivery issue the first `compass tdd-red` writes the manifest's
`scenario_freeze`: the spec's path and digest and the scenario ids the code
is written against. Where the issue owes `scenario-approval`, the red waits
for a person's answer at specify (`docs/checkpoints.md`).

A waiver excuses one check on one issue (the manifest's `waivers:`). Write it
with `compass waiver add --check <id> --reason "..."`, ask with `compass
evidence request --waiver W-<n>`, and stop: only a person, or an agent under a
delegation typed `--for waivers`, approves it (`docs/waivers.md`).

An approval under a delegation copies that delegation into the manifest's
`delegations_used:`, in the same save as the record. Compass writes it; do not
edit it (`docs/entry-exit-evaluation.md`).

A new project has no `governance/` directory: the fixed check set
(`governance/check-set.yml` in the plugin) is in force, and `compass.yml` holds
the project's settings, which can only add to it. An unmigrated 5.x project runs
on its own copied `governance/` until `compass policy migrate` on 8.x
converts it. `compass policy show` prints the check set, its digest and the
settings applied for a project with a `compass.yml` or none, but it does not
read that copy.

## Project lessons

A project keeps rules a person has had to repeat as lessons; the session
start shows the `always` ones after the contract. When the person states
one, run `compass lesson propose "<their words>"`, quoting them,
and never `compass lesson add`. A proposal takes effect only when someone runs
`compass lesson accept`. The CLI cannot tell whether the person or the model
typed a rule, so this instruction is what keeps the model on the proposing
side. A lesson is advice: a guardrail always wins.

## Writing voice

Before you write:

- a scenario's intent, a review, a commit message, or anything else this
  skill produces - read `skills/compass-runtime/writing-voice.md`, the principle
  and the tells that mark prose narrating the pipeline instead of
  communicating a decision;
- a repository-wide replacement - read `text-sweeps.md`, what a text sweep
  must not touch.

`writing-voice-worked-example.md` beside `writing-voice.md` carries the
before-and-after pairs from this project's own archive, for when the
principle alone does not settle a sentence.

## When you are unsure

Run `compass next` and `compass approach show`, and re-read the manifest.
The evidence was recorded at assessment precisely so a later session, or a
different agent, can pick the issue up without re-deriving the process. If
it does not answer the question, the assessment under-sized the work: say so
and re-assess rather than improvise.
