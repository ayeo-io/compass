---
name: tdd-discipline
description: The red-green-refactor cycle, and what to do with no natural failing test. Load when you write a test first.
---

# TDD Discipline

**TDD is a strategy, not a guardrail.**

- **The guardrail is tested-before-ship.** Every change lands with a test
  that fails without it. `compass quick-fix finish` checks it: the change's
  tests must fail on a copy of the base commit and pass on the working tree.
  It never adapts.
- **TDD is the strategy** - red-before-green, the default way to meet that
  guardrail. Compass does not check the order of the work: the red that
  `finish` records shows that the tests fail without the change, not that
  they were written first. `compass tdd-red -- <test command>`, run before
  the code, is the only way to record that. The strategy has one
  suspension: a **spike** turns it off (see below).

## Approach-awareness: suspended on a spike

On a **spike** the TDD strategy is **suspended**. Red-before-green is
the wrong discipline for code you are writing precisely to learn something and
will likely throw away - forcing it would throttle exploration for no safety
gain.

This is safe because of the hard rule under it: **nothing ships from a
spike.** A spike's code reaches production only by *graduating* -
re-assessing onto the path - and at that point the
guardrail applies in full: graduated code is tested before it ships,
usually rewritten under TDD, sometimes kept and tested afterwards. The strategy
is suspended; the guardrail is only *deferred to graduation*, never
skipped.

## The cycle

**Red → Green → Refactor**, one scenario at a time.

1. **Red.** Write a test for the next behavior and watch it fail *for the
   right reason*. A test that fails because of a typo is not a red - it has
   not yet described the behavior. The failure message should read like the
   absence of the feature.
2. **Green.** Write the smallest correct code that makes the test pass. Not the
   most elegant, not the most general - the smallest *correct*. Generality is
   earned in refactor, under a green suite.
3. **Refactor.** With the suite green, improve the design - names, duplication,
   structure. The test does not change here; if it has to, you were refactoring
   behavior, which means going back to red.

Then the next scenario. Small loops. A long gap between red and green is a sign
the step was too big.

## What "the failing test first" actually means

- The test exists and fails *before* the production code that satisfies it is
  written. Not after. Not "alongside."
- It fails because the behavior is absent - not because it is malformed.
- It is derived from a scenario in `acceptance-criteria.md`. The TDD strategy (red-before-green) and
  the BDD strategy are not two systems: the BDD scenario is the
  acceptance-level test and seeds the unit-level TDD cycle. The chain is
  scenario → test → code. For a change a real client can observe, the `atdd`
  skill spells it out: scenario, DSL, driver, unit tests. The scenario runs
  through the DSL and a driver as the outer loop; the code behind the driver
  is built here, one unit test at a time.
- One red at a time. A wall of failing tests written up front is not TDD; it is
  a test plan. Take them one behavior at a time so each green is a real,
  isolated step.

## The pre-tool hook

On a delivery issue `hooks/pre-tool.sh` needs no failing test before a code
edit, because `finish` proves the red. It refuses a code edit while the
scenarios wait for a person's approval (`code-before-approval`). The
response is to ask for the approval, not to find a path past the hook. It
reads a `.compass/work/<task>/.spike` marker file and does **not** block on
a spike, because the TDD strategy is suspended there.

## When the change has no natural red

In `skills/tdd-discipline/no-natural-red.md`.

## How much test, and working in a worktree

In `skills/tdd-discipline/test-surface-and-worktrees.md` - how test surface
scales with risk, what your tests are telling you, and how to work through
several units in one session.

## Anti-patterns

In `skills/tdd-discipline/anti-patterns.md`.

