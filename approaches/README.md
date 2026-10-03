# Delivery approaches

A **delivery approach** is the computed shape of the pipeline for one issue:
how heavy each of the eight stages is, which gates apply, and whether the work
runs solo or as a multiagent orchestration. Approaches are *composed* from the four assessment
dimensions - see `rubric.md` - not picked from this list.

The five files here are **reference shapes**: the common shapes that
composition lands near. Assess names the nearest one in the issue's
delivery-approach record so everyone shares vocabulary, then records any
per-stage deviation from it. "Feature, but verify adds the security
dimension" is a normal, expected output.

| Approach | One-line character | Gates | Read |
|---|---|---|---|
| **quick fix** | The change is small and safe - stay out of the way, but still tested before it lands. | 3 | `quick-fix.md` |
| **feature** | The default working shape - full pipeline, solo or pair. | 6 | `feature.md` |
| **initiative** | Big or cross-cutting - full weight, governance check, multiagent orchestration across worktrees. | 7 | `initiative.md` |
| **hotfix** | Something is broken in production now - reproduce-first, expedited implementation, mandatory follow-up. | 5 | `hotfix.md` |
| **spike** | You do not understand the problem well enough to state it - explore freely, then graduate or discard. Nothing ships from here. | 1 | `spike.md` |

The gate counts are what `governance/routing-policy.yml` computes for the
shape's own assessment, before any floor or requirement adds more. A policy
rule can raise them: a `critical` risk value turns a feature into an
initiative and adds further gates. `compass approach evaluate --verbose`
prints the set for any assessment, and it is the authority - this table is a
summary of it.

Every approach, however light or exploratory, obeys the **default guardrails**
(the five in `governance/guardrails.md`). What an approach adapts is *process weight*
and *strategy* - a spike, for instance, suspends the red-before-green TDD
strategy, but it cannot suspend the tested-before-ship guardrail, because
nothing lands from a spike without graduating to a real approach first. If an
approach file ever seems to permit crossing a guardrail, that is a bug in the
file: `docs/methodology.md` and `governance/guardrails.md` are the authority.

## How to read an approach file

Each states, in order:

- when composition points towards it;
- the per-stage weight;
- the gate set;
- the multiagent orchestration;
- the de-scope ledger, listing what it collapses or skips with the standing
  justification for each;
- what it is *not* allowed to do.
