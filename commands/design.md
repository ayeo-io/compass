---
description: Designer entry point - the UI contract as scenarios
argument-hint: "<surface or interaction being designed>"
allowed-tools: Read, Write, Edit, Glob, Grep
---

# /compass:design

The designer entry point. UI contracts in Compass are not mockup
annotations - they are **scenarios**, written Given/When/Then, that flow
*into* the acceptance criteria as spec input, on the same footing as the rest
of the spec. The designer feeds the shared spec; they are not a downstream
consumer of it.

**Surface:** $ARGUMENTS

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

- Adopt the designer's vocabulary - surfaces, states, interactions, the
  user's path through them.
- Load `intent-interview` and read its `role-translation.md` - the UI contract is the interaction perspective
  on the shared spec.
- Load `bdd-specification` - the contract is written in the same
  Given/When/Then form as the rest of the spec, so it composes cleanly when
  it reaches the define stage.
- Read `governance/` - any accessibility or UX floor is either a project
  guardrail (`guardrails.md`) or a strategy (`strategies.md`); the contract
  must honour the guardrails and respect the strategies.
- Read `intent.md` if one exists - the interaction serves the outcome.

## Procedure

1. **Write the UI contract as scenarios.** From `${CLAUDE_PLUGIN_ROOT}/templates/ui-contract.md`,
   capture each interaction as Given/When/Then: the state the user is in,
   the action they take, the observable result. Cover the empty state, the
   loading state, the error state, and the accessibility expectations - not
   just the happy path.
2. **Honour the guardrails.** Every contract scenario must be consistent
   with the guardrails in `governance/guardrails.md` (e.g. a project
   accessibility floor). A contract that cannot meet a guardrail is a
   tension to name now, not later.
3. **Write `ui-contract.md`** into `docs/compass/<created>-<issue-slug>/`,
   then register it with `compass issue artifact ui-contract --status draft
   --path <that path>`. Say so in one line if you created `docs/compass/`.

## How this connects to the pipeline

`ui-contract.md` is an input to the **define** stage. When `spec-author`
runs, it folds the UI contract scenarios into `acceptance-criteria.md` -
they become acceptance checks and seed the TDD cycle like any other
scenario. Because the contract is already Given/When/Then, spec-author
copies them without rewriting.

## Gate

`ui-contract.md` exists; every interaction is a Given/When/Then scenario
including the non-happy states; it is consistent with the guardrails in
`governance/`. Next: `/compass:assess` to compute the delivery approach,
then `/compass:define` will absorb the contract.
