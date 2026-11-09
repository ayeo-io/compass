# How test surface scales with risk, working in a worktree, and listening to your tests

Reference for how much test to write and what the tests are telling you, plus the worktree rules that apply only on a multiagent.

## How test surface scales with risk

This is the dimension the assessment *does* adapt. "More surface" means more of the
behavior's space is pinned by tests - more edges, more failure modes, more
adversarial inputs - not "tests at all," which is constant.

- **`trivial` risk** - the scenario and its obvious edges.
- **`contained`** - the scenario, its realistic edges, the failure modes
  that matter.
- **`cross-cutting`** - the above plus the interaction surface: how this
  behavior holds when adjacent features are also exercised.
- **`critical`** - the above plus adversarial and boundary inputs, the rollback
  path, and the failure modes that lose data or money. Plus whatever any
  project coverage or security guardrail floor requires.

No issue may go *below* a project coverage-floor guardrail in
the rules in force (`compass policy show`; an unmigrated 5.x project is
refused until `compass policy migrate` on 8.x). It can need *more* for higher risk, and must
never need less.

## Working through several units

Compass 9.0.0 builds the work units one after another in one
session, with no worktree per unit (ADR-090). Run each unit's full cycle -
including its red, failing test - before you start the next, so one unit's red
never hides another's. If a test for one unit reaches into another unit's
surface, the units are not independent: say so, and fold or reorder them.

## Listen to your tests

A hard-to-write test is a sign of a design problem - not a reason to write a clever test,
but a signal to change the design.

When a test needs extensive setup, elaborate mocking, or deep knowledge of
internal state to run, the code under test is telling you something: it has too
many dependencies, it couples the what to the how, or it lives in the wrong
place. The test is the first client of your code; if that client is struggling,
the next client will too.

The response to a hard-to-write test is **not** to write a harder test. It is
to ask: *what would make this test easy to write?* Then change the design to
match. This is TDD's second payoff - not just coverage, but continuous
design pressure towards simplicity.

Signs of a design problem:

- You cannot test the new behavior without instantiating five other classes.
- Your test setup is longer than the assertion.
- You need to reach into private state or patch internal calls to set up the
  scenario.
- The test breaks every time you touch an unrelated part of the codebase.

Each of these is the test speaking. The right answer is refactoring the
production code so the test becomes easy, not accepting the pain.

