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
| Define | **Thorough BDD discovery.** Greenfield: scenario discovery from `intent.md`. Brownfield: `behaviour-mapping` of current behaviour *then* the new scenarios. Scenarios are grouped by independence - this grouping seeds the distribution map. |
| Refine | **Thorough pass.** Self-QA, governance QA, and an explicit ambiguity ledger. Non-engineering roles review here. |
| Plan | **Thorough `technical-design.md` + `distribution-map.md`.** Architecture, every design decision recorded as an ADR-style note, governance check, and the mapping of scenario groups → independent work subtasks. |
| Breakdown | **Multiagent.** `scripts/multiagent.sh` creates one git worktree per subtask; one `builder` agent per worktree; one `orchestrator` agent that writes no feature code. |
| Implement | Thorough TDD inside each worktree, in parallel. The orchestrator watches for subtasks converging on shared surface and intervenes before they collide. |
| Verify | **All gates, all dimensions.** Per-subtask verification, then combined verification after integration. |
| Ship | `scripts/integrate.sh`: orchestrated merge of all worktrees, full regression across the combined result, living-docs update, every owed follow-up resolved. |

## Gate set

All gates. Review dimensions: `correctness`, `governance`, `traceability`,
`regression`, `security` (full, not scaled), `clarity`, `claims`. Plus every
`immovable_gate` from the routing policy. Plus a mid-implementation
checkpoint gate per worktree.

## Multiagent orchestration

Multiagent: 4+ subtasks, capped by the `caps` in
`governance/routing-policy.yml` (recorded in `delivery-approach.md` by the CLI). Note the
standing cap - **`critical` risk caps worktrees at 1** even on
the full approach, because coordination risk on a critical change outweighs the
parallelism. The full approach can therefore be heavy *and* solo; that is
intentional, not a contradiction.

Roles: `orchestrator` coordinates and integrates; `builder` agents implement,
one per worktree; `verifier` and `reviewer` run at the gates; `product-owner`
and `product-marketer` apply role checks at the requirements review and at
Ship time.

## De-scope ledger - what the full approach collapses or skips

Nothing. The full approach is the approach with an empty de-scope ledger by
definition - it is what the other approaches are measured against. The only
reductions allowed are ones a `cap` imposes (e.g. the worktree cap), and
those are recorded as *cap-driven*, not as de-scopes.

## The full approach may NOT

- Run without a `distribution-map.md`, even if it ends up solo (capped). The
  map is the record of *what could have been parallel and why it wasn't*.
- Let a `builder` agent touch a sibling worktree. Cross-subtask changes go
  through the orchestrator. This is what makes the isolation real.
- Skip the combined-regression step at ship time. Per-subtask green does not imply
  integrated green - the whole point of the orchestrator's ship role is to
  prove the combination.
- Be reassessed to a lighter approach without a written reason. If the full approach
  turns out to be heavier than the work needs, use
  `/compass:assess --reassess` and record why.
