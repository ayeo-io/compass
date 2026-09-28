---
description: Product owner entry point - capture intent before acceptance criteria
argument-hint: "<what you want and why>"
allowed-tools: Read, Write, Edit, Glob, Grep
---

# /compass:intent

The product owner / manager entry point. This sits **upstream of the
acceptance criteria** - an intent document is not an engineering issue and
must not be
collapsed into one. The spec will later be checked back against it.

**Intent:** $ARGUMENTS

## First: make sure this is a Compass project

Run `compass init`. It creates `.compass/` if it is not there and reports that
it did; if the project already exists it says so and changes nothing, so this
is safe to run every time and you do not need to check first.

**Report the result to the user in one line when it created the project.** A
`.compass/` directory appearing with no word said is how someone deletes it by
hand, or commits it without meaning to. It creates project state only - the
shipped governance defaults stay in force, and adopting your own is what
`/compass:init` offers separately.

## Setup

- Adopt the product owner's vocabulary - outcomes and users, not files and
  functions.
- Load `intent-interview` and read its `role-translation.md` - `intent.md` is one role's perspective on the work
  the spec will serve.
- Read `governance/strategies.md` - the product owner curates the product
  strategies there, and `intent.md` must be consistent with them (and with the
  guardrails in `governance/guardrails.md`).
- Invoke the `product-owner` agent.

## Procedure

1. **Write the intent.** From `${CLAUDE_PLUGIN_ROOT}/templates/intent.md`, capture:
   - **Problem** - what is wrong or missing today, for whom.
   - **Outcome** - the change in the user's world this should create. Not
     the feature; the result.
   - **Success signals** - how anyone will know the outcome happened. These
     become the seeds of scenarios and, later, of the marketer's claims.
   - **Constraints** - what is fixed: deadlines, platforms, things that
     must not change.
2. **Check against governance.** Does this intent document meet the guardrails and
   respect the product strategies? If it pulls against a product strategy,
   name the tension now - do not pass it downstream silently.
3. **Write `intent.md`** into `docs/compass/<created>-<issue-slug>/`, then
   register it with `compass issue artifact intent --status draft --path
   <that path>`. Say so in one line if you created `docs/compass/`.

## How this shapes the delivery approach

When an issue with an `intent.md` is assessed, the `product-owner` role adds
two things (see the delivery-approach rubric and the routing policy's
`role_rules`): the `intent.md` artifact, and the **intent-fidelity gate**.
The spec must be checked against `intent.md` before the plan stage. Assess reads
`intent.md` as the *actual outcome wanted*, not just the literal request.

## Gate

`intent.md` exists with all four sections real; it is consistent with the
product strategies and guardrails in `governance/`, or the tension is named.
Next: `/compass:assess` to compute the delivery approach - `intent.md` is now an
input the assess stage reads.
