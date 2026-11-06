# What a scenario is, and what makes one good

Reference on qualities, granularity and depth - consulted while writing.

## What a scenario is

```
Scenario: <a behavior, named as an outcome>
  Given <the world is in this concrete, specific state>
  When  <exactly one triggering action happens>
  Then  <this observable, checkable outcome holds>
```

A scenario is a single behavior with a single trigger. It is concrete enough
that someone could run it by hand and concrete enough that a test can
assert it automatically - those are the same bar.

## The qualities of a good scenario

- **Concrete state.** "Given a user" is too vague. "Given a user with a
  confirmed email and no active subscription" can be set up and asserted.
- **One When.** Two actions in `When` means two scenarios. The trigger is
  singular.
- **Observable Then.** The outcome must be checkable from outside - a returned
  value, a stored state, a rendered element, an emitted event. "Then it works"
  is not a Then. "Then the response is 402 and no charge row is written" is.
- **Declarative, not procedural.** Describe *what* is true, not the click-path
  to get there. The implementation can change; the behavior must not.
- **Named as an outcome.** "Scenario: expired token is rejected" beats
  "Scenario: test token". The name is the first thing the product owner,
  marketer, and QA read.

## Scenario granularity - splitting and merging

- **Split** when a scenario has an "and" in its `When`, or branches in its
  `Then` ("Then either X or Y"), or needs a paragraph of `Given` - those are
  multiple behaviors under one name.
- **Merge** when two scenarios differ only in an incidental value and assert the
  same behavior - use a scenario outline / examples table instead of copying.
- The unit is *one behavior*, not one feature and not one line of code. A
  feature is a set of scenarios; a line of code traces *up* to a scenario but is
  not one-to-one with it.

## How depth scales with the change

The vocabulary never changes. The depth does - and the assessment's size
tells you how much.

- **Atomic or small** - one scenario. The happy path of the new
  behavior, no more. If you cannot capture it in one unambiguous
  scenario, the size was misread. Say so and re-assess.
- **Medium** - a small scenario set: the happy path, the realistic edges,
  and the failure modes that actually matter. Not every conceivable edge -
  the ones with real consequence.
- **Large or product** - full discovery. Work the intent and the problem
  space for the whole behavior set. Then **group the scenarios by
  independence** - disjoint code, disjoint scenarios - because that grouping
  is the order in which the build takes the units.
- **The hotfix setting** (`urgency: live-defect`) - the first scenario *is*
  a failing regression test that reproduces the defect. It is written
  reproduce-first, before any fix, and it is simultaneously the BDD scenario
  and the TDD red. Before the issue closes it must read as a properly formed
  Given/When/Then scenario that names the defect, as part of the hotfix's
  follow-up (`approaches/path.md`).
- **Spike** - the BDD strategy does **not** run. A spike has no acceptance
  criteria - its output is knowledge, not behavior - so it has no specify
  stage: the *question* ("what do we need to learn, and what would a useful
  answer look like?") takes the place of the scenarios.
  You write no scenario file on a spike. If the spike graduates, real
  scenarios are written when it re-assesses onto the path,
  where acceptance-before-code applies in full.

