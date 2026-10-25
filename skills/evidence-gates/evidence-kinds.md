# The kinds of evidence, and what each is for

A vocabulary, looked up when you meet a kind you do not recognize.

## Pipeline stage vocabulary - commit, acceptance, and beyond

A deployment pipeline distinguishes stages by what they test and how fast
they test it - commit, acceptance, release, production. Compass maps onto
two of those stages and explicitly stays out of the rest.

**The commit stage** is the `.red`/`tdd-green` loop - the fastest-failing
checks the pipeline has. `compass tdd-red` records a failing test; `compass tdd-green` records a
passing suite. These are fast, isolated, developer-feedback cycles. Evidence
here is `test-run`; it is the closest feedback loop in the pipeline. The
pre-tool hook enforces the ordering (the TDD strategy); the evidence-not-assertion guardrail enforces
that the evidence is real, not asserted.

**The acceptance/releasability stage** is `verify.correctness` - the checks
that decide whether the work is releasable. This is the gate that says *yes, this behavior is
what was specified* (acceptance-before-code in evidence form) and *yes, the tests pass* (tested-before-ship in
evidence form). `verify.correctness` accepts only `test-run` evidence - not
assertions, not opinions, not coverage numbers. An issue that clears
`verify.correctness` is an issue whose acceptance criteria were met by running
the acceptance suite. That is the definition of releasable within Compass.

**Release and Production stages** are out of scope for Compass: Compass is not
a deployment pipeline. It has no
concept of staging environments, progressive rollout, smoke tests in
production, or canary evaluation. Those are deployment concerns; Compass ends
at ship time. **The evidence-not-assertion guardrail**
is what Compass contributes: *evidence, not assertion* - the same principle
that drives continuous delivery discipline, but scoped to the development and
verification pipeline.

