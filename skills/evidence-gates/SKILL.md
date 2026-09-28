---
name: evidence-gates
description: What counts as gate evidence, and how to clear a gate. Load at the verify stage.
---

# Evidence Gates

**The evidence-not-assertion guardrail** says a guardrail clears with artifacts
and command output, never a claim. "The tests pass" is not a
gate-passing statement on any delivery approach; the *recorded test run* is. This skill
covers what counts as evidence, the checklists for each review dimension, and -
just as important - the line between what is *checked* and what is *assessed*.

## Guardrails are checked; strategies are assessed

This is the distinction the whole gate model rests on. The two kinds of
governance are checked two different ways, and conflating them is the failure
mode the evidence-not-assertion guardrail exists to prevent.

- **Guardrails are *checkable*.** They are cleared with evidence - a test ran, a
  scan passed, a human approved, the artifact exists. A guardrail clears or it
  does not, and "clears" means there is recorded output a sceptic could re-run. A
  failed guardrail is a no-pass. A guardrail beats any strategy.
- **Strategies are *assessed*.** They are the reviewer's judgement - is this the
  simplest thing that works, does it follow the team's engineering or voice
  strategies, was a departure recorded. There is no pass/fail artifact for a
  strategy; there is an honest opinion, and it must be **labelled as judgement**,
  not dressed up as evidence. A strategy not followed is a note and a
  conversation, not an automatic gate failure.

Naming them differently is what stops a judgement call being presented as a
hard gate, and stops a hard gate being waved through on an opinion. When you
write the `governance` dimension into `verification-report.md`, the guardrail
findings and the strategy assessment go in clearly separated - evidence on one
side, judgement on the other.

## Evidence vs. assertion

| Assertion (does not clear a guardrail) | Evidence (clears a guardrail) |
|---|---|
| "The tests pass." | The recorded test-runner output: counts, the green summary, the command that produced it. |
| "Coverage is fine." | The coverage report, with the number, against any project coverage-floor guardrail. |
| "It's fast enough." | The benchmark output against any project performance-budget guardrail. |
| "No regressions." | The regression run, before-and-after, showing nothing green before is red now. |
| "It's secure." | The scan output; the dependency-CVE result where a project security guardrail needs it. |
| "Every claim is backed." | `launch-readiness.md` with each claim's backing scenario and that scenario's passing status. |

The test is simple: **could someone who does not trust you check it from what
you recorded?** If yes, it is evidence. If they would have to take your word, it
is assertion.

## Properties of real evidence

- **Reproducible** - it includes the command, so it can be re-run.
- **Current** - it is from this change, this run, not a remembered earlier one.
- **Complete** - it shows the whole relevant output, not a hand-picked green
  line. A run with skipped tests is not a green run; show the skips.
- **Honest about gaps** - where evidence is missing or a scenario could not be
  run, that absence is itself reported. A gap surfaced is a finding; a gap
  hidden is a lie the gate cannot catch.

## The kinds of evidence

A vocabulary - commit, acceptance, and the rest - in
`skills/evidence-gates/evidence-kinds.md`.

## How the two halves of the verify stage split

- The **Verifier** does the mechanical half: runs the scenarios as the
  acceptance suite, runs the TDD suite, runs regression, and **writes each
  capture to an evidence file and links it** from
  `verification-report.md`. It establishes what is true.
  **Link, do not paste.** A report that reproduces its evidence stops being
  something a person reads - it becomes a transcript with a summary at the top.
  The record belongs in `evidence/`; the report cites it and states what it
  shows.
- The **Reviewer** does the judgement half: applies the review dimensions to
  that evidence and the change, and renders pass / no-pass. It decides whether
  what is true is good enough.

Judgement rests on evidence. The Reviewer never passes a gate without the
Verifier's artifacts in hand.

## The review-dimension checklists

One checklist per dimension, in `skills/evidence-gates/review-dimensions.md`. Read the one for the dimension you are applying - the delivery approach says which the issue carries.

## Passing a gate - the procedure

1. Read `delivery-approach.md` for the gate set and the dimensions in play.
2. Verifier: run everything the dimensions need, write the raw output to an
   evidence record and link it from `verification-report.md`, flag every gap.
3. Reviewer: walk each dimension's checklist against the evidence and the
   change. Record per-dimension **pass** or **no-pass with the specific reason**.
4. The gate passes only if every applicable dimension passes. One no-pass sends
   the work back to the implement stage, or to a re-assess. A gate is not "mostly passed."

## Architecture checks and the verify.architecture gate

In `skills/evidence-gates/architecture-checks.md`. It applies only where a project has declared an architecture check.

## Coverage, and the anti-patterns

In `skills/evidence-gates/coverage-and-anti-patterns.md`.

## Traceability - the chain a gate is checked against

In `skills/evidence-gates/traceability.md`. Read it whenever you write an
artifact: it is how code, scenarios, claims and intents point at each other,
and `verify.traceability` is checked against exactly that chain.
