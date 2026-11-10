# The full assess procedure

Read by `/compass:assess` for a spike, or on `--reassess`. A delivery issue
starts with `compass quick-fix start` (`commands/assess.md`), which assesses
a change of any size in one call.

Assess is the first of the four stages of the path (`approaches/path.md`),
and every issue runs it. It reads the three scored dimensions - that is
**judgment** - and then hands them to the CLI, which **computes** the
evidence the change owes. You do not pick a process, and you do not select
the evidence in your head: you assess the work, record the assessment, and
`compass approach evaluate` applies the configuration in force to produce
the `evidence_required` list. This is the determinism boundary - see
`docs/methodology.md` §2.

Assess works on day one with **zero project setup**: the shipped default
guardrails, strategies, and routing policy apply as-is, so `/compass:init` is
optional and not a prerequisite. If a project has run `/compass:init`, its
`compass.yml` extends those defaults - read `compass policy show` for
what is in force. An unmigrated 5.x project runs on its own copied
`governance/` until `compass policy migrate` on 8.x converts it.

The issue is the one `/compass:assess` was given.

## First: make sure this is a Compass project

Run `compass init`. It creates `.compass/` if it is not there and reports that
it did; if the project already exists it says so and changes nothing, so this
is safe to run every time and you do not need to check first.

**Report the result to the user in one line when it created the project.** A
`.compass/` directory appearing with no word said is how someone deletes it by
hand, or commits it without meaning to. It creates project state only - the
shipped defaults stay in force, and writing a `compass.yml` for the project is
what `/compass:init` offers separately.

## Setup

- Load the `adaptive-routing` skill - it is the procedural companion to the
  assessment rubric (`${CLAUDE_PLUGIN_ROOT}/approaches/rubric.md`).
- Read `${CLAUDE_PLUGIN_ROOT}/governance/routing-policy.md` for the *why*.
  What `compass approach evaluate` actually runs is the effective
  configuration, which `compass policy show` prints: the shipped default
  preset with the project's `compass.yml` over it. The CLI matches the
  **evidence rows**, then adds the configuration's **floors, immovable gates
  and project guardrails**. You do not apply these by hand; the CLI does. An unmigrated 5.x project runs on its own
  copied `governance/`. `compass policy show` prints the shipped default and
  says the project runs on its copy; `compass approach evaluate` reads the copy.
- Read `compass.yml` for project settings (the test command, the
  autonomy setting), or `.compass/config.yml` in a 5.x project that has no
  `compass.yml`. The same `compass.yml` holds the project's changes to the
  routing rules.
- For a non-trivial or ambiguous issue, read the three scored dimensions
  with care in this session; Compass starts no agent for it (ADR-090).
- If the issue came with a brief, or a note of the team's own such as
  `ui-contract.md` or `positioning.md` exists, read it - intent is the
  *outcome wanted*, not just the literal request.

## `--reassess`

If `--reassess` is passed, this is a re-assessment during the work, not a new
assessment - typically because implementation revealed the assessment was
misread. Run `compass approach show` and read `manifest.yml`, re-read the
three scored dimensions, update the manifest's `assessment:` block, then re-run
`compass approach evaluate --write --reason "..." --justify DIM="..."` to recompute
the evidence, with one `--justify` for each value you changed.
**Always pass `--reason`** on a re-assessment: the CLI records the event in
the manifest's `reassessments:` log (as kind `unchanged` when the evidence did
not move), with the reason. A re-assessment is a normal event. The failure
is an issue that outgrows its assessment unrecorded; a re-assessment with no
reason tells a reviewer nothing.

A re-assessment of an issue assessed before the path moves it onto the path:
the CLI writes the path keys, removes the old `stages:` map and logs the old
approach as `from_route` in `reassessments:`.

A re-assessment also commits the next **generation** of the issue's stored
configuration (`manifest.yml` names it in `generation:`), and the
`reassessments:` entry records it as `generation: {from, to}`. An issue has
no configuration of its own (ADR-094): the manifest's `config:` is not read,
and a check the issue cannot meet is excused with a waiver. After an
interrupted re-assessment, the next re-assessment writes the folder it left
again. `docs/generation-store.md` has the details.

Re-assessing is also how a **spike graduates**: the spike's findings become
an input to a fresh assessment for the real delivery work. If the new
assessment puts the issue on the path, remove the `.spike` marker so the TDD strategy is back in
force; if it is still a spike, leave the marker in place.

## Procedure (follows the rubric exactly)

1. **Create the manifest.** First read `.compass/current-task`. If it names
   an issue whose folder `.compass/work/<issue-slug>/` exists, reuse that
   issue and do not make a second one. If not, pick a slug and make
   `.compass/work/<issue-slug>/`. Write `manifest.yml` from
   `${CLAUDE_PLUGIN_ROOT}/templates/manifest.yml` into the folder. This is the
   machine-readable manifest the CLI reads and writes.
1a. **Load project architecture if present.** If the project has an
    `architecture/` directory at the project root, write its narrative files,
    `invariants.yml` and decision records yourself into
    `architecture-loaded.yml` in the issue directory - that file is what
    downstream agents read for architectural context; no CLI verb does this
    yet. A project without one keeps working. Do **not** write load state
    into the manifest's `assessment:` block; that block is the judgment only.

