---
id: ADR-070
title: Role is not an assessment dimension, and the documents on disk bring the claims gate and the intent block
status: proposed
date: 2026-10-16
supersedes: ''
superseded_by: ''
---

Proposed by the architect for remove-role-from-assessment on 2026-10-16, from ayeo-io/compass-delivery-record#149, "Remove role from assessment and routing; keep the roles as consulted perspectives", which jed72 wrote on the same day.

## Context

Role was one of the assessment dimensions: `engineer`, `product-owner`, `product-marketer`, `designer` or `qa`. It is the only dimension that describes who is in the room rather than the change, and the only one the evaluator cannot check. A misread role routes silently, against the policy's rule that a misclassification fails loudly.

What role did in the engine stood in for "these documents are in play":

- RP-ROLE-001, for a marketer, added `verify.claims`, required `launch-readiness.md` and blocked the ship stage until every claim in `positioning.md` traced to a passing scenario.
- RP-ROLE-002, for a product owner, blocked the plan stage until the spec was checked against `intent.md`.
- RP-SROLE-001, for a designer, suggested `ui-contract.md`.
- The full approach built `verify.claims` in, because a marketer was probably involved.

Four earlier decisions bound the answer:

- ADR-001: the assessment is judgement and everything after it is mechanism.
- ADR-006: older records keep working.
- ADR-036: an issue runs against its stored generation, and a CLI upgrade never changes an open issue.
- ADR-037: a configuration change is classified by its effect at every assessment a rule can tell apart.

## Decision

1. **Role leaves the shipped default.** The preset's dimensions, its rules and its biases no longer name a role, and neither does the generated routing policy view. The product-owner, product-marketer and designer stay as perspectives a session consults, with their entry points, the way `architect` already is.
2. **Document presence is a derived reading.** `compass approach evaluate` reads which of the issue's documents are on disk: a kind whose registry entry names a path that resolves to a file, or whose file is at the kind's home. It passes them to the evaluator as `artifacts`, beside the assessment and never inside it. A rule reads them with the condition `artifacts_any`, matched as `labels_any` is. A configuration cannot declare a dimension named `artifacts`.
3. **Two artifact rules replace the two blocking role rules.** They form a rule set of kind `artifact-rules`. RP-ART-001 fires when `positioning` is present: it adds `verify.claims`, asks for `launch-readiness` and blocks the ship stage until every claim traces to a passing scenario. RP-ART-002 fires when `intent` is present and blocks the plan stage until the spec is checked against it. RP-SROLE-001 is dropped; its advice is in the behaviour-mapping guidance.
4. **The full approach does not build in `verify.claims`.** The gate is owed only where a positioning document is.
5. **A stored or copied 6.x policy keeps its role rules.** The evaluator's one pass for document rules reads the `artifact_rules` block and, where a stored generation or copied governance holds one, the `role_rules` block. When the policy in force declares no `role` dimension, the evaluator drops `role` from the readings before matching. An issue moves to the new rules at its next reassessment.
6. **The classifier crosses documents as it crosses labels.** The grid gains a set axis of the document kinds the conditions name. The cap of eight named labels is unchanged, and the grid names at most four documents, so no layer that names eight labels today is refused. The classifier version is 7.
7. **The 6.x inputs keep working.** `--justify role=` and `quick-fix start --role` are accepted, record nothing and say so on standard error. A preset fixture's `role` is ignored with a note. `compass issue migrate` lists a recorded `assessment.role` as no longer read and leaves it. `governance/legacy-views.yml` maps each retired rule id to its replacement, and `policy migrate` and the merge name the replacement when a project edited a retired rule. `policy lint` refuses a project rule that reads `role` unless the project declares that dimension itself.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| A check at ship that demands `verify.claims` when `positioning.md` exists | The check reads the disk at the moment it matters | A gate added outside the evaluator is invisible to the classifier, so deleting the rule would be reported as equivalent |
| An assessment dimension `documents` | One more key in a known place | Presence is a fact the CLI reads, not judgement (ADR-001) |
| Encode presence as labels such as `has:positioning` | No new axis in the grid | A person writes labels, so one could be typed to fake a document |
| Delete the role-rule pass | The issue says routing loses it | An in-flight issue with a stored generation would lose its plan block without a word (ADR-036) |
| Delete the role flags | Nothing reads the value | Adopters pass them; deleting a flag is the maintainer's decision |

## Consequences

**Positive:**
- The claims gate and the intent block follow documents a check can see, whoever wrote them.
- An engineer on the full approach no longer clears a claims gate with nothing to check.
- An issue with a stored generation, and a project on copied governance, keep their routing on upgrade.

**Negative:**
- A document written after the last evaluation takes effect at the next one, so a positioning document added mid-flight needs a reassessment.
- An open issue with no stored generation, in a project with a `compass.yml`, takes the new default at once: a recorded role stops routing it.
- The classifier grid is four times larger for the shipped default, which names two document kinds.

**Neutral / follow-on:**
- The rubric and docs still say "four dimensions". A separate issue rewords them as three scored dimensions, two switches and domain labels.
- Deleting `--justify role=` and `quick-fix start --role` waits for the maintainer.
- A ship-time check that refuses a positioned issue whose gate set lacks `verify.claims` can follow.

## References

- ADR-001, ADR-004, ADR-006, ADR-007, ADR-036, ADR-037, ADR-039, ADR-053.
- `governance/routing-policy.md` owns the rules; `docs/upgrade-7-0-0.md` says what an adopter does.
