---
name: compass-runtime
description: Which command runs each stage, which skill it loads, where issue state lives. Load when an issue begins.
---

# Compass - the stage map

The rules of behavior are in `compass-contract.md`, and the SessionStart hook
puts them in every session before you read this. They are not repeated here,
so the two cannot disagree.

What this file carries is the mapping a session needs once it is already
following the contract - which command runs which stage, what each writes,
which skill it loads, and where the result lands on disk.

If anything here conflicts with `docs/methodology.md`, the methodology doc
wins. First Compass session? `docs/five-minutes.md` has the mental model and a
worked example; `docs/safety-contract.md` says what Compass guarantees and
what it explicitly does not.

## The stages and their commands

| Stage | Command | Artifact it writes |
|---|---|---|
| Assess | `/compass:assess` | the manifest's assessment and approach |
| Define acceptance criteria | `/compass:define` | `acceptance-criteria.md` |
| Requirements review | `/compass:refine` | the decisions taken and the Definition of Ready, as records |
| Plan | `/compass:plan` | the design and its work units, in the hand-off and `devlog.md` |
| Break down the work | `/compass:breakdown` | the order of the work units |
| Implement | `/compass:implement` | code + the red and green records (named by binding) |
| Test & review | `/compass:verify` | the gate evidence and the Definition of Done, as records (`compass check` lists each item's state) |
| Ship | `/compass:ship` | the integration commit + settled follow-ups |

`/compass:assess` itself carries only that light path. The full assess
procedure - setup, `--reassess`, steps 1 to 7 and the gate - is in
`approaches/assess-procedure.md`, which assess names for every heavier
approach and for `--reassess`.

When assess computes a **quick fix**, the eight rows above collapse into one
command: `/compass:quick-fix` carries the whole light path - assess, the one
scenario, red-green, the check, the commit - inlined in a single file, and it
is read alone. It is the same pipeline
at its lightest weight, not a way around it: if `compass approach evaluate`
returns anything heavier, the rows above are what runs.

Cross-issue: `/compass:status` (one issue or a flat list), `/compass:flow`
(the managed cross-issue view - advisory, never gating), and
`compass board render` (the same view as one page in the browser;
`docs/board.md`). Entry points for the consulted perspectives:
`/compass:intent` (product owner), `/compass:position` (marketer),
`/compass:design` (designer - produces the UI contract), `/compass:consult`
(multi-role decisions). `/compass:init` is optional, and it is not what
creates the project: the entry points above run `compass init` for you.

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
- **Define and refine** - load `bdd-specification`; on brownfield work whose
  behavior is not yet written down, also load `behavior-mapping`.
- **Plan** - load `plan-authoring` (which optional design sections earn a
  place) and `governance-check` (how to check the design against the
  governance in force).
- **Implementing** - load `tdd-discipline`; build the map's units in turn.
- **Test & review** - load `evidence-gates`, and `receiving-code-review`
  when answering a review's comments.
- **A change to behavior a real client can observe** - also load `atdd`:
  stage 1 at refine, stage 2 at implement and stage 3 at verify. Each ends at
  that stage's checkpoint, whose request lists the stage's review questions.
  No stage or gate moves. Not for a refactor.
- **An unexpected test failure while implementing** - load `systematic-debugging`,
  and after three failed fixes re-assess rather than try a fourth.
- **Role-facing work** - load `intent-interview` and read its
  `role-translation.md`, which is how one set of acceptance criteria is read
  through five role perspectives.
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
compass.yml                     The one file a person edits: settings, and the project's edits to the shipped default (written by /compass:init or compass policy migrate)
.compass/
├── state.yml                   What the CLI wrote: what initialized the project, and when
├── config.yml                  Projects from 5.x only: read until the project moves its settings with compass policy migrate; no 6.0.0 command writes it
├── legacy/, migration.yml      Written by compass policy migrate: the superseded files, and the digests of them
├── current-task                One-line pointer to the active issue
├── work/
│   └── <issue-slug>/            One directory per issue: its machine state
│       ├── manifest.yml         The manifest
│       ├── generations/<n>/     The configuration the issue runs against (written by compass approach evaluate --write)
│       ├── evidence/            red/green records + typed gate evidence
│       ├── .red, .spike, ...    The markers the hook reads
│       └── devlog.md            Append-only running log
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
written at define before any scenario. Every issue whose stored
configuration sets `release_line: true` on its approach (quick fix, regular,
hotfix and full on the shipped default) owes a release line, the manifest's
`release_note` (`schemas/manifest.schema.json`). Give it with
`--release-note "<text written for a user>"` on `compass ship-commit`,
`compass quick-fix finish` or `compass acceptance record`; a landing refuses
the issue without one (`docs/release-line.md`).

A new project has no `governance/` directory: the shipped default preset is in
force, and `compass.yml` holds only what differs from it. An unmigrated 5.x
project runs on its own copied `governance/` until `compass policy migrate`
converts it. `compass policy show` shows what is in force for a project with a
`compass.yml` or none, but it does not read that copy.

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

- a devlog entry, a requirements review, or anything else this skill
  produces - read `skills/compass-runtime/writing-voice.md`, the principle
  and the tells that mark prose narrating the pipeline instead of
  communicating a decision;
- a repository-wide replacement - read `text-sweeps.md`, what a text sweep
  must not touch.

`writing-voice-worked-example.md` beside `writing-voice.md` carries the
before-and-after pairs from this project's own archive, for when the
principle alone does not settle a sentence.

## When you are unsure

Run `compass approach show` and re-read the manifest. The approach was
recorded at assessment precisely so a later session, or a different agent, can
pick the issue up without re-deriving the process. If it does not answer the question, the assessment under-sized
the work: say so and re-assess rather than improvise.
