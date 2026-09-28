---
description: Marketer entry point - positioning, and the claims that will need scenarios
argument-hint: "<what is being positioned>"
allowed-tools: Read, Write, Edit, Glob, Grep
---

# /compass:position

The product marketer entry point. The marketer works **parallel to the
define stage** - not downstream of a finished engineering process. Every
public claim must trace to a passing scenario; the claims gate blocks
shipping until it does.

**Subject:** $ARGUMENTS

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

- Adopt the marketer's vocabulary - claims, voice, audience.
- Load `intent-interview` and read its `role-translation.md` - positioning is the claims perspective on the
  shared spec.
- Read `governance/strategies.md` - the marketer curates the voice &
  positioning strategies there; voice, claims discipline, and the honesty
  policy come from them. Read `governance/guardrails.md` too - the
  traceability guardrail keeps every public claim traced to a backing
  criterion.
- Read `acceptance-criteria.md` if it exists - claims point at scenarios.
- Invoke the `product-marketer` agent.

## Procedure

1. **Write positioning.** From `${CLAUDE_PLUGIN_ROOT}/templates/positioning.md`: the audience,
   the core message, and the claim set. For **every claim**, name the
   scenario in `acceptance-criteria.md` that backs it. A claim with no
   backing scenario is not yet a claim - it is either a scenario that needs
   writing (raise it with `spec-author` at the define stage) or a claim
   that must be dropped.
2. **Write launch readiness.** From `${CLAUDE_PLUGIN_ROOT}/templates/launch-readiness.md`: the
   checklist of what must be true to launch - each claim backed, each
   backing scenario passing, voice consistent with the voice & positioning
   strategies, the honesty policy applied to what the product cannot yet
   do.
3. **Write `positioning.md` and `launch-readiness.md`.**

   **Where it goes.** `docs/compass/<created>-<issue-slug>/positioning.md`, where the
   date is the manifest's `created:` field - not today's. Then register it:
   `compass issue artifact positioning --status draft --path <that path>`. The CLI
   refuses a path that climbs out of the project, so the record is checked
   rather than claimed. If you had to create `docs/compass/`, **say so in one
   line** - a directory appearing with nothing said is how it gets deleted by
   hand or committed by accident.
   `launch-readiness.md` goes to the same directory and is registered the
   same way, with `--path` naming its own file.

## How this shapes the delivery approach

The `product-marketer` role (see the delivery-approach rubric and the
routing policy's `role_rules`) adds the `positioning.md` /
`launch-readiness.md` artifacts, turns on the `claims` review dimension,
and **blocks shipping** until every claim in `positioning.md` traces to a
passing scenario. `verify.claims` is a blocking role gate - the role rule
adds it on every delivery approach while a marketer is in play.

## Gate

`positioning.md` and `launch-readiness.md` exist; every claim names a
backing scenario; voice is consistent with the voice & positioning
strategies in `governance/`. The claims gate is then carried into
`/compass:verify` and enforced at `/compass:ship`.
