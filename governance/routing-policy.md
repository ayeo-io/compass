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
in a project to see that project's own policy and autonomy setting. In a
project with a `compass.yml` it renders the effective configuration, the
`compass.yml` over the shipped default preset, and the page says so. A project
with no `compass.yml` gets the page from `governance/routing-policy.yml`, as
before.

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
`cli/compass_pkg/legacy_adapter.py` produced it once from `routing-policy.yml`
and `guardrails.yml`. The preset is now the source of the shipped defaults, and
the two files are views generated from it.

- Change a default in the preset (or in `legacy-views.yml` for a value only the
  views hold), then run `python3 scripts/generate-legacy-views.py`.
  Never edit `routing-policy.yml` or `guardrails.yml` by hand: their first
  lines say so, and `tests/test_default_views.py` fails with the command to
  run when a view differs from what the generator writes. A changed default
  also needs the file's `version:` raised, which lives in `legacy-views.yml`
  under `routing_policy` or `guardrails`, and the content-hash fixture
  `tests/fixtures/governance-content-hashes.json` re-recorded with
  `python3 scripts/generate-legacy-views.py --pin-hashes`
  (`tests/test_governance_drift.py` fails until both are done).
- `python3 scripts/generate-legacy-views.py --check` writes nothing and exits 1
  on a stale view.
- The comments, banner, vocabulary-scan markers and layout of the two views are
  in `cli/compass_pkg/legacy_views_template.py`. Change a comment there, then
  regenerate. The values come only from the preset and `legacy-views.yml`.
- `tests/fixtures/preset-digests.yml` pins a digest for each preset file and
  for the whole preset. `tests/test_preset_digests.py` fails when a preset file
  changes without its pin moving; pin again with
  `python3 scripts/generate-legacy-views.py --pin`. A pin is kept for each
  preset version, so a re-pin updates the current entry and leaves the
  earlier ones.
- The mutation-proof register test and the plain-language check read the
  checks and the guardrail statements from the preset.

The preset also holds checks of kind `human`: the seven Definition of Ready
items and the seven Definition of Done items. Each statement is the text of
the template item (`templates/requirements-review.md` and
`templates/verification-report.md`), and `tests/test_ready_and_done_data.py`
fails when either differs. The `plan` stage's `entry` list holds the first
seven and the `verify` stage's `exit` list holds the second seven. Each check
needs the capability `entry-exit-evaluation`, which is off in `default@6`,
so `compass check` does not run them and the two views do not name them (a
legacy `checks:` entry needs an implementation). A Definition of Ready check
returns `not-applicable` when its stage is skipped, because a collapsed or
skipped refine meets it by construction. A Definition of Done check returns
`fail`, as `dod-evidence-typed` does.

`governance/legacy-views.yml` holds what the two files contain that the
catalogues have no field for. Only the generator of the views reads it, and it
goes with the views at 7.0.0.

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
answers. Only the classifier reads this path, and `compass approach evaluate` still
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

## How two configurations are compared

`cli/compass_pkg/classify.py` compares a child configuration with its parent
by what each owes, as `architecture/decisions/ADR-037-configuration-changes-are-classified-by-effect.md`
decides. It calls `obligations` for both at every point of the assessment grid
and compares the facts. Nothing reads it yet, so no command prints its
result. `classify(parent, child)` returns a `Classification`, and the later
`policy` commands print `json.dumps(classification.to_json(), indent=2)` and
build their text from the same dictionary.

The grid:

- A closed dimension runs over the union of both configurations' values.
  Values that no predicate in either configuration can tell apart are one
  class, and one value of the class is evaluated. The shipped policy has 288
  grouped closed points and, with its four named labels, 4,608 grouped points
  of 51,840 raw points. The raw count includes an assessment that omits each
  optional dimension (`goal`, `urgency` and `role` in the shipped preset); the
  evaluator needs only `risk`, `familiarity` and `size`. An omitted dimension is
  a value of its own, so a rule that reads it is told apart from every value.
  `exhaustive=True` runs every raw point. It is an argument of `classify`, and
  the later `policy` commands expose it as a flag.
- A value only one configuration accepts is its own class. Where a predicate
  reads it, the point is `incomparable`. Where none does, the class is left
  out of the grid, because no assessment holds in both configurations.
- The named labels are the labels any predicate names. Every subset is a
  point. More than eight classify the layer `incomparable` with the count and
  no scan, even for two configurations that differ in nothing else, except
  that identical configurations are `equivalent` without a scan.
