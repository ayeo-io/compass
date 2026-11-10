---
description: Commit a checked change and record the ship approval
allowed-tools: Read, Write, Edit, Bash(compass *), Glob, Grep
---

# /compass:ship

Ship is the last stage of the path: the change is checked, a person approves
it, and it is committed. `compass quick-fix finish -m "<message>" -- <test
command>` does the three (`/compass:quick-fix`). `compass next` names the
step that is open.

## The commit

- `finish` commits once a person has given the ship approval, and the `G5`
  sign-off on an issue that owes one. When its `next:` line asks for an
  approval, ask the person to type `/compass:approve <n>` and stop. After the
  approval, run the same `finish` again. It commits the change and the
  issue's record, on a new branch named after the issue when you are on the
  default branch. A commit on a branch is not a landing.
- When the person has approved and names the branch for the commit, switch
  to that branch and run `compass ship-commit`. It commits the files
  `finish` recorded, with the message `finish` stored. `finish --no-commit`
  writes the record and leaves every commit to `compass ship-commit`.
- Never use `git commit` in place of either.
- The message says what changed and why, for a reader who was not in the
  conversation. No `Co-Authored-By:` trailer for an agent and no "Generated
  with" footer, in the message or a pull-request body.

## The ship approval

One person approves each change, and you never give it: the pre-tool hook
refuses `gh pr review --approve`. Two records count:

- **The typed approval.** `finish` writes the request and the person types
  `/compass:approve <n>`.
- **A review of the merged pull request.** After the merge, run `compass
  issue link set --pr <n>`. It reads the reviews and records an approval by a
  person who is not the pull request's author. Then run the `next:` line it
  prints, if any.

An approval covers the change the person saw. After more edits, `finish`
commits on the branch and asks again, and `compass check` fails
`ship-approval-present` until a person approves the new state or the review
of the merged pull request is read. A `G5` sign-off is not a ship approval.

## Evidence a project adds

When the project's `require_evidence` adds a review, `finish` prints one
`next:` line for each item it owes. Follow the item's checklist in
`skills/evidence-gates/review-dimensions.md`, write the output to a file,
register it and pass the gate with it:

```
compass evidence add <EV-id> --type <type> --path <file>
compass gate pass <gate> --evidence <EV-id>
```

A gate takes evidence ids, not file paths. Then run the same `finish` again.

If the issue is itself a sweep, rename or cleanup that touches many files,
have an agent that has not seen the change check it, not its author:
`${CLAUDE_PLUGIN_ROOT}/governance/strategies.md` describes the practice,
fresh eyes on a sweep (`S9`; an unmigrated 5.x project is refused until it
migrates).

## The stage 2 and 3 reviews

On an issue the four-layer acceptance strategy (`S17`) applies to, the end
of build is the end of stage 2 of the `atdd` skill, and the end of ship is
the end of stage 3. Wait for approval only if the stage (`build` or `ship`)
is in the manifest's `checkpoints:`. The three commands of each hand-off:

```
compass evidence request --checkpoint build
compass evidence approve --checkpoint build --approver <name> --role <role>
compass issue checkpoint add build --outcome skipped --by builder

compass evidence request --checkpoint ship
compass evidence approve --checkpoint ship --approver <name> --role <role>
compass issue checkpoint add ship --outcome skipped --by verifier
```

- If the stage is listed, ask with the first command and stop. The person
  types `/compass:approve <n>`, or runs the second command at a terminal.
- If it is not listed and `compass next` names the review, show the
  hand-off, say you are going on and name the autonomy setting, and record
  it with the third command.

## Hand-off

When `finish` asks for the ship approval, hand the result to the person:
what changed, the test command and its result, and each mode in the
manifest's `failure_modes_descoped` with its reason, or "None": a mode named
at specify must not disappear before ship. Ask them to check the change
against the scenarios. After the approval, run the same `finish` again: it
commits.

## Voice

The hand-off is evidence a person reads, not a status board. Say what passed
and what it means - never that the issue is "ready for the next command."
See `skills/compass-runtime/writing-voice.md`.

## Spike note

On a spike, ship is **conclude, then graduate or discard** - never "merge to
main". Conclude is a findings check, not a test gate: *did we answer the
question?* It runs none of the review dimensions, because a spike ships
nothing. The question is answered - or explicitly answered with
"inconclusive, here is why" - and the finding is written down. Then the
findings feed a fresh `/compass:assess` for real delivery work (graduation),
or the spike is discarded with its learnings recorded. Follow the conclude
and graduate-or-discard steps in `${CLAUDE_PLUGIN_ROOT}/approaches/spike.md`
instead of the steps above.
