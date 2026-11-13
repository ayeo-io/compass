# Selecting the evidence, and the spike

This file describes what `compass approach evaluate` does; a session does not
do it by hand. `approaches/composition-reference.md` covers the same ground
from the configuration's side; this is the reading that goes with the skill.

## How the evidence is selected

The four stages are the same for every delivery issue, so the CLI computes
no stage weights. It computes the `evidence_required` list:

- **One row matches every delivery issue** (`RP-EVID-COMMON`): `request`,
  `scenarios`, `red-before-green`, `suite-green`, `correctness`,
  `governance`, `traceability` and `ship-approval`. Risk, familiarity, size
  and urgency add no review and no record.
- **Two additions apply on top, each a person's approval.**
  `scenario-approval` (the person approves the scenarios at specify) for a
  `G5` label or critical risk; `human-approval` (the `G5` sign-off) for a
  `G5` label.
- **The configuration adds** the tokens of each `require_evidence` rule that
  matches, the gate of each floor of the project's own, each immovable gate
  and project guardrail, and the skill a floor asks for. The records of the
  four-layer acceptance strategy (`S17`) are owed only where a rule adds
  `outer-loop`, `isolation` or `layering`.

`${CLAUDE_PLUGIN_ROOT}/governance/routing-policy.md`, "The evidence rows", holds the exact
conditions and tokens (an unmigrated 5.x project is refused until it
migrates).

The configuration also names advisory strategies, such as "when size is
unclear, estimate up". A strategy is a starting point, not a verdict:
depart from one when the issue warrants, and say why in the `--justify`
reason of the value it touches.

## The spike

When goal reads `exploration`, the CLI selects the **spike** - the approach
for work you cannot yet state as delivery. Set `goal: exploration` when
*all three* hold: the goal is genuinely exploration, not delivery; the work
is a question rather than a known change; and nothing irreversible is in
scope.

What is different about a spike:

- **The TDD strategy (red-before-green) is suspended.** Red-before-green is
  the wrong discipline for code written precisely to learn something and
  likely thrown away. The approach-aware pre-tool hook does not block on a
  spike - it reads a `.compass/work/<issue-slug>/.spike` marker file.
  **Assess writes that marker when the CLI selects a spike**; without it the
  hook will still block.
- **It runs assess, build and ship, with no specify stage.** A spike has no
  acceptance criteria - its output is knowledge. Assess writes down the
  question and the timebox; build explores; ship concludes.
- **Nothing lands from a spike.** The only exit that keeps code is
  *graduating* - re-assessing onto the path, where the tested-before-ship,
  acceptance-before-code and traceability guardrails apply in full. This is
  what makes suspending the TDD strategy safe: a spike cannot put untested
  code on `main`, because it has no way to `main` at all.
- A question that can only be answered by touching irreversible surface
  (`auth`, `payments`, `personal-data`, `migrations`) is **not** a spike:
  assess refuses exploration with a `G5` label or critical risk.

## The configuration bounds the evidence

The configuration in force (explained in
`${CLAUDE_PLUGIN_ROOT}/governance/routing-policy.md`; an unmigrated 5.x
project is refused until it migrates) can add evidence, never remove
it. The evaluator records every rule that fires *with its rationale* in the
manifest's `policy_rules_fired:`. Never apply a constraint silently - a
reader of `compass approach evaluate --verbose` must see which rules were
active.

A person can override an assessment value per issue: re-run the evaluation
with the new value and its reason, and the evidence follows. A person
cannot override a floor or an immovable gate per issue. A project can add a
floor with a reviewed change to its `compass.yml` (a tighten-only setting,
`docs/configuration.md`), never remove one. Excusing one check on one issue
needs a waiver a person approves (`docs/waivers.md`).
