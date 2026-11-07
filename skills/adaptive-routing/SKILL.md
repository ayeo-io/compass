---
name: adaptive-routing
description: Reading the three scored dimensions for the CLI. Load at the assess stage.
---

# Adaptive Routing

This skill is the craft behind `approaches/rubric.md`. `approaches/rubric.md`
holds the rules; this skill says how to apply them.

## The mental model

You are not picking a process. Every delivery issue runs the same four
stages: assess, specify, build and ship (`approaches/path.md`). What you
compute is the evidence the change owes before it ships. The assessment has
three scored dimensions (`risk`, `familiarity`, `size`), two switches
(`goal`, `urgency`) and any domain labels. The three scored dimensions are
three independent questions. The CLI matches one evidence row from them,
and the switches and labels add to it: `goal: exploration` selects the
spike, `urgency: live-defect` is the hotfix setting, and a domain label adds
gates and sign-offs. The configuration in force can add evidence, never
remove it. Its prose is in
`${CLAUDE_PLUGIN_ROOT}/governance/routing-policy.md` (an unmigrated 5.x
project runs on its own copied `governance/`).

## The shipped defaults are enough - you work with them

`/compass:init` is optional. The fixed check set carries active
default guardrails, default strategies, and a default routing policy, and the
plugin holds their prose in `${CLAUDE_PLUGIN_ROOT}/governance/`. A project can
only add to it, with the tighten-only settings of its `compass.yml`;
`compass policy show` prints what is in force, except that an unmigrated 5.x project runs on its own copied
`governance/` until `compass policy migrate` on 8.x. If a project has no `compass.yml` and no project-specific additions,
that is a valid, complete governance state - you route against the shipped defaults <!-- vocabulary-scan: allow - route is a verb here -->
exactly as you would route against an extended set. <!-- vocabulary-scan: allow - route is a verb here -->
"assess and go on day one"
is honest precisely because the defaults are real, in-force content. Never
treat a project without a `compass.yml` as missing a prerequisite.

## Scoring the dimensions - heuristics

**risk** - *consequence, never effort.*
- The sign of `critical`: can this lose data, lose money, breach auth/privacy,
  or resist a clean rollback? If yes, it is critical even if it is one line.
- Critical risk alone does not bring the human sign-off of guardrail 5
  (`G5`); the labels do. When the change is one of them, apply `auth`,
  `payments`, `personal-data` or `migrations` as well as the risk. A
  migration that can lose data is labeled `migrations`, whatever its risk.
- The sign of `trivial`: is the worst case cosmetic, instantly obvious, and
  instantly reversible - with no data, money, auth, or other team touched?
- The common mistake: scoring risk by how hard the change is. A hard
  change can be contained; a trivial-looking change can be critical. Score the
  failure, not the work.

**Familiarity** - *new code, or old code, and is the old code mapped?*
- `brownfield-unmapped` is not a judgment of code quality - it means the
  behavior is not written down as scenarios. It does not change the
  evidence. At medium size or more, with cross-cutting or critical risk, or
  with a domain label, it triggers a floor (`RP-FLOOR-002`):
  `behavior-mapping` must run at specify. Do not skip it. On
  an atomic or small change with trivial or contained risk and no domain
  label, the skill is advice (`RP-ADV-002`).
- "Trivially readable" greenfield or brownfield can be treated as mapped, but
  be honest - "I could figure it out" is not "it is written down."

**Size** - *the dimension humans get wrong most.*
- People under-estimate size far more than they over-estimate it. When
  genuinely torn between two values, take the higher one. Giving evidence
  that turned out easy to give is cheap; discovering during the build that
  the evidence selected was too light is expensive and demoralizing.
- Anchor on concrete tests: `atomic` is one file and no design decision;
  `medium` has one or two design decisions; `large` has real architecture and
  is plausibly parallelisable.

**The switches** - *`goal` and `urgency` are read, not scored.* Either can
be left out. `goal: exploration` selects the spike; `urgency: live-defect`
is the hotfix setting, which adds `reproduce-first` and, on an atomic or
small fix, selects the defect row. Set it only for something broken for
users now. Each switch you set still needs a `--justify`. Domain labels need
none.

**Goal** - *the actual outcome, not the literal request.*
- Read the intent the product owner gave, if any. "Add a CSV export" under an
  intent that says "let finance self-serve" may need filters, scheduling, and permissions - the
  literal request under-describes the intent.
- Role is not scored. A document on disk adds no gate: Compass needs and checks
  only `acceptance-criteria.md` (ADR-091).
- One goal value is **exploration** - "I cannot frame this well
  enough to deliver it yet." Exploration selects the **spike**, the one
  approach that is not on the path. Still score all three dimensions; the
  switch is what selects the spike. See "The spike" in `composition.md`.

If you cannot justify a value in one honest line, **ask the human.** An
unjustified guess is worse than a question, every time.

## Selecting the evidence

The CLI does it. You score the three dimensions, read the two switches and
the domain labels, and run
`compass approach evaluate --write --justify DIM="<why>"`, with one
`--justify` for each new or changed dimension or switch, or
`compass quick-fix start` with each value and its reason. It matches the
evidence row and adds what the labels and the configuration add. That split
is the determinism boundary and it is the point of the whole design:
judgment produces the assessment, mechanism produces the evidence.

The detail - including the spike - is in
`skills/adaptive-routing/composition.md`, for when a result needs
explaining. `--verbose` names the row that matched and every rule that
fired.

## Nothing is skipped on the path

The path has no stage modes, so there is no stage to collapse or skip and
no de-scope ledger to write, and the path writes no `devlog.md` (ADR-092).
What a light change leaves out is the
evidence it does not owe, and the `evidence_required` list in the manifest
is the record of that. `compass approach show` prints it on one line.

### Anti-patterns

- **An assessment scored low to owe less** - a risk or size read down to
  "just get the change in." `compass approach show` makes this visible; do
  not do it.
- **A time-saving justification** - a `--justify` reason that is "to save
  time." Time is not a safety argument. The reason must say why the value is
  true of the change, not why it is convenient.
- **Silent constraint** - adding or omitting a gate without a line in the
  manifest's `policy_rules_fired:`. Only the CLI writes the gates.

## When to re-assess

Re-assessing during an issue is a normal event, not a failure. Trigger it when:

- The build reveals the size was under-read - a "small" change is growing
  into a multi-module refactor.
- Specify finds the spec is bigger or more ambiguous than the assessment
  assumed.
- A label surfaces late (you discover the change reaches auth).

Run `/compass:assess --reassess`: re-score the dimensions and record what changed and
why in the manifest's `reassessments:` log. An assessment quietly outgrown is
the failure; an assessment honestly re-assessed is the system working.
