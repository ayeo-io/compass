---
name: atdd
description: Scenarios, behavior mapping and four-layer acceptance tests. Load at specify, build and ship.
---

# Scenarios and acceptance tests in four layers

Adapted from the `atdd` skill of jed72, the Compass maintainer, a personal skill that is not published. The text is the source's except for these adaptations, one per line:

- The model's three stages land on the Compass stages: stage 1 at specify, stage 2 at build, stage 3 at ship. No stage is added and no gate moves.
- The review that ends each stage is that stage's checkpoint, and its questions moved to `skills/atdd/references/stage-reviews.md`.
- Stage 1 ends in a recorded red: the driver factory imports the driver inside a pytest fixture, and a red recorded at specify unlocks no production code.
- Each Given, When or Then line is one DSL call, any role writes scenarios, and engineers own the DSL and the drivers.
- Where a project's `require_evidence` adds only `outer-loop` or `isolation`, a change reuses existing DSL methods only and goes back to assess for a new one; a spike suspends the strategy.
- Edge cases follow the Compass rule for each implied failure mode in place of a list of suggestions for the person.
- Compass never reads project test code: a layering test the project owns checks the layers.
- The reference example is linked on GitHub, because `examples/` is not in the plugin copy.
- The chain is the one the scenario sections of this skill and `tdd-discipline` describe.
- The system under test can be a local build as well as a deployment.
- Stage 3 runs each scenario twice in a row, not one, so every scenario the issue adds is proven isolated.
- The description says when Compass loads the skill, in place of the source's list of triggers.
- Files are named by their repository path, as other Compass skills name them.
- The text uses US English and the Compass vocabulary.

The sections on scenarios and on behavior mapping are Compass's own, from the `bdd-specification` and `behavior-mapping` skills this one replaced.

## What it is for

