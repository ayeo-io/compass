---
description: Acceptance criteria as BDD scenarios every role reads
allowed-tools: Read, Write, Edit, Glob, Grep
---

# /compass:define

Define turns intent into Given/When/Then acceptance criteria. This is the
**shared artifact** - the product owner reads it for intent fidelity, the
marketer for claims, the engineer for tests, the designer for the UI
contract, QA for coverage. Write it so all five roles can.

## Setup

- Read `delivery-approach.md`. Its weight for this stage tells you how deep
  to go:
  - one scenario (quick fix);
  - a small feature set (feature);
  - full BDD discovery (initiative);
  - on a **spike** - collapsed into *the question* (what do we need to
    learn, and what would a useful answer look like), not acceptance
    criteria for code.

  Honour it.
- Load the `bdd-specification` skill.
- If `delivery-approach.md` assesses familiarity as `brownfield-unmapped`,
  also load `behaviour-mapping` - reverse-engineer the *current*
  behaviour into scenarios **before** writing the scenarios for the change. A
  policy floor forces this unless the change is atomic or small, with trivial
  or contained risk and no domain label; you cannot safely change what you have not first
  described.
- Invoke the `spec-author` agent - it owns this stage.
- Read any upstream role artifacts for this issue: `intent.md` (the outcome to
  hit), `ui-contract.md` (designer scenarios that flow in here),
  `positioning.md` (claims that will need backing scenarios).

## Procedure

1. **Discovery or behaviour mapping.** Greenfield: discover scenarios from the
   intent document or request. Brownfield-unmapped: map current behaviour
   first, then
   add the change scenarios.
2. **Write scenarios** as Given/When/Then - happy path, the realistic edges,
   the failure modes that matter. Depth scales with the delivery approach,
   but never to zero: "no scenario" is never a valid state. On a quick fix
   the single scenario must be genuinely unambiguous, because the
   requirements review is collapsed only because the scenario is unambiguous.
   Then ask yourself which input classes and failure modes the brief
   implies that no scenario yet covers. Each answer becomes a scenario, a
   light one if need be, or is recorded with
   `compass scenario descope "<mode>" --reason "<why>"`, which the verifier
   lists in the verification report. Nothing named is dropped silently.
   - **Worked example, a rate limit.** The brief says "limit search to 100
     requests a minute". The happy path is one client under the limit. It
     implies: a client exactly at 100, a client over it, two clients sharing
     an address, and the counter's reset at the minute boundary. Each of the
     first three becomes a scenario; the reset is de-scoped with the reason
     "the limiter library's own tests cover the window".
   - **Worked example, a CSV import.** The brief says "import customers from
     a CSV file". It implies: an empty file, a header with no rows, a row
     with a missing required column, a duplicate customer, and a file that
     is not UTF-8. The first four become scenarios; the encoding case is
     de-scoped with the reason "non-UTF-8 files are out of scope for this
     release; a follow-up issue adds encoding detection".
3. **Group by independence.** On larger work, group scenarios by which touch
   disjoint surface - this grouping seeds the distribution map at the plan
   stage.
4. **Maintain traceability** - load `evidence-gates` and read its
   `traceability.md`; each scenario traces to
   an intent (`intent.md`, the request, the defect).
5. **Write `acceptance-criteria.md`** from `${CLAUDE_PLUGIN_ROOT}/templates/acceptance-criteria.md` -
   the prose spec every role reads.

   **Where it goes.** `docs/compass/<created>-<issue-slug>/acceptance-criteria.md`, where the
   date is the manifest's `created:` field - not today's. Then register it:
   `compass issue artifact acceptance-criteria --status draft --path <that path>`. The CLI
   refuses a path that climbs out of the project, so the record is checked
   rather than claimed. If you had to create `docs/compass/`, **say so in one
   line** - a directory appearing with nothing said is how it gets deleted by
   hand or committed by accident.
6. **Write the `scenarios:` block of `manifest.yml`** - the machine-readable
   index of the prose spec. Each scenario gets a stable `id`, a `title`, a
   linked `intent` id, and the `tests` that exercise it. This is what
   `compass check` reads to check the acceptance-before-code and
   traceability guardrails; implementation then traces `changed_files` to
   these ids. On a spike, there are no scenarios - the block stays empty.

## Hotfix note

On a hotfix, this stage is **reproduce-first**: the spec is a failing
regression test that reproduces the defect - simultaneously the BDD scenario
and the TDD red. Write that test now; the proper scenario is promoted into
`acceptance-criteria.md` as the follow-up owed at ship time.

## Spike note

On a spike, this stage is **collapsed into the question**: the spike's spec
is "what do we need to learn, and what would a useful answer look like?" -
not Given/When/Then acceptance criteria: a spike has no acceptance
criteria, because its output is knowledge, not behaviour. Record the question
and the timebox; the BDD strategy does not apply here. See `${CLAUDE_PLUGIN_ROOT}/approaches/spike.md`.

## Hand-off

Close this stage by handing the spec to a human, in these words or close to
them. The point is to make the review a deliberate moment rather than an
implied one - a reviewer who is told what to look for finds more than one who
is told a file is ready.

> I have written the acceptance criteria to
> `docs/compass/<created>-<issue-slug>/acceptance-criteria.md`.
>
> It opens with a Summary - Goal, Approach, and Why now / what changes - so
> you can see what this delivers before reading any scenarios. Below that are
> N scenarios in M groups, each traced to an intent.
>
> Worth a cold read. Specifically, look for:
> - **Intent fidelity** - do these scenarios deliver the outcome you actually
>   want, not just the request as literally phrased?
> - **Untestable Thens** - any outcome that could not be observed from
>   outside.
> - **Missing failure modes** - what goes wrong here that no scenario covers?
> - **Ambiguous quantifiers** - "quickly", "large", "most" with no number.
>
> On approval this goes to refine - the requirements review - which QAs it
> against governance and resolves any ambiguity into a recorded decision.
> Nothing is built from it until then.

Fill in the real path, counts, and group names - a prompt that still says
`<issue-slug>` has not been read by the person sending it.

## Gate

On delivery work:
- `acceptance-criteria.md` exists;
- every scenario is Given/When/Then;
- every scenario traces to an intent;
- no described behaviour is missing a scenario;
- `manifest.yml`'s `scenarios:` block mirrors it - each with an id, a linked
  intent, and at least one test.

On a spike: the question
and timebox are recorded. Log to `devlog.md`. Next: `/compass:refine` (or
straight to `/compass:plan` if `delivery-approach.md` collapsed the
requirements review - and it is skipped entirely on a spike).
