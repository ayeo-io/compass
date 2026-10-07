# Routing Policy - How the Delivery Approach Is Bounded and Biased

Assess (see `approaches/rubric.md` for the sizing rubric) reads the four
assessment dimensions and computes the delivery approach. This file
governs that computation, using
the same split as the rest of `governance/`:

- **Routing rules** - hard. They *bound* what assess may do. A
  routing rule can force a delivery approach to be at least a certain weight,
  cap how far it may scale up, or add a gate that no delivery approach may
  remove. Assess cannot bypass these, and a human cannot override them
  per-issue - changing one means amending this file.
- **Routing strategies** - soft. They *bias* what assess does by default -
  the delivery-approach shapes it reaches for, the way it breaks ties. A
  routing strategy is the starting point; assess (or a human) can depart from
  it for a given issue, and that departure is just recorded in
  `delivery-approach.md`.

This is the answer to the obvious objection to any adaptive framework - *"if
the process can flex, what stops it flexing to nothing?"* The routing
rules are what stop it. The flex is real, and it is bounded by this file.

To see every delivery approach at once - its stage weights, the stages that
wait for a person, its gates and its documents - open
`docs/approach-diagram.html`. `compass approach diagram` generates it from
the policy, and a test fails when the committed copy is out of date. Run it
in a project to see that project's own policy and autonomy setting.

Assess applies this policy after reading the four dimensions
and composing a candidate delivery approach, before writing `delivery-approach.md`. Every routing
rule that fires is recorded in `delivery-approach.md` with its rationale - so any
`delivery-approach.md` shows not just the delivery approach, but which bounds were active and why.

**This document explains; `routing-policy.yml` enforces.** The companion
`governance/routing-policy.yml` is the machine-readable, authoritative policy -
it has the live floors, caps, immovable gates, role rules, and default shapes,
each with a stable id, and `compass approach evaluate` runs it deterministically.
The YAML excerpts below are *illustrative*; where this prose and that file
could be read to differ, the `.yml` wins. The crucial boundary: the
four-dimension *assessment* is judgement (assess produces it, and that
judgement is the adaptivity); this policy governs only what happens *after* -
composing and constraining the delivery approach from the assessment, which is deterministic.

---

## Routing rules (hard - they bound assess)

### `floors` - an assessment value forces *at least* a given approach

A floor says: "when the context looks like X, the delivery approach may not
be lighter than Y." Floors are how domain risk overrides the raw dimension
assessment - the canonical case is that size reads a one-line auth change as
`atomic`, but a floor forces it heavier because the risk of auth is not a
function of line count.

### `caps` - limits on scaling up

The mirror of floors. Where a floor stops the delivery approach going too
light, a cap stops it going too heavy in a way that adds risk. The default
cap - critical risk caps worktrees at 1 - encodes a real tradeoff: multiagent
orchestration is faster, but it is also coordination risk, and on a critical
change the coordination risk costs more than the speed saves.

### `immovable_gates` - gates no delivery approach may remove

Delivery approaches adapt *which* review dimensions apply. Immovable gates
are the floor under that adaptation: no assessment value, and no delivery
approach, can drop one.

### blocking `role_rules` - a role's involvement enforces a gate

When a role's involvement makes a gate non-negotiable, that is a routing
rule. The two defaults wire the non-engineering roles in as enforced
participants, not optional consultees.

The shipped defaults (see `routing-policy.yml` for the live, id-tagged set):

- **floors** - `RP-FLOOR-001` critical risk → at least the full approach,
  never skip refine/verify/ship; `RP-FLOOR-002` brownfield-unmapped familiarity
  at standard size or more, with cross-cutting or critical risk, or with one
  of the four domain labels → define
  runs full-weight with `behaviour-mapping` (below that, `RP-ADV-002` gives
  the skill as advice); `RP-FLOOR-003`
  touching auth/payments/personal-data/migrations → at least the full approach.
- **caps** - `RP-CAP-001` critical risk caps worktrees at 1.
- **immovable_gates** - `RP-GATE-001..003`: `verify.correctness`,
  `verify.governance`, `verify.traceability`. Deliberately not here:
  `verify.regression` is scoped by the delivery approach and
  `verify.claims` by the role in play, so neither is immovable.
- **role_rules** - `RP-ROLE-001` the product-marketer's involvement blocks shipping
  until claims trace to scenarios; `RP-ROLE-002` the product-owner's involvement
  gates Plan on the spec being checked against `intent.md`.

The `verify.governance` immovable gate is what makes `G5` (a human signs off
on the irreversible) hold: a change labelled with an irreversible surface is
floored to the full approach, where the human checkpoint is part of the gate set.

---

## Routing strategies (soft - they bias assess)

These are the assess stage's defaults: the delivery-approach shapes it
reaches for, and how it breaks ties. Assess starts here and tunes; a
departure is normal and is recorded in `delivery-approach.md`, not punished.

