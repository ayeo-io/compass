<!--
TEMPLATE: distribution-map.md
Role in the pipeline: the record of how the work splits into units and why.
The plan stage produces it, and the session builds the units in the order
it gives. Compass starts no worktree and no agent for it (ADR-090).

Independence has two tests, both must hold: disjoint code AND disjoint
scenario groups.

Fill every {{PLACEHOLDER}}.
-->

# Distribution Map - {{ISSUE_SLUG}}

<!-- compass:render document-header -->
<!-- /compass:render -->

---

## Work units

<!-- Write the number of independent work units, or their list, such as
     [U1, U2]. -->

units: {{N}}

| Unit | From technical-design.md | Scenario group(s) | Code surface |
|---|---|---|---|
| U1 | {{plan Work units, U1}} | {{group A}} | {{files / modules}} |
| U2 | {{plan Work units, U2}} | {{group B}} | {{…}} |
| U3 | {{…}} | {{…}} | {{…}} |

## Independence analysis

<!-- For each pair of units, are they independent? Independent = disjoint
     code AND disjoint scenarios. Shared surface = either fold into one
     subtask or sequence them. Be honest - optimistic decomposition surfaces
     as a collision at integration. -->

| Unit pair | Disjoint code? | Disjoint scenarios? | Verdict |
|---|---|---|---|
| U1 ↔ U2 | {{yes/no}} | {{yes/no}} | {{independent \| shared surface - fold \| shared surface - sequence}} |
| U1 ↔ U3 | {{…}} | {{…}} | {{…}} |

**Shared foundations pulled forward:** {{e.g. "U0: the shared `Money` type - lands first, others branch from it" - or "none"}}

## Scenario-group → subtask mapping

<!-- One subtask per independent unit. Each subtask owns a disjoint set of
     scenarios from acceptance-criteria.md. -->

| Subtask | Owns work unit(s) | Owns scenario ids | Branch name |
|---|---|---|---|
| subtask-1 | {{U1}} | {{`TRC-A1`, `TRC-A2`}} | {{compass/<issue-slug>/subtask-1}} |
| subtask-2 | {{U2}} | {{`TRC-B1`}} | {{compass/<issue-slug>/subtask-2}} |

<!-- Optional Wave column. Add it only when the subtasks cannot all start at
     once - a dependent unit whose foundation must land first, or a count
     over the cap - by giving the table a "Wave" column, with a
     positive whole number on every row:

     | Subtask | Owns work unit(s) | Owns scenario ids | Branch name | Wave |
     |---|---|---|---|---|
     | subtask-1 | U1 | `TRC-A1` | compass/<issue-slug>/subtask-1 | 1 |
     | subtask-2 | U2 | `TRC-B1` | compass/<issue-slug>/subtask-2 | 2 |

     The session then builds one wave after another. With no Wave column,
     as above, every subtask is one wave. -->

## Proposed worktree orchestration

- Proposed orchestration: {{solo \| pair (2–3) \| multiagent (4+)}}
- Proposed subtask count: {{N}}
- The session builds each subtask in turn, in its own tree; no worktree or agent is started.

## The cap that applies

<!-- Orchestration is a routed decision. The worktree cap comes from the
     routing-guardrail `caps` in governance/routing-policy.yml, recorded in
     delivery-approach.md by the CLI. THE STANDING CAP: critical risk pins
     max_worktrees to 1 - full-approach scale work can be heavy AND solo. If the cap
     and the proposed count disagree, the cap wins; record it as
     cap-driven, not as a de-scope. -->

- Routing-guardrail cap from `delivery-approach.md`: {{e.g. "critical risk → max_worktrees: 1" - or "none"}}
- **Final subtask count after caps:** {{N}}
- If capped below the proposed count: {{which units were folded/sequenced as a result, and the new branch plan}}

---

## Gate

<!-- The breakdown stage's exit checks, written by `compass issue render` from the issue's
     configuration (`compass issue template show distribution-map`). An item is met by
     evidence recorded with `--meets`, a person's `compass evidence approve --check` or a
     follow-up recorded with `--defers`. A tick on this page counts for nothing. The
     shipped default lists none. -->

<!-- compass:render breakdown-exit -->
<!-- /compass:render -->

Next stage: **break down the work** (`/compass:breakdown`) - orders the units for this session to build.
