---
id: ADR-088
title: Each scenario needs a red before its first green
status: proposed
date: 2026-11-03
supersedes: ''
superseded_by: ''
---

## Context

`suite-passed` checks guardrail `G1`, that a change is tested before it lands. Since 2026-09-24 it also needs a failure observed first: one red record, bound or unbound, or an acceptance record, anywhere on an issue that declares scenarios (`red_first.missing_first_failure`). One red on the issue does not show which scenarios had a failing test before the code, or that the red came before the green. A reader of the record cannot tell (ayeo-io/compass-delivery#347).

Since the earlier rule, a red is bound to its scenario by its file name (`red-<id>.json`, `red-<id>.outer.json` for the outer loop, ADR-082), one outer-loop run bound to several scenarios writes one file for each (ADR-081), and a bound green needs a red bound to its own scenario (`tdd_green._red_record_for`). So the records already say which scenario each red is for. `suite-passed` did not read that.

## Decision

1. **The rule.** On an issue under the rule, each scenario that needs a test must have a red bound to it, of either loop, that counts as a red does for the issue (`red_first._record_verdict`) and is dated no later than the scenario's first green. `suite-passed` fails and names each scenario with no red, and each scenario whose every red is after its first green, by its id. The earlier rule for the issue still applies: an issue whose scenarios are all narrative still needs one red or an acceptance.
2. **The first green.** A scenario's first green is the earliest registered green bound to it, of either loop. When none is bound to it, it is the earliest unbound green. A red in the same second as the green counts, because records carry the time to the second.
3. **What needs no red.** A `verifiable: narrative` scenario, which is cleared by its written body. A scenario closed by an acceptance declared before the issue's first green, as the earlier rule reads it: one bound to the scenario closes that scenario, and one bound to none closes every scenario, as it closed the issue before.
4. **An unbound red.** An unbound red counts for the scenario only when one scenario of the issue needs a red. With two or more, it does not say which one it is for.
5. **Which issues.** The rule applies to an issue created on or after 2026-11-03 (`RED_PER_SCENARIO_FROM`). It also applies to an issue whose `created:` is earlier or missing when every dated evidence record of the issue is on or after that date, because `created:` can be edited. An issue with work recorded before the date keeps the earlier rule. When it lacks something the new rule asks for, the pass detail of `suite-passed` gives a notice that names it, and the verdict does not change.
6. **The version.** `suite-passed` moves to 1.1.0. No archived issue was created on or after the date, so the corpus verdicts do not change and the major stays at 1.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| Tell an old issue by its stored `acceptance_strategy` block | The newest checks use it to tell issues assessed before strategy `S17` | The block says when the strategy shipped, not this rule; issues assessed with it before this change would gain the rule |
| Tell an old issue by any evidence dated on or after the date, as the earlier rule does | One pattern for both cutoffs | An issue in flight on the date would gain the rule at its next record, and the issue says an issue created before the change keeps today's rule |
| Count an unbound red for every scenario | Changes the least for issues that record unbound reds | Two scenarios and one unbound red would pass, which is what the rule exists to fail |
| Use only greens bound to the scenario as its first green | Simpler | A scenario with only an unbound green would need a red at any time, even after the code landed |
| Add a corpus case for the new rule | Shows the behavior on the corpus | Any new case changes the verdict digest, which needs major 2, and 232 archived issues pin major 1, so `compass check` would refuse `suite-passed` on each |
| Need a red strictly before the green | Matches "before" exactly | A fast test can record its red and green in one second, and the record cannot show the order within it |

## Consequences

- A reader can see from `suite-passed` which scenarios had a failing test first. Its pass detail on a newer issue lists the scenarios met by a red, closed by an acceptance and narrative.
- A session that records one red and greens for several scenarios is told to record a red for each with `compass tdd-red --scenario <id>`.
- An old issue keeps its verdict. The notice names what it lacks under the new rule.
- The new behavior is shown by `tests/test_red_per_scenario.py`, not by the check corpus.

## References

- ayeo-io/compass-delivery#347 [Require a red for each scenario before its green].
- ADR-038 (implementation versions), ADR-081 (one run bound to several scenarios), ADR-082 (the outer-loop file).
- `cli/compass_pkg/red_first.py` (`scenario_reds`, `scenario_notice`), `cli/compass_pkg/checks.py` (`_check_suite_passed`).
- `tests/test_red_per_scenario.py`.
