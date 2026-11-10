---
name: evidence-gates
description: What counts as evidence, and the review checklists a project's settings can add. Load when a change owes a review.
---

# Evidence Gates

**The evidence-not-assertion guardrail** says a guardrail clears with artifacts
and command output, never a claim. "The tests pass" is not a
gate-passing statement on any delivery issue; the *recorded test run* is. This skill
covers what counts as evidence, the review-dimension checklists, and the line
between what is *checked* and what is *assessed*.

## Guardrails are checked; strategies are assessed

- **Guardrails are *checkable*.** They are cleared with evidence - a test ran, a
  scan passed, a human approved, the artifact exists. A guardrail clears or it
  does not, and "clears" means there is recorded output a skeptic could re-run. A
  failed guardrail is a no-pass. A guardrail beats any strategy.
- **Strategies are *assessed*.** They are the reviewer's judgment - is this the
  simplest thing that works, does it follow the team's engineering or voice
  strategies, was a departure recorded. There is no pass/fail artifact for a
  strategy; there is an honest opinion, and it must be **labeled as judgment**,
  strategy; there is an honest opinion, and it must be **labeled as judgment**,
  not dressed up as evidence. A strategy not followed is a note and a
  conversation, not an automatic gate failure.

In the `governance` dimension, report the guardrail findings (evidence) and
the strategy assessment (judgment) separately.

## Evidence vs. assertion

| Assertion (does not clear a guardrail) | Evidence (clears a guardrail) |
|---|---|
| "The tests pass." | The recorded test-runner output: counts, the green summary, the command that produced it. |
| "Coverage is fine." | The coverage report, with the number, against any project coverage-floor guardrail. |
| "It's fast enough." | The benchmark output against any project performance-budget guardrail. |
| "No regressions." | The regression run, before-and-after, showing nothing green before is red now. |
| "It's secure." | The scan output; the dependency-CVE result where a project security guardrail needs it. |
| "Every claim is backed." | The manifest's `claims:`, each with its backing scenario, and that scenario's passing status. |

The test is simple: **could someone who does not trust you check it from what
you recorded?** If yes, it is evidence. If they would have to take your word, it
is assertion.

## The red and green records

`compass quick-fix finish` writes them. The fields of a record, the loop it
belongs to, the scenario freeze and the records of the Definition of Done are
in `skills/evidence-gates/red-green-records.md`.

## Properties of real evidence

- **Reproducible** - it includes the command, so it can be re-run.
- **Current** - it is from this change, this run, not a remembered earlier one.
- **Complete** - it shows the whole relevant output, not a hand-picked green
  line. A run with skipped tests is not a green run; show the skips.
- **Honest about gaps** - missing evidence, or a scenario that could not be
  run, is reported. A hidden gap is one the gate cannot catch.

## The kinds of evidence

A vocabulary - commit, acceptance, and the rest - in `skills/evidence-gates/evidence-kinds.md`.

## The review-dimension checklists

One checklist per dimension, in `skills/evidence-gates/review-dimensions.md`.
The issue's `evidence_required` list says which the issue carries.

## Passing a gate

`compass quick-fix finish` passes the three gates every delivery issue has
(`verify.correctness`, `verify.governance`, `verify.traceability`) from the
test records and the output of `compass check`. Do not pass them by hand.

A gate that the project's settings add is yours to pass. `finish` names the
command for each on a `next:` line. Run what the dimension's checklist needs,
write the raw output to a file, register it as evidence and pass the gate
with it. Then run the same `finish` again. One no-pass sends the work back
to the code: a gate is not "mostly passed".

## Architecture checks and the verify.architecture gate

In `skills/evidence-gates/architecture-checks.md`. It applies only where a project has declared an architecture check.

## Coverage, and the anti-patterns

In `skills/evidence-gates/coverage-and-anti-patterns.md`.

## Traceability - the chain a gate is checked against

In `skills/evidence-gates/traceability.md`: how code, scenarios, claims and
intents point at each other. `verify.traceability` is checked against that
chain.
