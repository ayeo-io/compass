# Compass methodology

Compass is an adaptive, spec-driven delivery framework. It applies enough
process for the work at hand while preserving a small set of non-negotiable
outcomes.

This document defines the stable model. Commands, templates and policies are
its executable expression.

## 1. Why adaptive process

A fixed workflow fails at both ends:

- it makes small, familiar changes too expensive; and
- it gives large, risky or unfamiliar changes too little protection.

A ladder of “light, medium, heavy” improves the situation but still collapses
different questions into one scale. A one-file migration can be small and
dangerous. A large prototype can be exploratory and disposable.

Compass therefore computes a delivery approach from several dimensions rather
than asking the user to select a process tier.

## 2. Assessment and routing

Every issue begins with an assessment:

| Dimension | Question | Typical values |
|---|---|---|
| Risk | How far does a failure reach? | trivial, contained, cross-cutting, critical |
| Familiarity | How well is the affected system understood? | greenfield, mapped brownfield, unmapped brownfield |
| Size | How much delivery work is involved? | atomic, small, medium, large, product |
| Goal and role | What outcome is wanted, and who is entering? | delivery or exploration; product, design, engineering, marketing or QA |

Assessment is judgement. The assessor must explain uncertain or consequential
choices, and a human can correct them before work proceeds.

Routing is mechanism. Once the assessment exists, the kit applies
`governance/routing-policy.yml`, including floors, caps and immovable gates.

> Judgement goes into the assessment. Everything after it is deterministic:
> the same assessment plus the same policy produces the same approach, every
> time.

The kit writes the result to `delivery-approach.md`, including:

- the recorded assessment;
- the computed approach;
- the stages, artifacts and gates that apply;
- the allowed delivery orchestration; and
- anything omitted, with the reason it is safe to omit.

De-scoping is therefore a visible decision rather than an accidental gap.

## 3. One flow, adaptive depth

Compass has eight methodological stages, one command per stage:

| Command | Methodological stage | Purpose |
|---|---|---|
| `/compass:assess` | Assess | Read the four dimensions and compute the delivery approach. |
| `/compass:define` | Define | State observable behaviour. |
| `/compass:refine` | Requirements review | Resolve ambiguity. |
| `/compass:plan` | Plan | Decide how to build it. |
| `/compass:breakdown` | Breakdown | Decide how work can be distributed safely. |
| `/compass:implement` | Implement | Produce tested changes and evidence. |
| `/compass:verify` | Verify | Review behaviour, quality, traceability and gates. |
| `/compass:ship` | Ship | Integrate, recheck and close the issue. |

The vocabulary remains stable. The weight changes:

- a stage can be full, light, collapsed or skipped;
- a collapsed stage still records the decision it would otherwise contain;
- a skipped stage needs an explicit de-scope reason; and
- assessment always runs for delivery or exploration work that will change
  files.

## 4. Reference shapes

Most computed approaches resemble one of five reference shapes. They are
starting points, not selectable levels.

| Shape | Typical response |
|---|---|
| Quick fix | One scenario, focused implementation and verification; plan and breakdown normally collapse. |
| Regular | A small scenario set, proportionate design, solo or paired implementation and normal verification. |
| Full | Product intent, architecture and delivery planning at full weight; detailed design, test strategy and parallel subtasks where useful. |
| Hotfix | Reproduce before changing code, restore service safely, then complete the owed specification and evidence. |
| Spike | Time-boxed exploration with no production delivery; conclude, discard, defer or reassess into a delivery approach. |

Risk and size remain independent. Policy can raise a small auth or migration
change above its size-based default, and can cap parallelism where coordination
risk would outweigh speed.

## 5. Guardrails and strategies

Compass separates non-negotiable outcomes from context-sensitive practices.

### Guardrails

Guardrails are few, checkable and blocking:

1. Delivery code is tested before it ships. Stated exactly as
   `governance/guardrails.yml` states it, because a reader who finds two
   wordings has no way to know which is current: **no code reaches main unless
   it traces to a declared test and a green test run is on record.**
2. Acceptance is defined before implementation.
3. Code, criteria, intent and public claims remain traceable.
4. Gates clear with evidence rather than assertion.
5. A human approves irreversible or critical-risk work.

An approach can reduce process weight but never removes a guardrail.

### Strategies

Strategies are strong defaults that improve the work when they fit. You can
depart from a strategy if you record why; that is not treated as a breach.

Examples include:

- BDD and TDD;
- ADRs;
- threat modelling;
- accessibility review;
- performance modelling;
- writing for a cold reader; and
- visual architecture and design models.

Use a diagram inside an HLD or LLD when it makes the design easier to
understand:

| Need | Useful strategy |
|---|---|
| System scope and ownership | C4 context or container diagram |
| Runtime interaction | Mermaid sequence diagram |
| Data relationships | Mermaid ERD |
| Types and responsibilities | Mermaid class or UML class diagram |
| Component dependencies | C4 component or focused dependency diagram |

