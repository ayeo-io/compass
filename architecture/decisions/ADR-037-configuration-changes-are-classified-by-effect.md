---
id: ADR-037
title: A configuration change is classified by its effect over the assessment grid
status: accepted
date: 2026-10-06
supersedes: ''
superseded_by: ''
---

## Context

The maintainer accepted this record on 2026-10-06.

ADR-033 (projects add checks, gates and dimension values as data) lets a project, and a single issue, change the shipped configuration. A change that adds process is free; a change that removes process needs an approved waiver. ADR-035 (delivery approaches, stages and modes are configuration data) applies the same rule to stages, modes and gates. Both rest on one question: is a layer stricter or less strict than its parent?

The shape of an edit does not answer it. A rule's effect depends on every other rule and on the assessment:

- a new rule that raises a minimum can change nothing, because another rule already raises further;
- an issue that picks a heavier delivery approach can owe fewer checks, because the lighter one carried a gate the heavier one lacks;
- a new rule tried first can stop a floor's rule from matching without deleting the floor;
- a check can keep its id and widen what it accepts.

The evaluator is deterministic (Inv-7) and reads the assessment only through `when:` predicates (`reading_matches`, `cli/compass_pkg/core.py:848`) and the vocabulary check. The shipped `assessment_vocabulary` (`governance/routing-policy.yml:273-281`) has 4 risk, 3 familiarity, 5 size, 2 goal, 2 urgency and 5 role values: 1,200 closed assessments. Labels are an open set.

## Decision

**A classifier compares a child layer with its parent and returns one of four classes:**

- `equivalent`: every point owes the same;
- `tightening`: no point owes less, and at least one owes more;
- `loosening`: at least one point owes less, and no point owes more;
- `incomparable`: anything else, including one point that owes less and another that owes more, or a change no order decides.

`equivalent` and `tightening` need nothing. `loosening` and `incomparable` refuse without an approved waiver, and the refusal names the first point and field where the layer is less strict, with the parent value and the new value.

**Both configurations are evaluated over the assessment grid.** The grid is every closed assessment (1,200 today) crossed with every subset of the labels that any predicate in either configuration names. At each point the classifier calls the same evaluator that assess calls, under each configuration, and compares the obligations each produces: stage modes, entry and exit checks, the gate set and each gate's checks and accepted evidence types, artifacts owed and their depth, required skills, blocked stages, checkpoints per autonomy setting, ceilings, and each active check's compared fields. An evaluator refusal is an outcome: two identical refusals are equal, and anything else at that point is incomparable. The delivery approach chosen and the rules that fired are not obligations and are not compared.

**Values no predicate can tell apart are grouped, exactly.** Two values of a dimension fall in one class when every predicate in both configurations gives them the same answer, and one value per class is evaluated. This is exact, not a sample: two assessments that answer every predicate the same way produce the same obligations. Each closed dimension runs over the union of both configurations' values. A value only one side has is incomparable where a predicate reads it. A test runs the grouped and the full grid over every classifier fixture and must get the same result. Another test records every assessment read the evaluator makes and checks that the collected predicates cover it. Computed from the predicates in the shipped `routing-policy.yml` and `guardrails.yml`, today's grid has 288 grouped closed points of 1,200, and 4 named labels (`auth`, `payments`, `personal-data`, `migrations`): 4,608 grouped points of 19,200.

**At most eight named labels.** Above eight named values across all set-typed dimensions, the classifier does not sample. It classifies the layer `incomparable` and says why, with the count (`governance/decisions/2026-10-06-label-cap-stays-at-eight.md`). At eight labels the raw grid is 307,200 points.

**Fields compare by fixed rules:**

| Field | Stricter when |
|---|---|
| Ordered: stage mode by `rank`, severity, `on_skipped`, artifact depth | higher in the declared order |
| Obligation set: entry and exit checks, gates, gate checks, artifacts owed, required skills, blocked stages, required artifacts, checkpoints, a check's `inputs` | a superset |
| Way set: `accepts`, `reviewers`, a check's `approvers` (who may tick a human check, not the layer's waiver approvers of ADR-039) | a subset (the reverse order) |
| Ceiling or parameter, including a `params` value | as its owner declares (`tighter: higher`, `lower` or `none`): the check registry for a check parameter, the field table for every other ceiling; `none` is the default, and makes any change incomparable |
| `kind`, `impl`, any enum value; `statement` of a `human` or `judged` check | never: any change is incomparable |

A way set lists ways to satisfy an obligation, so more members is less strict. An absent `reviewers` is the widest set, any agent session. An absent `approvers` is also the widest, so removing the list is loosening. A check that keeps its id but changes its definition compares by its definition, not its id.

**One field table serves the classifier and locks.** The table above is held once, as data. A lock (ADR-039, waivers, locks and unlocks) refuses exactly what this classifier calls loosening or incomparable on the locked entry's fields, so the two cannot disagree about what counts.