2. **Read the three scored dimensions - this is the judgment** - risk,
   familiarity and size, plus the optional switches (`goal` and `urgency`) and
   the `labels:` domain tags. Each dimension and each switch you set gets a
   value and a one-line justification; labels need none. If a value cannot be justified, ask the user
   rather than guessing. When size is unsure, estimate *up*. Note:
   **exploration goal** - "I cannot state this well enough to deliver it
   yet" - selects a **spike**, and **live-defect urgency** - something is
   broken for users now - is the hotfix setting. Write these into the manifest's `assessment:` block. The assessment
   is the only part of the computation that is judgment - everything below
   is mechanism.
   Apply `auth`, `payments`, `personal-data` or `migrations` whenever the
   change is one of those: these labels, not the risk, bring the sign-off of
   guardrail 5 (`G5`). Critical risk alone does not. When risk is critical
   and none of them is set, `compass approach evaluate` names them under "Pay
   attention to"; check whether the change is one of them before you go on.
3. **Compute the delivery approach - this is the mechanism.** First run
   `compass approach evaluate --issue <slug>` without `--write`, and read
   the evidence it prints. Then run
   `compass approach evaluate --issue <slug> --write --justify
   <dimension>="<why>"` with one `--justify` for each assessed dimension (a
   changed value on a re-run needs a new one; an unchanged value keeps its
   line). The CLI records them under the manifest's `justifications:` key
   and refuses a new or changed value that has none. It applies
   the configuration in force to the assessment: it matches one evidence
   row, adds what the labels, the risk and the configuration add, and
   writes `delivery_approach` (`delivery`, or `spike`), `evidence_required`,
   `gates` (status pending), `acceptance_strategy`, `checkpoints` and
   `policy_rules_fired` to `manifest.yml`. It writes no `stages:` map: the
   four stages are fixed. You do not select the evidence or apply a policy
   rule by hand - same assessment + same configuration => same evidence,
   every time. If the assessment is a misclassification, the CLI fails
   loudly; re-read the dimension it rejected.
4. **Read back the evidence.** Run `compass approach show`. Its evidence
   line lists what the change owes before it ships, and it is what the
   person confirms in step 7. The manifest is the record: Compass writes no
   delivery-approach document and no `devlog.md` for a new issue (ADR-092).
   Nothing is skipped on the path, so there are no de-scope reasons to
   write. The dimensions' justifications and each rule that fired are
   already in the manifest (`justifications:`, `policy_rules_fired:`), so do
   not copy them.

5. **Set the `.compass/current-task` pointer** with `compass issue use
   <slug>`, so every later `compass` call resolves to this issue without an
   `--issue` flag, and another session working on another issue is told
   that the pointer moved.
   If this issue was found while working on another, record that too:
   `compass issue raised-by <parent> --found-at <where>`, where `<where>`
   is `define`, `plan`, `implement`, `verify`, `review`, `ci` or
   `after-landing` (the CLI keeps these values; `define` and `plan` are
   found while specifying, `implement` while building, `verify` at ship).
6. **On a spike, write the `.spike` marker.** If the CLI's approach is
   `spike`, create an empty marker file at `.compass/work/<issue-slug>/.spike`.
   The approach-aware pre-tool hook reads this to know the TDD strategy is
   suspended for this issue (the hook does not block code edits). Do **not**
   create this marker on a delivery issue.
7. **Confirm.** The assessment is advisory until confirmed. Present the
   evidence line, invite override of any *dimension*, and if a dimension
   changes, re-run `compass approach evaluate --write --justify DIM="..."` -
   never hand-edit the computed evidence. Name who asked for the override,
   and why, in its `--justify` reason, which the manifest keeps.
   Immovable gates and floors cannot be overridden; changing one means a
   reviewed change to the project's `compass.yml` (`docs/configuration.md`),
   not overriding one issue's evidence. A loosening needs a waiver that the
   project's owner approves.
   Wait for the confirmation only if `assess` is in the manifest's
   `checkpoints:`, which the project's `autonomy` setting in
   `compass.yml` decides (or `.compass/config.yml` in a project without
   one). If it is not listed, present the
   evidence line, say you are going on without waiting and name the setting,
   and record the passed hand-off with `compass issue checkpoint add assess
   --outcome skipped --by router`. If `assess` is listed, ask with `compass
   evidence request --checkpoint assess`; the person types `/compass:approve`, or
   runs `compass evidence approve --checkpoint assess --approver <name> --role
   <role>` at a terminal, which records the answer. An issue assessed before
   outcomes were recorded is not judged: both commands refuse it and write
   nothing, so say so and go on.

## Voice

Assess output is read by a person deciding what happens next, not narrated
to them. State the assessment and the evidence it owes - never which stage
you are entering. See `skills/compass-runtime/writing-voice.md`.

## Gate

`manifest.yml` exists with an `assessment:` block and a CLI-computed
`delivery_approach`, `evidence_required` and `gates`; every dimension has a
justification; `.compass/current-task` points at the slug. On a spike, the
`.compass/work/<issue-slug>/.spike` marker exists. Then follow the `next:`
line that `compass next` prints.
