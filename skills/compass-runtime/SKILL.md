---
name: compass-runtime
description: Which skill each stage loads and where issue state lives. Load when an issue begins.
---

# Compass - the stage map

The rules of behavior are in `compass-contract.md`, and the SessionStart hook
puts them in every session before you read this. They are not repeated here,
so the two cannot disagree.

This file maps each stage to its command, its records, its skill and its
place on disk. If it conflicts with `docs/methodology.md`, the methodology doc
wins. First session: `docs/five-minutes.md` takes one change through the
path; `docs/safety-contract.md` says what Compass guarantees and what it does
not.

## The stages and their commands

Every delivery issue runs one path of four stages: assess, specify, build and
ship (ADR-092, `approaches/path.md`). The stages have no commands of their
own. One command runs the path, and a `next:` line names each step.

| Stage | What runs it | What it writes |
|---|---|---|
| Assess | `compass quick-fix start`, or `/compass:assess` for the full procedure, `--reassess` and the spike | the assessment, the request link, `evidence_required` (the evidence the change owes), the gates and the checkpoints |
| Specify | `compass scenario add`, `compass scenario tests set` | the scenarios in `acceptance-criteria.md` and the test each one names |
| Build | `compass tdd-red`, then the code, then `compass tdd-green` | the red and green records, and the outer-loop, isolation and layering records where the four-layer strategy (`S17`) applies |
| Ship | `compass quick-fix finish` or `/compass:ship`, then `compass ship-commit` | the gate evidence, the commit with the issue's record and `trail.md`, and after the merge the ship approval |

- `/compass:go` runs the whole path in one session. It assesses with
  `compass quick-fix start`, shows `compass approach show`, then follows the
  `next:` line until `compass check` passes. It stops only where a `next:`
  line says to wait for a person.
- `/compass:quick-fix` is its short form, for a change the person already
  knows is small: start, red, finish.
- `/compass:assess` holds the light path. The full procedure (steps 1 to 7
  and the gate) is in `approaches/assess-procedure.md`, for a change that is
  not small, a spike and `--reassess`.
- `/compass:ship` passes the gates with evidence and commits;
  `/compass:resume` continues an issue from its state on disk.

**Follow the `next:` line.** Every verb that writes a record of a path issue
ends its text output with `next: <command>`, and `compass next` prints the
issue's stage and that line at any time:

```text
Build [gate: verify.correctness] | next: compass tdd-red --loop outer --scenario TRC-001 -- <acceptance test command>
```

Run the command it names. At ship it names the commit:
`compass ship-commit --issue <slug> -m "<message>" --release-note "<plain text>"`.

A spike runs assess, build (explore) and ship (conclude): `approaches/spike.md`.

`/compass:status` reports one issue or lists them all; `/compass:flow` shows
blockers and follow-ups across issues, and never gates. `/compass:init` is
optional: the entry commands run `compass init`, which creates `.compass/`.

**An 8.x project** runs `compass migrate` once: a dry run lists the changes,
and `--apply` writes them (`docs/upgrade-9-0-0.md`). The aliases were removed
at 7.0.0, so an old command spelling exits 2; `docs/upgrade-7-0-0.md` lists
each one beside its new spelling, and `compass --help` lists the verbs now.

**The binding decides the filename.** `compass tdd-red --scenario <id>` and
`compass tdd-green --scenario <id>` write `evidence/red-<id>.json` and
`evidence/green-<id>.json`; a run with no `--scenario` writes
`evidence/red.json` and `evidence/green.json`. With `--loop outer` the name
ends `.outer.json`, so an inner-loop record does not replace it (ADR-082).
One scenario's record cannot overwrite another's.

## The request link and the ship approval

- **The request link.** Assess records what asked for the change and who
  asked: `--request <url or owner/repo#N>` and `--requester "<name>"`.
  Without them the check `request-recorded` fails; `compass next` names the
  command that records them.
- **The ship approval.** One person approves each change, and the agent
  cannot give it. After the merge, `compass issue link set --pr <n>` reads it
  from an approving review by a person who is not the author. With no such
  review, run `compass evidence request --ship` and stop for
  `/compass:approve`. No landing waits for it.

## Which skill, per stage

This session runs every stage; Compass starts no stage agent (ADR-090).

