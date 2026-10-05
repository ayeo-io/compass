# The full assess procedure

Read by `/compass:assess` when the change is not a small one an engineer
is making, when `compass quick-fix start` computed a heavier approach, or
on `--reassess`. The light path stays in `commands/assess.md`.

Assessing is the one stage that never skips. It reads the four assessment
dimensions - that is **judgement** - and then hands them to the CLI, which
**computes** the delivery approach deterministically. You do not pick a
process, and you do not compose the approach in your head: you assess the
work, record the assessment, and `compass approach evaluate` applies
`governance/routing-policy.yml` to produce the approach. This is the
determinism boundary - see `docs/methodology.md` §2.

Assess works on day one with **zero project setup**: the shipped default
guardrails, strategies, and routing policy apply as-is, so `/compass:init` is
optional and not a prerequisite. If a project has run `/compass:init`, its
`governance/` extends those defaults - read whichever is in force.

The issue is the one `/compass:assess` was given.

## First: make sure this is a Compass project

Run `compass init`. It creates `.compass/` if it is not there and reports that
it did; if the project already exists it says so and changes nothing, so this
is safe to run every time and you do not need to check first.

**Report the result to the user in one line when it created the project.** A
`.compass/` directory appearing with no word said is how someone deletes it by
hand, or commits it without meaning to. It creates project state only - the
shipped governance defaults stay in force, and adopting your own is what
`/compass:init` offers separately.

## Setup

- Load the `adaptive-routing` skill - it is the procedural companion to the
  delivery-approach rubric (`${CLAUDE_PLUGIN_ROOT}/approaches/rubric.md`).
- Read `governance/routing-policy.md` for the *why*. The machine-readable
  `governance/routing-policy.yml` is what `compass approach evaluate` actually
  runs: the CLI applies its **policy floors, caps, immovable gates, and
  blocking role rules** (hard) and its **default shapes and
  tie-breaking biases** (soft). You do not apply these by hand; the CLI does.
- Read `.compass/config.yml` for project settings (test command, multiagent
  worktree root). Routing rules are not here - they live in
  `routing-policy.yml`.
- For a non-trivial or ambiguous issue, invoke the `router` agent to read
  the four dimensions.
- If a `intent.md`, `ui-contract.md`, or `positioning.md` already exists for
  this issue, read it - intent is the *outcome wanted*, not just the literal
  request.

## `--reassess`

If `--reassess` is passed, this is a re-assessment during the work, not a new
assessment - typically because implementation revealed the assessment was
misread. Read the existing `delivery-approach.md` and `manifest.yml`, re-read the
four dimensions, update the manifest's `assessment:` block, then re-run
`compass approach evaluate --write --reason "..."` to recompute the approach.
**Always pass `--reason`** on a re-assessment: when the CLI sees the approach
change, it records the event in the manifest's `reassessments:` log, and the
reason is the signal `compass retro` reads. Then write a **new
revision** of `delivery-approach.md` (keep the prior revision visible). A
re-assessment is a normal event. The failure is an issue that outgrows its
approach unrecorded; a re-assessment with no reason gives `compass retro`
nothing to read.

Re-assessing is also how a **spike graduates**: the spike's findings become
an input to a fresh assessment for the real delivery work. If the new approach is
no longer a spike, remove the `.spike` marker so the TDD strategy is back in
force; if it is still a spike, leave the marker in place.

## Procedure (follows the delivery-approach rubric exactly)

1. **Create the manifest.** Pick a slug, make `.compass/work/<issue-slug>/`,
   and write `manifest.yml` from `${CLAUDE_PLUGIN_ROOT}/templates/manifest.yml` into it. This is the
   machine-readable manifest the CLI reads and writes.
1a. **Load project architecture if present.** If the project has an
    `architecture/` directory beside `governance/`, write its narrative files,
    `invariants.yml` and decision records yourself into
    `architecture-loaded.yml` in the issue directory - that file is what
    downstream agents read for architectural context; no CLI verb does this
    yet. A project without one keeps working. Do **not** write load state
    into the manifest's `assessment:` block; that block is the judgement only.

