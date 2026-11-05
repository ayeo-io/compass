# Delivery approach - Regular

> The default working shape. Full pipeline at moderate weight, solo or pair.

## Assess composes towards the regular approach when

- size is `medium` (several files, 1–3 days, one or two design
  decisions), **and**
- risk is `contained` or a low end of `cross-cutting`, **and**
- familiarity is either `greenfield` or brownfield (mapped or unmapped - if
  unmapped, a routing rule (RP-FLOOR-002) adds `behavior-mapping` to define,
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
| Assess | Thorough. The approach recorded in the manifest. |
| Define | A small **feature set** of scenarios - happy path, the realistic edges, the failure modes that matter. Brownfield-unmapped: map current behavior into scenarios first. |
| Refine | **Lightweight pass.** Resolve ambiguities, QA the spec against itself and against governance. Records each decision taken. |
| Plan | **A real design.** Technical approach, the one or two design decisions stated, governance check run. If the work splits into 2–3 independent units, a short list of them. |
| Breakdown | **Solo.** On the current branch; when the plan lists 2–3 independent units, the session builds them one after another (ADR-090). |
| Implement | Thorough TDD per scenario. Test surface scaled to `contained`/`cross-cutting` risk. |
| Verify | **Two review points** - one mid-implementation checkpoint, one at the end - clearing six gates. |
| Ship | Integrate (merge pair worktrees if used), run regression, update living docs, one devlog entry. |

## Gate set

Six gates: `correctness`, `governance`, `traceability`,
`regression`, `clarity`, and `security` *scaled to risk*. `claims` is
added when the manifest lists claims.

## Multiagent orchestration

Solo by default. From 9.0.0 the session builds the plan's work units one
after another, with no worktree and no agent (ADR-090).

## De-scope ledger - what the regular approach collapses or skips, and why it is safe

| Item | Action | Standing justification |
|---|---|---|
| Dedicated orchestrator | skipped | One session builds every unit (ADR-090), so there is nothing to integrate. |
| Full list of work units | reduced to a short list | Independence among 2–3 units is verifiable by reading; the full mapping process is for multiagent-scale work. |

If the requirements review finds the spec is bigger or more ambiguous
than the regular approach assumed,
re-assess - do not push the regular approach through a problem shaped for the full approach.

## The regular approach may NOT

- Skip the requirements review entirely. The regular approach's spec is a feature set, not a single
  certified-unambiguous scenario - there is always something to QA. The requirements review
  may be *lightweight*, never *absent*.
- Split into four or more units. That is full-approach territory and needs the
  full list of work units. If the work needs one, the
  assessment was wrong - re-assess to the full approach.
- Drop the regression dimension. The regular approach touches enough surface that
  "nothing that passed before now fails" must be checked.
