---
name: bdd-specification
description: Writing and checking Given/When/Then acceptance scenarios. Load at specify.
---

# BDD Specification

**BDD is a strategy, not a guardrail** - expressing acceptance criteria
as Given/When/Then scenarios. It is the default way to
satisfy the **acceptance-before-code guardrail**: *acceptance defined
before it is built - stated, and checkable*. Keep that relationship
straight.

- **Acceptance-before-code is the guardrail** - hard, checkable. No code is written that no stated,
  checkable acceptance criterion describes. The outcome - acceptance is stated
  and it is checkable - is non-negotiable on every delivery issue.
- **BDD is the strategy** - Given/When/Then is the *form*. It is the default,
  but it is a strategy: a context where the form genuinely does not
  fit is a recorded strategy deviation, not a framework violation. The hard
  line is that acceptance exists and is checkable; Given/When/Then is the
  default way to make it so.

In Compass the BDD spec is not documentation that precedes the tests - it *is*
the tests, read at a different time. `acceptance-criteria.md` is written once at
the specify stage, and its tests run red then green at build and as the
acceptance check at ship. It is also the one artifact
five roles read (see `skills/intent-interview/role-translation.md`). Write it knowing all of that.
For a change a real client can observe, the `atdd` skill runs one chain from
it: scenario, DSL, driver, unit tests, each Given, When or Then line one DSL call.

## Example-first refinement chain

In `skills/bdd-specification/refinement-chain.md`.

## The Summary comes before the scenarios

A spec opens with a **Summary** in prose, above the role-guide block, before a
single Given/When/Then. Three fields:

- **Goal** - one sentence, what this change delivers in user terms.
- **Approach** - two to three sentences, the shape of the change at the level a
  perspective reviewer would want.
- **Why now / what changes** - one short paragraph, the visible outcome and what
  an adjacent role would notice afterwards.

This is the **cold-reader** strategy (write for a cold reader) applied to the spec itself. A
reviewer opening a spec they did not write should be able to say what is being
built and why before deciding whether to read the scenarios in detail. Without
it they have to synthesize that picture from the Gherkin - easy for the author,
progressively harder for everyone else, and the point at which review quietly
stops happening.

The Summary is **additive**. It does not replace scenarios, and it is not a
place to restate them. Length scales with the size of the change the same way
scenario depth does: an atomic or small change one to two sentences per
field, a medium change ordinary paragraphs, a large change or a product up to
200 words per field where the work warrants it.

## Settle edge cases before scenarios

For an id or header field, agree the missing, empty and whitespace cases with
the person before you write a scenario. Do the same for any message the request
leaves out. Reproduce a reported bug on current code, not an old build.

## Failure modes the brief implies

After the happy path and the edges, ask which
input classes and failure modes the brief implies that no scenario yet covers.
Specify settles each implied failure mode with the person or descopes it: it
becomes a scenario, a light one if need be, or is recorded with
`compass scenario descope "<mode>" --reason "<why>"`. Build adds no
scenario the specification does not state. At ship, name every recorded
mode in the report to the person, so nothing named is dropped silently.

- **Worked example, a rate limit.** "Limit search to 100 requests a minute"
  implies a client exactly at 100, a client over it, two clients sharing an
  address, and the counter's reset at the minute boundary. The first three
  become scenarios; the reset is de-scoped because the limiter library's own
  tests cover the window.
- **Worked example, a CSV import.** "Import customers from a CSV file"
  implies an empty file, a header with no rows, a row missing a required
  column, a duplicate customer, and a file that is not UTF-8. The first four
  become scenarios; the encoding case is de-scoped as out of scope for this
  release, with a follow-up issue that adds encoding detection.

## Self-review before the requirements review

When `acceptance-criteria.md` is written, run these four scans over it yourself before
handing off. **Fix what you find inline** - edit the spec directly. Do not write
a review artifact, and do not invoke a reviewer agent or subagent for this.

1. **Placeholder scan** - any unfilled `{{...}}` left in the file, including the
   three Summary fields (Goal, Approach, Why now / what changes). An unfilled
   Summary is the most common one, because it is written first and easiest to
   defer.
2. **Orphan-intent scan** - every `INT-n` in the intent-links table has at least
   one scenario serving it. An intent with no scenario is a stated outcome
   nobody agreed to check.
3. **Untestable-Then scan** - any `Then` phrased as "it works", "is correct",
   "behaves properly", or "feels right". If it cannot fail, it cannot pass.
4. **Ambiguous-quantifier scan** - "quickly", "large", "most", "soon" with no
   number attached. Either attach the number or cut the word.

