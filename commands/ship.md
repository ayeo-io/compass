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