```yaml
routing_strategies:
  # The reference shapes triage composes toward. See approaches/.
  # These mirror governance/routing-policy.yml; the live file also carries an
  # `id:` and a `rationale:` per entry, which the evaluator reports when a
  # shape fires.
  default_shapes:
    - when: { size: [atomic, small], risk: [trivial, contained] }
      lean_toward: quick-fix
    - when: { size: standard }
      lean_toward: regular
    - when: { size: [large, product] }
      lean_toward: full
    - when: { urgency: live-defect, size: [atomic, small] }
      lean_toward: hotfix
    - when: { goal: exploration }      # "I need to understand this before I can scope it"
      lean_toward: spike

  # Tie-breaking biases.
  biases:
    - "When size is genuinely unclear, estimate up - it is cheaper to
       collapse a stage that turned out easy than to discover mid-implementation
       that the approach was too light."
    - "A non-engineering role in play usually pulls the route heavier, because
       it adds artifacts and assessed strategies - but this is a bias, not a
       floor. A marketer glancing at a tiny change need not trigger the full approach."
    - "Prefer the lightest route that still clears the routing guardrails and
       the applicable gates. Process weight is a cost; spend it where it buys safety."

  # Advisory role defaults (the blocking versions are routing guardrails above).
  role_defaults:
    - when: { role: designer }
      suggest_artifact: ui-contract.md
      rationale: "A new user-facing surface usually wants a UI contract; advisory."
```

---

## Checkpoints (soft - they set when a session waits)

A checkpoint is a stage hand-off where a session stops and waits for a
person: assess step 7 (confirm the approach), and the define, refine and plan
hand-offs. `compass.yml` (or `.compass/config.yml` in a project without one) sets `autonomy: controlled | balanced |
autonomous` (balanced when left out). The `autonomy_checkpoints:` table maps
each value and route to the checkpoints that wait, and the evaluator writes
the answer into the manifest as `checkpoints:`.

| Route | controlled | balanced | autonomous |
|---|---|---|---|
| quick fix | assess | none | none |
| regular | assess, define, refine, plan | define, plan | none |
| full | assess, define, refine, plan | assess, define, refine, plan | none |
| hotfix | assess, define | none | none |
| spike | assess | none | none |

- A stage the route collapses or skips has no hand-off, so it never waits.
- A hand-off that does not wait still writes its document, shows its
  summary, names the setting and logs the skipped checkpoint to `devlog.md`.
- The table can name only the four checkpoint stages. `compass policy lint`
  and the evaluator refuse anything else, so the setting cannot reach a gate,
  evidence, the pre-tool hook, `compass check`, guardrail 5 or the sign-off
  the domain labels bring.
- An `autonomy` value that is not one of the three is refused, not read as
  balanced.
- A policy without the table, or a table that leaves out a value or a
  route, waits at every hand-off the route runs. Only a route listed with an
  empty list never waits. Route keys are the current route names, and a
  retired name (`express`, `standard`, `expedition`, or `feature` and
  `initiative` before 5 October 2026) is read as its current one; an unknown route, or one route named twice, is refused.

## Schema reference

The authoritative structure is `routing-policy.yml`, validated by `compass
policy lint` - against the executable `schemas/routing-policy.schema.json`
(when `jsonschema` is installed) and the CLI's built-in linter. The
human-readable field-by-field companion is `schemas/routing-policy.reference.yml`.
In brief:

`when` conditions match against the assessment - `risk`, `familiarity`,
`size`, `goal`, `role`, `urgency` - or `labels_any` (a domain-tag list:
`auth`, `payments`, `personal-data`, `migrations`, `public-api`, …). A list
value means "any of".

A policy written before the v2 freeze keeps working: the evaluator maps the
retired dimension names on read, so an unmigrated project file still
matches. Write the current names in anything new.

The evaluator refuses an `assessment:` key that
`schemas/manifest.schema.json` does not allow, such as `risk_reason`, before
it writes anything. `compass check` and `compass issue lint` refuse the same
keys, with or without `jsonschema` installed.

Routing-rule keys: `force_minimum_route`, `require_phase`,
`require_skill`, `never_skip`, `max_worktrees`, `forbid_route`,
`block_phase` + `until`, `require_artifact`, `add_gate`, `gate`. Every rule
carries a stable `id` (e.g. `RP-FLOOR-001`) so `delivery-approach.md` can
name exactly which one fired.

Routing-strategy keys: `lean_toward`, `suggest_artifact`, free-text `biases`.

---

## Amending this file

- **Loosening a routing rule weakens the framework for everyone,
  quietly.** It should be deliberate, logged, ideally reviewed - not a
  convenience edit mid-issue. If a rule keeps being painful, fix the delivery
  approach that makes it painful; do not remove the rule.
- **Routing strategies are meant to be tuned.** Adjust `default_shapes` and
  `biases` freely as the team learns how its work actually distributes. That
  is the soft layer doing its job.

## The default preset

