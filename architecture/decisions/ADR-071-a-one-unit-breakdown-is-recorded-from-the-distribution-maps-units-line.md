---
id: ADR-071
title: A one-unit breakdown is recorded from the distribution map's units line
status: proposed
date: 2026-10-16
supersedes: ''
superseded_by: ''
---

## Context

The regular and full approaches give breakdown the weight `multiagent`, so `multiagent-run-recorded` wants a recorded subtask run before the issue lands. Most changes on these approaches are one unit of work, and the session builds them alone. The check then failed until someone recorded a subtask by hand, which said a dispatch happened when it did not, or the owner granted a waiver. Cost spike H6 (branch `spike/h6`, commit `dbeab05a`) ran sdd-bench scenarios on the regular and full approaches. Unchanged Compass made 4.0 `issue subtask` calls per run, and one run made 28 waiver-related calls. With the change below, total tokens per run fell 18 to 20%.

ADR-025 made `compass issue subtask` the writer of `subtasks:`. RP-CAP-001 caps critical work at one worktree because "coordination risk on critical changes outweighs parallelism". So one unit is the usual shape of critical work, and the decision must keep the review a critical change gets.

## Decision

1. **The map declares its units.** A distribution map carries a line of its own, `units: N` or a list such as `units: [U1, U2]`. On a multiagent breakdown, `compass issue artifact set distribution-map` refuses a map without the line or with a count below one, and a map saying `units: 1` whose subtask table names two or more subtasks. A solo or skipped breakdown reads nothing.
2. **One unit is recorded by the CLI.** Registering a map that says `units: 1` writes one subtask with `orchestration: single-unit`, model `main-session`, the map as its brief and HEAD as its base. It claims no worktree and no builder. Registering the verification report names it on the record and marks it `done`. A map registered later with two or more units removes the single-unit record. A subtask recorded by hand is never changed. This amends ADR-025: `compass issue artifact set` is a second writer of `subtasks:`, through `subtasks.py`.
3. **The check judges the record on its own terms.** A single-unit record passes when every gate has passed, the map still says `units: 1` and a verification report exists. It fails beside any other subtask, because one of the two records would then be untrue. The gates stand in for the package review a separate builder gets: with one unit the package is the integrated result, which the verify stage reviews.
4. **Critical risk keeps its second reviewer.** On a critical-risk issue the record also needs a passing last review round, recorded with `compass issue subtask set <id> --round pass`, because the critical review cadence adds a second reviewer.
5. **The version.** No stored record carries `orchestration: single-unit`, so the corpus verdicts hold and `multiagent-run-recorded` moves to 1.1.0 (ADR-038).

Registering the map is already the breakdown stage's record under ADR-050, because the catalogue gives `distribution-map` the stage `breakdown`. The writers list does not change.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| Compute `breakdown: solo` from the map | It removes the check for one-unit work | It changes the routing weights and drops the recorded breakdown; the route stays the CLI's decision, not the map's |
| Need a review round at every risk | It is simpler | Below critical, one unit's package review is the review at the verify stage; the round would bring back a hand-made record |
| Accept the record without the gates | The spike did | A completed issue is judged whatever its gates say, so a failed gate would pass the check |

## Consequences

- A one-unit regular or full issue reaches a passing `compass check` with no `issue subtask`, `issue configure` or waiver call.
- A map registered before this change has no `units:` line. It is not re-read until it is registered again, and then the refusal names the line and its two forms.
- A critical-risk one-unit issue still needs one recorded review round.

## References

- ADR-006 (backward compatibility), ADR-025 (the subtask record), ADR-038 (implementation versions), ADR-050 (stage exits), RP-CAP-001.
- `cli/compass_pkg/multiagent_check.py`, `cli/compass_pkg/subtasks.py` (`map_refusal`, `record_single_unit`, `report_single_unit`), `cli/compass_pkg/artifact_cmd.py`.
- `tests/test_one_unit_breakdown.py`.
