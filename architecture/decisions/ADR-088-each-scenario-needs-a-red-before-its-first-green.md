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
2. **The first green.** A scenario's first green is the earliest of the registered greens bound to it, of either loop, and the unbound greens, because an unbound green runs every scenario. A red in the same second as the green counts, because records carry the time to the second.
3. **The time of a green run again.** `compass tdd-green` replaces the record of its binding and loop on each run. The new record carries `first_timestamp`, the earliest of the replaced green's `first_timestamp` (or `timestamp`) and its own `timestamp`, and its `content_digest` covers it. The check reads a green's time as the earlier of `first_timestamp` and `timestamp`, so a green record written before the field reads by its `timestamp`. The value can only move earlier, so an edited earlier record can make the check stricter, never looser.
4. **What needs no red.** A `verifiable: narrative` scenario, which is cleared by its written body. A scenario closed by an acceptance: one bound to the scenario closes it when its `declared_at` is before that scenario's first green, and one bound to none closes every scenario when its `declared_at` is before the issue's first green. Acceptance records are not greens for this comparison. An acceptance with no `declared_at` closes nothing under this rule; the earlier rule still counts it for an older issue.
5. **An unbound red.** An unbound red counts for the scenario only when one scenario of the issue needs a red. With two or more, it does not say which one it is for.
6. **Which issues.** The rule applies to an issue created on or after 2026-11-03 (`RED_PER_SCENARIO_FROM`). It also applies to an issue whose `created:` is earlier or missing unless a record the CLI writes is dated before that date or has no date, because `created:` can be edited. A record the CLI writes is a red that counts, a green or an acceptance record, each passing the identity test a red passes; a note or any other file with a `timestamp` does not count. An issue with such a record before the date was in flight under the earlier rule, and keeps it. When it lacks something the new rule asks for, the pass detail of `suite-passed` gives a notice that names it, and the verdict does not change.
7. **The version.** `suite-passed` moves to 1.1.0. No archived issue was created on or after the date, so the corpus verdicts do not change and the major stays at 1.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| Tell an old issue by its stored `acceptance_strategy` block | The newest checks use it to tell issues assessed before strategy `S17` | The block says when the strategy shipped, not this rule; issues assessed with it before this change would gain the rule |
| Tell an old issue by any evidence dated on or after the date, as the earlier rule does | One pattern for both cutoffs | An issue in flight on the date would gain the rule at its next record, and the issue says an issue created before the change keeps today's rule |
| Count an unbound red for every scenario | Changes the least for issues that record unbound reds | Two scenarios and one unbound red would pass, which is what the rule exists to fail |
| Use the greens bound to the scenario as its first green, and the unbound greens only when none is bound | Simpler | A bound green would hide an earlier unbound green that already ran the scenario's code, so a red after the code would pass |
| Keep every run of a green as its own file | Shows each run | Every reader of `green-<id>.json` and the registry would need a second form; carrying one field forward keeps one record per binding and loop |
| Judge a bound acceptance against the issue's first green | One time for every acceptance | An acceptance declared for one scenario after another scenario's green would fail, though the failure message asks for exactly that |
| Read any evidence file with a `timestamp` as work on the issue | Reads every record | A note dated before the cutoff would hold a new issue on the earlier rule |
| Add a corpus case for the new rule | Shows the behavior on the corpus | Any new case changes the verdict digest, which needs major 2, and 232 archived issues pin major 1, so `compass check` would refuse `suite-passed` on each |
| Need a red strictly before the green | Matches "before" exactly | A fast test can record its red and green in one second, and the record cannot show the order within it |

## Consequences

- A reader can see from `suite-passed` which scenarios had a failing test first. Its pass detail on a newer issue lists the scenarios met by a red, closed by an acceptance and narrative.
- A session that records one red and greens for several scenarios is told to record a red for each with `compass tdd-red --scenario <id>`.
- An old issue keeps its verdict. The notice names what it lacks under the new rule.
- The new behavior is shown by `tests/test_red_per_scenario.py`, not by the check corpus.

## References

- ayeo-io/compass-delivery#347, the issue that asks for a red for each scenario before its green.
- ADR-038 (implementation versions), ADR-081 (one run bound to several scenarios), ADR-082 (the outer-loop file).
- `cli/compass_pkg/red_first.py` (`scenario_reds`, `scenario_notice`), `cli/compass_pkg/checks.py` (`_check_suite_passed`).
- `tests/test_red_per_scenario.py`.
