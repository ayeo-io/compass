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
   per-stage weight, the gate set, the orchestration and the de-scope
   reasons - and `compass approach show` prints the decision. Read everything
   else with it as the reference. After a re-assessment, the manifest's
   `reassessments:` log names what changed.
3. **Read `acceptance-criteria.md` and `devlog.md`** - the spec, and the
   record of the work so far. Read any note the team keeps beside them too,
   such as a role note.
4. **Find the current stage.** Run `compass next`: it names the stage
   that is next. Cross-check against the approach's stage weights so a collapsed stage
   counts as handled, not pending. Note any owed follow-up.
5. **Report, then continue.** State plainly: the delivery approach, the
   last completed stage, the next command to run, and any blocker or owed
   follow-up. Then continue from that stage - invoke the matching
   `/compass:*` command's procedure.
6. **A quick fix finishes in one command.** If the approach is quick fix, write
   the failing test and run `compass tdd-red --scenario <id> -- <test
   command>`, write the fix, then run `compass quick-fix finish -m
   "<message>" --no-commit -- <test command>`. It traces the changed files,
   runs the check and passes the three gates, even for an issue another
   session started. Do not pass the gates by hand.

## When the records do not answer the question

If the delivery approach does not explain the process from here, the
assessment under-sized it. Say so and re-assess (`/compass:assess --reassess`) rather
than improvising a process. A guessed process is not a resumed issue.