2. **Read the four dimensions - this is the judgement** - risk, familiarity,
   size, goal & role, plus the `labels:` domain tags. Each gets a value and a
   one-line justification. If a value cannot be justified, ask the user
   rather than guessing. When size is unsure, estimate *up*. Note:
   **exploration goal** - "I cannot state this well enough to deliver it
   yet" - leads towards a **spike**, the way live-defect urgency leads towards
   a hotfix. Write these into the manifest's `assessment:` block. The assessment
   is the only part of the computation that is judgement - everything below
   is mechanism.
3. **Compute the delivery approach - this is the mechanism.** Run
   `compass approach evaluate --issue <slug> --write`. The CLI applies
   `routing-policy.yml` to the assessment: it composes the first approach,
   applies the floors, caps, immovable gates, and blocking role rules, and
   folds the resulting `delivery_approach`, `stages`, `gates` (status
   pending), `orchestration`, and `policy_rules_fired` back into `manifest.yml`. You
   do not compose the approach or apply a policy rule by hand - same
   assessment + same policy => same approach, every time. If the assessment
   is a misclassification, the CLI fails loudly; re-read the dimension it
   rejected.
4. **Write `delivery-approach.md`** from `${CLAUDE_PLUGIN_ROOT}/templates/delivery-approach.md`
   into the issue directory, from the CLI's output. It must contain:
   - the four dimensions with justifications;
   - the computed approach;
   - every policy rule the CLI reported as fired (with its rationale);
   - the final per-stage weight, gate set, and orchestration;
   - **the de-scope ledger** - every stage the CLI marked collapsed or
     skipped, each with an explicit "safe to skip because..." line. A stage
     with no justification runs.

   `delivery-approach.md` is the human-readable version of what `manifest.yml`
   records mechanically.
5. **Set the `.compass/current-task` pointer** with `compass issue use
   <slug>`, so every later `compass` call resolves to this issue without an
   `--issue` flag, and another session working on another issue is told
   that the pointer moved.
6. **On a spike, write the `.spike` marker.** If the CLI's approach is a
   spike, create an empty marker file at `.compass/work/<issue-slug>/.spike`.
   The approach-aware pre-tool hook reads this to know the TDD strategy is
   suspended for this issue (the hook does not block code edits). Do **not**
   create this marker on any other approach.
7. **Confirm.** The assessment is advisory until confirmed. Present the
   approach, invite override of any *dimension*, and if a dimension changes,
   re-run `compass approach evaluate --write` - never hand-edit the computed
   approach. Record overrides in `delivery-approach.md` with who and why.
   Immovable gates and floors cannot be overridden; changing one means
   amending `governance/routing-policy.yml`, not overriding one issue's
   approach. Under `/compass:go`, the approach summary it already showed is
   the confirmation: do not stop to wait for one, but act on an override
   whenever the person gives it.
   Wait for the confirmation only if `assess` is in the manifest's
   `checkpoints:`, which the project's `autonomy` setting in
   `.compass/config.yml` decides. If it is not listed, present the
   approach, say you are going on without waiting and name the setting,
   and log the skipped checkpoint to `devlog.md`. `/compass:go` does not
   wait here even when `assess` is listed.

## Voice

Assess output is read by a person deciding what happens next, not narrated
to them. State the assessment and the approach - never which stage you are
entering. See `skills/compass-runtime/writing-voice.md`.

## Gate

`manifest.yml` exists with an `assessment:` block and a CLI-computed
`delivery_approach`/`stages`/`gates`; `delivery-approach.md` exists, every
dimension has a justification, and every skipped stage has a written reason;
`.compass/current-task` points at the slug. On a spike, the
`.compass/work/<issue-slug>/.spike` marker exists. Then start a `devlog.md`
entry and proceed to `/compass:define`.
