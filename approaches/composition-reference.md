# How the evidence is computed

Assess does not load this file.

This describes what `compass approach evaluate` does: how the evidence a
change owes is computed from the assessment and the configuration in force.
A session does not do any of it by hand - that is the determinism boundary.
The CLI computes; you score the dimensions and run the command.

Read this when you tune a project's `compass.yml`, or when you need to
understand why the CLI returned the evidence it did. `compass approach
evaluate --verbose` names the row that matched and each rule that fired for
any assessment, and that is usually the faster answer.

## One path, and the evidence on it

Every delivery issue runs the same four stages: assess, specify, build and
ship (`approaches/path.md`). The stages have no modes, so nothing about them
is computed. What is computed is the `evidence_required` list, and from it
the gates, the four-layer acceptance strategy (`S17`) block and the
checkpoints. `cli/compass_pkg/evidence_required.py` holds the function. It is
a pure function: the same assessment and the same configuration give the
same list, every time.

The computation, in order:

1. **Match one row.** The spike row for `goal: exploration`; the light row
   for a small change with trivial or contained risk; the defect row for a
   small fix under `urgency: live-defect`; the standard row for every other
   delivery assessment.
2. **Apply the additions.** Cross-cutting or critical risk and the `G5`
   labels add `architecture`; a `G5` label or critical risk adds
   `scenario-approval`; a `G5` label adds `human-approval`; `urgency:
   live-defect` adds `reproduce-first`.
3. **Add the `S17` tokens** the row's routing owes, unless the project turns
   the strategy off or assess is told `--expected-acceptance validation` or
   `refactor`.
4. **Add what the configuration adds.** Each floor that matches adds its gate
   (`add_gate`) or asks for a skill (`require_skill`, such as
   `atdd` from `RP-FLOOR-002`). Each immovable gate and project
   guardrail is added. The advisory strategies are listed.

The function never reads a configuration's approaches, shapes, stage modes
or caps. A frozen preset or a stored generation can still hold them; they
stay valid for the issues assessed under them and are not read for a new
assessment. Familiarity does not change the evidence.

The rows, the additions and the tokens of each are in
`governance/routing-policy.md`, "The evidence rows". This file does not copy
them.

## The review dimensions by row

The gates are the review dimensions. A row owes the gate of each dimension
it lists:

| Dimension | Light row | Defect row | Standard row | Spike |
|---|---|---|---|---|
| correctness | yes | yes | yes | - |
| governance | yes | yes | yes | - |
| traceability | yes | yes | yes | - |
| regression | - | yes | yes | - |
| security | - | yes | yes | - |
| clarity | - | - | yes | - |
| architecture | - | with cross-cutting risk | with cross-cutting or critical risk, or a `G5` label | - |

`correctness`, `governance` and `traceability` are on for every delivery
issue because they *are* the default guardrails in review form. A spike runs
none of them: it ships nothing, so it has only its own gate,
`spike.conclude` ("was the question answered?"); see `approaches/spike.md`.

## The configuration bounds the evidence

The configuration in force can add evidence, never remove it:

1. **Floors** add a gate, a skill or a document to an assessment they match.
2. **Immovable gates** are added to every delivery issue.
3. **Project guardrails** add their gates.

Every rule that fires is recorded in the manifest's `policy_rules_fired:`.
Assess never applies a constraint silently: if a label added a gate, the
manifest says which rule did it and quotes its rationale.
