# Acceptance suite checklist

Use this list for the review at the end of stage 3, at the checkpoint of the verify stage, and when you review an existing suite. Report each failed item under its layer. One failure is enough to report, even in a small suite.

## Executable specification

- [ ] It uses business language only. It names no endpoints, status codes, selectors, tables or columns.
- [ ] Each scenario is one test.
- [ ] Each Given, When or Then line is exactly one DSL call.
- [ ] It has no loops, conditions or explanatory comments.
- [ ] Every identifier that must be unique goes through the alias helper.
- [ ] The first step creates the scenario's own account, workspace or tenant.

## DSL

- [ ] A search for `assert`, `expect` and `should` finds nothing.
- [ ] Checks are named `confirmX`, not `assertX`.
- [ ] It depends on the driver interface, never on one driver.
- [ ] Identifiers go through `alias`. Descriptive values get defaults through `optional` or `optionalList`.
- [ ] It makes no network calls, holds no business logic and does not read the system's payloads.
- [ ] Each scenario gets a new DSL instance.
- [ ] Its method names are the same as the driver's.

## Protocol driver

- [ ] It holds every check. A check passes by returning and fails by throwing the language's normal exception.
- [ ] No check returns a boolean or uses the test framework's `expect()`.
- [ ] Failure messages show the expected and the actual value.
- [ ] It waits for asynchronous work by polling with a timeout, never by sleeping.
- [ ] It reaches the system only the way real clients do. It does not call application code or read the database.
- [ ] It checks results by asking the system, not by trusting state the tests remember.
- [ ] Every method is on the interface as well as the implementation.
- [ ] Methods that do nearly the same thing are merged.

## System under test and isolation

- [ ] Only third parties you do not control are stubbed, such as payment, email and the clock.
- [ ] Your own database, cache, queues and services are real.
- [ ] Nothing cleans up after each scenario. If the environment is cleared, it happens once, before a run.
- [ ] The suite passes when run in parallel.
- [ ] Each scenario run twice in a row gives the same result.

## Support code

- [ ] The alias helper has a run ID, a counter shared by the run and an alias map for each scenario.
- [ ] A factory picks the driver at start-up, for example from `ACCEPTANCE_PROTOCOL=api|web|cli`, and imports it where the runner can report a missing one.
- [ ] A DSL root groups the domain parts.
- [ ] The project's layering test passes.

## Scope

- [ ] The suite tests only behavior the specification states. Each implied failure mode was settled at refine with the person, or descoped.
