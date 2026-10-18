# Delivery approach - design-scope-review-and-bug-report

<!-- compass:render document-header -->
> **Issue:** design-scope-review-and-bug-report · **Approach:** regular
> **Stage:** assess · **Owner:** router
> **Status:** approved
> **Date:** 2026-10-18
> **Reads:** none
> **Audience:** Anyone joining the issue reads it to see how much process the work gets and why.
<!-- /compass:render -->

---

## The assessment

<!-- compass:render assessment -->
| Dimension | Value | Justification |
|---|---|---|
| Risk | cross-cutting | Adds a ship-commit refusal every shipping issue meets and changes two shipped approach defaults |
| Familiarity | brownfield-mapped | ship-commit, the catalogue and approaches.yml were changed by the earlier PRD 35 work and have tests |
| Size | medium | Three requirements across the preset, ship-commit, templates and docs, about ten files |
| Goal | delivery | The requirements state what is delivered |

Labels: none
<!-- /compass:render -->

<!-- compass:render readiness -->
Repository readiness: 6 of 11 signals, floor met
<!-- /compass:render -->

---

## The composed candidate

Candidate: **regular**, with one deviation: `verify.architecture` joins the gate set because the risk is cross-cutting (`RP-REQUIRE-003`).

Candidate review dimensions: correctness, governance, traceability, regression, clarity, security and architecture.

---

## Policy rules that fired

<!-- compass:render policy-rules -->
Policy: generation 2 of this issue (parent 6.0.0)
Generation: 2

| Type | Rule | What it changed | Rationale |
|---|---|---|---|
| requirement | RP-REQUIRE-003 | gate 'verify.architecture' added to the approach's gate set | Architecture checked before cross-cutting or critical changes land. |
| artifact_rule | RP-ART-002 | stage 'plan' blocked until: the spec has been checked against intent.md for intent fidelity | Built-the-thing-right and built-the-right-thing are different checks. |
<!-- /compass:render -->

---

## The final delivery approach

### Per-stage weight

<!-- compass:render stage-weights -->
| Stage | Weight |
|---|---|
| assess | thorough |
| define | thorough |
| refine | lightweight |
| plan | thorough |
| breakdown | multiagent |
| implement | thorough |
| verify | thorough |
| ship | thorough |
<!-- /compass:render -->

### Gate set

<!-- compass:render gate-set -->
Gates: 7

- `verify.correctness`
- `verify.governance`
- `verify.traceability`
- `verify.regression`
- `verify.clarity`
- `verify.security`
- `verify.architecture` - added by RP-REQUIRE-003
<!-- /compass:render -->

### Model tiers

<!-- compass:render model-tiers -->
| Seat | Tier | Set by | Floor effort | Floors that did not fire |
|---|---|---|---|---|
| assess | strong | RP-TIER-001 | none | none |
| define | strong | RP-TIER-002 | none | none |
| refine | strong | RP-TIER-003 | none | none |
| plan | strong | RP-TIER-004 | none | none |
| breakdown | strong | RP-TIER-005 | none | none |
| implement | standard | RP-TIER-006 | none | RP-MODEL-001, RP-MODEL-002, RP-MODEL-003 |
| verify | fast | RP-TIER-007 | none | none |
| review | strong | RP-TIER-008 | none | none |
| ship | fast | RP-TIER-009 | none | none |

`compass approach show --model <seat>` and `--effort <seat>` print the model and the effort a seat runs on, from the `models` setting and the floors.
<!-- /compass:render -->

### Multiagent orchestration

- Orchestration: solo. The three parts share `docs/artifact-catalogue.md` and `docs/upgrade-7-0-0.md`, and the two approach changes share the preset, the generated views and their pins, so two builders would edit the same files.
- Subtask count: n/a (solo)
- Worktree root: one worktree, `../compass-design-scope`, made by the orchestrator
- Cap in effect: none
- Orchestrator agent: n/a (solo)

---

## The de-scope ledger

| Stage / check | Action | Safe to skip / collapse because… |
|---|---|---|
| Breakdown | computed multiagent, built solo | The parts share files (see Multiagent orchestration). A person decides this at ship. |

---

## Owed follow-ups

- [ ] A person decides on the breakdown: multiagent computed, solo built.

---

## Human overrides

No human overrides. Approach confirmed as composed.

---

## Confirmation

- [x] Approach presented to the invoker. `assess` is not a checkpoint under this project's autonomy setting, so the work goes on without waiting.
- [x] Every dimension in The assessment has a justification.
- [x] Every skipped/collapsed stage in The de-scope ledger has a "safe to skip because…" line.
- [x] `devlog.md` opened with the assess entry.

Next stage: **define acceptance criteria** (`/compass:define`).