**A delivery approach's `weight` is never read by the classifier.** Weight orders approaches for the evaluator's floors. What an approach owes is compared through its obligations, so a heavier approach that owes less is caught.

## Alternatives considered

- **Classify by the shape of the edit.** Each operation would get a class: removing a gate loosens, adding a check tightens, raising a weight tightens. Rejected: the shape says nothing reliable about the effect. A rule that raises a minimum can change nothing, a heavier approach can owe fewer checks, and a rule tried first can disable a floor without touching it. An edit-shape classifier would excuse each of these.
- **Sample the grid: each label alone and all labels together.** Rejected: a loosening can appear only at one combination, such as two labels together without a third. A sample cannot prove "strict everywhere", and a waiver exemption must not rest on one.
- **Compare only at the issue's own assessment.** Rejected: a project layer applies to every future assessment, so one point says nothing about the rest. `compass issue configure` still prints the result at the issue's own assessment as extra information.
- **No classifier: every change to a shipped entry needs a waiver.** Rejected: a project that only adds process would need approvals for every change, and the approvals would stop meaning anything.

## Consequences

- "Stricter everywhere" is proved over the grid. The claim holds only while every predicate is collected, which the coverage test checks.
- Lint cost grows with points times rules. Lint stops once it has found one looser and one stricter point; `compass policy diff` scans the whole grid. A benchmark must time the grouped and raw grid at four and eight labels before the classifier ships, and the label cap is revisited only with its numbers.
- A ninth named label makes a layer incomparable, so it needs a waiver even when it only adds process.
- A ceiling with no declared direction is incomparable on any change. A lower review-round ceiling limits cost and also reduces the chances to correct a defect, so it is not tightening by itself.
- Every new obligation field must be added to the one field table, or a change to it reads as `equivalent`.

## References

- ADR-033: the classifier is the third of four mechanisms its decision depends on; locks are the fourth.
- ADR-035: the format whose changes are classified.
- ADR-036 (an issue runs against a stored generation of its configuration): each generation stores the classification of each layer.
- `cli/compass_pkg/routing.py` (`evaluate_route`), `cli/compass_pkg/core.py` (`reading_matches`), `governance/routing-policy.yml`.

## Amendment (2026-10-07): where a ceiling that is not a check parameter declares its direction

Proposed while the maintainer was away, and marked for the maintainer's confirmation. The decision above already allows `higher` or `lower`; it left open where a ceiling that has no check registry entry declares one.

- The field table declares it, as `CEILING_DIRECTIONS` in `cli/compass_pkg/catalogue_spec.py`, beside `OBLIGATION_FIELDS`, so the classifier and locks read one table. The caller's `directions` argument overrides it in tests only, and a loader must never fill it from project data.
- Lower is stricter for the subtask ceiling, the worktree cap and the three budget ceilings (`run_cost_usd`, `run_minutes`, `run_cycles`). No ceiling at all is the loosest.
- The four correction loops (`builder_attempts`, `review_rounds`, `replans`, `repeated_error`) and any ceiling a project adds stay `none`, for the reason in the consequences above.

## Amendment (2026-10-07): which modules may import `obligations`

Decided while the maintainer was away, and marked for the maintainer's confirmation. The code kept one reader of the obligation comparison, and a test (`test_ob_8_only_classify_and_effective_read_the_new_path`) enforces it.

- `classify` and `effective` may import `obligations`. No other module may.
- `effective` holds the configuration an issue runs against, so it is the one place that turns it into the evaluator's policy (`EffectiveView.evaluator_policy()`, which calls `obligations.policy_adapter`). The modules that read governance call the effective view and never import `obligations` themselves.
- The test finds an import in any form, including a parenthesised list, and a planted import in a third module makes it fail.

## Amendment (2026-10-08): a check's `when` reads one derived key, `ships`

Decided while the maintainer was away, and marked for the maintainer's confirmation. The ruling on the spike's Definition of Done asked for a `when` that keeps a spike from owing the Definition of Done, and said that a predicate that cannot name the approach needs a comparison rule.

- `obligations` evaluates a check's `when` and `blocking_when` against the assessment plus one derived key, `ships`: whether the approach the route chose ships (`obligations.listing_assessment`). The goal is optional, so a `when` on it cannot say "not exploration".
- No comparison rule is added. `ships` adds no field to the table. The classifier already evaluates each check's `when` at every grid point through `obligations`, so removing `when: {ships: true}` from a check shows as the spike owing that check, which is tightening.
- The same derived reading is used wherever the configuration is evaluated against an assessment: a check's `when` and `blocking_when`, a guardrail gate's `when` (in `obligations` and in `compass check`), and the stage lists.
- `ships` is not a dimension. The grid does not vary it, and it follows from the approach the other readings route to.
