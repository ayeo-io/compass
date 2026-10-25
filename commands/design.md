---
description: Designer entry point - the UI contract as scenarios
argument-hint: "<surface or interaction being designed>"
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
---

# /compass:design

The designer entry point. UI contracts in Compass are not mockup
annotations - they are **scenarios**, written Given/When/Then, that go
*into* the acceptance criteria as spec input, and count the same as the rest
of the spec. The designer writes part of the shared spec; they do not only
read it after others write it.

**Surface:** $ARGUMENTS

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

- Adopt the designer's vocabulary - surfaces, states, interactions, the
  user's path through them.
- Load `intent-interview` and read its `role-translation.md` - the UI contract is the interaction perspective
  on the shared spec.
- Load `bdd-specification` - the contract is written in the same
  Given/When/Then form as the rest of the spec, so the define stage can add it
  without rewriting it.
- Run `compass policy show` for the rules in force, and read the reasons in
  `${CLAUDE_PLUGIN_ROOT}/governance/guardrails.md` and `strategies.md` - any
  accessibility or UX floor is either a project guardrail (an entry in
  `compass.yml`) or a strategy; the contract must honor the guardrails and
  respect the strategies. An unmigrated 5.x project runs on its own copied
  `governance/` until `compass policy migrate`.
- Read `intent.md` if one exists - the interaction serves the outcome.

## Procedure

1. **Write the UI contract as scenarios.** From `${CLAUDE_PLUGIN_ROOT}/templates/ui-contract.md`,
   capture each interaction as Given/When/Then: the state the user is in,
   the action they take, the observable result. Cover the empty state, the
   loading state, the error state, and the accessibility expectations - not
   just the happy path.
2. **Honor the guardrails.** Every contract scenario must be consistent
   with the guardrails in force (`compass policy show`; an unmigrated 5.x
   project runs on its own copied `governance/`; e.g. a project
   accessibility floor). If a contract cannot meet a guardrail, name
   the conflict now, not later.
3. **Write `ui-contract.md`** into `docs/compass/<created>-<issue-slug>/`,
   then register it with `compass issue artifact set ui-contract --status draft
   --path <that path>`. Say so in one line if you created `docs/compass/`.

## How this connects to the pipeline

`ui-contract.md` is an input to the **define** stage. When `spec-author`
runs, it adds the UI contract scenarios to `acceptance-criteria.md` -
they become acceptance checks and each starts a TDD cycle like any other
scenario. Because the contract is already Given/When/Then, spec-author
copies them without rewriting. The design role is a perspective; it does not
change the assessment.

## Gate

`ui-contract.md` exists; every interaction is a Given/When/Then scenario
including the non-happy states; it is consistent with the guardrails in
force. Next: `/compass:assess` to compute the delivery approach,
then `/compass:define` adds the contract to the acceptance criteria.
