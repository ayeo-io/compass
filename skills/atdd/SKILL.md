---
name: atdd
description: Acceptance tests in four layers - specification, DSL, driver, system - for a change a real client can observe. Load at refine, implement and verify.
---

# Acceptance tests in four layers

Adapted from the `atdd` skill of jed72, the Compass maintainer, a personal skill that is not published. The text is the source's except for these adaptations, one per line:

- The model's three stages land on the Compass stages: stage 1 at refine, stage 2 at implement, stage 3 at verify. No stage is added and no gate moves.
- The review that ends each stage is that stage's checkpoint, and its questions moved to `skills/atdd/references/stage-reviews.md`.
- Stage 1 ends in a recorded red: the driver factory imports the driver inside a pytest fixture, and a red recorded at refine unlocks no production code.
- Each Given, When or Then line is one DSL call, any role writes scenarios, and engineers own the DSL and the drivers.
- A quick fix or hotfix reuses existing DSL methods only and goes back to assess for a new one; a spike suspends the strategy.
- Edge cases follow the Compass rule for each implied failure mode in place of a list of suggestions for the person.
- Compass never reads project test code: a layering test the project owns checks the layers.
- The reference example is linked on GitHub, because `examples/` is not in the plugin copy.
- The chain is the one `bdd-specification` and `tdd-discipline` describe.
- The system under test can be a local build as well as a deployment.
- Stage 3 runs each scenario twice in a row, not one, so every scenario the issue adds is proven isolated.
- The description says when Compass loads the skill, in place of the source's list of triggers.
- Files are named by their repository path, as other Compass skills name them.
- The text uses US English and the Compass vocabulary.

## What it is for

An acceptance test describes what the system does for its users, in words a product owner would recognize. It does not describe how the system does it. A test that names an endpoint, a status code, a CSS selector or a database column is tied to today's implementation. The next refactor breaks it, even though the behavior has not changed.

The four-layer model keeps that detail out of the test by giving each kind of knowledge one place to live. This skill covers the outer loop: one executable test per business scenario, run against a real deployment or a local build. The inner loop, unit-level red-green-refactor, is the `tdd-discipline` skill.

The chain, in order: scenario, DSL, driver, unit tests. A scenario in `acceptance-criteria.md` becomes an executable specification; each of its lines is one DSL call; each DSL call reaches the system through a protocol driver; and the code the driver reaches is written test-first, with unit tests. Refine settles each implied failure mode with the person or descopes it, and implement adds no scenario the specification does not state.

## When it applies

The four-layer acceptance strategy covers a change to behavior a real client can observe: what a person or a program sees through an interface real clients use, such as an API, a web UI or a CLI. A refactor, a config change or a document change does not use it.

### Regular and full

All three stages run, as below.

### Quick fix and hotfix

These approaches reuse existing DSL methods only. Write the scenario with the DSL the project already has, take it red, then green. Add no DSL method, driver method or support code. A change that needs a new DSL method is re-assessed: run `/compass:assess --reassess` and give the reason. A hotfix still proves isolation at verify.

### Spike

A spike suspends the strategy as it suspends strategy `S2` (red before green). Nothing ships from a spike. When a spike graduates, the strategy applies in full.

## The layers

From the top down:

