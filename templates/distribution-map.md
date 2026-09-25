<!--
TEMPLATE: distribution-map.md
Produced by: the plan stage (`/compass:plan`) on pair/multiagent-capable work;
             consumed by breakdown (`/compass:breakdown`) and the
             `orchestrator` agent.
Lives at:    docs/compass/<created>-<issue-slug>/distribution-map.md
Role in the pipeline: the record of what could run in parallel and why.
The plan stage produces it; `scripts/multiagent.sh` reads it to create
worktrees. Initiative-scale work writes this file even if a cap pins it
solo - the map is the record of what could have been parallel and why it
wasn't.

Independence has two tests, both must hold: disjoint code AND disjoint
scenario groups (see the worktree-multiagent skill).

Fill every {{PLACEHOLDER}}.
-->
<!-- absorbed: "solo - the map is the" -->

# Distribution Map - {{ISSUE_SLUG}}

> **Stage:** plan · **Date:** {{DATE}} · **Reads from:** technical-design.md §4, acceptance-criteria.md
> **Consumed by:** breakdown, `scripts/multiagent.sh`, the `orchestrator` agent

---

## 1. Work units

| Unit | From technical-design.md | Scenario group(s) | Code surface |
|---|---|---|---|
| U1 | {{plan §4 U1}} | {{group A}} | {{files / modules}} |
| U2 | {{plan §4 U2}} | {{group B}} | {{…}} |
| U3 | {{…}} | {{…}} | {{…}} |

## 2. Independence analysis

<!-- For each pair of units, are they independent? Independent = disjoint
     code AND disjoint scenarios. Shared surface = either fold into one
     subtask or sequence them. Be honest - optimistic decomposition surfaces
     as a collision at integration. -->

| Unit pair | Disjoint code? | Disjoint scenarios? | Verdict |
|---|---|---|---|
| U1 ↔ U2 | {{yes/no}} | {{yes/no}} | {{independent \| shared surface - fold \| shared surface - sequence}} |
| U1 ↔ U3 | {{…}} | {{…}} | {{…}} |

**Shared foundations pulled forward:** {{e.g. "U0: the shared `Money` type - lands first, others branch from it" - or "none"}}

## 3. Scenario-group → subtask mapping

<!-- One subtask per independent unit. Each subtask owns a disjoint set of
     scenarios from acceptance-criteria.md. -->

| Subtask | Owns work unit(s) | Owns scenario ids | Branch name |
|---|---|---|---|
| subtask-1 | {{U1}} | {{`TRC-A1`, `TRC-A2`}} | {{compass/<issue-slug>/subtask-1}} |
| subtask-2 | {{U2}} | {{`TRC-B1`}} | {{compass/<issue-slug>/subtask-2}} |

<!-- Optional Wave column. Add it only when the subtasks cannot all start at
     once - a dependent unit whose foundation must land first, or a count
     over the worktree cap - by giving the table a fifth column, "Wave",
     with a wave number on every row:

     | Subtask | Owns work unit(s) | Owns scenario ids | Branch name | Wave |
     |---|---|---|---|---|
     | subtask-1 | U1 | `TRC-A1` | compass/<issue-slug>/subtask-1 | 1 |
     | subtask-2 | U2 | `TRC-B1` | compass/<issue-slug>/subtask-2 | 2 |

     `scripts/multiagent.sh` then provisions one wave at a time: `--wave N`
     creates that wave's worktrees only, and the cap is measured against
     that wave's row count rather than the map's total. With no Wave column,
     as above, every subtask is one wave. -->

## 4. Proposed worktree orchestration

- Proposed orchestration: {{solo \| pair (2–3) \| multiagent (4+)}}
- Proposed subtask count: {{N}}
- Worktree root: {{.compass/config.yml `multiagent.worktree_root`, default ../.compass-worktrees}}
- One worktree + one `builder` per subtask; {{plus one `orchestrator` (multiagent) \| lead builder integrates (pair)}}.

## 5. The cap that applies

<!-- Orchestration is a routed decision. The worktree cap comes from the
     routing-guardrail `caps` in governance/routing-policy.yml, recorded in
     delivery-approach.md by the CLI. THE STANDING CAP: critical risk pins
     max_worktrees to 1 - initiative-scale work can be heavy AND solo. If the cap
     and the proposed count disagree, the cap wins; record it as
     cap-driven, not as a de-scope. -->

- Routing-guardrail cap from `delivery-approach.md`: {{e.g. "critical risk → max_worktrees: 1" - or "none"}}
- **Final subtask count after caps:** {{N}}
- If capped below the proposed count: {{which units were folded/sequenced as a result, and the new branch plan}}

---

## Gate

- [ ] Every scenario in `acceptance-criteria.md` is owned by exactly one subtask.
- [ ] Every "independent" verdict in §2 passed both tests (disjoint code AND scenarios).
- [ ] Final subtask count respects every cap in §5.

Next stage: **break down the work** (`/compass:breakdown`) - runs `scripts/multiagent.sh` with this map.
