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
  does not, and "clears" means there is recorded output a skeptic could re-run. A
  failed guardrail is a no-pass. A guardrail beats any strategy.
- **Strategies are *assessed*.** They are the reviewer's judgment - is this the
  simplest thing that works, does it follow the team's engineering or voice
  strategies, was a departure recorded. There is no pass/fail artifact for a
  strategy; there is an honest opinion, and it must be **labeled as judgment**,
  not dressed up as evidence. A strategy not followed is a note and a
  conversation, not an automatic gate failure. The exception is a strategy
  that carries blocking checks, such as the four-layer acceptance strategy
  (`S17`): its checks sit outside every gate, and a recorded step-off makes
  them advisory.

Naming them differently is what stops a judgment call being presented as a
hard gate, and stops a hard gate being waved through on an opinion. When you
write the `governance` dimension into `verification-report.md`, the guardrail
findings and the strategy assessment go in clearly separated - evidence on one
side, judgment on the other.

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

## Records that meet a Definition of Done item

An item of the Definition of Done is met by a record in the manifest, never by a
tick on the page: `compass gate pass ... --meets <item>` or `compass evidence
add ... --meets <item>` records evidence, `compass follow-up add FU-<id>
--defers <item> --summary "..."` carries the item to ship, and a person ticks
an item by typing `/compass:approve` for a `compass evidence request --check
<item>`, or with `compass evidence approve --check <item>` at a terminal. `dod-evidence-typed`
fails an item with no record. `compass issue render` writes the list and each
item's state into the verification report.

## The loop a red or green belongs to

`compass tdd-red` and `compass tdd-green` write `loop` on each record:
`outer` with `--loop outer`, for a run of the acceptance suite through a
client interface, and `inner` with `--loop inner`, for a unit test. With no
flag the loop is `outer` on a quick fix the four-layer acceptance strategy
applies to, because its one declared test is its acceptance test, and
`inner` everywhere else. `compass quick-fix finish` takes the same flag. A
record with no field reads as inner. Where the four-layer acceptance strategy (`S17`)
applies, the check `outer-loop-recorded` needs an outer-loop red and an
outer-loop green recorded on the tree as it is now (ADR-080). `suite-passed`
reads every green, whatever its loop. An outer-loop record has its own file,
`red-<id>.outer.json` or `green-<id>.outer.json` (`red.outer.json` unbound),
and its own registry entry, so later inner-loop work keeps it (ADR-082).

An outer-loop green names what the suite ran against and through (ADR-085):
`--candidate <build id>|local` writes `candidate` and `candidate_kind`
(`deployed`, or `local` with the record's own `tree_id` as the candidate),
and `--client api|web|cli` writes `client`. Any other client is refused. Where
the four-layer acceptance strategy applies, `compass tdd-green` and `compass
quick-fix finish` refuse an outer-loop green that names no candidate or no
client before the command runs, `compass evidence add` refuses to register
one, and `outer-loop-recorded` fails one registered another way. A unit-test
green names neither: `compass tdd-green --loop inner` refuses the flags, and
`compass quick-fix finish`, which chooses its own loop, does not write them
on the inner loop. Like the red,
`compass tdd-green --loop outer` takes `--scenario` more than once, or
`--every-scenario`: one run writes one green per scenario, sharing a
`run_id`, and every scenario needs its red first. `compass quick-fix finish`
reuses a green already on record only when it is of the same loop and names
the same candidate and client.

Each loop keeps its own `attempts` count per scenario, so an outer-loop green
counts outer-loop runs only (ADR-084). An outer-loop run that fails counts as
a run and writes no record, so a pass on the same tree with the same
command after it has `attempts` 2 and `rerun_without_change: true`, which
`no-trusted-rerun` fails unless the test is quarantined. An outer-loop green
bound to a scenario writes `test`, the scenario's first declared test, which
`no-trusted-rerun` looks up in `governance/quarantine.yml`. Where the
four-layer acceptance strategy applies, `outer-loop-attempts-recorded` fails
an outer-loop green with no `attempts` or with one that is not a whole number
of 1 or more. A green run again keeps the time of its first run in `first_timestamp` (ADR-088).
Each record holds `file_sha256`, the SHA-256 of each changed file and declared test; `evidence/SHA256SUMS` lists them and each record file for `sha256sum -c` (ADR-089).

For the outer loop, a pytest setup error that names a missing module of the
project is an import red, as a collection error is, and the record lists
`missing_modules`. A missing module outside the project is refused. Exit 4 is
never a red: the refusal quotes pytest's first error line, and names the fix
when `conftest.py` imports the driver at module level. With `--loop outer`,
`--scenario` can repeat and `--every-scenario` binds one run to every
scenario: one record per scenario, sharing a `run_id`. A red that ends stage 1
(outer loop, an approach that runs refine, no technical design, distribution
map or subtask registered) writes `before_implement: true`, no `.red` marker
and moves no document (ADR-081). A runner that is not pytest is read from the JUnit report its adapter writes to `COMPASS_JUNIT_REPORT` (ADR-087).
Only `compass isolation record` and `compass layering record` write the isolation and layering records (ADR-086).

## Records that also move a document

`compass tdd-red` and `compass acceptance record` are the first records of the
implement stage, except a stage 1 red, which moves nothing. Each one moves the documents of earlier stages that are still
`draft` and have a path: to `approved` (with `approved_by` naming the command),
or to `awaiting-approval` when the document has a human check. A person
approves that document by typing `/compass:approve` for a `compass evidence
request --artifact <kind>`, or with `compass evidence approve --artifact <kind>`
at a terminal. That approval is recorded as `artifact-approval`, which no gate accepts and the
sign-off check of `G5` never reads.

`compass acceptance record --release-note "<text>"` also stores the issue's
release line in `release_note`, once the command passes. A failed run stores
nothing, and the flag is refused on a completed or closed issue
(`docs/release-line.md`).

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
- The **Reviewer** does the judgment half: applies the review dimensions to
  that evidence and the change, and renders pass / no-pass. It decides whether
  what is true is good enough.

Judgment rests on evidence. The Reviewer never passes a gate without the
Verifier's artifacts in hand.

## The review-dimension checklists

One checklist per dimension, in `skills/evidence-gates/review-dimensions.md`. Read the one for the dimension you are applying - the delivery approach says which the issue carries.

## Passing a gate - the procedure

1. Read `delivery-approach.md` for the gate set and the dimensions in play.
2. Verifier: run everything the dimensions need, write the raw output to an
   evidence record and link it from `verification-report.md`, flag every gap.
3. Reviewer: walk each dimension's checklist against the evidence and the
   change. Record per-dimension **pass** or **no-pass with the specific reason**.
4. Before the verification report is complete, make sure that every required
   review dimension passed with evidence attached, that every gate in the
   delivery-approach record and every immovable gate is green, and that no
   evidence block is empty. The report holds no tick boxes.
5. The gate passes only if every applicable dimension passes. One no-pass sends
   the work back to the implement stage, or to a re-assess. A gate is not "mostly passed."

## Architecture checks and the verify.architecture gate

In `skills/evidence-gates/architecture-checks.md`. It applies only where a project has declared an architecture check.

## Coverage, and the anti-patterns

In `skills/evidence-gates/coverage-and-anti-patterns.md`.

## Traceability - the chain a gate is checked against

In `skills/evidence-gates/traceability.md`. Read it whenever you write an
artifact: it is how code, scenarios, claims and intents point at each other,
and `verify.traceability` is checked against exactly that chain.
