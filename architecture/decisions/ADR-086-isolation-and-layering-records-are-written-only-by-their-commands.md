---
id: ADR-086
title: Isolation and layering records are written only by their commands
status: accepted
date: 2026-11-03
supersedes: ''
superseded_by: ''
---

## Context

Strategy `S17`, the four-layer acceptance strategy, says the acceptance suite is isolated (its scenarios share no data) and layered (each test layer calls only the layer below it). PRD-2026-002, the four-layer acceptance strategy, asks for both to be proven by records the project's own commands write, never by a written note (requirements FR-07 and FR-10). Compass reads records, never the project's test code, so it cannot judge either property itself. The product owner decided that every scenario of the issue runs twice, named by the test ids the manifest declares, and that one issue can step off the strategy through an approved issue waiver.

## Decision

1. **Two evidence types, two commands.** `compass isolation record` writes `evidence/isolation-proof.json` and the registry entry `EV-ISOLATION` (type `isolation-proof`). `compass layering record` writes `evidence/layering.json` and the registry entry `EV-LAYERING` (type `layering`). A new run replaces the issue's one record of its type. `compass evidence add` refuses both types, as it refuses `checkpoint-approval`.
2. **The isolation proof.** `compass isolation record --candidate <build id>|local --client api|web|cli --parallel "<command>" --repeat "<command> {tests}"` runs the parallel command once. Then, for each scenario that declares tests, it runs the repeat command twice with `{tests}` replaced by those test ids: as one word each where `{tests}` is a word of its own, joined by spaces inside a longer word. Each string is split with `shlex.split` and run with no shell, through `tdd._run_test`. The record holds the parallel run's exit code, and for each scenario its tests, the two exit codes and whether they were the same, with the candidate and the client as an outer-loop green names them (ADR-085). It refuses, with exit 2, a `--repeat` with no `{tests}`, an issue that declares no test, and a missing or unknown candidate or client.
3. **The layering record.** `compass layering record [--test-path P] [-- <command>]` runs the command, or `project.layering_command` when none is given. The record holds the command, the test path (`--test-path`, else `project.acceptance_support.layering_test`), the exit code, `tests_ran`, the tree id and the time. `tests_ran` is the number of test cases in pytest's JUnit report when the runner wrote one, read by `pytest_report.tests_ran`, and null otherwise. With no command and no setting it exits 2.
4. **Exit 0 on a failed run.** Both commands exit 0 when the record is written, even when a run failed: the check judges the record, as `compass bdd verify` records a failed run.
5. **`isolation-proven`.** It passes when the parallel run passed, every test the issue declares is in a repeat entry, both runs of each entry passed, the record was made on the tree as it is now, and its candidate is that of the newest outer-loop green that names one. With no outer-loop green the candidates are not compared: `outer-loop-recorded` reports the missing green.
6. **`layering-test-passed`.** It fails a missing, unreadable or failed record, a record that shows 0 tests ran, and one made on another tree. It does not judge a null `tests_ran`, so a layering test that is a shell script passes when it exits 0.
7. **Routing.** `isolation-proven` needs a record on the routings `on` and `existing-dsl-isolation` (the hotfix); `layering-test-passed` on `on` only. On `existing-dsl` (the quick fix), and on an issue the strategy does not apply to, both decline with "not required". A declined row lists a record the issue holds, with its result, so the result is seen and judges nothing.
8. **Blocking, unlocked, outside every gate.** Both checks are `severity: blocking`, in no gate and in no lock, and run through `outside_gate`, as the strategy's other checks do. A project waiver or an approved issue waiver can make either advisory. `compass check` names each issue waiver of one of the strategy's checks, with its reason and whether the issue's generation holds it as approved.
9. **No parser.** The modules the strategy adds hold no import of a code parser. The JUnit report is read in `pytest_report`, which `compass tdd-red` already uses. `tests/acceptance/atdd_strategy/test_isolation_layering.py` scans the modules for such an import.
10. **The retrospective.** `compass retro --acceptance` counts closed issues per acceptance kind (`validation`, `refactor` and in scope), and names each out-of-scope issue that holds an `isolation-proof` or `layering` record.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| One repeat run of the whole suite, read through the runner's report | One run is cheaper than two per scenario | It needs a report parser for each language |
| Repeat one scenario, as the PRD first said | One run is cheaper | A fixed choice can pick a scenario with no unique identifier, which proves nothing (refine decision Q12) |
| Let the project register any JSON file as the record | No new command | A hand-written file is a claim, not a record (guardrail `G4`) |
| Fail a null `tests_ran` | A count shows the test ran | A layering test in another language writes no JUnit report |
| Exit 1 when a run fails | The command's exit shows the result | The record is the result, and a script that stops on exit 1 would not register it |
| Compare the proof with every outer-loop green's candidate | Several greens can name several candidates | The newest green is the candidate the issue ships; an older one was replaced |

## Consequences

- An in-scope issue on the regular or full approach needs an isolation proof and a layering record at verify; a hotfix needs the isolation proof. A quick fix needs neither.
- An issue assessed before the checks were in its configuration does not run them until its next `compass approach evaluate --write` (ADR-036).
- The isolation proof costs one parallel run and two runs per scenario. The project pays it, at verify only.

## References

- ADR-080 (the `loop` field), ADR-082 (the outer-loop file and registry entry), ADR-085 (candidate and client), ADR-039 (waivers), ADR-064 (checks outside every gate).
- `cli/compass_pkg/isolation.py`, `cli/compass_pkg/layering.py`, `cli/compass_pkg/strategy_records.py`, `cli/compass_pkg/approvals.py`, `cli/compass_pkg/pytest_report.py`, `cli/compass_pkg/acceptance_strategy.py`.
- `tests/acceptance/atdd_strategy/test_isolation_layering.py`.