- Each fact is compared by the kind the field table gives it
  (`catalogue_spec.OBLIGATION_FIELDS`). A field the table omits is not
  compared. A stage only one side has is compared by existence: adding one is
  `tighter` and removing one is `looser`, even a stage in mode `skipped`. Two
  modes with one rank, a mode with no rank and a value outside its order cannot
  be compared. A ceiling's direction is declared in `CEILING_DIRECTIONS` in
  `catalogue_spec.py`: lower is stricter for the subtask ceiling, the worktree
  cap and the three budget ceilings (`run_cost_usd`, `run_minutes`,
  `run_cycles`), and no ceiling at all is the loosest. The four correction
  loops and a ceiling the table omits have no direction, so any change to
  them is `incomparable`. A check parameter's direction comes from the check
  registry. A check that is renamed with an identical definition is
  `incomparable`, because a check keeps its id.
- `stages.order` and `gates.stage` are the footprint of a lock, not facts the
  classifier reads. Reordering an unlocked stage or moving a gate to another
  stage reads `equivalent` here, and the locks increment compares both.

The verdicts are `equivalent`, `tightening`, `loosening` and `incomparable`.
A point is `equal`, `tighter`, `looser` or `mixed`.

`Classification.to_json()` is a public document. It has the same fields in
the same order for every verdict, and a point that does not exist is `null`:

```json
{"schema": 1, "result": "equivalent", "reason": "every point owes the same",
 "scan": "full", "parent": "default@6", "child": "project",
 "exhaustive": false, "complete": true,
 "grid": {"labels": [], "label_count": 0, "label_cap": 8,
          "points": 4, "raw_points": 16, "evaluated": 4},
 "counts": {"equal": 4, "tighter": 0, "looser": 0, "mixed": 0},
 "first_looser": null, "first_tighter": null, "first_mixed": null}
```

- `scan` is `full`, `early-exit`, `identical` or `cap`, so a consumer can tell
  a scan from a shortcut: `identical` compared nothing because the inputs
  are equal, and `cap` compared nothing because more than eight labels are
  named. `parent` and `child` are what the caller passed as `parent_name` and
  `child_name` (or `null`), and the classifier reads them for nothing else.

- A point in `first_looser`, `first_tighter` or `first_mixed` holds
  `assessment` (the closed dimensions in catalogue order, then `labels`),
  `represents` (the values the point stands for; `null` is an assessment that
  omits the dimension), `outcome`, `summary` and
  `changes`.
- A change holds `fact`, `field` (a key of the field table, or
  `evaluation.refused` or `dimensions.values`), `key` (the stage, gate, check,
  artifact or ceiling it is about, or `null`), `outcome` (`tighter`, `looser`
  or `incomparable`), and the `parent` and `child` values as plain JSON.
- `points` is the number of points the run uses, `raw_points` the ungrouped
  count, and `evaluated` how many were compared. They are 0 when the cap
  stops the run. `complete` is false when early exit stopped the scan.
- `JSON_SHAPE` in the module is the shape, `json_shape_errors` checks a
  document against it, and `tests/fixtures/classifier-json-example.json` is the
  pinned example. A change to the shape fails `tests/test_classifier.py`, and
  adding a field raises `schema`.

`scripts/bench-classifier.py` times the grouped grid and, with `--raw`, the
full grid at four and eight labels. It prints the clock and the CPU time of the
process, and the CPU time is the figure to read the targets against: the clock
moves with the load of the machine. The numbers belong in the pull request that
changes the classifier.

Speed has three targets, on the benchmark machine:

| Case | Target |
|---|---|
| A changed layer at the four labels the shipped policy names | 5 s or less |
| A changed layer at eight labels | 30 s or less |
| An unchanged layer | no scan |

The measures taken, in this order, and the ones not allowed:

- **A stored classification.** `classify_stored(store, parent, child, ...)`
  returns the result held in `store` (a mapping the caller owns) when the same
  two configurations, capabilities, issue layers, directions and scan were
  classified before. The key (`classification_key`) holds a digest of each side,
  `CLASSIFIER_VERSION`, and every table the comparison reads, so a changed rule
  table or registry makes a new key. Raise `CLASSIFIER_VERSION` when a change to
  the comparison, the grid or the evaluator can change a verdict:
  `tests/test_classifier_speed.py` pins the functions that decide one, so a
  change to them fails until the author has decided. An entry that is not a
  classification is scanned again, and a function passed as `tighter` is never
  stored. `Classification.from_json` reads a stored document back.
- **One evaluator call for each side at a point.** The evaluator copies none of
  the policy it routes (`routing.canonical_view`), routes once for all autonomy
  values (only the checkpoints differ, `routing.route_checkpoints`), and the
  scan builds each side's policy once (`obligations.Preparation`).
  Points where both sides owe the same are not compared field by field.
- Not allowed: sampling the grid, deciding a refusal at the issue's own point,
  raising the label cap without numbers, and skipping a dimension without a
  test that proves the skip exact. Each of the other measures the ruling lists
  (one cache shared across layers, fixed chunks, a progress line) is held back
  until the numbers need it.

`classify.scan(parent, child, grid, on_point=..., **options)` is the one loop
over a grid. `classify` and the lock check both run through it, and the
callback receives each point and the `Scan`, whose `obligations(side,
assessment)` and `ctx` it can read.
