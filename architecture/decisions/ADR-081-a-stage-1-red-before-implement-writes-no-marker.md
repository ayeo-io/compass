---
id: ADR-081
title: A stage 1 red before implement writes no marker
status: accepted
date: 2026-11-01
supersedes: ''
superseded_by: ''
---

## Context

Strategy `S17`, the four-layer acceptance strategy, ends stage 1 at refine with an outer-loop red: the acceptance suite fails because the driver is not written yet. Two things stopped Compass from recording it.

- The driver factory in `conftest.py` imports the driver. A module-level import makes pytest exit 4 with no JUnit report, and `compass tdd-red` refuses exit 4 so that a usage error cannot unlock code. An import inside the fixture makes pytest report a setup error, which `compass tdd-red` refused as "no test failed".
- Every red was the first record of implement. It wrote the `.red` marker, which the pre-tool hook reads to allow production edits, and moved the documents of the earlier stages (ADR-050). A red at refine would approve the refine documents before the refine checkpoint and unlock code before plan.

## Decision

1. **The setup error.** With `--loop outer`, `pytest_report.judge` accepts a JUnit `error` whose message starts "failed on setup" and whose text names a missing module that `in_project` finds. It records an import red with the list `missing_modules`. A setup error for a module outside the project is refused and names the module as not a module of this project. With `--loop inner`, the refusal of compass 8.0.4 stays.
2. **Exit 4.** Exit 4 is never a red. For the outer loop, the refusal quotes pytest's first error line on stderr, and says when pytest printed nothing there. When that line says `conftest.py` failed to load and the error is a missing module of the project, the refusal says to import the driver inside the driver-factory fixture. The terminal text words the message only and never decides a red.
3. **Stage 1.** A red is a stage 1 red when its loop is outer, the issue's `stages` run refine, and no technical design, distribution map or subtask is registered (`acceptance_strategy.stage_one`). A stage 1 red writes `before_implement: true`, writes no `.red` marker and moves no document. `next_cmd._testing_started` does not count it, so the issue does not read as in implement.
4. **Several scenarios.** With `--loop outer`, `--scenario` can repeat and `--every-scenario` names every scenario of the manifest that needs a test. One run writes one record per scenario, each with the same `run_id` and the list `scenarios_in_run`. When pytest wrote a report, each scenario needs a declared test that failed or errored in it; otherwise nothing is written and the command exits 2 naming the scenario.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| Read exit 4 and the terminal output as a red | Works with a module-level import | A syntax error in `conftest.py` prints the same first line, a usage error could unlock code, and a mistyped import would be a red |
| A marker the pre-tool hook ignores | Keeps one write path | The hook would need a second reader of red records |
| Key the rule to the stage name alone | Simpler test | Quick fix and hotfix collapse refine, so their outer-loop red must unlock code as before |
| One record that lists every scenario | One file per run | Every reader of `red-<scenario>.json` would need a second form |

## Consequences

- A stage 1 red unlocks no code. The inner-loop red at implement writes the marker, as strategy `S2` asks.
- Quick fix and hotfix keep today's behavior: their outer-loop red writes the marker and moves the documents.
- A team whose `conftest.py` imports the driver at module level is told to move the import into the fixture.
- An inner-loop red bound to the same scenario as a stage 1 red writes its own file, so both are kept (ADR-082).

## References

- The technical design of the issue `atdd-strategy` (ayeo-io/compass-delivery#307), decisions `DD-6` and `DD-7`, and its requirements review, decisions `Q4`, `Q7` and `Q14`. Both are issue documents kept in the delivery record.
- `cli/compass_pkg/pytest_report.py`, `cli/compass_pkg/tdd.py`, `cli/compass_pkg/acceptance_strategy.py` (`stage_one`), `cli/compass_pkg/next_cmd.py` (`_testing_started`).
- `tests/acceptance/atdd_strategy/test_stage1_red.py` (`TRC-C1` to `TRC-C4`, `TRC-C6` to `TRC-C8`).
