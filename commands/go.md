---
description: Run a change from the request to a checked commit
argument-hint: "<what you want>"
allowed-tools: Read, Write, Edit, Bash(compass *), Glob, Grep
---

# /compass:go

One command for every change. Do not ask the person which Compass command to
use.

**Change:** $ARGUMENTS

One request is one issue. Never start a second issue for follow-on work or
feedback in the same request; add it to this one.

1. Start, once:

   ```
   compass quick-fix start <slug> --intent "<what will be true afterwards>" \
     --request <issue URL or owner/repo#N> --requester "<who asked>"
   ```

   Add `--labels <label,...>` only for `auth`, `payments`, `personal-data`,
   `migrations` or a label the project adds, and `--risk "critical - <why>"`
   only for critical risk. If `start` creates `.compass/`, say so in one line.

2. Only with one of those: write every scenario in the
   `acceptance-criteria.md` that `start` names, each in the form of the first
   one, with the next `TRC-` id. Run `compass evidence request --checkpoint
   specify`, ask the person to type `/compass:approve <n>`, and stop. Code
   edits are refused until then.

3. Write the tests and the code. Run the tests, and the project's linters
   and type checker if it has them.

4. Finish:

   ```
   compass quick-fix finish -m "<commit message>" -- <test command>
   ```

   It writes the whole record. When its `next:` line asks for a person's
   approval, stop. It commits once a person has approved, on a new branch if
   you are on the default one. Do not check that commit again.

5. After feedback, edit and run `finish` again, once.

Each command ends with a `next:` or `done:` line: do what it says. `compass
next` prints the `next:` line again. If a command refuses, its message says
why and how to clear it.

If you cannot state what will be true afterwards, it is a spike: run
`/compass:assess`.

## When you write scenarios

- When the labels include `public-api`, or the change touches a service in
  `architecture/relations.md` or a `lens_trigger_tag` in
  `architecture/invariants.yml`, take the architect's perspective first, and
  write `architecture-notes.md` beside the acceptance criteria before you
  write the scenarios.
- Ask which input classes and failure modes the intent implies that no
  scenario covers. Each becomes a scenario or is recorded with
  `compass scenario descope "<mode>" --reason "<why>"`.
- Scan the criteria for placeholders, orphan intents, untestable Thens and
  ambiguous quantifiers, and fix each in place. This self-review is not
  repeated later.

## Before you edit shared code

Run the existing suite and see it pass: that run is the baseline of the
`regression-baseline` strategy (`S6`). Run the suite again after the change.

## Hand-off

When you wrote scenarios, hand `acceptance-criteria.md` to the person for a
cold read. Ask them to look for intent fidelity, untestable Thens, a missing
failure mode and ambiguous quantifiers. The manifest's `checkpoints:` lists
the stages that wait for a person. Where the `specify` checkpoint is
listed, wait for approval; build starts after it. Otherwise say you are going
on, and name the autonomy setting.
