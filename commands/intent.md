---
description: Product owner entry point - capture intent before acceptance criteria
argument-hint: "<what you want and why>"
allowed-tools: Read, Write(./.compass/**), Write(./docs/**), Edit(./.compass/**), Edit(./docs/**), Bash(compass *), Glob, Grep
---

# /compass:intent

The product owner / manager entry point. This comes **before the
acceptance criteria** - the intent is not an engineering issue and
must not be
collapsed into one. The spec will later be checked back against it.

**Intent:** $ARGUMENTS

## First: make sure this is a Compass project

Run `compass init`. It creates `.compass/` if it is not there and reports that
it did; if the project already exists it says so and changes nothing, so this
is safe to run every time and you do not need to check first.

**Report the result to the user in one line when it created the project.** If
a `.compass/` directory appears and nobody says so, someone can delete it by
hand, or commit it by mistake. It creates project state only - the
shipped defaults stay in force, and writing a `compass.yml` for the project is
what `/compass:init` offers separately.

## Setup

- Adopt the product owner's vocabulary - outcomes and users, not files and
  functions.
- Load `intent-interview` and read its `role-translation.md` - the intent is
  one role's perspective on the work the spec will serve.
- Read `${CLAUDE_PLUGIN_ROOT}/governance/strategies.md` - the product
  strategies there are the ones the intent must be consistent with (and with
  the guardrails in `guardrails.md`, in the same directory). Run
  `compass policy show` to see the guardrails in force. An unmigrated 5.x
  project runs on its own copied `governance/` until `compass policy migrate`.
- Take the product owner's perspective in this session; Compass starts no
  agent for it (ADR-090).

## Procedure

1. **Capture the intent.** Ask for, and write down in the conversation:
   - **Problem** - what is wrong or missing today, for whom.
   - **Outcome** - the change for the user that this should create. Not
     the feature; the result.
   - **Success signals** - how anyone will know the outcome happened. Scenarios
     start from these, and later the marketer's claims do too.
   - **Constraints** - what is fixed: deadlines, platforms, things that
     must not change.
2. **Check against governance.** Does this intent meet the guardrails and
   respect the product strategies? If it conflicts with a product strategy,
   name the conflict now - do not pass it on to a later stage without saying
   so.
3. **Hand the intent on.** Compass writes no intent document and registers
   nothing: the one document it needs is `acceptance-criteria.md`. Pass the
   four parts to `/compass:assess` as the description of the work. The specify
   stage writes the problem and the outcome into the Summary of
   `acceptance-criteria.md`, and each outcome into its Intent links with an
   `INT-n` id. A team that wants to keep the intent as its own note can, and
   Compass does not read it.

## How this shapes the delivery approach

Assess reads the intent as the *actual outcome wanted*, not just the literal
request. The specify stage checks the scenarios against that outcome (the
**intent-fidelity** check).

## Gate

The intent has all four parts; it is consistent with the product strategies
and guardrails in force, or the conflict is named. Next: `/compass:assess` to
compute the delivery approach, with the intent as its description.
