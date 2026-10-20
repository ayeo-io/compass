# Anti-patterns, and when red does not become green

Read when something has gone wrong, not while it is going right.

## Anti-patterns

- **Green-first, test-after.** Writing the code, then a test that happens to
  pass. The test never proved anything; it only documented what the code
  already did. This is the single thing the hook exists to prevent.
- **The assertion-free test.** A test that runs the code but asserts nothing,
  or asserts something trivially true. It is green without testing anything.
- **The test that never went red.** If you did not watch it fail, you do not
  know it can.
- **Behavior change during refactor.** Changing behavior during the refactor
  step. Behavior changes start at red.
- **Skipping refactor under deadline.** The mess compounds. Refactor is
  part of the cycle, not optional - even a hotfix refactors,
  when the refactor is itself low-risk.
- **Testing implementation, not behavior.** Writing assertions that are coupled
  to how the code works internally - checking which methods were called, which
  internal variables were set, or which collaborators were invoked in which
  order. The test should observe *what* the code does from outside, not *how*
  it does it. A reliable check: **swap the implementation - does the test
  survive? It should.** If swapping a correct reimplementation breaks the test,
  the test was asserting implementation details, not behavior. Test what the
  contract promises; let the implementation change freely underneath.

## When red does not become green

If a test is failing for a reason you did not predict, stop cycling and load
`systematic-debugging`. Repeatedly re-running a red test with a different guess
each time is not the TDD cycle - it is the reflex the cycle exists to replace.
That skill also carries the escape clause: three consecutive failed fixes means
the assessment was wrong, and the next move is `/compass:assess
--reassess`, not a fourth try.
