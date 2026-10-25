# Coverage as evidence, and the anti-patterns

Read when a coverage question comes up or something looks wrong.

## Coverage as evidence

A project coverage-floor guardrail (e.g. "line coverage does not drop below
80%") is expressed as a *project guardrail* backed by a check, not as a
claim or an assertion. The coverage report is the evidence.

One important caveat: **coverage is a floor, never a target**. A high coverage
number is a side effect of test discipline, not its goal. Chasing a coverage
metric - writing tests specifically to hit a number - produces tests that
cover lines without asserting anything useful.
The real goal is the design-feedback loop (the TDD strategy: "Listen to your
tests"). Treat the floor as a minimum that catches a serious regression in
test discipline; treat the design-feedback loop as the thing that builds
quality in.

## Anti-patterns

- **The assertion gate** - "all green, looks good" with nothing recorded. The most
  common way the evidence-not-assertion guardrail is quietly broken.
- **The dressed-up strategy** - presenting a strategy assessment ("this follows
  our engineering strategies") as if it were an evidence-backed guardrail
  clearance. It is judgment; label it as judgment.
- **The waved-through guardrail** - clearing a guardrail on an opinion instead
  of an artifact. The mirror of the dressed-up strategy, and worse.
- **Cherry-picked output** - pasting the one green line and not the summary that
  shows three skips.
- **Stale evidence** - output from a run before the last change.
- **The judgment-free pass** - Reviewer signing off without the Verifier's
  artifacts, on the change "looking fine."
- **Deadline as a dimension** - letting "we need to ship" stand in for a real
  check. Hotfix compresses the stages *before* the verify stage; it never
  compresses the gate.