This skill has three parts, by when they apply: the scenarios, for every change ([Scenarios](#scenarios) to [The requirements review](#the-requirements-review)); [Behavior mapping](#behavior-mapping), for code whose behavior is not written down; and the four layers, for a change a client can observe ([When it applies](#when-it-applies) on).

An acceptance test describes what the system does for its users, in words a product owner would recognize. It does not describe how the system does it. A test that names an endpoint, a status code, a CSS selector or a database column is tied to today's implementation. The next refactor breaks it, even though the behavior has not changed.

The four-layer model keeps that detail out of the test by giving each kind of knowledge one place to live. It covers the outer loop: one executable test per business scenario, run against a real deployment or a local build. The inner loop, unit-level red-green-refactor, is the `tdd-discipline` skill.

The chain, in order: scenario, DSL, driver, unit tests. A scenario in `acceptance-criteria.md` becomes an executable specification; each of its lines is one DSL call; each DSL call reaches the system through a protocol driver; and the code the driver reaches is written test-first, with unit tests. Specify settles each implied failure mode with the person or descopes it, and build adds no scenario the specification does not state.

## Scenarios

**BDD is a strategy, not a guardrail** - expressing acceptance criteria as Given/When/Then scenarios. It is the default way to satisfy the **acceptance-before-code guardrail**: *acceptance defined before it is built - stated, and checkable*. Keep that relationship straight.

- **Acceptance-before-code is the guardrail** - hard, checkable. No code is written that no stated, checkable acceptance criterion describes. The outcome - acceptance is stated and it is checkable - is non-negotiable on every delivery issue.
- **BDD is the strategy** - Given/When/Then is the *form*. It is the default, but it is a strategy: a context where the form genuinely does not fit is a recorded strategy deviation, not a framework violation. The hard line is that acceptance exists and is checkable; Given/When/Then is the default way to make it so.

In Compass the BDD spec is not documentation that precedes the tests - it *is* the tests, read at a different time. `acceptance-criteria.md` is written once at the specify stage, and its tests run red then green at build and as the acceptance check at ship. It is also the one artifact every role reads. Write it knowing all of that. For a change a real client can observe, the four layers below run one chain from it: scenario, DSL, driver, unit tests, each Given, When or Then line one DSL call. How a vague idea becomes scenarios, the example-first refinement chain, is in `skills/atdd/references/refinement-chain.md`. What a scenario is, and how to write a good one, is in `skills/atdd/references/scenario-craft.md`.

### The Summary comes before the scenarios

A spec opens with a **Summary** in prose, above the role-guide block, before a single Given/When/Then. Three fields:

- **Goal** - one sentence, what this change delivers in user terms.
- **Approach** - two to three sentences, the shape of the change at the level a perspective reviewer would want.
- **Why now / what changes** - one short paragraph, the visible outcome and what an adjacent role would notice afterwards.

This is the **cold-reader** strategy (write for a cold reader) applied to the spec itself. A reviewer opening a spec they did not write should be able to say what is being built and why before deciding whether to read the scenarios in detail. Without it they have to synthesize that picture from the Gherkin - easy for the author, progressively harder for everyone else, and the point at which review quietly stops happening.

The Summary is **additive**. It does not replace scenarios, and it is not a place to restate them. Length scales with the size of the change the same way scenario depth does: an atomic or small change one to two sentences per field, a medium change ordinary paragraphs, a large change or a product up to 200 words per field where the work warrants it.

### Settle edge cases before scenarios

For an id or header field, agree the missing, empty and whitespace cases with the person before you write a scenario. Do the same for any message the request leaves out. Reproduce a reported bug on current code, not an old build.

### Failure modes the brief implies

After the happy path and the edges, ask which input classes and failure modes the brief implies that no scenario yet covers. Specify settles each implied failure mode with the person or descopes it: it becomes a scenario, a light one if need be, or is recorded with `compass scenario descope "<mode>" --reason "<why>"`. Build adds no scenario the specification does not state. At ship, name every recorded mode in the report to the person, so nothing named is dropped silently.

- **Worked example, a rate limit.** "Limit search to 100 requests a minute" implies a client exactly at 100, a client over it, two clients sharing an address, and the counter's reset at the minute boundary. The first three become scenarios; the reset is de-scoped because the limiter library's own tests cover the window.
- **Worked example, a CSV import.** "Import customers from a CSV file" implies an empty file, a header with no rows, a row missing a required column, a duplicate customer, and a file that is not UTF-8. The first four become scenarios; the encoding case is de-scoped as out of scope for this release, with a follow-up issue that adds encoding detection.

## Self-review before the requirements review

When `acceptance-criteria.md` is written, run these four scans over it yourself before handing off. **Fix what you find inline** - edit the spec directly. Do not write a review artifact, and do not invoke a reviewer agent or subagent for this.

1. **Placeholder scan** - any unfilled `{{...}}` left in the file, including the three Summary fields (Goal, Approach, Why now / what changes). An unfilled Summary is the most common one, because it is written first and easiest to defer.
2. **Orphan-intent scan** - every `INT-n` in the intent-links table has at least one scenario serving it. An intent with no scenario is a stated outcome nobody agreed to check.
3. **Untestable-Then scan** - any `Then` phrased as "it works", "is correct", "behaves properly", or "feels right". If it cannot fail, it cannot pass.
4. **Ambiguous-quantifier scan** - "quickly", "large", "most", "soon" with no number attached. Either attach the number or cut the word.

**This complements the requirements review; it does not replace it.** The review still runs on every change with more than one scenario, and it does things this cannot: it QAs the spec against governance, resolves contradictions, and records an ambiguity ledger with owners. The self-check is simply what a spec-author owes the reviewer - the cheap findings fixed by whoever made them, so the review's attention goes to the questions that actually need a decision.

**On a one-scenario change, this self-check *is* the QA.** Its fixes are edits to `acceptance-criteria.md`, which is the record. Say what it found in the message that hands the scenario to the person; a finding left only in your reasoning did not happen (persistence over conversation). How the two reviews split the work, why there is no subagent critic between them, and the anti-patterns of a spec are in `skills/atdd/references/requirements-review.md`.

## The requirements review

The requirements review ends the specify stage. It is where the spec is checked *as a spec*, before anyone builds from it. Walk it for:

- **Contradictions** - two scenarios that cannot both hold.
- **Gaps** - a stated outcome (or a success signal in the Intent links) with no scenario.
- **Untestable Thens** - outcomes that cannot be observed from outside.
- **Ambiguous quantifiers** - "quickly", "most", "large" with no number.
- **Governance conflicts** - scenarios that cross a guardrail (a project coverage or security floor, an irreversible-surface rule) or that depart from an applicable strategy without a recorded reason. A guardrail conflict is a must-fix; a strategy departure is a note and a conversation.

Record each ambiguity, its resolution, and who resolved it (`compass issue decision add` for one you resolved yourself). Before the review is done:

- no ambiguity is left `open`: every entry is `resolved`;
- `acceptance-criteria.md` reflects every resolution;
- each scenario has an id, an intent and a declared test (`G2`), which `compass next` checks before it names a build step;
- the non-engineering roles in play have reviewed, and on a change that owes `scenario-approval` the person has approved the finished spec: run `compass evidence request --checkpoint specify` and stop until they type `/compass:approve`. `compass tdd-red` refuses until then.

The path has no Definition of Ready (ADR-092): the records above are what end specify. The requirements review is one read on a change with one scenario, where the self-review carries it; it is *skipped* on spike because the unknown is the point; and it is never simply *absent* on a change with more than one scenario.

## Behavior mapping

The rule behind behavior mapping is simple: **you cannot safely change behavior you have not first written down.** On `brownfield-unmapped` familiarity the routing policy makes this a floor (`RP-FLOOR-002`) - behavior mapping runs at specify, before any new scenario, before any change. On an atomic or small change with trivial or contained risk and no domain label it is advice (`RP-ADV-002`): pin what the code does now where the change touches it with a test. It produces Given/When/Then scenarios that describe what the code **does now**, marked as baseline scenarios in `acceptance-criteria.md`.

The procedure has six steps: bound the surface to the behavior the change will touch, find its interfaces, read behavior and not intent, characterize with tests where the code is opaque, write the baseline scenarios, and flag the surprises as decisions of the requirements review. Follow it in full in `skills/atdd/references/behavior-mapping.md`, which also covers what it produces, a messy current behavior and the anti-patterns.

Keep the two kinds of scenario labeled and distinct: **baseline** is what the code does now, the regression baseline; **target** is what the change will make it do, the new acceptance criteria. When the change ships, some baseline scenarios are *intentionally* superseded by target scenarios - that is a recorded decision, not a silent overwrite. The baseline you are *not* changing must still pass at ship; that is the proof you preserved what you meant to.

## When it applies

The four-layer acceptance strategy covers a change to behavior a real client can observe: what a person or a program sees through an interface real clients use, such as an API, a web UI or a CLI. A refactor, a config change or a document change does not use it.

The routing of the strategy follows the `S17` tokens a project's `require_evidence` adds. With none owed it is `guidance`: this skill is advice and no check of the strategy runs.

- `layering` owed: routing `on`. All three stages run, as below, and the change owes `outer-loop`, `isolation` and `layering`.
- `isolation` owed: routing `existing-dsl-isolation`. Reuse existing DSL methods only and prove isolation at build.
- `outer-loop` owed: routing `existing-dsl`. Reuse existing DSL methods only. Write the scenario with the DSL the project already has, take it red, then green. Add no DSL method, driver method or support code. A change that needs a new DSL method is re-assessed: run `/compass:assess --reassess` and give the reason.

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

### Stage 1, the specify stage: specification and DSL

Write the scenarios, then DSL methods that read like them, then the driver interface. The DSL calls driver methods that do not exist yet, so the suite fails. That failure is the expected starting point. Every scenario first creates its own account, workspace or tenant, and each scenario gets a new DSL instance. Stage 1 needs support code first, listed in `skills/atdd/references/support-code.md`: if any of it is missing, build it first or ask the person how to proceed.

The failure must be one a runner reports. In Python, the driver factory imports the driver inside a pytest fixture, so a missing driver is a setup error in the JUnit report, and that is the stage 1 red. A module-level import in `conftest.py` stops pytest before it writes a report (exit 4), and that run is refused as a red. Record the red with `compass tdd-red --loop outer --every-scenario -- <suite command>`. A red recorded at specify does not unlock production code: production code waits for build. The specify checkpoint reviews stage 1.

### Stage 2, the build stage: protocol driver

Implement the driver interface and put every check in it. Use plain exceptions, not the test framework's `expect()`, and never return a boolean for the caller to check. Wait for asynchronous work by polling with a timeout, not by sleeping. Stub only third-party services you do not control. The code behind the driver is built with the `tdd-discipline` cycle, one unit test at a time.

The build checkpoint reviews stage 2: the interface is complete and the tests run. Whether they pass depends on whether the system has the feature yet.

### Stage 3, the ship stage: tidy up and prove isolation

Run the suite in parallel, then run each scenario twice in a row. Both must give the same result every time. Merge driver methods that do nearly the same thing. Go through `skills/atdd/references/checklist.md` before the review. Where the project owes them, record the proof with `compass isolation record` and the layering test with `compass layering record`: they are the last build records, and `compass next` names them before any ship step. The checkpoint of the ship stage reviews stage 3.

## Isolation

Acceptance tests run against a real system, so they are slow. To keep the suite fast enough you run them in parallel, and then they must not share data. Isolate them at three levels:

- **System.** Stub only third parties you do not control, such as a payment provider, an email service or the clock. Your own database and services stay real. If you stub them, you test a system nobody deploys.
- **Functional.** Each scenario starts by creating its own partition (an account, workspace or tenant) and works only inside it.
- **Temporal.** Each identifier that must be unique goes through an alias helper. The same scenario can then run again, in the same run or a later one, without meeting its old data. How the helper works, what to alias and why there is no cleanup are in `skills/atdd/references/isolation.md`.

## Rules

- Implement only the behavior the specification states. Specify settles each implied failure mode with the person or descopes it with `compass scenario descope`; build adds no scenario the specification does not state.
- Never sleep in a test. Poll with a timeout.
- Check results by asking the system, not by trusting what the test code remembers.
- The driver reaches the system only the way real clients do. It does not call application code directly or read the database.
- When you add a driver method, add it to the interface as well as the implementation.
- Compass never reads or parses project test code. The project's layering test checks the layers, and Compass reads its recorded result.

## Other work and the reference example

To review an existing suite, follow `skills/atdd/references/review-a-suite.md`. If you have a feature description but no scenarios, follow `skills/atdd/references/from-a-feature-description.md`.

A Python example and a TypeScript example, each with an API driver, a CLI driver and a layering test, are in `examples/atdd-adapters/python/` and `examples/atdd-adapters/typescript/` of the Compass repository: <https://github.com/ayeo-io/compass/tree/main/examples/atdd-adapters>. The installed plugin does not include `examples/`, so open them on GitHub.

The four-layer model comes from Dave Farley's work on acceptance testing (*Continuous Delivery*, [cd.training](https://courses.cd.training/)). The isolation and review-stage practices also draw on Dawid Dahl's [AAID](https://github.com/dawid-dahl-umain/augmented-ai-development).
