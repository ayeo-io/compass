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

1. **Match one row.** The spike row for `goal: exploration`; the common row
   (`RP-EVID-COMMON`) for every other assessment. Risk, size, familiarity and
   urgency add nothing to it.
2. **Apply the additions.** A `G5` label (`auth`, `payments`, `personal-data`,
   `migrations`, and each label in `signoff_labels`) or critical risk adds
   `scenario-approval`; a `G5` label adds `human-approval`.
3. **Add what the configuration adds.** Each `require_evidence` rule that
   matches adds its tokens; it fires as `RP-SETTING-<n>`. Each floor of the
   project's own that matches adds its gate (`add_gate`) or asks for a skill
   (`require_skill`, such as `atdd` from `RP-FLOOR-002`). Each immovable gate
   and project guardrail is added. The advisory strategies are listed. The
   shipped check set has no floor that adds a gate.
4. **Route the `S17` strategy** from the tokens owed. With no `S17` token
   owed (`outer-loop`, `isolation`, `layering`) the routing is `guidance` and
   no check of the strategy runs. A token owed turns it on, unless the
   project turns the strategy off or assess is told `--expected-acceptance
   validation` or `refactor`.

The function never reads a configuration's approaches, shapes, stage modes
or caps. A frozen preset or a stored generation can still hold them; they
stay valid for the issues assessed under them and are not read for a new
assessment. Familiarity does not change the evidence.

The rows, the additions and the tokens of each are in
`governance/routing-policy.md`, "The evidence rows". This file does not copy
them.

## The review dimensions

The gates are the review dimensions. A delivery issue owes three by default:

| Dimension | Common row | Spike |
|---|---|---|
| correctness | yes | - |
| governance | yes | - |
| traceability | yes | - |
| regression, security, clarity, architecture | only where `require_evidence` adds the token | - |

`correctness`, `governance` and `traceability` are on for every delivery
issue because they *are* the default guardrails in review form. `compass
quick-fix finish` passes them from the test records and the output of
`compass check`. A spike runs none of them: it ships nothing, so it has only
its own gate, `spike.conclude` ("was the question answered?"); see
`approaches/spike.md`.

## The configuration bounds the evidence

The configuration in force can add evidence, never remove it:

1. **Floors** add a gate, a skill or a document to an assessment they match.
2. **Immovable gates** are added to every delivery issue.
3. **Project guardrails** add their gates.

Every rule that fires is recorded in the manifest's `policy_rules_fired:`.
Assess never applies a constraint silently: if a label added a gate, the
manifest says which rule did it and quotes its rationale.
