---
id: ADR-087
title: A runner that is not pytest writes its JUnit report where Compass names it
status: accepted
date: 2026-11-03
supersedes: ''
superseded_by: ''
---

## Context

Strategy `S17`, the four-layer acceptance strategy, must ask the same of every language (PRD-2026-002, requirement FR-04 for increment B). `compass tdd-red` reads a red from pytest's JUnit report, never from the terminal output (ADR-081). It gets that report by adding `--junitxml` to `PYTEST_ADDOPTS`, which only pytest reads. A TypeScript suite run by `node:test` has its own JUnit reporter, but nothing told it where to write the report, so Compass judged its red by the exit code alone and could not tell a missing driver from any other failure. A project starts its runner through its own script, such as an npm script, so Compass cannot add a flag to the runner's command line.

## Decision

1. **The report's path.** `pytest_report.with_report` sets `COMPASS_JUNIT_REPORT` to the temporary report path beside `PYTEST_ADDOPTS`, for every command it runs. A project's runner adapter writes its JUnit report there. `compass tdd-red` and `compass layering record` read the report when the run wrote it, whichever runner wrote it.
2. **node:test's report.** A `failure` of type `hookFailed` is a setup error, as pytest's "failed on setup" error is, and does not count as a failed test. A `failure` of type `cancelledByParent`, a test its describe block cancelled, is not a failed test. A failed testcase named after a test file whose error holds only the file process's exit code is a file that did not load, and counts as pytest's collection error does: it is refused. A missing module is read from `ERR_MODULE_NOT_FOUND`: a file the hook imports is a module of the project when its folder exists inside the project root and outside folders of installed packages; a package is not. The record's `missing_modules` names a file by its path relative to the project root.
3. **Binding a scenario.** A declared test in a JavaScript or TypeScript file, `<file>::<test name>`, matches a failed testcase whose classname is that file and whose name is that name. node's own JUnit reporter gives every testcase the classname "test", so the reference example's runner adapter uses a small reporter of its own that writes the file there. Every other path keeps the rule pytest's ids follow.
4. **The no-parser rule.** Compass reads the report, never the project's test code. The modules of the strategy keep their no-parser scan (`TRC-F13`); reading the report needs no TypeScript parser.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| A `--report <path>` option on `compass tdd-red` | The command line says where the report is | A new option on two commands and their frozen CLI lists, and the project must repeat a path its runner adapter already knows |
| Read node's `--test-reporter-destination` from the command line | No new name | The flag sits inside an npm script or an adapter, where Compass does not look |
| Read the terminal output of `node --test` | Works with no adapter change | The reason `pytest_report.py` exists: terminal output does not settle a red |
| Match a TypeScript test by its name alone | node's own JUnit reporter works unchanged | A scenario that names a wrong or missing file would bind to any test with the same name |

## Consequences

- A project in any language records its stage 1 red from its own report when its runner adapter writes the report to `COMPASS_JUNIT_REPORT`. The TypeScript reference example, `examples/atdd-adapters/typescript/`, shows one.
- A runner that ignores the variable keeps today's behavior: the red is judged by its exit code, and the record says so.
- A project that uses node's own JUnit reporter, whose classname is always "test", cannot bind a scenario to a TypeScript test; its red is still read from the report. The example's reporter, `tests/acceptance/junitReporter.ts`, is the one to copy.

## References

- The technical design of the issue `atdd-strategy` (ayeo-io/compass-delivery#307), work item U12 and decision `DD-15`, kept in the delivery record.
- `cli/compass_pkg/pytest_report.py`, `cli/compass_pkg/tdd.py`, `cli/compass_pkg/layering.py`.
- `tests/acceptance/atdd_strategy/test_stage1_red.py` (`TRC-C5`) and `tests/acceptance/atdd_strategy/test_cross_cutting.py` (`TRC-X3`).
