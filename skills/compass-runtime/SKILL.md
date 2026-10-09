---
name: compass-runtime
description: Which command runs each stage, which agent owns it, where issue state lives. Load when an issue begins.
---

# Compass - the stage map

The rules of behaviour are in `compass-contract.md`, and the SessionStart hook
puts them in every session before you read this. They are not repeated here,
so the two cannot disagree.

What this file carries is the mapping a session needs once it is already
following the contract - which command runs which stage, what each writes,
which agent owns it, and where the result lands on disk.

If anything here conflicts with `docs/methodology.md`, the methodology doc
wins. First Compass session? `docs/five-minutes.md` has the mental model and a
worked example; `docs/safety-contract.md` says what Compass guarantees and
what it explicitly does not.

## The stages and their commands

| Stage | Command | Artifact it writes |
|---|---|---|
| Assess | `/compass:assess` | `delivery-approach.md` + the manifest's assessment |
| Define acceptance criteria | `/compass:define` | `acceptance-criteria.md` |
| Requirements review | `/compass:refine` | `requirements-review.md` (ends with the Definition of Ready) |
| Plan | `/compass:plan` | `technical-design.md` (+ `distribution-map.md` on parallel work) |
| Break down the work | `/compass:breakdown` | worktrees + subtask assignments |
| Implement | `/compass:implement` | code + the red and green records (named by binding) |
| Test & review | `/compass:verify` | `verification-report.md` (ends with the Definition of Done) |
| Ship | `/compass:ship` | the integration commit + settled follow-ups |

`/compass:assess` itself carries only that light path. The full assess
procedure - setup, `--reassess`, steps 1 to 7 and the gate - is in
`approaches/assess-procedure.md`, which assess names for every heavier
approach and for `--reassess`.

When assess computes a **quick fix**, the eight rows above collapse into one
command: `/compass:quick-fix` carries the whole light path - assess, the one
scenario, red-green, the check, the commit - inlined in a single file, and it
is read with the `quick-fix` skill and nothing else. It is the same pipeline
at its lightest weight, not a way around it: if `compass approach evaluate`
returns anything heavier, the rows above are what runs.

Cross-issue: `/compass:status` (one issue or a flat list), `/compass:flow`
(the managed cross-issue view - advisory, never gating). Role entry points:
`/compass:intent` (product owner), `/compass:position` (marketer),
`/compass:design` (designer - produces the UI contract), `/compass:consult`
(multi-role decisions). `/compass:init` is optional, and it is not what
creates the project: the entry points above run `compass init` for you.

A command spelling that a release held and 6.0.0 renamed keeps working through
an alias until 7.0.0. The alias prints the new spelling on standard error and
gives the new command's output and exit code. A spelling that no release held has no alias: its
unknown-command message names the new spelling. `docs/upgrade-6-0-0.md` lists
the aliases. `governance/terminology.yml` names each retired word beside the
one that replaced it, and `docs/glossary.md` says the same in prose; the
current verbs are whatever `compass --help` lists.

**The binding decides the filename.** `compass tdd-red --scenario <id>` and
`compass tdd-green --scenario <id>` write `evidence/red-<id>.json` and
`evidence/green-<id>.json`; a run with no `--scenario` writes
`evidence/red.json` and `evidence/green.json` instead. Nothing else is touched, so
recording one scenario cannot overwrite the record another gate is citing -
and a reader knows where their evidence went without guessing.

## Which agent and which skill, per stage

- **Assess** - load the `adaptive-routing` skill; consider the `router`
  agent.
- **Define and refine** - load `bdd-specification`; on brownfield work whose
  behaviour is not yet written down, also load `behaviour-mapping`. The
  `spec-author` agent owns both stages.
- **Plan** - load `plan-authoring` (which optional design sections earn a
  place) and `governance-check` (how to check the design against the
  governance in force). The `planner` agent owns it.
- **Implementing in parallel** - load `worktree-multiagent`. The `orchestrator`
  agent coordinates; `builder` agents work, one per worktree, each loading
  `tdd-discipline`.
- **Test & review** - the `verifier` and `reviewer` agents run; load
  `evidence-gates`. Load `receiving-code-review` when answering their
  comments.
- **An unexpected test failure while implementing** - load
  `systematic-debugging`, and after three failed fixes re-assess rather than
  try a fourth.
- **Role-facing work** - load `intent-interview` and read its
  `role-translation.md`, which is how one set of
  acceptance criteria is read through five role perspectives. The
  `product-owner`, `product-marketer` and `architect` agents apply specific
  ones.
- `evidence-gates` carries `traceability.md`, read whenever an artifact is
  written.

The full set is in `agents/`. The files in `agents/` are the authority.

## Worktrees and multiagent

Only the `orchestrator` agent creates worktrees (`scripts/multiagent.sh`) and
integrates them (`scripts/integrate.sh`). A `builder` works *inside* its
assigned worktree and never touches a sibling's. The approach's distribution
map says how many subtasks exist; policy can cap the count. On solo work there
is no worktree - work on the current branch.

## Where state lives

```
compass.yml                     The one file a person edits: settings, and the project's edits to the shipped default (written by /compass:init or compass policy migrate)
.compass/
├── state.yml                   What the CLI wrote: what initialised the project, and when
├── config.yml                  Projects from 5.x only: read until the project moves its settings with compass policy migrate; no 6.0.0 command writes it
├── legacy/, migration.yml      Written by compass policy migrate: the superseded files, and the digests of them
├── current-task                One-line pointer to the active issue
├── work/
│   └── <issue-slug>/            One directory per issue: its machine state
│       ├── manifest.yml         The manifest
│       ├── delivery-approach.md The delivery-approach record (prose). A quick fix keeps it in docs/compass/ instead
│       ├── generations/<n>/     The configuration the issue runs against (written by compass approach evaluate --write)
│       ├── evidence/            red/green records + typed gate evidence
│       ├── .red, .spike, ...    The markers the hook reads
│       └── devlog.md            Append-only running log
└── flow/
    └── digest-<date>.md         Periodic cross-issue digest

docs/compass/
└── <created>-<issue-slug>/      One directory per issue: its documents
    ├── intent.md                Intake (if a product owner was involved)
    ├── ui-contract.md           Designer contracts (if a designer was involved)
    ├── acceptance-criteria.md   The shared artifact every role reads
    ├── requirements-review.md   (ends with the Definition of Ready gate)
    ├── technical-design.md      The design
    ├── distribution-map.md      Multiagent orchestration (full-approach scale work)
    ├── positioning.md           Marketer messaging (if in play)
    ├── launch-readiness.md      Marketer claims gate (if in play)
    └── verification-report.md   (ends with the Definition of Done gate)
```

An issue's documents are in `docs/compass/<created>-<issue-slug>/`, where
`<created>` is the manifest's `created:` date. `compass issue artifact-path
<kind>` prints where one document is.

A new project has no `governance/` directory: the shipped default preset is in
force, and `compass.yml` holds only what differs from it. A project from 5.x
that copied `governance/` into its root keeps running on that copy until
`compass policy migrate` converts it. `compass policy show` shows what is
in force.

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

Re-read `delivery-approach.md`. It was written at assessment precisely so a
later session, or a different agent, can pick the issue up without re-deriving
the process. If it does not answer the question, the assessment under-sized
the work: say so and re-assess rather than improvise.
