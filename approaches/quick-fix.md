# Delivery approach - Quick fix

> The change is small and safe. Stay out of the way.
> Still tested before it lands.

## Running it

`/compass:quick-fix` is the entry point. It inlines every stage below into one
command file, read with the `quick-fix` skill, so the light path costs one
command and one skill rather than five commands and three skills. The per-stage
weights in this document are what that command implements.

## Assess composes towards quick fix when

- size is `atomic` or `small`, **and**
- risk is `trivial` or `contained`, **and**
- no floor raises the approach, **and**
- role is `engineer` (a non-engineering role in play almost always pulls the
  approach up, because it adds artifacts and gates).

Typical issues: copy fixes, a bounded bug fix with an obvious cause, adding a
small variant of an existing pattern, a config change with a known shape.

## Per-stage weight

| Stage | Weight on quick fix |
|---|---|
| Assess | Thorough. Always runs, always writes `delivery-approach.md`. ~minutes. |
| Define | **One scenario.** A single Given/When/Then that names the new behaviour. That scenario is the spec. |
| Refine | **Collapsed** - permitted only because the one scenario is unambiguous. If it is not unambiguous, the assessment does not produce quick fix. |
| Plan | **Collapsed** to a one-line "edit which file(s)" note in `delivery-approach.md`. No `technical-design.md`. |
| Breakdown | **Skipped.** Solo, current branch, no worktree. |
| Implement | Thorough TDD: write the failing test for the scenario, make it green, refactor. Test surface = the one scenario plus its obvious edges. |
| Verify | Lightweight gate: run the new test + the existing suite, paste output. |
| Ship | Trivial: commit on the current branch, one-line devlog entry. |

## Gate set

One review point, at Verify, clearing three gates: `correctness`,
`governance`, `traceability`. (Per `router.md`; a routing rule can add more -
for example a label can add `security` - but never removes these three.)

## Multiagent orchestration

Solo. No worktree. Breakdown is a no-op.

## De-scope ledger - what quick fix collapses or skips, and why it is safe

| Stage | Action | Standing justification |
|---|---|---|
| Refine | collapsed | The spec is a single scenario the assessment marked unambiguous. Nothing to clarify. |
| Plan | collapsed to a one-liner | No design decision and no new architecture - size `atomic`/`small` with trivial or contained risk means the plan is "edit this file." |
| Breakdown | skipped | One subtask of work. Parallelism would be pure overhead. |

These justifications are copied into the issue's `delivery-approach.md` so the skip is
auditable per-issue, not just per-approach.

## quick fix may NOT

- Skip the tested-before-ship guardrail. A quick fix adapts test *surface*,
  never test *existence*. The red-before-green TDD strategy applies on
  quick fix - only a spike suspends it. The `pre-tool` hook enforces
  that strategy and quick fix does not exempt itself from it.
- Skip the define stage. "No scenario" is never a quick fix state - the one scenario is
  the minimum, not zero.
- Be used when risk or size reads high. If risk is `cross-cutting`+ or
  size is `medium`+, the evaluator computes a heavier approach. quick fix
  is for issues that are small on both axes. Unmapped familiarity does not
  block it: the approach record gives `behaviour-mapping` as advice
  (`RP-ADV-002`).
- Be used to "just get the change in" past the approach the evaluator
  actually computed. `delivery-approach.md` makes that visible.
