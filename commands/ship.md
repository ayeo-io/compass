---
description: Review the change, pass the gates with evidence, and commit
allowed-tools: Read, Write, Edit, Bash(compass *), Glob, Grep
---

# /compass:ship

Ship is the last stage of the path. This session reviews the change, passes
each gate with recorded evidence, links every owed follow-up to an issue and,
when the person asks, commits. Evidence is recorded command output and
artifacts a reader can open, never assertion: "it works" passes no gate. An
open Definition of Done item must link to an issue, or ship refuses to close
the issue.

## Setup

- Run `compass approach show` for the evidence the change owes, and
  `compass next` for the first step that is still open.
- Load the `evidence-gates` skill.
- For a change to behavior a real client can observe, also load `atdd`:
  ship runs its stage 3, the isolation proof and the checklist.
- Run the suites and the review in this session; Compass starts no verifier
  or reviewer agent (ADR-090). A project that lists the advisory
  `agent-review` check can also have an agent review the change and record
  its verdict (`docs/judged-checks.md`).
- If `manifest.yml` holds `claims:`, the `claims` dimension applies - review
  them from the marketer's perspective too.
- If this issue is itself a sweep, rename, or cleanup touching many files,
  check it the way `${CLAUDE_PLUGIN_ROOT}/governance/strategies.md` `S9`
  describes (an unmigrated 5.x project runs on its own copied `governance/`
  until `compass policy migrate` on 8.x): a fresh agent that has not seen the
  change, not its author.
- A guard offered as part of the change is accepted on a demonstrated failure
  rather than a passing test - `${CLAUDE_PLUGIN_ROOT}/governance/strategies.md`
  `S10` states the method.
- Where a review comment and the author disagree about a quantity - how many
  call sites, how much output, how often it fires - measure the number and
  report it before defending either position
  (`${CLAUDE_PLUGIN_ROOT}/governance/strategies.md` `S11`; an unmigrated 5.x
  project reads its own copied `governance/`).

## Spike note

On a spike, ship is **conclude, then graduate or discard** - never "merge to
main". Conclude is a findings check, not a test gate: *did we answer the
question?* It runs none of the review dimensions, because a spike ships
nothing. The question is answered - or explicitly answered with
"inconclusive, here is why" - and the finding is written down. Then the
findings feed a fresh `/compass:assess` for real delivery work (graduation),
or the spike is discarded with its learnings recorded. Follow the conclude
and graduate-or-discard steps in `${CLAUDE_PLUGIN_ROOT}/approaches/spike.md`
instead of the procedure below.

## Procedure

1. **Run the scenarios and the suite.** Run every scenario in
   `acceptance-criteria.md` as an acceptance check. Run the full suite
   through `compass tdd-green -- <cmd>`, which confirms it passes and writes
   the record. Point to that record rather than reproducing the run.
2. **Run `compass check`.** This is the **mechanical half** of the gate: the
   CLI runs the `guardrails.yml` checks against `manifest.yml` and
   `evidence/` - every scenario has a test, the suite passed, every changed
   file traces to a scenario, every `pass` gate has resolving evidence, and
   so on. It exits non-zero on any failure. You still judge the *judgment*
   dimensions (clarity, security depth, governance-as-assessed).
3. **Review dimensions.** Apply each dimension the evidence line lists -
   `correctness`, `governance`, `traceability`, and as the change needs
   `regression`, `security`, `clarity`, `claims`. The `governance` dimension
   checks the work against the governance in force (`compass policy show`;
   an unmigrated 5.x project runs on its own copied `governance/` until
   `compass policy migrate` on 8.x): the guardrails (hard, evidence-backed - `compass check` is the mechanical
   part) and the applicable strategies (assessed as judgment, reported
   separately). How to do the review is below.
4. **Pass the gates.** As each gate is cleared, register the evidence, then
   pass the gate with it:
   `compass evidence add <EV-id> --type <type> --path <file>`, then
   `compass gate pass <gate> --evidence <EV-id>`. A gate takes evidence ids
   from the issue's registry, not file paths, and the CLI checks the type at
   write time. `compass quick-fix finish` passes the three immovable gates
   itself. Each `next:` line names the next gate.
5. **Report the result.** Compass writes no verification report: the gates,
   the evidence and the Definition of Done are records in the manifest, and
   `compass check` prints them. In the hand-off, say each dimension, each
   gate, its evidence and pass or fail. Read the manifest's
   `failure_modes_descoped` and name each mode and its reason, or say "None":
   a mode named at specify must not disappear before ship.