1. **Executable specification.** The scenario, written in the language of the domain. Each Given, When or Then line maps to exactly one DSL call. It holds no code logic and no technical detail.
2. **DSL.** The vocabulary the specifications are written in. It fills in defaults so that a scenario states only what matters to it, turns identifiers into aliases (see [Isolation](#isolation)) and passes each call to the driver. It does not assert, make network calls or know the shape of the system's data.
3. **Protocol driver.** The only layer that talks to the system, and only through an interface that real clients use: the API, the web UI or a CLI. It hides multi-step interactions and holds every check. A check passes by returning and fails by throwing the language's normal exception. The message shows what was expected and what was found, for example `Expected tag 'kotlin' in [java, spring]`.
4. **System under test.** The deployed application, or a local build of it, with its own database, cache, queues and internal services. It is the thing you are testing, so none of it is replaced by stubs.

Any role can write a scenario: a product owner, a designer, QA or an engineer writes it in `acceptance-criteria.md`, in Given/When/Then. Engineers own the DSL and the drivers.

The DSL depends on the driver's interface, not on one driver. This is what lets one specification run over the API, the web UI or the CLI. A factory picks the driver at start-up, for example from `ACCEPTANCE_PROTOCOL=api|web|cli`, and no test changes.

Here is a scenario:

```gherkin
Given the user has an account
And they have a completed todo "Buy milk"
When they archive it
Then it appears in the archive
```

And the specification that runs it:

```typescript
dsl.user.hasAccount({ email: "user@test.com" });
dsl.todo.hasCompleted({ name: "Buy milk" });
dsl.todo.archive({ name: "Buy milk" });
dsl.todo.confirmInArchive({ name: "Buy milk" });
```

Name set-up methods `hasX`, actions with a plain business verb and checks `confirmX`. The DSL says "confirm" rather than "assert" because the check itself happens one layer down, in the driver. Driver methods have the same names as the DSL methods they serve.

## Work in three stages

Each stage ends with a review: the checkpoint of the Compass stage it runs in. The questions for each are in `skills/atdd/references/stage-reviews.md`. Do not start the next stage until the review is answered, or recorded as skipped where the project's autonomy setting does not stop there.

### Stage 1, the refine stage: specification and DSL

Write the scenarios, then DSL methods that read like them, then the driver interface. The DSL calls driver methods that do not exist yet, so the suite fails. That failure is the expected starting point. Every scenario first creates its own account, workspace or tenant, and each scenario gets a new DSL instance.

The failure must be one a runner reports. In Python, the driver factory imports the driver inside a pytest fixture, so a missing driver is a setup error in the JUnit report, and that is the stage 1 red. A module-level import in `conftest.py` stops pytest before it writes a report (exit 4), and that run is refused as a red. A red recorded at refine does not unlock production code: production code waits for implement.

The refine checkpoint reviews stage 1.

### Stage 2, the implement stage: protocol driver

Implement the driver interface and put every check in it. Use plain exceptions, not the test framework's `expect()`, and never return a boolean for the caller to check. Wait for asynchronous work by polling with a timeout, not by sleeping. Stub only third-party services you do not control. The code behind the driver is built with the `tdd-discipline` cycle, one unit test at a time.

The implement checkpoint reviews stage 2: the interface is complete and the tests run. Whether they pass depends on whether the system has the feature yet.

### Stage 3, the verify stage: tidy up and prove isolation

Run the suite in parallel, then run each scenario twice in a row. Both must give the same result every time. Merge driver methods that do nearly the same thing. Go through `skills/atdd/references/checklist.md` before the review.

The checkpoint of the verify stage reviews stage 3.

## Isolation

Acceptance tests run against a real system, so they are slow. To keep the suite fast enough you run them in parallel, and then they must not share data. Isolate them at three levels:

- **System.** Stub only third parties you do not control, such as a payment provider, an email service or the clock. Your own database and services stay real. If you stub them, you test a system nobody deploys.
- **Functional.** Each scenario starts by creating its own partition (an account, workspace or tenant) and works only inside it.
- **Temporal.** Each identifier that must be unique goes through an alias helper. The same scenario can then run again, in the same run or a later one, without meeting its old data.

The alias helper has three parts:

- a run ID, created once when the run starts;
- a counter shared by the whole run, safe to use from parallel tests;
- an alias map for each scenario, so that one name always gives the same alias inside that scenario.

`alias("user@test.com")` then returns a value such as `user@test.com-r8f3-17`, and returns the same value each time that scenario asks for it.

Alias identifiers such as email addresses, usernames, order numbers and item names. Give descriptive values such as passwords, roles and addresses a default in the DSL, so that a scenario states only the values its behavior depends on.

Do not clean up after each scenario. Aliased data cannot collide, so it can stay. If the test environment needs the space back, clear it once before a run starts.

## Support code to have first

Stage 1 needs the following. If any of it is missing, build it first or ask the person how to proceed.

- The alias helper described in [Isolation](#isolation), plus helpers for defaults, for example `alias`, `optional` and `optionalList`.
- The driver interface and a factory that picks a driver at start-up, importing the driver where the runner can report a missing one.
- A DSL root that groups the domain parts, such as `dsl.user` and `dsl.todo`.
- A layering test, owned by the project, that fails when the DSL makes a check or a specification line is more than one DSL call.

## Rules

- Implement only the behavior the specification states. Refine settles each implied failure mode with the person or descopes it with `compass scenario descope`; implement adds no scenario the specification does not state.
- Never sleep in a test. Poll with a timeout.
- Check results by asking the system, not by trusting what the test code remembers.
- The driver reaches the system only the way real clients do. It does not call application code directly or read the database.
- When you add a driver method, add it to the interface as well as the implementation.
- Compass never reads or parses project test code. The project's layering test checks the layers, and Compass reads its recorded result.

## Review an existing suite

Start with two searches. They find the most common problems, and the ones that do the most damage.

1. Search the DSL for `assert`, `expect` and `should`. Each match is a violation, however small the suite. The check belongs in the driver.
2. Search the specifications for literal email addresses, usernames and entity names. Each one that skips the alias helper stops the suite from running twice or in parallel.

Then work through `skills/atdd/references/checklist.md` and report what you find, grouped by layer. The other common problems, roughly from most to least frequent, are:

- status codes or selectors in specifications;
- a stubbed internal database;
- cleanup after each scenario;
- a DSL that reads raw response payloads.

## Start from a feature description

If you have a feature description but no scenarios, follow `skills/atdd/references/from-a-feature-description.md`.

## Reference example

A Python example with an API driver, a CLI driver and a layering test is in `examples/atdd-adapters/python/` of the Compass repository: <https://github.com/ayeo-io/compass/tree/main/examples/atdd-adapters/python>. The installed plugin does not include `examples/`, so open it on GitHub.

---

The four-layer model comes from Dave Farley's work on acceptance testing (*Continuous Delivery*, [cd.training](https://courses.cd.training/)). The isolation and review-stage practices also draw on Dawid Dahl's [AAID](https://github.com/dawid-dahl-umain/augmented-ai-development).
