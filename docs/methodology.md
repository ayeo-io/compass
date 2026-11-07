# Compass methodology

Compass is an adaptive, spec-driven delivery framework. It applies enough
process for the work at hand while preserving a small set of non-negotiable
outcomes.

This document defines the stable model. Commands, templates and policies are
its executable expression.

## 1. Why adaptive process

A fixed workflow fails for both small and large work:

- it makes small, familiar changes too expensive; and
- it gives large, risky or unfamiliar changes too little protection.

A three-level scale of “light, medium, heavy” improves the situation but still collapses
different questions into one scale. A one-file migration can be small and
dangerous. A large prototype can be exploratory and disposable.

Compass therefore runs every change on one path and computes the evidence
the change owes from several dimensions, rather than asking the user to
select a process tier.

## 2. Assessment and routing

Every issue begins with an assessment:

| Dimension | Question | Typical values |
|---|---|---|
| Risk | How far does a failure reach? | trivial, contained, cross-cutting, critical |
| Familiarity | How well is the affected system understood? | greenfield, mapped brownfield, unmapped brownfield |
| Size | How much delivery work is involved? | atomic, small, medium, large, product |
| Goal | What outcome is wanted? | delivery or exploration |
| Urgency | Is this a fix to a defect that is live? | none or live-defect |

Assessment is judgement. The assessor must explain uncertain or consequential
choices, and a human can correct them before work proceeds.

Routing is mechanism. Once the assessment exists, the kit selects the
evidence the change owes from fixed evidence rows, then applies the
project's policy - the fixed check set, with the tighten-only settings of the
project's `compass.yml` - including its floors and immovable gates.