6. **Settle owed follow-ups.** Check `manifest.yml`'s `follow_ups:`,
   `failure_modes_descoped:` and `claims:` lists:
   - **Defect follow-up** (`urgency: live-defect`): the reproduction test is
     a real Given/When/Then scenario in `acceptance-criteria.md` *and*
     `manifest.yml`'s `scenarios:`, traceable to the defect, with its root
     cause stated. Work the fix still owes goes to a GitHub issue, linked
     with `compass follow-up add FU-<id> --github owner/repo#N --summary
     "..."`.
   - **Marketer claims gate** (when `manifest.yml` holds `claims:`): every
     claim in `claims:` traces to a passing scenario id.
     `compass check`'s `claim-traces-to-scenario` check is the mechanical
     check behind it.
   - A Definition of Done item you cannot meet now is carried to a GitHub
     issue with `compass follow-up add FU-<id> --defers <item> --github
     owner/repo#N --summary "..."`. A follow-up with no `--github` meets no
     item, and the command refuses it. The linked follow-up need not be
     resolved before ship: the GitHub issue tracks the work.
7. **Update living docs.** Update READMEs, architecture notes, and any docs
   the change touched, so they match the code. If `manifest.yml` holds
   `claims:`, draft the release notes from them, so every line is already a
   scenario-backed claim.
8. **Run `compass check` as the final mechanical gate**, and record its
   output. See the Definition of Done below.
9. **Commit, when the person asks.** See "Commit" below.
10. **Offer a project lesson (advisory - never a gate).** See below.

## How the review is done

This session does the review that a separate reviewer agent did before 9.0.0
(ADR-090).

- **Clarity.** Judge the tells named in `skills/compass-runtime/writing-voice.md`:
  does the prose communicate a decision, or narrate the pipeline? Run
  `scripts/voice-tells.py` over the issue's documents for the tells a fixed
  string can find. Cold-reader writing is a strategy
  (`${CLAUDE_PLUGIN_ROOT}/governance/strategies.md` `S8` names the calibration
  sample; an unmigrated 5.x project reads its own copied `governance/`), so a
  finding is a note and a conversation, never an automatic gate failure.
  Flag a short code with no plain words in front of it: the fix is to
  put the meaning first and the code in brackets, never to delete the code.
- **Patterns.** Where the design names patterns, check them against the code
  (`S16`). It is advice: never fail a gate on it.
- **Comments.** Open every comment with a plain-word label - **issue**,
  **suggestion**, **nitpick**, **question**, **praise** (`S12`) - and label
  honestly.
- **Settled decisions.** Before you recommend a rename or a reversal, read
  `governance/decisions/` if the project has one. A point that collides with an
  entry is "settled by <path>", not a defect.
- **Review rules.** If the project has `governance/review-rules.yml`, run
  `compass review-rule list --changed-files <paths>` and apply the rules it
  prints. Report a breach under the RR- id it breaks, and do not flag what a
  rule's `allowed` list permits.
- **Dangling references.** Flag any reference a reader cannot resolve
  ("Option 2", "Finding 3", "per the review"), and any issue or pull-request
  link with no statement of what it is.
- **Attribution.** Flag a commit or pull-request body that carries an agent
  co-author trailer or a generated-with line.
- **No green by edit.** Never edit production code or scenarios to make a run
  go green; a run that fails is a finding.

## Answering the reviewer

Load `receiving-code-review`. Check every suggestion against the code
before acting on it: a suggestion that is right about the symptom and wrong
about the cause is the normal case, and implementing it verbatim leaves the
symptom and adds a change nobody needed. Where the reviewer is wrong, say
so, with technical reasons rather than preference or seniority. Record
what you did with each comment - a resolved thread with no reply is a
decision nobody can audit.

## The stage 2 and 3 reviews

On an issue the four-layer acceptance strategy (`S17`) applies to, the end
of build is the end of stage 2 of the `atdd` skill, and the end of ship is
the end of stage 3. Wait for approval only if the stage (`build` or `ship`)
is in the manifest's `checkpoints:`, which lists it only where the strategy
applies. The three commands of each hand-off, stage 2 at build and stage 3
at ship:

```
compass evidence request --checkpoint build
compass evidence approve --checkpoint build --approver <name> --role <role>
compass issue checkpoint add build --outcome skipped --by builder

compass evidence request --checkpoint ship
compass evidence approve --checkpoint ship --approver <name> --role <role>
compass issue checkpoint add ship --outcome skipped --by verifier
```

- If it is listed, ask with the first command and wait. The request lists the
  review questions. The person types `/compass:approve` or
  `/compass:reject` in Claude Code, or runs the second command at a terminal.
- A rejection sends the issue back to that stage: `compass next` names it,
  with the reason.
- If the stage is not listed and `compass next` names the review, show
  the hand-off, say you are going on without waiting and name the autonomy
  setting. Record it with the third command.

`compass check` does not fail on a listed review with no outcome;
`compass ship-commit` refuses to land the issue until it has one.

## The Definition of Done

`compass check` judges the Definition of Done. Each item is met by a record
(`compass gate pass ... --meets <item>` or `compass evidence add ... --meets
<item>`), by a person's approval, or by a follow-up that defers it and links
to a GitHub issue (`--defers <item> --github owner/repo#N`). A person ticks the item that needs a person by typing
`/compass:approve` after you ask with `compass evidence request --check
<item>`, or with `compass evidence approve --check <item>` at a terminal. A
`human-approval` record comes only from an approval; `compass evidence add`
refuses it. `compass check` lists each item and its state; a tick written on
a page counts for nothing.

