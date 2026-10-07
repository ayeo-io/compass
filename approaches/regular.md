# Delivery approach - Regular

> The default working shape. Full pipeline at moderate weight, solo or pair.

## Assess composes towards the regular approach when

- size is `standard` (several files, 1–3 days, one or two design
  decisions), **and**
- risk is `contained` or a low end of `cross-cutting`, **and**
- familiarity is either `greenfield` or brownfield (mapped or unmapped - if
  unmapped, a routing rule (RP-FLOOR-002) adds `behaviour-mapping` to define,
  or RP-ADV-002 gives it as advice on an atomic or small change with trivial or contained risk
  with no domain label),
  **and**
- no floor forces the full approach.

Typical issues: a new feature of normal size, a refactor of one module, an
integration with one external service, a meaningful bug fix with design
choices in it.

## Per-stage weight

| Stage | Weight on the regular approach |
|---|---|
| Assess | Full. `delivery-approach.md` written. |
| Define | A small **feature set** of scenarios - happy path, the realistic edges, the failure modes that matter. Brownfield-unmapped: map current behaviour into scenarios first. |
| Refine | **Light-to-full pass.** Resolve ambiguities, QA the spec against itself and against governance. Writes `requirements-review.md`. |
| Plan | **Real `technical-design.md`.** Technical approach, the one or two design decisions stated, governance check run. If the work splits into 2–3 independent units, a short distribution map. |
| Breakdown | **Solo or pair.** Solo on the current branch by default; pair (2–3 worktrees) if the distribution map shows clean independence and the multiagent settings in `compass.yml` (or `.compass/config.yml` in a project without one) are met. |
| Implement | Full TDD per scenario. Test surface scaled to `contained`/`cross-cutting` risk. |
| Verify | **Two review points** - one mid-implementation checkpoint, one at the end - clearing six gates. |
| Ship | Integrate (merge pair worktrees if used), run regression, update living docs, one devlog entry. |

## Gate set

Six gates: `correctness`, `governance`, `traceability`,
`regression`, `clarity`, and `security` *scaled to risk*. `claims` is
added if the product-marketer role is in play.

## Multiagent orchestration

Solo by default. Pair (2–3 worktrees, one `builder` agent each, no dedicated
orchestrator - the lead builder integrates) when the distribution map shows
genuinely independent units and the size justifies the setup cost.

## De-scope ledger - what the regular approach collapses or skips, and why it is safe

| Item | Action | Standing justification |
|---|---|---|
| Dedicated orchestrator agent | skipped | At ≤3 subtasks the integration is small enough for the lead builder; a separate orchestrator is overhead. |
| Full distribution map | reduced to a short list | Independence among 2–3 units is verifiable by reading; the full mapping process is for multiagent-scale work. |

If the requirements review finds the spec is bigger or more ambiguous
than the regular approach assumed,
re-assess - do not push the regular approach through a problem shaped for the full approach.

## The regular approach may NOT

- Skip the requirements review entirely. The regular approach's spec is a feature set, not a single
  certified-unambiguous scenario - there is always something to QA. The requirements review
  may be *light*, never *absent*.
- Run as a multiagent orchestration. Four or more subtasks is full-approach territory; it needs the
  orchestrator and the full distribution map. If the work needs one, the
  assessment was wrong - re-assess to the full approach.
- Drop the regression dimension. The regular approach touches enough surface that
  "nothing that passed before now fails" must be checked.
