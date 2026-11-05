# Routing Policy - How the Delivery Approach Is Bounded and Biased

Assess (see `approaches/rubric.md` for the sizing rubric) scores the three
dimensions and computes the delivery approach. This file
governs that computation, using
the same split as the rest of `governance/`:

- **Routing rules** - hard. They *bound* what assess may do. A
  routing rule can force a delivery approach to be at least a certain weight,
  cap how far it may scale up, or add a gate that no delivery approach may
  remove. Assess cannot bypass these, and a human cannot override them
  per-issue - a project changes one in its `compass.yml`
  (`docs/configuration.md`), and a loosening needs a waiver that the project's
  owner approves.
- **Routing strategies** - soft. They *bias* what assess does by default -
  the delivery-approach shapes it reaches for, the way it breaks ties. A
  routing strategy is the starting point; assess (or a human) can depart from
  it for a given issue, and that departure is just recorded in
  `devlog.md`.

This is the answer to the obvious objection to any adaptive framework - *"if
the process can flex, what stops it flexing to nothing?"* The routing
rules are what stop it. The flex is real, and it is bounded by this file.

To see every delivery approach at once - its stage weights, the stages that
wait for a person, its gates and its documents - open
`docs/approach-diagram.html`. `compass approach render` generates it from
the policy, and a test fails when the committed copy is out of date. Run it
in a project to see that project's own policy and autonomy setting. In a
project with a `compass.yml` it renders the effective configuration, the
`compass.yml` over the shipped default preset, and the page says so. A project
with no `compass.yml` gets the page from `governance/routing-policy.yml`, as
before.

Assess applies this policy after scoring the three dimensions
and composing a candidate delivery approach, before writing the approach to the
manifest. Every routing rule that fires is recorded in the manifest's
`policy_rules_fired:` with its rationale - so `compass approach show --verbose`
shows not just the delivery approach, but which bounds were active and why.

