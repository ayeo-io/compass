# Delivery approach - Full

> Big, cross-cutting, or greenfield. Full weight, every gate, multiagent
> orchestration across worktrees.

## Assess composes towards the full approach when

- size is `large` or `product`, **or**
- risk is `critical` (a floor forces this regardless of size),
  **or**
- familiarity is `greenfield` at scale or `brownfield-unmapped` and large, **or**
- a floor forces it (e.g. `labels: [auth, payments, migrations]`).

Typical issues: a new subsystem, a multi-module refactor, a migration, anything
touching auth/payments/personal-data at more than trivial size, a product
launch's worth of work.

## Per-stage weight

| Stage | Weight on the full approach |
|---|---|
| Assess | Thorough, plus explicit labels - the full approach is where domain floors most often fire. |
| Define | **Thorough BDD discovery.** Greenfield: scenario discovery from the intent. Brownfield: `behavior-mapping` of current behavior *then* the new scenarios. Scenarios are grouped by independence - this grouping seeds the plan's work units. |
| Refine | **Thorough pass.** Self-QA, governance QA, and an explicit ambiguity ledger. Non-engineering roles review here. |
| Plan | **Thorough design and work units.** Architecture, every design decision stated with what was rejected, governance check, and the mapping of scenario groups → independent work units. |
| Breakdown | **Ordered units.** The session orders the plan's work units; it starts no worktree and no agent (ADR-090). |
| Implement | Thorough TDD, one unit after another, in this session. |
| Verify | **All gates, all dimensions.** Verification of each unit, then of the whole result. |
| Ship | **Combined regression.** A full regression across the whole result, living-docs update, every owed follow-up resolved. |

## Gate set

All gates. Review dimensions: `correctness`, `governance`, `traceability`,
`regression`, `security` (full, not scaled), `clarity`. `claims` is added when the manifest lists claims. Plus every
`immovable_gate` from the routing policy. Plus a mid-implementation
checkpoint gate per worktree.

## Multiagent orchestration

From 9.0.0 the breakdown mode keeps the name multiagent, but the session builds
the plan's work units one after another, with no worktree or agent
per unit (ADR-090). The `caps` in `governance/routing-policy.yml` still record a
subtask ceiling in the manifest; nothing binds on it until #351
replaces the stages.

Roles: one session builds, checks and reviews (ADR-090); the product owner
and the product marketer perspectives apply role checks at the requirements
review and at Ship time.

## De-scope ledger - what the full approach collapses or skips

Nothing. The full approach is the approach with an empty de-scope ledger by
definition - it is what the other approaches are measured against. The only
reductions allowed are ones a `cap` imposes (e.g. the worktree cap), and
those are recorded as *cap-driven*, not as de-scopes.

## The full approach may NOT

- Run without listing its work units, even if it ends up solo (capped). The
  list is the record of *what could have been parallel and why it wasn't*.
- Build two units at once. The session builds one unit after another, so a
  change to shared code is made once, in order.
- Skip the combined-regression step at ship time. Per-subtask green does not imply
  integrated green - the whole point of the ship stage's regression run is to
  prove the combination.
- Be reassessed to a lighter approach without a written reason. If the full approach
  turns out to be heavier than the work needs, use
  `/compass:assess --reassess` and record why.
