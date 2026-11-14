# Compass methodology

This page states the model behind Compass: one path for every change, the
evidence a change owes, and the rules that do not move.

## 1. Why adaptive process

A fixed workflow costs a small change too much and protects a risky change
too little. Compass runs every change on one path and computes the evidence
it owes. You do not pick a process tier.

## 2. Assessment and routing

Every issue begins with an assessment:

| Dimension | Values |
|---|---|
| Risk | trivial, contained, cross-cutting, critical |
| Familiarity | greenfield, mapped brownfield, unmapped brownfield |
| Size | atomic, small, medium, large, product |
| Goal | delivery or exploration |
| Urgency | none or live-defect |

Assessment is judgement. The assessor gives a reason for each value, and a
person can correct it before work goes on.

Routing is mechanism. The kit computes the evidence from the assessment and
the project's policy: the fixed check set, with the tighten-only settings of
`compass.yml`. The same assessment and policy give the same evidence each
time
([safety contract](safety-contract.md#1-routing-is-deterministic-after-assessment)).

The kit writes the result to the manifest, and `compass approach show`
prints it:

- the assessment, with a reason for each value;
- the approach: `delivery` for the path, or `spike`;
- the evidence the change owes (`evidence_required`) and its gates;
- the checkpoints where the session waits for a person;
- anything omitted, with the reason.

## 3. One path, adaptive evidence

Every delivery change runs the same four stages, in order. The stages have
no modes (ADR-092).

| Stage | Purpose |
|---|---|
| Assess | Score the dimensions and compute the evidence. |
| Specify | Write the scenarios, each with the test that proves it. |
| Build | Write the tests and the code. `compass quick-fix finish` shows that the tests fail without the change and pass with it. |
| Ship | `finish` passes each gate with typed evidence, a person approves, and `finish` commits. |

`/compass:go`, `/compass:quick-fix` and `/compass:assess` run the path in one
session with two commands (ADR-099): `compass quick-fix start` opens the
issue, and `compass quick-fix finish` writes the record. Each call that
writes a record prints a `next:` line with the one step that comes next.

## 4. The evidence rows

Every delivery issue owes one evidence row, `RP-EVID-COMMON`
(`governance/routing-policy.md`, "The evidence rows"):

- the request link and who asked;
- scenarios;
- tests that fail without the change and pass with it;
- a green suite;
- the correctness, governance and traceability gates;
- a person's approval of the change.

Risk, size, familiarity and urgency add no review and no record (ADR-099).
On top of the row:

- A `G5` label or critical risk adds a person's approval of the scenarios.
  Every code edit waits for it.
- A `G5` label adds a person's sign-off before the change lands.
- A project's `require_evidence` setting adds the evidence it names: a
  review, the Definition of Done, a reproduction first for a live defect, or
  the records of the four-layer acceptance strategy (`S17`).

A spike (`goal: exploration`) is not on the path. It explores, concludes
and ships nothing.

**The request link** (`request`, ADR-096). Assess records it with
`--request` and `--requester`. The check `request-recorded` fails until both
are on record. No edit is refused for it.

**The approval of the change** (`ship-approval`, ADR-095). A person types
`/compass:approve` when `compass quick-fix finish` asks, and `finish` then
commits. After a later change, `finish` asks again. Compass also reads the
approval from the merged pull request: an approving review by a person who
is not its author. A `G5` sign-off does not count for it.

**The red freezes the scenarios.** The manifest records the spec's digest
and the scenario ids, and `compass check` says when the spec changed since.

## 5. Guardrails and strategies

Five guardrails apply to every change. `compass check` fails on a breach
under enforced adoption, and the [safety contract](safety-contract.md) lists
what it cannot see:

1. Delivery code is tested before it ships. The check set
   (`governance/check-set.yml`) states it: **no code reaches main unless
   it traces to a declared test and a green test run is on record.**
2. Acceptance is defined before implementation.
3. Code, criteria, intent and public claims stay traceable.
4. Gates clear with evidence, not assertion.
5. A person approves irreversible work: an issue labelled `auth`, `payments`,
   `personal-data` or `migrations`.

A strategy is a strong default, such as BDD, TDD, an ADR, a threat model or
a C4 or Mermaid diagram in a design. You can depart from one if you record
why; that is not a breach.

A guardrail beats a strategy. The evidence the change owes, or a person,
settles a conflict between strategies.

## 6. Artifacts are a review pack

Compass stores each issue in two places:

| Place | Holds |
|---|---|
| `.compass/work/<issue>/` | `manifest.yml`, the evidence, the markers and `trail.md`. |
| `docs/compass/<created>-<issue>/` | The documents. `<created>` is the manifest's `created:` date. |

- `manifest.yml` holds the assessment, the evidence owed, the gates, the
  scenarios, the follow-ups, the reassessments, the evidence registry and
  each delegation an agent approved under (`delegations_used:`).
  `compass next` names the next action.
- `trail.md` states who asked, what was agreed, the red and green of each
  scenario, who approved and what shipped. A reviewer checks it with
  `sha256sum -c` and no Compass.
- `acceptance-criteria.md` is the one document Compass needs and checks
  (ADR-091). A team can keep its own notes beside it; Compass does not read
  them.
- Compass writes no `devlog.md`. An archived issue keeps its own.

By default `compass ship-commit` commits the record with the code. A project
can keep it out with `record.commit: false`. Detail:
[the delivery record](https://github.com/ayeo-io/compass/blob/main/docs/delivery-record.md).

## 7. One specification, several roles

Product, design, engineering, marketing and QA share one
`acceptance-criteria.md`. There are no role entry points (ADR-093): a brief
from any role opens its Summary and Intent, and the session takes a role's
perspective when the work needs it. The architect perspective checks the
issue against the project architecture. It does not create a second
specification.

## 8. Evidence and gates

"Tests pass" is a claim. A recorded command, exit code and evidence type is
evidence the CLI can inspect. Gate evidence is typed: a written note cannot
clear a gate that needs a test run.

Where a project needs the Definition of Done, a record in the manifest
meets each item: typed evidence, a person's approval, or a follow-up that
links to the GitHub issue that tracks the work (`compass follow-up add
FU-<id> --defers <item> --github owner/repo#N`).

There is no Definition of Ready. The scenarios with their declared tests
are the readiness record.

Compass evidence does not replace CI and does not prove that software is
correct.

## 9. One session

One session builds the change, and `finish` proves the red and the green
for all its scenarios in one run. Compass starts no worktree and no agent
per unit of work (ADR-090).

## 10. Reassessment

When risk, size, familiarity or goal changes, run
`/compass:assess --reassess --reason "..."`. It computes the evidence again
and records the change.

`compass flow` shows status, blockers and follow-ups across issues. It is
advisory and does not gate delivery.

## 11. The three layers: methodology, kit and adapter

| Layer | Contains | Porting rule |
|---|---|---|
| Methodology | Documentation, governance prose, the path, the spike and templates | Reuse unchanged. |
| Kit | Python CLI, machine-readable policy, schemas and issue manifest | Invoke unchanged. |
| Adapter | Runtime commands, skills, hooks and installation wiring - `bin/compass` and `.claude-plugin/` in the shipped one | Rebuild for the target runtime. |

The adapter produces the assessment, because that needs judgement. It calls
the kit for routing and checks, because those must be deterministic.
[Portability](portability.md) holds the adapter contract.