**This document explains; `routing-policy.yml` enforces.** The companion
`governance/routing-policy.yml` is the machine-readable, authoritative policy -
it has the live floors, caps, immovable gates and default shapes,
each with a stable id, and `compass approach evaluate` runs it deterministically.
The YAML excerpts below are *illustrative*; where this prose and that file
could be read to differ, the `.yml` wins. The crucial boundary: the
*assessment* (three scored dimensions, two switches and the domain labels) is judgement (assess produces it, and that
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

A gate a release removed owes nothing. 9.0.0 removed the gate
`verify.analyze` with the command that wrote its evidence (ADR-091).
`routing.REMOVED_GATES` lists it. A frozen preset (`default@6`, `default@7`),
a stored generation or copied governance can still hold the rules
`RP-REQUIRE-001` and `RP-REQUIRE-002`, which add it. The evaluator leaves a
removed gate out of every gate set it writes or prints. A rule whose only
effect was to add one does not fire. A manifest written before 9.0.0 that
lists the gate is not rewritten. `ship-commit`, `compass issue status set`,
and `compass next` read it as owing nothing,
so a pending `verify.analyze` does not keep the issue from landing.

### blocking `artifact_rules` - read, and not fired since 9.0.0

A rule of this set reads the condition `artifacts_any`, the documents of the
issue. Since 9.0.0 no command reads which documents an issue has (ADR-091), so
a rule that names a document does not fire, and a document on disk adds no
gate and blocks no stage. A frozen preset or a stored generation can still
hold such a rule; it is read and does not fire. A stored 6.x
generation keeps its `role_rules` until the issue is re-assessed, and a
project's copied 6.x governance keeps them until `compass policy migrate` runs.

The shipped defaults (see `routing-policy.yml` for the live, id-tagged set):

- **floors** - `RP-FLOOR-001` critical risk → at least the full approach,
  never skip refine/verify/ship; `RP-FLOOR-002` brownfield-unmapped familiarity
  at medium size or more, with cross-cutting or critical risk, or with one
  of the four domain labels → define
  runs thorough-weight with `behavior-mapping` (below that, `RP-ADV-002` gives
  the skill as advice); `RP-FLOOR-003`
  touching auth/payments/personal-data/migrations → at least the full approach.
- **caps** - `RP-CAP-001` critical risk caps worktrees at 1.
- **immovable_gates** - `RP-GATE-001..003`: `verify.correctness`,
  `verify.governance`, `verify.traceability`. Deliberately not here:
  `verify.regression` is scoped by the delivery approach, so it is not
  immovable.
- **artifact_rules** - none from 9.0.0. `RP-ART-001` (a `positioning.md` added
  `verify.claims`) and `RP-ART-002` (an `intent.md` gated Plan) went with the
  documents (ADR-091): no command reads which documents an issue has on disk.
  The frozen presets `default@6` and `default@7` still declare them.

The `verify.governance` immovable gate is what makes `G5` (a human signs off
on the irreversible) hold: a change labelled with an irreversible surface is
floored to the full approach, where the human checkpoint is part of the gate set.
From 7.0.0 the checkpoint's trigger is those four labels only. Critical risk
still floors an issue to the full approach and every other gate, but it does
not bring the sign-off on its own, so `compass approach evaluate` names the
four labels when risk is critical and none is set
(`governance/guardrails.md`).

---

## Routing strategies (soft - they bias assess)

These are the assess stage's defaults: the delivery-approach shapes it
reaches for, and how it breaks ties. Assess starts here and tunes; a
departure is normal and is recorded in `devlog.md`, not punished.

```yaml
routing_strategies:
  # The reference shapes triage composes toward. See approaches/.
  # These mirror governance/routing-policy.yml; the live file also carries an
  # `id:` and a `rationale:` per entry, which the evaluator reports when a
  # shape fires.
  default_shapes:
    - when: { size: [atomic, small], risk: [trivial, contained] }
      lean_toward: quick-fix
    - when: { size: medium }
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
    - "Prefer the lightest delivery approach that still clears the routing guardrails and
       the applicable gates. Process weight is a cost; spend it where it buys safety."
```

---

## Checkpoints (soft - they set when a session waits)

A checkpoint is a stage hand-off where a session stops and waits for a
person: assess step 7 (confirm the approach), the define, refine and plan
hand-offs, and the `implement` and `verify` hand-offs, which end stages 2 and 3 of
the four-layer acceptance strategy (`S17`). `compass.yml` (or `.compass/config.yml` in a project without one) sets `autonomy: controlled | balanced |
autonomous` (balanced when left out). The `autonomy_checkpoints:` table maps
each value and approach to the checkpoints that wait, and the evaluator writes
the answer into the manifest as `checkpoints:`.

| Approach | controlled | balanced | autonomous |
|---|---|---|---|
| quick fix | assess | none | none |
| regular | assess, define, refine, plan, `implement`, `verify` | define, plan | none |
| full | assess, define, refine, plan, `implement`, `verify` | assess, define, refine, plan | none |
| hotfix | assess, define | none | none |
| spike | assess | none | none |

- A stage the approach collapses or skips has no hand-off, so it never waits.
- `implement` and `verify` are listed only where the strategy applies to the
  issue, as `compass approach evaluate --write` stores it. An issue the
  strategy does not apply to lists the other four. Each ends a stage of the
  `atdd` skill: the request for the `refine`, `implement` or `verify` checkpoint of
  an in-scope issue lists the review questions of stage 1, 2 or 3 from
  `skills/atdd/references/stage-reviews.md`.
- At an `implement` or `verify` hand-off with no outcome, `compass next` stops and
  names `compass evidence request --checkpoint <stage>` when the checkpoint is
  listed. When it is not listed and the strategy applies, `compass next` goes on
  and names `compass issue checkpoint add <stage> --outcome skipped --by
  <agent>`. A person who rejects the review with `/compass:reject` sends the
  issue back: `compass next` names that stage, with the reason, until an
  outcome newer than the rejection is recorded. `compass check` does not fail
  on a listed review with no outcome; `compass ship-commit` refuses it.
- A hand-off that does not wait still writes its document, shows its
  summary, names the setting and records its outcome with `compass issue
  checkpoint add <stage> --outcome skipped --by <agent>`. A person's answer to
  a hand-off is recorded with `compass evidence approve --checkpoint <stage>`,
  as a `checkpoint-approval` record and a `waited` outcome; it never meets
  guardrail `G5`. Both outcomes are kept in the manifest's
  `checkpoint_outcomes`, one per stage. `compass ship-commit` refuses an
  issue that lists a checkpoint with no outcome (`checkpoint-no-outcome`).
  Only an issue whose first assessment wrote `checkpoint_outcomes` is judged;
  an issue assessed before outcomes were recorded is never refused, and the
  two commands refuse it.
- The table can name only the six checkpoint stages. `compass policy lint`
  and the evaluator refuse anything else, so the setting cannot reach a gate,
  evidence, the pre-tool hook, `compass check`, guardrail 5 or the sign-off
  the domain labels bring.
- An `autonomy` value that is not one of the three is refused, not read as
  balanced.
- **The readiness floor caps `autonomous`** (ADR-058). `approach evaluate
  --write` refuses, with exit 2 and before it prints or writes anything, an
  issue whose effective autonomy is `autonomous` when:
  - the CI runner reports an untrusted contribution, read from the
    environment before the readiness record, so a committed record cannot
    clear it; no setting lifts this refusal;
  - the readiness record is missing, stale or unreadable;
  - the record was measured for an untrusted contribution; or
  - a readiness signal with `required_for_autonomous: true` is absent.

  Each message names `autonomy` as the setting to change. `balanced` and
  `controlled` are never refused. Without `--write` the default view shows
  whether a write would be refused, and `--json` carries `readiness`. The
  floor is not a gate or a routing rule: it changes no approach, gate or
  checkpoint, and `compass check` never reads it. Every `--write` records the
  readiness summary in the manifest's `readiness:` key. `docs/readiness.md`
  holds the signals and the record.
- A policy without the table, or a table that leaves out a value or an
  approach, waits at every hand-off the approach runs. Only an approach listed with an
  empty list never waits. Approach keys are the current approach names, and a
  retired name (`express`, `standard`, `expedition`, or `feature` and
  `initiative` before 5 October 2026) is read as its current one; an unknown approach, or one approach named twice, is refused.

## Loop ceilings (nothing applies them from 9.0.0)

The `loop_ceilings` rules (RP-LOOP-001 to 008) bounded a multiagent run - tries
per subtask, review rounds, replans and the same error in a row - and the
unattended headless runner - sessions, minutes and money. 9.0.0 removed both
(ADR-090), so nothing applies the limits. The rules stay in the policy, read
by `cli/compass_pkg/loop_ceilings.py`, so the classifier still compares a
layer that changes one, until the configuration layers are replaced.

## Model tiers (removed in 9.0.0)

9.0.0 runs each issue in one session, so no stage hands work to an agent with
its own model or effort (ADR-090). The shipped default holds no `model_tiers`
or `model_floors` rule set, and an assessment writes no `models:` key. A
stored generation that holds the two rule sets still reads, and a `models:`
key an older assessment wrote is left as it is.

## Schema reference

The authoritative structure is `routing-policy.yml`, validated by `compass
policy lint` - against the executable `schemas/routing-policy.schema.json`
(when `jsonschema` is installed) and the CLI's built-in linter. The
human-readable field-by-field companion is `schemas/routing-policy.reference.yml`.
In brief:

`when` conditions match against the assessment - `risk`, `familiarity`,
`size`, `goal`, `urgency` - or `artifacts_any` (the documents present for
the issue, such as `positioning` or `intent`) or `labels_any` (a domain-tag list:
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
carries a stable `id` (e.g. `RP-FLOOR-001`) so the manifest's
`policy_rules_fired:` can name exactly which one fired.

Routing-strategy keys: `lean_toward`, `suggest_artifact`, free-text `biases`.

---

## Changing routing

A 6.0.0 project does not edit this file or `routing-policy.yml`, which is
generated (see "The default preset" below). Routing changes go in the
project's `compass.yml`; `compass policy lint` checks them and
`compass policy show` prints the result. A project that copied these files
under 5.x edits its copy until `compass policy migrate` converts it.

- **Loosening a routing rule weakens the framework for everyone,
  quietly.** It needs a waiver that the project's owner approves, and it should
  be deliberate, logged, ideally reviewed - not a convenience edit mid-issue.
  If a rule keeps being painful, fix the delivery approach that makes it
  painful; do not remove the rule.
- **Routing strategies are meant to be tuned.** `default_shapes` and `biases`
  are rule sets in the default preset, and a project changes them through
  `rules:` in its `compass.yml` as the team learns how its work actually
  distributes. `compass policy lint` reports any change that loosens the
  default, and that change then needs a waiver. That is the soft layer doing
  its job.

## The default preset

`governance/presets/default/` holds the same defaults in catalogue form, one
file per catalogue, with `preset.yml` and `evidence-types.yml`
(`architecture/decisions/ADR-042-shipped-defaults-live-in-a-preset-directory.md`).
`cli/compass_pkg/legacy_adapter.py` produced it once from `routing-policy.yml`
and `guardrails.yml`. The preset is now the source of the shipped defaults, and
the two files are views generated from it.

Each artifact in `artifacts.yml` names the stage that owns it with `stage:`
(`architecture/decisions/ADR-050-artifact-status-is-written-by-stage-exits-and-by-a-persons-approval.md`).
A stage command that writes a later record approves the artifacts of earlier
stages. An artifact with no `stage` is owned by ship. The check
`artifacts-approved` that judged them was removed in 9.0.0 (ADR-091).
`evidence-types.yml` holds the type `artifact-approval`, which no gate accepts.
`compass approach evaluate --write` merges the registry by kind and round, so every
round of a kind that repeats survives a reassessment. It never marks a voluntary entry
(a kind no approach, rule or `every_approach` flag names) as `superseded`
(`architecture/decisions/ADR-054-an-artifact-kind-can-repeat-keyed-by-round.md`).

The live preset is version 8.0.0. It carries the four-layer acceptance
strategy (`S17`): the advisory check `acceptance-applicability-agrees` in
`checks.yml`, and `acceptance_strategy` on each approach in `approaches.yml`,
which sets the strategy to `on` for regular and full, `existing-dsl` for
quick-fix and `existing-dsl-isolation` for hotfix. An approach without the key
reads `on` when it ships and `suspended` when it does not, so the locked spike
entry, which ships nothing, stays as it was and reads `suspended`. The classifier does not compare the field
(compare kind `never`), because the project setting `acceptance_strategy`
turns the whole strategy off with no approval. `compass approach evaluate
--write` stores the issue's applicability from it, as the strategy's entry in
`governance/strategies.md` says. The 7.0.0 preset is kept, byte for byte as v8.0.4 shipped it, in
`governance/presets/default@7/` for `compass policy update`; resolution reads
only the live preset, whatever major a project's `extends:` names. So the pin
decides instead: a project whose `compass.yml` extends `compass:default@6` or
`@7` stores no applicability at assess and gets no row from the strategy's
check. `compass policy lint` refuses `acceptance_strategy: suspended` on an
approach that ships (`M-ACCEPTANCE-SUSPENDED`); the settings key is the one way
to turn the strategy off (decided by jed72, 2026-10-30).

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
items and the seven Definition of Done items. The preset is the only place
their text lives: 9.0.0 writes no requirements review or verification report
to hold them (ADR-091), and `tests/test_ready_and_done_data.py` fails when a
statement names a removed document. The `plan` stage's `entry` list holds the first
seven and the `verify` stage's `exit` list holds the second seven. Each check
needs the capability `entry-exit-evaluation`, which is off in `default@6`,
so `compass check` does not run them and the two views do not name them (a
legacy `checks:` entry needs an implementation). A Definition of Ready check
returns `not-applicable` when its stage is skipped, because a collapsed or
skipped refine meets it by construction. A Definition of Done check returns
`fail`, as `dod-evidence-typed` does. Each Definition of Done check says
`when: {ships: true}`, so an approach that does not ship, the spike, owes none
of them when the capability is on. `ships` is a key that evaluation derives
from the approach, not a dimension. `docs/entry-exit-evaluation.md` states
how the lists run once the capability is on.

Before 9.0.0 an approach owed documents, such as the intent and the
requirements review on the regular approach (ADR-065, ADR-072). 9.0.0 owes
none but the acceptance criteria (ADR-091); a stored generation keeps its own
set. Quick fix, regular, hotfix and
full set the approach field `release_line: true`: an issue whose stored
generation sets it owes a release line, and every landing refuses it while its
manifest's `release_note` holds none (`docs/release-line.md`). The spike, which
is locked, has no such field. The field is compared `false` below `true`, so a
project that sets it `false` on an approach that has it loosens the approach
and needs a waiver (ADR-039). The decision is
`architecture/decisions/ADR-065-regular-issues-owe-an-intent-and-shipping-issues-record-a-release-line.md`.

`governance/legacy-views.yml` holds what the two files contain that the
catalogues have no field for. Only the generator of the views reads it, and it
goes with the views at 9.0.0.

The conversion changes these things, and the test rebuilds the two files
from the preset and `legacy-views.yml` to show nothing is lost:

- `checked_at` keeps its first stage as the gate's `stage`; the full list is
  in `legacy-views.yml`.
- The floor effect `force_minimum_route` becomes `force_minimum_approach`
  (ADR-041).
- Old dimension names and old stage names (`clarify`, `build`, `land`)
  become the current names. `legacy-views.yml` spells stages with the current
  names; the migration reads a copy's retired names as the current ones.
- A document named by file (`intent.md`) becomes its id (`intent`).
- The fallback approach becomes the last rule of `default_shapes`, and the
  `biases` become a rule set with no effect.
- Each check gets an `on_skipped` value from what it returns when it cannot
  run. The replay against the archive sample is in
  `tests/test_obligations.py` and is described below.

## The evidence rows

From 9.0.0 assess selects the evidence a change owes, not a delivery
approach. `cli/compass_pkg/evidence_required.py` computes it: a pure function
of the assessment and the configuration in force. It returns the ordered
`evidence_required` list, the gate ids derived from it, the routing of the
four-layer acceptance strategy (`S17`) and the rules that fired. No command
calls it yet; the writer of the four-stage path will.

The rows, first match wins:

| Rule | When | Evidence | `S17` routing |
|---|---|---|---|
| `RP-EVID-SPIKE` | goal `exploration` | none; gate `spike.conclude` | `suspended` |
| `RP-EVID-LIGHT` | size atomic or small, risk trivial or contained, urgency not `live-defect`, no `G5` label | every-issue tokens | `existing-dsl` |
| `RP-EVID-DEFECT` | urgency `live-defect`, size atomic or small, risk not critical, no `G5` label | every-issue tokens, `regression`, `security`, `definition-of-done` | `existing-dsl-isolation` |
| `RP-EVID-STANDARD` | any other delivery assessment | every-issue tokens, `regression`, `security`, `clarity`, `definition-of-done` | `on` |

The every-issue tokens are `scenarios`, `red-before-green`, `suite-green`,
`correctness`, `governance` and `traceability`. The additions to a delivery
row:

| Rule | When | Adds |
|---|---|---|
| `RP-REQUIRE-003` | risk cross-cutting or critical | `architecture` |
| `RP-REQUIRE-004` | a `G5` label | `architecture` |
| `RP-EVID-REPRODUCE` | urgency `live-defect`, at any size | `reproduce-first` |
| `RP-EVID-SIGNOFF` | a `G5` label, or risk critical | `scenario-approval` |
| `G5` | a `G5` label | `human-approval` |

The `G5` labels are `auth`, `payments`, `personal-data` and `migrations`.
Exploration with critical risk or a `G5` label is refused, as in 8.x: a spike
must not touch a surface that owes a person's sign-off.

The `S17` tokens are `outer-loop` (any routing), `isolation` (routing `on` or
`existing-dsl-isolation`) and `layering` (routing `on`). They are left out
when the project turns the strategy off, or when assess is told
`--expected-acceptance validation` or `refactor`.

The configuration adds only what a project can still set for a new issue:
the gate of each floor that matches (`add_gate`) and each immovable gate, the
skill a floor asks for (`require_skill`, such as `behavior-mapping` from
`RP-FLOOR-002`) and the advisory strategies. A gate that a token stands for
joins as that token, so `gates` stays derived from `evidence_required`. The
function never reads the configuration's approaches, shapes, stage modes or
caps. Familiarity does not change the evidence.

The rows reproduce the gate sets 8.0.4 owed: the light row is the old quick
fix (3 gates), the defect row the old hotfix (5 gates) and the standard row
the old regular and full approaches (6 gates). The `S17` routings are those
the 9.0.0 preset names for the same approaches. `tests/test_evidence_required.py`
checks this on all 1,200 assessments of the contract 1 grid under each of the
16 subsets of the `G5` labels, against the 8.0.4 governance copy in
`tests/fixtures/v8.0.4-governance.tgz`.

## What a configuration owes an assessment

`cli/compass_pkg/obligations.py` computes the facts the classifier compares
for one resolved configuration and one assessment: stage modes, entry and
exit checks, the gate set with each gate's checks and accepted evidence
types, artifacts and their depth, required skills, blocked stages, required
artifacts, checkpoints for each autonomy value, ceilings and each active
check's compared fields. It computes no approach. `policy_adapter` turns the merged
catalogues into the dictionary `evaluate_route` takes, and the evaluator
answers. `compass approach evaluate` reads the same resolved configuration: an
issue's stored generation, or else the `compass.yml` over the shipped default,
and `--verbose` prints which. Only an issue with no `generation:` in a project
with no `compass.yml` reads `routing-policy.yml`: the generated view, or in an
unmigrated 5.x project the project's own copy.

The evaluator took four additions, and a call that uses none of them answers
as before:

- `stage_mode_ranks` in the policy (stage, then mode, then rank). A floor's
  lift raises a mode ranked below `thorough` and leaves a mode with no rank, or
  one ranked equal to `thorough` or above, alone. Without the key the lift is
  the fixed set `collapsed`, `skipped` and `lightweight`, which is what the shipped ranks
  reproduce
  (`governance/decisions/2026-10-06-stage-mode-ranks-cover-the-depth-ladder-only.md`).
- `dimension_orders` in the policy (dimension, then its values in ascending
  order). A `when:` clause with `at_least` reads the configuration's order.
  Without the key the shipped orders of risk and size apply.
- `issue`, an issue's own layer, applied in the order
  `governance/decisions/2026-10-05-floors-win-over-the-issue-layer.md` fixes.
  It names the candidate, replaces the candidate's base stage modes and can
  lower the subtask ceiling. The floors, caps and artifact rules apply after it,
  so a floor lifts a mode the issue lowered, and a floor that replaces the
  candidate drops the issue's modes (the result lists them as ignored). A cap
  lowers an issue's ceiling and an issue never raises one.
- `waived_stages` in `issue`: the stages whose entry in the issue's layer
  holds an issue waiver. Such a stage keeps the issue's mode on an approach a
  floor raised, so an owner-approved solo build of a `migrations` issue is
  recorded as `breakdown: skipped`. A floor's `never_skip` and
  `require_phase` still lift the stages they name, and the gates, guardrails,
  artifacts and forced approach do not change. When the issue's layer or
  assessment changes, the reassess lints the layer at the issue's own
  assessment, and refuses the waiver unless its approval record is valid
  (ADR-039)
  (`governance/decisions/2026-10-17-a-waived-stage-mode-holds-on-a-floor-raised-approach.md`).
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

- The adapted preset gives the 1,200 assessments of the compatibility
  baseline, their label subsets and the archive assessments the approach
  today's policy gives them. The two values the catalogues spell differently differ in spelling
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
- A rank below `thorough` on `expedited` is not reported over today's policy,
  because no floor names `implement` and the lift never reaches that stage.
  With one floor added to both paths that names it, the same rank is reported.
- A dropped floor or gate is reported.

## How two configurations are compared

`cli/compass_pkg/classify.py` compares a child configuration with its parent
by what each owes, as `architecture/decisions/ADR-037-configuration-changes-are-classified-by-effect.md`
decides. It calls `obligations` for both at every point of the assessment grid
and compares the facts. Given `at=` an assessment, `classify` compares at that
one point instead (`grid_at`, a grid of one point). The lint, the locks and the
preview compare an issue's own layer that way, at the issue's own assessment,
and a project layer over the grid. Nothing reads it yet, so no command prints its
result. `classify(parent, child)` returns a `Classification`, and the later
`policy` commands print `json.dumps(classification.to_json(), indent=2)` and
build their text from the same dictionary.

The grid:

- A closed dimension runs over the union of both configurations' values.
  Values that no predicate in either configuration can tell apart are one
  class, and one value of the class is evaluated. The shipped policy has 72
  grouped closed points and, with its four named labels and the two documents
  its artifact rules read, 4,608 grouped points of 34,560 raw points. The raw count includes an assessment that omits each
  optional dimension (`goal` and `urgency` in the shipped preset); the
  evaluator needs only `risk`, `familiarity` and `size`. An omitted dimension is
  a value of its own, so a rule that reads it is told apart from every value.
  `exhaustive=True` runs every raw point. It is an argument of `classify`, and
  the later `policy` commands expose it as a flag.
- A value only one configuration accepts is its own class. Where a predicate
  reads it, the point is `incomparable`. Where none does, the class is left
  out of the grid, because no assessment holds in both configurations.
- The named labels are the labels any predicate names, and the named
  documents are the kinds any `artifacts_any` condition names. Every subset of
  each is a point. More than eight named labels, or more than four named
  documents, classify the layer `incomparable` with the count and no scan, even for two configurations that differ in nothing else, except
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
  A readiness parameter's direction comes from the readiness registry:
  `higher`, `lower`, `none` or the direction `equivalent`. `equivalent` is
  declared on `tests-under-limit.command` only. A changed value of such a
  parameter is `equal` when both sides name the same implementation, both
  values are present and both are in the implementation's `choices`, and
  `incomparable` otherwise; it is never `tighter` or `looser`. The registry
  refuses `equivalent` on a parameter with no `choices`, the check registry
  refuses it on every parameter, and a catalogue or preset cannot declare it.
  A readiness parameter one side leaves out is `incomparable` whatever its
  direction: the classifier fills in no runtime default, and this rule raised
  `CLASSIFIER_VERSION` to 5 (governance decision
  2026-10-14-a-declared-equivalent-parameter-choice-classifies-as-equivalent).
  An approach's `release_line` is compared at each point for the approach the
  assessment chose, `false` below `true`, with no field read as `false`, so
  setting it `false` is `looser`. That rule raised `CLASSIFIER_VERSION` to 6
  (ADR-065).
  A check parameter that is a list can declare the direction `superset`. Only
  `trigger_paths` and `trigger_contents` of `contracts-declared` did, and 9.0.0
  removed that check (ADR-091), so no shipped check declares it now. The
  classifier compares each side as a set of exact entries. A `trigger_contents`
  entry is the pair of path glob and text, compared whole, and the classifier
  does not judge how broad a glob is. Neither reordering a list nor repeating
  an entry changes the set, so the change is `equal`. A project list that holds
  every shipped entry and at least one more is `tighter`, because a trigger
  path makes the check run, so more entries check more changes. A project list
  that lacks a shipped entry and adds none is `looser`, because fewer entries
  check fewer changes. A project list that lacks a shipped entry and adds
  another is `incomparable`. A list that is missing, is not a list, or holds a
  malformed entry is `incomparable` and raises no error. The registry refuses
  `superset` on a parameter that is not a list. `CLASSIFIER_VERSION` is 13
  since the list rule (ADR-073), the rule that a check a release removed
  owes nothing (ADR-090) and the same rule for a review gate (ADR-091).
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
          "points": 4, "raw_points": 16, "evaluated": 4, "artifacts": []},
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
  the policy it reads (`routing.canonical_view`), evaluates once for all autonomy
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
