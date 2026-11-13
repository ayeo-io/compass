---
name: compass-runtime
description: Where issue state lives and which skill helps with what. Load when a `next:` line does not answer the question.
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
ship (ADR-092, `approaches/path.md`). Two commands run the path, and a
`next:` line names each step.

| Stage | What runs it | What it writes |
|---|---|---|
| Assess | `compass quick-fix start`; `/compass:assess` for a spike and `--reassess` | the assessment, the request link, `evidence_required` (the evidence the change owes), the gates and the first scenario |
| Specify | the session, only where a person approves the scenarios before code | the scenarios in `acceptance-criteria.md`, and the request for the `specify` approval |
| Build | the session: the tests and the code | no record |
| Ship | `compass quick-fix finish` | the scenarios and the changed files it reads, the red and green records, the three gates, the request for the ship approval, then the commit with the issue's record and `trail.md` |

- `/compass:go`, `/compass:quick-fix` and `/compass:assess` teach the same
  two commands. `/compass:assess` also starts a spike and holds `--reassess`
  (`approaches/assess-procedure.md`).
- `/compass:ship` covers the commit and the ship approval;
  `/compass:resume` continues an issue from its state on disk.

**The older record commands** - `compass tdd-red`, `tdd-green`, `scenario
add`, `changed-file add`, `evidence add` and `gate pass` - still work. A
project needs them only when its settings add evidence (`require_evidence`
in `compass.yml`): `finish` then names each added item on a `next:` line.
`compass tdd-red` is also the only way to record that a test was written
before the code.

**Follow the `next:` line.** `start` and `finish` end with `next:` or
`done:`, and `compass next` prints the issue's stage and its `next:` line at
any time:

```text
Build [gate: verify.correctness] | next: write the tests and the code, then compass quick-fix finish -m "<commit message>" -- <test command>
```

Do what it says.

A spike runs assess, build (explore) and ship (conclude): `approaches/spike.md`.

`/compass:status` reports one issue or lists them all; `/compass:flow` shows
blockers and follow-ups across issues, and never gates. `/compass:init` is
optional: the entry commands run `compass init`, which creates `.compass/`.

**An 8.x project** runs `compass migrate` once: a dry run lists the changes,
and `--apply` writes them (`docs/upgrade-9-0-0.md`). The aliases were removed
at 7.0.0, so an old command spelling exits 2; `docs/upgrade-7-0-0.md` lists
each one beside its new spelling, and `compass --help` lists the verbs now.

## The request link and the ship approval

- **The request link.** Assess records what asked for the change and who
  asked: `--request <url or owner/repo#N>` and `--requester "<name>"`.
  Without them the check `request-recorded` fails; `compass next` names the
  command that records them.
- **The ship approval.** One person approves each change, and the agent
  cannot give it. `finish` writes the request and the person types
  `/compass:approve <n>`. Or, after the merge, `compass issue link set --pr
  <n>` reads it from an approving review by a person who is not the author.

## Which skill helps

This session runs every stage; Compass starts no stage agent (ADR-090). A
change needs no skill. Load one when it helps:

- `adaptive-routing` - rating risk, familiarity and size for a spike or a
  re-assessment.
- `atdd` - scenarios and acceptance tests for behavior a real client can
  observe. It is guidance: no check of it runs unless the project's settings
  add one.
- `tdd-discipline` - writing the test first, and a change with no natural
  failing test.
- `evidence-gates` - what counts as evidence, when the project's settings
  add a review.
- `governance-check` - a change that needs a design a reviewer can argue
  with.
- `receiving-code-review` - answering a review's comments.
- `systematic-debugging` - an unexpected test failure. After three failed
  fixes re-assess rather than try a fourth.
- `intent-interview` - a brief or an idea with no acceptance criteria yet.

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
(ADR-096, `docs/delivery-record.md`). By default it is committed: the commit
that `finish` or `compass ship-commit` makes holds the issue folder and its
documents folder with the code. It is kept out when `compass.yml` says so,
when git ignores the folder or outside git; then `compass record sync` can
copy it elsewhere. Never stage `.compass/` yourself. `compass record commit`
commits the fields the merge adds, and the `next:` line names it.

**The release line.** A change that ships owes the manifest's `release_note`.
`finish` takes it from `--release-note "<text written for a user>"`, or from
the first line of the commit message (`docs/release-line.md`).

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