`governance/presets/default/` holds the same defaults in catalogue form, one
file per catalogue, with `preset.yml` and `evidence-types.yml`
(`architecture/decisions/ADR-042-shipped-defaults-live-in-a-preset-directory.md`).
`cli/compass_pkg/legacy_adapter.py` produced it from `routing-policy.yml` and
`guardrails.yml`, and `tests/test_default_preset.py` fails when the preset and
the two files stop matching. Nothing reads the preset yet. Until the increment
that makes `routing-policy.yml` a generated view, change the defaults in
`routing-policy.yml` and `guardrails.yml` and regenerate the preset with
`write_preset` in the adapter.

`governance/legacy-views.yml` holds what the two files contain that the
catalogues have no field for. Only the generator of the views will read it,
and it goes with the views at 7.0.0.

The conversion changes these things, and the test rebuilds the two files
from the preset and `legacy-views.yml` to show nothing is lost:

- `checked_at` keeps its first stage as the gate's `stage`; the full list is
  in `legacy-views.yml`.
- The floor effect `force_minimum_route` becomes `force_minimum_approach`
  (ADR-041).
- Old dimension names and old stage names (`clarify`, `build`, `land`)
  become the current names; `legacy-views.yml` keeps the
  spelling each file uses.
- A document named by file (`intent.md`) becomes its id (`intent`).
- The fallback approach becomes the last rule of `default_shapes`, and the
  `biases` become a rule set with no effect.
- Each check gets an `on_skipped` value from what it returns when it cannot
  run. The replay against the archive sample is in
  `tests/test_obligations.py` and is described below.

## What a configuration owes an assessment

`cli/compass_pkg/obligations.py` computes the facts the classifier compares
for one resolved configuration and one assessment: stage modes, entry and
exit checks, the gate set with each gate's checks and accepted evidence
types, artifacts and their depth, required skills, blocked stages, required
artifacts, checkpoints for each autonomy value, ceilings and each active
check's compared fields. It does not route. `policy_adapter` turns the merged
catalogues into the dictionary `evaluate_route` takes, and the evaluator
answers. Nothing reads this path yet, and `compass approach evaluate` still
reads `routing-policy.yml`.

The evaluator took four additions, and a call that uses none of them answers
as before:

- `stage_mode_ranks` in the policy (stage, then mode, then rank). A floor's
  lift raises a mode ranked below `full` and leaves a mode with no rank, or
  one ranked equal to `full` or above, alone. Without the key the lift is the
  fixed set `collapsed`, `skipped` and `light`, which is what the shipped ranks
  reproduce
  (`governance/decisions/2026-10-06-stage-mode-ranks-cover-the-depth-ladder-only.md`).
- `dimension_orders` in the policy (dimension, then its values in ascending
  order). A `when:` clause with `at_least` reads the configuration's order.
  Without the key the shipped orders of risk and size apply.
- `issue`, an issue's own layer, applied in the order
  `governance/decisions/2026-10-05-floors-win-over-the-issue-layer.md` fixes.
  It names the candidate, replaces the candidate's base stage modes and can
  lower the subtask ceiling. The floors, caps and role rules apply after it,
  so a floor lifts a mode the issue lowered, and a floor that replaces the
  candidate drops the issue's modes (the result lists them as ignored). A cap
  lowers an issue's ceiling and an issue never raises one.
- `RoutingConflict`, the error class of the two refusals: exploration that a
  floor would turn into delivery, and an approach a cap forbids. A caller that
  compares policies treats these as results (`Refused`). Every other error is
  a fault in an input and raises.

The evaluator applies one hit policy to each effect, and it does not read a
declared one. `policy_adapter` raises when a rule set declares a different
hit policy. It also raises for an approach outside the five the evaluator
knows, and for a `ships` value that differs from the one it assumes. These
three guards go when the evaluator takes the catalogue form.

Two replays tie the new path to today's behaviour, and each has a planted
fault that makes it fail:

- The adapted preset routes the 1,200 assessments of the compatibility
  baseline, their label subsets and the archive assessments as today's policy
  does. The two values the catalogues spell differently differ in spelling
  only: a document is its id (`intent`, not `intent.md`) and a stage is its
  current name (`ship`, not `land`). The replay takes the stage names from the
  table in `core`.
- The preset's `on_skipped` values give today's verdicts on the archive
  sample for the nine checks that decline. The four checks a `landed_by`
  pointer stands down (`scenarios-have-tests`, `suite-passed`,
  `scenario-has-id-and-intent`, `gate-evidence-present`) differ in 16 cases:
  today they report nothing to check when the pointer holds, and `on_skipped`
  says `fail`. The caller of the check path applies that relaxation, and the
  increment that moves `compass check` to the resolved configuration decides
  where it lives. The test pins the four names and fails on a fifth.

What the stage-mode rank replay shows:

- The ranked lift gives today's answer over the whole baseline.
- A rank of 2 on `reproduce-first` is reported, because a floor names `define`.
- A rank below `full` on `expedited` is not reported over today's policy,
  because no floor names `implement` and the lift never reaches that stage.
  With one floor added to both paths that names it, the same rank is reported.
- A dropped floor or gate is reported.
