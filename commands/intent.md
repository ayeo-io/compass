---
description: Product owner entry point - capture intent before acceptance criteria
argument-hint: "<what you want and why>"
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
---

# /compass:intent

The product owner / manager entry point. This comes **before the
acceptance criteria** - an intent document is not an engineering issue and
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
- Load `intent-interview` and read its `role-translation.md` - `intent.md` is one role's perspective on the work
  the spec will serve.
- Read `${CLAUDE_PLUGIN_ROOT}/governance/strategies.md` - the product
  strategies there are the ones `intent.md` must be consistent with (and with
  the guardrails in `guardrails.md`, in the same directory). Run
  `compass policy show` to see the guardrails in force. An unmigrated 5.x
  project runs on its own copied `governance/` until `compass policy migrate`.
- Invoke the `product-owner` agent.

## Procedure

1. **Write the intent.** From `${CLAUDE_PLUGIN_ROOT}/templates/intent.md`, capture:
   - **Problem** - what is wrong or missing today, for whom.
   - **Outcome** - the change for the user that this should create. Not
     the feature; the result.
   - **Success signals** - how anyone will know the outcome happened. Scenarios
     start from these, and later the marketer's claims do too.
   - **Constraints** - what is fixed: deadlines, platforms, things that
     must not change.
2. **Check against governance.** Does this intent document meet the guardrails and
   respect the product strategies? If it conflicts with a product strategy,
   name the conflict now - do not pass it on to a later stage without saying
   so.
3. **Write `intent.md`** into `docs/compass/<created>-<issue-slug>/`, then
   register it with `compass issue artifact set intent --status draft --path
   <that path>`. Say so in one line if you created `docs/compass/`.

## How this shapes the delivery approach

When an issue with an `intent.md` is assessed, the artifact rule RP-ART-002
(see the routing policy) blocks the plan stage until the spec is checked
against `intent.md` (the **intent-fidelity gate**). Assess reads
`intent.md` as the *actual outcome wanted*, not just the literal request.

## Gate

`intent.md` exists with all four sections filled in; it is consistent with
the product strategies and guardrails in force, or the conflict is named.
Next: `/compass:assess` to compute the delivery approach - `intent.md` is now an
input the assess stage reads.
