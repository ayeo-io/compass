---
description: Marketer entry point - positioning and the claims it needs
argument-hint: "<what is being positioned>"
allowed-tools: Read, Write(./.compass/**), Write(./docs/**), Edit(./.compass/**), Edit(./docs/**), Bash(compass *), Glob, Grep
---

# /compass:position

The product marketer entry point. The marketer works **at the same time as
the define stage** - not after the engineering process has finished. Every
public claim must trace to a passing scenario; the claims gate blocks
shipping until it does.

**Subject:** $ARGUMENTS

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

- Adopt the marketer's vocabulary - claims, voice, audience.
- Load `intent-interview` and read its `role-translation.md` - positioning is the claims perspective on the
  shared spec.
- Read `${CLAUDE_PLUGIN_ROOT}/governance/strategies.md` - voice, claims
  discipline, and the honesty policy come from the voice & positioning
  strategies there. Read `${CLAUDE_PLUGIN_ROOT}/governance/guardrails.md` too -
  the traceability guardrail keeps every public claim traced to a backing
  criterion. `compass policy show` prints the rules in force. An unmigrated 5.x project runs
  on its own copied `governance/` until `compass policy migrate`.
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
   `compass issue artifact set positioning --status draft --path <that path>`. The CLI
   refuses a path outside the project, so the record is checked
   rather than claimed. If you had to create `docs/compass/`, **say so in one
   line** - if a directory appears and nobody says so, someone can delete it
   by hand or commit it by mistake.
   `launch-readiness.md` goes to the same directory and is registered the
   same way, with `--path` naming its own file.

## How this shapes the delivery approach

When `positioning.md` is present, the artifact rule RP-ART-001 (see the
routing policy) asks for `launch-readiness.md`, adds `verify.claims`, and
**blocks shipping** until every claim in `positioning.md` traces to a
passing scenario. It applies on every delivery approach.

On an issue already assessed, re-assess after writing `positioning.md` so
`verify.claims` joins the gate set.

## Gate

`positioning.md` and `launch-readiness.md` exist; every claim names a
backing scenario; voice is consistent with the voice & positioning
strategies in force. The claims gate is then carried into
`/compass:verify` and enforced at `/compass:ship`.