> Judgement goes into the assessment. Everything after it is deterministic:
> the same assessment and policy produce the same evidence,
> every time ([safety contract](safety-contract.md#1-routing-is-deterministic-after-assessment)).

The kit writes the result to the manifest, and `compass approach show` prints
it. It records:

- the recorded assessment, with a reason for each value;
- the approach: `delivery` for the path, or `spike`;
- the evidence the change owes (`evidence_required`) and the gates derived
  from it;
- the checkpoints where the session waits for a person; and
- anything omitted, with the reason it is safe to omit.

De-scoping is therefore a visible decision rather than an accidental gap.

## 3. One path, adaptive evidence

Every delivery change runs the same four stages, in order. The stages are
fixed in code and have no modes (ADR-092).

| Stage | Purpose |
|---|---|
| Assess | Score the dimensions and compute the evidence the change owes. |
| Specify | State observable behavior as scenarios, each with the test that proves it. |
| Build | For each scenario, record a failing test, write the code, then record a passing test. |
| Ship | Review the change, pass each gate with typed evidence, and commit. |

`/compass:go` runs the path in one session, and `/compass:quick-fix` is its
short form for a change the person already knows is small. `/compass:assess`
runs the assessment alone, and `/compass:ship` holds the review and the
commit. Every call that writes a record prints a `next:` line with the one
command to run next.

What changes from one change to the next is the evidence each stage judges,
not which stages run. Assessment always runs for delivery or exploration work
that will change files.

## 4. The evidence rows

The kit picks one evidence row, first match wins, then adds evidence on top
(`approaches/path.md`):

| Row | When | What it owes |
|---|---|---|
| Light | Atomic or small, trivial or contained risk, no hotfix setting, no `G5` label | Scenarios, a red before each green, a green suite, and the correctness, governance and traceability reviews. |
| Defect | Atomic or small, under the hotfix setting, not critical, no `G5` label | The light row, plus the regression and security reviews and the Definition of Done. |
| Standard | Every other delivery assessment | The light row, plus the regression, security and clarity reviews and the Definition of Done. |

On top of the row:

- cross-cutting or critical risk, or a `G5` label, adds the architecture
  review;
- a `G5` label or critical risk adds a person's approval of the scenarios;
- a `G5` label adds a person's sign-off before the change ships;
- the hotfix setting, `urgency: live-defect`, adds a reproduction first; and
- the four-layer acceptance strategy (`S17`) adds its outer-loop, isolation
  and layering records where it applies.

A spike (`goal: exploration`) is not on the path. It explores, concludes,
and ships nothing.

Risk and size remain independent. Policy can raise the evidence a small auth
or migration change owes above what its size alone would ask.

## 5. Guardrails and strategies

Compass separates non-negotiable outcomes from context-sensitive practices.

### Guardrails

Guardrails are few and checkable. `compass check` fails on a breach under
enforced adoption, and the [safety contract](safety-contract.md) lists what it
cannot see:

1. Delivery code is tested before it ships. Stated exactly as
   the check set (`governance/check-set.yml`) states it, because a reader who finds two
   wordings has no way to know which is current: **no code reaches main unless
   it traces to a declared test and a green test run is on record.**
2. Acceptance is defined before implementation.
3. Code, criteria, intent and public claims remain traceable.
4. Gates clear with evidence rather than assertion.
5. A human approves irreversible work: an issue labelled `auth`, `payments`,
   `personal-data` or `migrations`.

A small change owes less evidence but never loses a guardrail.

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

The conflict rule is simple: a guardrail beats a strategy. The evidence the
change owes, or a human, settles a conflict between strategies.

## 6. Artifacts are a review pack

Compass stores each issue in two places. The machine state - the manifest, the
evidence and the markers - is in `.compass/work/<issue>/`. The
documents are in `docs/compass/<created>-<issue>/`, where `<created>` is the
manifest's `created:` date.

The main file in `.compass/work/<issue>/` is `manifest.yml`: the assessment,
the evidence the change owes, the gates, the scenarios, the follow-ups, the
reassessments and the evidence registry. `compass next` names the next
action. From 9.0.0 Compass writes no `devlog.md`; an archived issue keeps
its own.

The one document Compass needs and checks is `acceptance-criteria.md`, written
to `docs/compass/<created>-<issue>/` (ADR-091). Its Summary and Intent links
carry the product intent. A team can keep its own notes beside it, such as a
design, ADRs or `positioning.md`; Compass does not read them.

An artifact must be understandable to a reader who was not in the conversation:
context before detail, resolvable references, explicit decisions and no
pipeline narration.

The terminal points to the decision and the document to review. Full
policy output and logs remain available as evidence without dominating the
conversation.

## 7. One specification, several roles

Product, design, engineering, marketing and QA share one
`acceptance-criteria.md`. From 9.0.0 there are no role entry points
(ADR-093): a brief from any of them opens the Summary and Intent of the
acceptance criteria, and the session takes a role's perspective when the work
needs it.

- Product checks intent fidelity.
- Design contributes interaction behaviors.
- Engineering derives tests and implementation.
- QA challenges coverage and evidence.
- Marketing traces claims to tested behavior.

This prevents parallel specifications from drifting.

The architect perspective is cross-cutting. It checks
the issue against project architecture and annotates the design without
creating a second specification.

## 8. Evidence and gates

Compass distinguishes a claim from evidence. “Tests pass” is a claim. A
recorded command, exit code and evidence type is evidence the CLI can inspect.

Gate evidence is typed. A correctness gate can need a test run; a written
note cannot satisfy it. A high-risk gate can need a structured human
approval rather than a checkbox.

The Definition of Done is therefore checkable state, not narrative status.
It is the exit list of the build stage. Each item is met by a record in the
manifest: typed evidence, a person's approval, or a follow-up that defers the
item and links to the GitHub issue that tracks the work (`compass follow-up
add FU-<id> --defers <item> --github owner/repo#N`). From 9.0.0 there is no Definition of
Ready: the scenarios with their declared tests are the readiness record.

The [safety contract](safety-contract.md) states the exact guarantees and
limits. In particular, Compass evidence does not replace normal CI or prove
software correctness.

## 9. One session

From 9.0.0 Compass starts no worktree and no agent per unit of work
(ADR-090). One session builds the change scenario by scenario: each scenario
goes through its own red and green before the next one starts. No runtime
needs isolated workspaces, and Compass records no orchestration or subtask
count for a new issue.

## 10. Reassessment

An adaptive framework must learn whether it is adapting well.

Reassess when risk, size, familiarity or goal changes materially, with
`/compass:assess --reassess --reason "..."`. The re-assessment computes the
evidence again and records the change. Do not continue as if nothing changed.

Across issues, `compass flow` shows status, blockers and follow-ups. It is
advisory: it never tunes governance and does not gate delivery. sdd-bench,
not Compass, measures whether the framework helps.

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
2. Adapt the evidence and the strategies, never the guardrail outcome.
3. Keep judgement explicit and mechanism deterministic.
4. Make de-scoping a written decision.
5. Use one shared specification across roles.
6. Prefer evidence over assertion and files over conversation.
7. Parallelise only independent work.
8. Treat reassessment as a normal event, not a failure.
9. Generate artifacts for human review, not agent consumption alone.
