---
name: tdd-discipline
description: The red-green-refactor cycle as Compass runs it, including what to do when a change has no natural failing test. Load while implementing.
---

# TDD Discipline

**TDD is a strategy, not a guardrail** - and keeping that relationship
straight is the whole point.

- **The guardrail is tested-before-ship** - hard, checkable, universal. No
  code reaches `main` without a passing automated test it traces to. It is
  checked at the verify stage and at ship time, with evidence. It never adapts and it
  has no exception.
- **TDD is the strategy** - red-before-green, the strong, shipped-on
  default way to satisfy that guardrail on every delivery approach. But it
  is a strategy, which means it has exactly one suspension: a **spike**
  turns it off (see below). The *outcome* (the tested change) is
  non-negotiable; the *ritual* (red-first) is the default method,
  suspendable in one defined place.

This is the distinction that keeps Compass from applying full process to
every change: a one-character typo fix still goes red first; what the
approach adapts is how much
*surface* the tests cover, and on a spike, whether the ritual runs at all.
What no delivery approach adapts is the outcome.

## Approach-awareness: suspended on a spike

On a **spike** the TDD strategy is **suspended**. Red-before-green is
the wrong discipline for code you are writing precisely to learn something and
will likely throw away - forcing it would throttle exploration for no safety
gain.

This is safe because of the hard rule under it: **nothing ships from a
spike.** A spike's code reaches production only by *graduating* -
re-assessing into a real delivery approach - and at that point the
guardrail applies in full: graduated code is tested before it ships,
usually rewritten under TDD, sometimes kept and tested afterwards. The strategy
is suspended; the guardrail is only *deferred to graduation*, never
skipped.

On every other approach - quick fix, feature, initiative, hotfix - the TDD
strategy applies. Red comes first. It is on the quick fix, and it is on
the hotfix under time pressure.

## The cycle

**Red → Green → Refactor**, one scenario at a time.

1. **Red.** Write a test for the next behaviour and watch it fail *for the
   right reason*. A test that fails because of a typo is not a red - it has
   not yet described the behaviour. The failure message should read like the
   absence of the feature. One case is still a red although pytest cannot
   collect the test: the test imports a module of this project that is not
   written yet. `compass tdd-red` records it as an **import red** when the
   module's top-level package already exists as a Python package within
   three levels of the project root. For a new top-level package, create its
   directory first. Any other collection error is refused, and so is a run
   in which pytest's report shows no failed test, whatever its exit code.
2. **Green.** Write the smallest correct code that makes the test pass. Not the
   most elegant, not the most general - the smallest *correct*. Generality is
   earned in refactor, under a green suite.
3. **Refactor.** With the suite green, improve the design - names, duplication,
   structure. The test does not change here; if it has to, you were refactoring
   behaviour, which means going back to red.

Then the next scenario. Small loops. A long gap between red and green is a sign
the step was too big.

## What "the failing test first" actually means

- The test exists and fails *before* the production code that satisfies it is
  written. Not after. Not "alongside."
- It fails because the behaviour is absent - not because it is malformed.
- It is derived from a scenario in `acceptance-criteria.md`. The TDD strategy (red-before-green) and
  the BDD strategy are not two systems: the BDD scenario is the
  acceptance-level test and seeds the unit-level TDD cycle. The chain is
  scenario → test → code.
- One red at a time. A wall of failing tests written up front is not TDD; it is
  a test plan. Take them one behaviour at a time so each green is a real,
  isolated step.

## Working under the pre-tool hook

`hooks/pre-tool.sh` enforces the red-before-green strategy mechanically: it will
**block a code edit that has no corresponding failing test.** It is the TDD
strategy enforced by a hook, in service of the guardrail. It is also
**approach-aware**: it reads a `.compass/work/<task>/.spike` marker file
and does **not** block on a spike, because the TDD strategy is suspended
there.

- If the hook blocks you on delivery work, the correct response is to go
  write the failing test, not to find a path past the hook.
- Disabling, bypassing, or tricking the hook where it applies is breaking
  the TDD strategy - and on delivery work that is how the guardrail gets
  quietly broken. There is no deadline and no convenience that licenses
  it.
- The hook checks for a *failing* test, so the natural workflow already
  satisfies it: write the red, see it fail, then edit the code.
- On a spike the hook is silent by design - that is the strategy being
  suspended, not the hook being bypassed. The safety comes from the fact
  that nothing ships from a spike, not from the hook.

## When the change has no natural red

In `skills/tdd-discipline/no-natural-red.md`.

## How much test, and working in a worktree

In `skills/tdd-discipline/test-surface-and-worktrees.md` - how test surface
scales with risk, what your tests are telling you, and the worktree rules for
multiagent orchestrations.

## Anti-patterns

In `skills/tdd-discipline/anti-patterns.md`.