**This complements the requirements review; it does not replace it.**
The review still runs on every change with more than one scenario, and it
does things this cannot: it QAs the spec against governance, resolves
contradictions, and records an ambiguity ledger with owners. The
self-check is simply what a spec-author owes the reviewer - the cheap
findings fixed by whoever made them, so the review's attention goes to
the questions that actually need a decision.

### The split, stated plainly

The two overlap enough that a reader meeting both wonders which is redundant.
Neither is. They differ in *who does them*, *what they cost*, and *what kind of
finding they can produce*.

| | Inline self-review (while writing) | Requirements review (end of specify) |
|---|---|---|
| **Who** | the spec-author, alone | spec-author plus reviewer; the person where `scenario-approval` is owed |
| **Cost** | minutes - four mechanical scans over one file | needs reading, and often a human decision |
| **Finds** | placeholder, orphan-intent, untestable-`Then`, ambiguous-quantifier | contradictions between scenarios, gaps across the whole set, governance conflicts, ambiguities that need someone to *choose* |
| **Output** | edits to `acceptance-criteria.md`, in place | a resolution and an owner per ambiguity, recorded as decisions |
| **When** | every delivery issue | every delivery issue with more than one scenario; a one-scenario change and the hotfix's reproduction need only the self-review; a spike has neither |

The dividing line: **the self-review fixes what one person can see and
settle alone; the requirements review resolves what needs a decision.** An unfilled placeholder has
one correct answer and the author already knows it. "Do these two scenarios
contradict each other, and which one is wrong?" does not - and pretending
otherwise is how a spec ships with an unresolved contradiction.

The review does not re-run the four scans. If it finds one of them still
open, that means the self-review was skipped: worth saying so, not worth
silently absorbing.

**On a one-scenario change, this self-check *is* the QA.** Its fixes are
edits to `acceptance-criteria.md`, which is the record. Say what it found
in the message that hands the scenario to the person; a finding left only
in your reasoning did not happen (persistence over conversation).

*Why there is no subagent critic here.* The R1 project shipped a
subagent review loop between spec and plan and then removed it in their
[v5.0.6 release](R1/releases/tag/v5.0.6).
They reported regression testing across five versions and five
trials that found identical quality scores whether the loop ran or not, at
roughly 25 minutes of overhead per run. Compass has not repeated that
measurement and takes the published result at face value. Compass already has
two review points that earn their cost: **the requirements review**, which
QAs the spec against governance, and the **review** at ship. A
third pass between them would double the time without measurably
improving the spec.

## What a scenario is

In `skills/bdd-specification/scenario-craft.md`.

## The requirements review - QA the spec against itself and against governance

The requirements review ends the specify stage. It is where the spec is
checked *as a spec*, before anyone builds from it.
Walk it for:

- **Contradictions** - two scenarios that cannot both hold.
- **Gaps** - a stated outcome (or a success signal in the Intent links) with no scenario.
- **Untestable Thens** - outcomes that cannot be observed from outside.
- **Ambiguous quantifiers** - "quickly", "most", "large" with no number.
- **Governance conflicts** - scenarios that cross a guardrail (a project
  coverage or security floor, an irreversible-surface rule) or that depart from
  an applicable strategy without a recorded reason. A guardrail conflict is a
  must-fix; a strategy departure is a note and a conversation.

Record each ambiguity, its resolution, and who resolved it (`compass issue
decision add` for one you resolved yourself). Before the review is done:
- no ambiguity is left `open`: every entry is `resolved`;
- `acceptance-criteria.md` reflects every resolution;
- each scenario has an id, an intent and a declared test (`G2`), which
  `compass next` checks before it names a build step;
- the non-engineering roles in play have reviewed, and on a change that
  owes `scenario-approval` the person has approved the scenarios: run
  `compass evidence request --checkpoint specify` and stop until they type
  `/compass:approve`.

The path has no Definition of Ready (ADR-092): the records above are what
end specify. The requirements review:
- is one read on a change with one scenario, where the self-review carries it;
- is *skipped* on spike because the unknown is the point;
- is never simply *absent* on a change with more than one scenario.

## Anti-patterns

- **The implementation scenario** - `Given the cache is warm, When flushCache()
  is called…`. That tests the code's shape, not its behavior. Scenarios outlive
  implementations.
- **The unfalsifiable Then** - "Then the user has a good experience." If it
  cannot fail, it cannot pass; it is not a scenario.
- **The orphan-creating spec** - leaving real behavior with no scenario.
  The acceptance-before-code guardrail forbids code that no stated acceptance criterion describes; the
  spec is where you prevent the orphan, not the ship stage.
- **The novel** - a scenario with five `Given` lines and three `When` lines.
  Split it.