These are strategies, not mandatory sections. A diagram that adds no
information is process weight; a diagram that makes a difficult relationship clear
is valuable design work.

The conflict rule is simple: a guardrail beats a strategy. The delivery
approach, or a human, settles a conflict between strategies.

## 6. Artifacts are a review pack

Compass stores each issue beneath `.compass/work/<issue>/`.

Two files anchor the pack:

- `README.md` is the human dashboard: delivery approach, status, decisions,
  approval and next action.
- `manifest.yml` is the manifest: assessment, stage state, gates,
  traceability and evidence registry.

Other artifacts are selected by the delivery approach. They can include:

| Concern | Typical artifacts |
|---|---|
| Product intent | `intent.md` |
| Acceptance | `acceptance-criteria.md`, `requirements-review.md` |
| Architecture and design | HLD, LLD, ADRs, `technical-design.md`, `architecture-notes.md` |
| Delivery | `distribution-map.md`, implementation plan |
| Quality | test strategy, `verification-report.md`, `evidence/` |
| Launch | `positioning.md`, `launch-readiness.md` |
| History | `devlog.md`, follow-ups and reassessments |

An artifact must be understandable to a reader who was not in the conversation:
context before detail, resolvable references, explicit decisions and no
pipeline narration.

The terminal points to the decision and the document to review. Full
policy output and logs remain available as evidence without dominating the
conversation.

## 7. One specification, several roles

Product, design, engineering, marketing and QA contribute through distinct
entry points but share `acceptance-criteria.md`.

- Product checks intent fidelity.
- Design contributes interaction behaviours.
- Engineering derives tests and implementation.
- QA challenges coverage and evidence.
- Marketing traces claims to tested behaviour.

This prevents parallel specifications from drifting. See the
[roles guide](roles-guide.md) for the role commands, artifacts and a worked
example.

The architect perspective is cross-cutting rather than an entry-point role. It checks
the issue against project architecture and annotates the design without
creating a second specification.

## 8. Evidence and gates

Compass distinguishes a claim from evidence. “Tests pass” is a claim. A
recorded command, exit code and evidence type is evidence the CLI can inspect.

Gate evidence is typed. A correctness gate can need a test run; a written
note cannot satisfy it. A high-risk gate can need a structured human
approval rather than a checkbox.

The Definition of Ready and Definition of Done are therefore checkable state,
not narrative status. Unchecked items must refer to typed evidence or an
explicit follow-up.

The [safety contract](safety-contract.md) states the exact guarantees and
limits. In particular, Compass evidence does not replace normal CI or prove
software correctness.

## 9. Safe parallelism

Planning identifies independent work units before choosing an orchestration:

| Orchestration | Use |
|---|---|
| Solo | One subtask on the current branch. |
| Pair | Two or three isolated subtasks with a clear integration owner. |
| Multiagent | Four or more isolated subtasks plus an orchestrator responsible for integration. |

Parallelism is useful only when subtasks have separable scenarios and code
surfaces. The delivery approach can cap parallelism for critical work even
when the issue is large.

The reference adapter uses Git worktrees so each subtask can run failing tests
without destabilising its siblings. A different runtime must give each
subtask its own workspace or reduce the orchestration.

## 10. Reassessment and the retrospective signal

An adaptive framework must learn whether it is adapting well.

Reassess when risk, size, familiarity or goal changes materially. Record the
reason instead of absorbing the change silently.

Across issues, Compass exposes advisory signals:

- `compass retro` shows whether delivery approaches are commonly increased or reduced;
- `compass rework-scan` identifies configured cross-issue churn patterns;
- `compass flow` surfaces status, blockers and follow-ups; and
- friction records highlight recurring over-weight, under-weight or
  tooling problems.

These signals never tune governance automatically and do not gate delivery.
They inform a human decision to change the rubric, policy or strategies.

## 11. The three layers: methodology, kit and adapter

Compass separates what it believes from how a runtime runs it:

| Layer | Contains | Porting rule |
|---|---|---|
| Methodology | Documentation, governance prose, reference approaches and templates | Reuse unchanged. |
| Kit | Python CLI, machine-readable policy, schemas and issue manifest | Invoke unchanged. |
| Adapter | Runtime commands, agents, skills, hooks and installation wiring - `bin/compass` and `.claude-plugin/` in the shipped one | Rebuild for the target runtime. |

The adapter produces the assessment because that needs judgement. It calls
the kit for routing and checks because those must remain deterministic.

See [Portability](portability.md) for the adapter conformance contract.

## 12. Design principles

1. Compute the process; do not select it from a menu.
2. Adapt process weight and strategy, never the guardrail outcome.
3. Keep judgement explicit and mechanism deterministic.
4. Make de-scoping a written decision.
5. Use one shared specification across roles.
6. Prefer evidence over assertion and files over conversation.
7. Parallelise only independent work.
8. Treat reassessment as a normal event, not a failure.
9. Generate artifacts for human review, not agent consumption alone.