- **Assess** - load the `adaptive-routing` skill.
- **Specify** - load `atdd`. Every change uses its scenarios part. On
  `brownfield-unmapped` code, do its behavior mapping part first. When the
  change needs a design a reviewer can argue with, load `governance-check`
  (how to write the design down and check it against the check set).
- **Build** - load `tdd-discipline`; build the units in turn.
- **Ship** - load `evidence-gates`, and `receiving-code-review` when
  answering a review's comments.
- **A change to behavior a real client can observe** - the four-layer part of
  `atdd`: stage 1 at specify, stage 2 at build and stage 3 at ship. Each ends
  at that stage's checkpoint, whose request lists its review questions. No
  stage or gate moves. Not for a refactor.
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
compass.yml                     The one file a person edits: settings, and the tighten-only settings that add to the check set
.compass/
├── state.yml                   What initialized the project, and when
├── config.yml                  Projects from 5.x only: read until the project moves its settings with compass policy migrate on 8.x; no 6.0.0 command writes it
├── legacy/, migration.yml      Written by compass policy migrate on 8.x: the superseded files, and the digests of them
├── current-task                One-line pointer to the active issue
└── work/
    ├── .gitignore              Keeps generations, lock files and markers out of the commit
    └── <issue-slug>/           One folder per issue: its record
        ├── manifest.yml        The manifest
        ├── trail.md            Who asked, what was agreed, red, green, who approved, what shipped, with sha256sum lines
        ├── evidence/           Red and green records, typed gate evidence, SHA256SUMS
        └── generations/<n>/    The configuration the issue runs against; not committed

docs/compass/
└── <created>-<issue-slug>/
    └── acceptance-criteria.md  The one document Compass needs and checks
```

In `docs/compass/<created>-<issue-slug>/`, `<created>` is the manifest's
`created:` date. A team can keep its own notes there; Compass does not read
them (ADR-091).

**The record mode** decides whether the issue's record ships with the code
(ADR-096, `docs/delivery-record.md`). By default it is committed:
`compass ship-commit` stages the issue folder and its documents folder with
the code. It is kept out when `compass.yml` says so, when git ignores the
folder or outside git; then `compass record sync` can copy it elsewhere.
Never stage `.compass/` yourself. `compass record commit` commits the fields
the merge adds, and the `next:` line names it.

**The release line.** A change that ships owes the manifest's `release_note`,
given with `--release-note "<text written for a user>"`. A landing without
one is refused (`docs/release-line.md`).

**The scenario freeze.** The first `compass tdd-red` writes the manifest's
`scenario_freeze` (the spec's digest and the scenario ids). Where the issue
owes `scenario-approval`, the red is refused until a person answers at
specify (`docs/checkpoints.md`).

**A waiver** excuses one check on one issue: `compass waiver add --check <id>
--reason "..."`, then `compass evidence request --waiver W-<n>`, and stop. Only
a person, or an agent under a delegation typed `--for waivers`, approves it
(`docs/waivers.md`).

A new project has no `governance/` directory: the fixed check set
(`governance/check-set.yml` in the plugin) is in force, and `compass.yml`
holds the project's settings, which can only add to it. An unmigrated 5.x
project with a copied `governance/` is refused until `compass policy migrate`
on 8.x converts it. `compass policy show` prints the check set, its digest and
the settings applied, but it does not read that copy.

## Project lessons

A project keeps rules a person has had to repeat as lessons; the session
start shows the `always` ones after the contract. When the person states one,
run `compass lesson propose "<their words>"`, quoting them,
and never `compass lesson add`. A proposal takes effect only when someone
runs `compass lesson accept`. The CLI cannot tell whether the person or the
model typed a rule, so this instruction keeps the model on the proposing
side. A lesson is advice: a guardrail always wins.

## Writing voice

Before you write a scenario's intent, a review, a commit message or other
prose, read `skills/compass-runtime/writing-voice.md`: the principle, and the
tells that mark prose narrating the pipeline instead of communicating a
decision. `writing-voice-worked-example.md` beside it holds before-and-after
pairs for when the principle alone does not settle a sentence. Before a
repository-wide replacement, read `text-sweeps.md`: what a text sweep must
not touch.

## When you are unsure

Run `compass next` and `compass approach show`, and re-read the manifest.
The assessment was recorded so a later session, or a different agent, can
pick the issue up without re-deriving the process. If it does not answer the
question, the assessment under-sized the work: say so and re-assess rather
than improvise.
