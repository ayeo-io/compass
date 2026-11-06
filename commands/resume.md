---
description: Continue an issue from its state on disk
argument-hint: "<issue-slug>"
allowed-tools: Read, Write, Bash(compass *), Glob, Grep
---

# /compass:resume

Resume an issue that already has state on disk - a later session, or a
different agent, continuing from where the work stopped. The artifacts were
written so that nobody has to work out the process again.

**Issue:** $ARGUMENTS

## Procedure

1. **Locate the issue.** Find `.compass/work/<issue-slug>/`. If the slug is
   ambiguous or missing, list the available issues and ask. Once found,
   run `compass issue use <slug>` - the `.compass/current-task` pointer it
   sets is how every `compass` call (and a later session) resolves to
   *this* issue without a `--issue` flag.
2. **Run `compass approach show` and read `manifest.yml` first.** The
   manifest is the contract for this issue - the delivery approach, the
   evidence the change owes, the gate set and the de-scope reasons - and
   `compass approach show` prints the decision. Read everything
   else with it as the reference. After a re-assessment, the manifest's
   `reassessments:` log names what changed.
3. **Read `acceptance-criteria.md`** - the spec - and the records of the
   work so far. An issue assessed before the path also has a `devlog.md`;
   read it. Read any note the team keeps beside them too, such as a role
   note.
4. **Find the current stage.** Run `compass next`: it names the stage of
   the path (assess, specify, build or ship) and prints the `next:` command.
   An issue assessed before the path shows its old stage as the path stage
   it maps to. Note any owed follow-up.
5. **Report, then continue.** State plainly: the delivery approach, the
   current stage, the next command to run, and any blocker or owed
   follow-up. Then continue as `/compass:go` does from its step 4: run each
   `next:` command, and stop only where one says to wait for a person.
6. **The finish is one command.** When only the red, the fix and the three
   immovable gates are left, write the failing test and run
   `compass tdd-red --scenario <id> -- <test command>`, write the fix, then
   run `compass quick-fix finish -m "<message>" --no-commit -- <test
   command>`. It traces the changed files, runs the check and passes the
   three gates, even for an issue another session started. Do not pass
   the gates by hand.

## When the records do not answer the question

If the delivery approach does not explain the process from here, the
assessment under-sized it. Say so and re-assess (`/compass:assess --reassess`) rather
than improvising a process. A guessed process is not a resumed issue.
