---
STATUS: ACCEPTED
date: 2026-05-24
---

# Compass - System Context

<!-- the assess stage reads this file at the start of every issue and includes it (with
     its SHA-256 fingerprint) in .compass/work/<issue>/architecture-loaded.yml.
     Downstream agents - spec-author, planner, and the architect - read
     architecture-loaded.yml to get persistent architectural context that
     survives session boundaries and context compaction.

     Keep this file factual and concise. It is machine-read as well as
     human-read. -->

## Purpose

Compass is an adaptive spec-driven development framework that runs inside
Claude Code. Its primary purpose is to reduce the cost of doing things right:
writing testable acceptance criteria before building, routing issues to the
appropriate level of process weight, and producing an auditable evidence trail that
proves work landed safely.

Compass governs its own development using the same mechanisms it gives to
adopters. This `architecture/` tree is the self-application of that governance.

## Components

The framework has five logical surfaces. Each maps to artifacts on disk and
to agent roles that own them.

### Pipeline

The pipeline is the ordered sequence of stages every delivery issue passes
through: assess → define → refine → plan → breakdown → implement → verify → ship.
Stage weights (full / light / skipped) are determined at assess by the router.
The pipeline is implemented through the slash commands in `commands/` and the
CLI subcommands in `cli/compass`.

Logical surface: **pipeline**

### Router

The router reads the four context dimensions (risk, familiarity, size,
goal + role) recorded in `manifest.yml.assessment` and deterministically selects a
delivery approach, stage weights, and gate set by running `governance/routing-policy.yml`
through `compass approach evaluate`. No human judgement enters after the assessment
is recorded; the delivery approach is a pure function of the assessment.

Logical surface: **router**

### Guardrails

Guardrails are the five hard, checkable, blocking rules that no delivery
approach, agent, or convenience can cross: `G1` (tested before it lands), `G2`
(acceptance defined before built), `G3` (traceability holds), `G4` (evidence
not assertion), `G5` (human signs off on the irreversible). They are encoded
in `governance/guardrails.yml` and checked mechanically by `compass check`.

Logical surface: **guardrails**

### Strategies

Strategies are directional biases that are on by default but are not blocking:
BDD (Given/When/Then scenarios as spec), TDD (red-green-refactor), simplest
correct implementation, and persistence over conversation. They are encoded in
`governance/strategies.md`. The TDD strategy enforcement is implemented in
`hooks/pre-tool.sh` (the `.red` marker gate).

Logical surface: **strategies**

### Role Pipeline

Compass has five roles - engineer, product owner, designer, marketer, QA -
each with its own entry point into the pipeline. Each role has entry-point slash commands
(`/compass:intent`, `/compass:position`, `/compass:design`,
`/compass:consult`) and dedicated agent files in `agents/`. The architect
role (`agents/architect.md`) is an advisory role over the role pipeline,
not a sixth full role.

Logical surface: **role pipeline**

## External dependencies

| Dependency | What Compass reads / writes | Criticality |
|---|---|---|
| `governance/routing-policy.yml` | The evaluator reads this at assess to compute the delivery approach | high |
| `governance/guardrails.yml` | `compass check` reads this to run gate assertions | high |
| `governance/strategies.md` | Consulted by agents when deciding TDD/BDD application | medium |
| `governance/signals.yml` | `hooks/stop.sh` and `compass rework-scan` read this | medium |
| `.compass/work/<issue>/manifest.yml` | The manifest; written by the assess stage, read by every stage | high |
| `.compass/work/<issue>/*.md` | Stage artifacts (acceptance criteria, technical design, requirements review, and so on) | high |
| `.compass/current-task` | One-line pointer resolved by CLI and hooks | high |
| `architecture/` (this tree) | Assess loads into `architecture-loaded.yml`; architect reads | medium |
| `templates/` | Worked examples and starting shapes for adopter artifacts | low |
| `gh` and GitHub | Only when `github_labels` is set in `compass.yml`: Compass writes an issue's labels to its linked GitHub issue and reads the labels back to compare. It stores no token | low |
| Claude Code session | The execution environment; not a file dependency | n/a |

## Boundary conditions

1. **Assess is always first.** No code-changing tool call may precede an assessment
   invocation for the active issue. The pre-tool hook (`hooks/pre-tool.sh`)
   enforces the `.red` marker contract; it cannot enforce assess itself, but the
   methodology makes assess mandatory.

2. **The assessment is the only judgement field in `manifest.yml`.** Everything else in
   `manifest.yml` is mechanism-produced: delivery_approach, stages, gates, scenarios,
   changed_files, evidence, follow_ups, reassessments. No mechanism may write into
   `manifest.yml.assessment`.

3. **A dropped or weakened guardrail is reported, not hidden.** A project's
   `governance/guardrails.yml` can omit a default `G1`–`G5` entry;
   `compass policy lint` and `compass check` name what is missing rather than
   counting it as passing (`docs/safety-contract.md` guarantee 2). Adopters
   declare architecture checks as project guardrails using the generic
   `command-passes` check (see ADR-009); the `verify.architecture` gate is
   added by `RP-REQUIRE-003` and `RP-REQUIRE-004` when risk or labels
   warrant it.

4. **The shipped core is framework-owned.** Changing a shipped delivery
   approach, assessment dimension, stage or guardrail needs a framework
   change with its own issue and ADR. A project can add checks, gates,
   assessment-dimension values and dimensions by configuration; loosening the
   default needs an approved waiver (ADR-033).

5. **The `architecture/` tree is advisory.** A project may operate Compass
   without an `architecture/` directory. Assess degrades gracefully to an
   empty load record. The architect degrades gracefully to heuristic
   analysis with a `WARNING:` prefix. Neither absence causes a phase to fail.

## Open questions

- None open at time of authoring (2026-05-24). Opened questions will be
  recorded here with a date and a link to the issue that raised them.