On an issue created before 9.0.0, `compass check` parses the
`### Definition of Done` section of the issue's verification report, where
every unchecked box must carry one of:

- `- [ ] (evidence: EV-<id>) <description>` - passes if `EV-<id>` is in
  `manifest.yml`'s evidence registry with an accepted type (`test-run`,
  `command-output`, `manual-review`, `artifact`, etc.).
- `- [ ] (follow-up: FU-<id>) <description>` - passes if `FU-<id>` is in
  `manifest.yml`'s `follow_ups:` with `status: outstanding`. An outstanding
  follow-up fails `compass check` until it is resolved
  (`compass follow-up resolve --issue <slug> <FU-id>`). An older follow-up
  can carry a `target_task: <slug>` field; when set, the named issue's ship
  check fails until this entry is resolved.
- `- [x] <description>` - a human-ticked box passes unconditionally.
- `- [ ] <bare description>` - **fails**. A narrative note (e.g. "USER TO
  APPLY") never clears an item - evidence, not assertion.

Cross-issue blocking: if an issue assessed before 9.0.0 has a `follow_ups:`
entry whose `target_task` points at the issue being shipped, and that
follow-up is still `status: outstanding`, `compass check` fails at ship even
if this issue's own items are clean. Resolve the other issue's follow-up
first. Nothing writes `target_task` since 9.0.0.

## Commit

- Commit on the current branch with `compass ship-commit -m "<message>"`,
  only when the person asks. It handles pre-commit hooks that fix files
  themselves (these can otherwise stop the commit with no error and leave
  HEAD where it was), retries once after re-staging the hooks' fixes, and
  **fails if HEAD did not move**, so a commit that did not happen cannot
  count as shipped. Pass `--issue <slug>` to mark the issue shipped only on
  a checked commit. An issue that owes a release line is refused without
  one: give it once, with `--release-note "<text written for a user>"`
  (`docs/release-line.md`). For a long message, `-F <file>` reads it from a
  file; never use `git commit` in its place.
- **Message rules:** the message follows the cold-reader strategy: say
  what changed and why, for someone who was not in the conversation; no
  `Co-Authored-By:` trailer for any agent and no "Generated with"
  footer. The same applies to a pull-request body.
- **After a review fix.** If review of the pull request changes the
  issue's own files after `ship-commit` committed it, commit the fix, re-run
  `compass tdd-green`, then run `compass ship-commit --issue <slug> -m
  <message>` with nothing staged. It moves `land_commit` to HEAD, and
  refuses while the newest green does not name HEAD's files.
- **Record the pull request.** When the pull request opens, run
  `compass issue link set --pr <n>` to record it on the issue. Run it again
  after the merge: a squash merge leaves the commit `ship-commit` made off
  the default branch, and the command moves `land_commit` to the merge
  commit `gh pr view` reports. `compass check` reports, as advice, a
  `land_commit` that origin's default branch does not reach.

## The ship approval

An issue whose `evidence_required` lists `ship-approval` needs one person's
approval of the change at ship. A review approval of the merged pull request
by a person other than its author gives it. Where there is none (no GitHub,
or the author is the only person), ask for the typed ship approval:

```
compass evidence request --ship
```

Then stop. The person types `/compass:approve`, or runs `compass evidence
approve --ship --approver <name> --role <role>` at a terminal. An agent
records it only under a delegation the person typed with `--for ship` and
confirmed with its code. A `G5` sign-off is not a ship approval. The check
never refuses `ship-commit`.

## Project lessons

This step never blocks shipping. If the person corrected something during
the issue and said they had to say it before, offer to keep it as a project
lesson: run `compass lesson propose "<their words>"`, quoting them, and
never `compass lesson add`. It takes effect only when someone runs
`compass lesson accept`.

## Hand-off

Close the review by handing the result to the person: each dimension, each
gate with its evidence and pass or fail, and each mode in
`failure_modes_descoped`. Ask them to check the judgment dimensions and any
deferred Definition of Done item. On approval, or when they ask, the commit
comes next.

## Voice

The hand-off is evidence a person reads, not a status board. Say what passed
and what it means - never that the issue is "ready for the next command."
See `skills/compass-runtime/writing-voice.md`.

## Gate - ship refuses to close the issue unless

- `compass check` passes, its output recorded and linked;
- every required *judgment* dimension passed with evidence;
- every gate in `manifest.yml` is `pass` with a resolving evidence pointer;
- every item of the Definition of Done is met on the record, or deferred to a
  follow-up that links to a GitHub issue;
- living docs are updated;
- **every owed follow-up links to the GitHub issue that tracks it** - no
  unlinked defect follow-up, no unbacked marketing claim, no de-scoped work
  left with no issue.

On an issue assessed before 9.0.0, a follow-up that cannot be completed now
keeps the issue open, and `/compass:status` keeps flagging it. A deferred
follow-up must be resolved before that issue closes.
