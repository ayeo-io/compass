# The CLI

This page lists each `compass` verb in one line, and says what `compass
flow`, `compass next`, the rail and the status line show. `compass <verb>
--help` gives the detail of a verb.

Each slash command calls the CLI, so each check runs as a program. A change
takes two commands: `compass quick-fix start` and `compass quick-fix
finish`. The older record commands, such as `tdd-red` and `gate pass`, still
work.

```text
# One change
compass init               create .compass/ in this directory
compass quick-fix start    open the issue for a change of any size
compass quick-fix finish   write the record: the red on a copy of the base commit, the green, the check; commit once a person has approved
compass next               the stage this issue reached, and the next command
compass ship-commit        commit exactly the files the issue recorded (--release-note: the issue's release line)
compass trail              write the issue's trail.md; --check exits 1 when it is out of date

# Assessment
compass approach evaluate  the assessment -> the evidence the change owes
compass approach show      three lines: approach, evidence, files
compass approach render    the path and the spike as one HTML table

# Scenarios and tests
compass scenario add       add a scenario to the manifest
compass scenario descope   record a failure mode no scenario covers, and why
compass scenario tests set replace the tests a scenario declares
compass bdd extract        acceptance criteria -> a runnable .feature
compass bdd verify         record which scenarios the runner ran
compass tdd-red            run a test, assert it FAILS, record the red
compass tdd-green          run a test, assert it PASSES, record the green
compass isolation record   run the suite in parallel and each scenario's tests twice; record the exit codes
compass layering record    run the project's layering test and record the run
compass acceptance start   open a record where there is no natural red
compass acceptance record  close it with what was observed
compass changed-file add   trace a changed file to the scenario that asked for it

# Evidence, gates and approvals
compass check              run the guardrail checks against the manifest and evidence
compass ci                 every mechanical gate, for continuous integration
compass gate pass          mark a gate passed; checks the evidence type
compass evidence add       add a typed evidence record (--type spike-conclusion with --decision and --next-issue closes a spike)
compass evidence request   ask a person for an approval; names the form, the approver and the scope
compass evidence approve   record a person's approval: a human check, an irreversible change (--guardrail), agent decisions (--decisions), a checkpoint (--checkpoint) or the change at ship (--ship)
compass evidence review    record a judgment against a judged check
compass waiver add         waive one check on one issue, with a reason; a person must approve it
compass waiver withdraw    remove an unapproved waiver, or mark an approved one withdrawn
compass follow-up add      record a follow-up the issue owes (--github, required on a path issue)
compass follow-up resolve  settle a follow-up; on an issue assessed before 9.0.0 an unresolved one blocks shipping

# The issue
compass issue use          make an issue the current one, for this session
compass issue lint         check the structure of an issue manifest
compass issue diagnose     explain one run from its records: stages, timeline, deviations
compass issue raised-by    record the issue this one was found in, and where: specify, build, ship, review, ci or after-landing (an 8.x stage name still reads)
compass issue decision add record a decision an agent took for the person (--from-ledger reads the requirements review)
compass issue decision set reopen such a decision; the checkpoint keeps waiting
compass issue checkpoint add  record a hand-off the autonomy setting passed (--outcome skipped --by <agent>)
compass issue status set   backlog, or done with --close-reason completed | not-planned | duplicate
compass issue status remove  end a backlog hold; the state then follows the records
compass issue blocked set  flag an in-progress or in-review issue as blocked, with a reason
compass issue blocked remove  clear the blocked flag
compass issue depends add  record an issue this one waits for (--reason, --until); build is blocked until it is met
compass issue depends remove  stop waiting for an issue
compass issue link set     link the GitHub issue (--github) or the pull request (--pr): its merge commit becomes land_commit and its approving reviews the ship approval
compass issue migrate      bring older issue directories to the current schema and settle the artifact status of done issues; --config pins an issue to the installed check versions
compass flow               every issue by state, blocked and stale (--json, --digest)

# Project settings and rules
compass policy lint        lint compass.yml, or the governance copy of a project without one; warns (L-SETTING-REMOVED) on each key 9.0.0 removed
compass policy show        the check set, its digest and the settings applied (--issue adds the issue's policy: block and waivers)
compass review-rule list   the review rules that apply to the changed files
compass migrate            move an 8.x project to 9.0.0 (dry run unless --apply; --settings-only, --issues-only); docs/upgrade-9-0-0.md
compass terminology        what a term means, from the frozen vocabulary
compass adr new            create the next numbered decision record

# Decisions and lessons
compass decision record    write a settled product decision; the decider comes from git
compass decision list      each decision's date, slug and outcome, newest first
compass decision show      print one decision
compass decision check     fail when a decision at a base ref was changed or removed
compass lesson add         record a project lesson; who added it comes from git
compass lesson propose     hold a lesson for acceptance (how the model adds one)
compass lesson accept      turn a pending proposal into a lesson
compass lesson list        each lesson and each pending proposal
compass lesson remove      delete one lesson
compass lesson decline     drop a pending proposal; its text stays in the file

# The delivery record
compass record sync        copy the delivery record to its own repository (ADR-031)
compass record restore     bring the delivery record back into this project
compass record commit      commit the issue record alone after the merge, when it ships with the code
compass release notes      the release lines of the issues completed since a git reference (--since)
```

## `compass flow`

`compass flow` prints every issue under `.compass/work/`, grouped by state.
It changes no issue state and exits 0 inside a Compass project.

| Flag | Result |
|---|---|
| `--json` | The same rows as data. Keys are additive within a major version (`tests/test_flow_board.py` pins the set). Each row has `depends_on` ([issue dependencies](https://github.com/ayeo-io/compass/blob/main/docs/issue-dependencies.md)). |
| `--digest` | A dated list of the backlog, oldest first. It flags an issue that waited too long. |
| `--work-root` | Reads another folder of issues. |

- The states: in progress, stale evidence, in review, ready, backlog, done
  in the last seven days, closed without delivery, a stored status Compass
  does not set, and folders it cannot place, each with its reason.
- The evidence check for an in-progress issue can write loose objects to
  the git object store. `git gc` removes them.
- 9.0.0 removed the HTML board, the `readiness` verb, the `--readiness`
  flag of `compass init`, and the `friction` and `readiness` keys
  (ADR-093). A command line that names one fails to parse.
- The code is `cli/compass_pkg/flow.py` and `issue_detail.py`.

## `compass next`

`compass next` prints one line: the issue's stage, the first gate not yet
passed, and the one command to run next.

```text
Build [gate: verify.correctness] | next: write the tests and the code, then compass quick-fix finish -m "<commit message>" -- <test command>
```

`compass next --json` gives the same command in a `next` field, and `null`
on a closed issue that owes nothing more.

### The `next:` command

The command comes from the issue's records, the first row that matches
(`cli/compass_pkg/next_step.py`):

| The records show | `next:` |
|---|---|
| `request` owed, the link or the requester not recorded | `compass issue link set --issue <slug> --request <url> --requester <name>` |
| `scenario-approval` owed, no outcome and no request | write the scenarios in acceptance-criteria.md, then `compass evidence request --checkpoint specify`, then stop for `/compass:approve` |
| `scenario-approval` owed, a request pending | stop: the scenarios wait for the person's approval. Ask them to type `/compass:approve <n>` |
| a gate not passed, or no green | write the tests and the code, then `compass quick-fix finish -m "<commit message>" -- <test command>` |
| a request for the ship approval or the `G5` sign-off pending | stop and ask the person to type `/compass:approve <n>`. After the approval, run the same `finish` again: it commits |
| the same, after a change that differs from the one approved | stop and ask the person to type `/compass:approve <n>`. Nothing else to run now |
| `human-approval` owed, none on record and no request | `compass quick-fix finish -m "<commit message>" -- <test command>`, which asks for the `G5` sign-off |
| every approval on record, the issue open | `compass quick-fix finish -m "<commit message>" -- <test command>` (it commits), or `compass ship-commit` on the branch the person names |
| landed, `ship-approval` owed, none on record | `compass issue link set --pr <n> --issue <slug>` after the merge, or `compass evidence request --ship`, then stop for `/compass:approve`; only the second once the merge is recorded |
| landed with its record committed with the code, and the issue folder holds a change git has not committed (the merge fields `compass issue link set --pr` wrote) | `compass record commit --issue <slug>` |

What a path issue owes comes from its `evidence_required` list.

- The request comes first. It is not a stop: the check `request-recorded`
  fails until the link and the requester are recorded. A waiver a person
  approves excuses it and ends the row.
- A spike first names `compass evidence add EV-SPIKE --type
  spike-conclusion`, then `compass gate pass spike.conclude`.
- A landed issue that owes the ship approval prints `all phases complete |
  next: <command>`.

On a path issue, each verb that writes a record of the issue ends its text
output with the same `next: <command>` line. `--json` and `--quiet` output
do not change.

### An issue assessed before the path

Each new assessment is a path issue (`governance/routing-policy.md`, "The
path writer"). An older issue keeps its legacy stages, and each rule reads
them as before. Such an issue:

- shows each legacy stage as the path stage it maps to, in `compass next`,
  the rail and the status line;
- prints no `next:` line after a record verb;
- keeps the rows of its older record: a scenario with no test, `compass
  tdd-red` and `compass tdd-green` for each scenario, the `S17` records its
  `acceptance_strategy` block names, each open Definition of Done item (when
  its verify stage is `thorough`) and each gate not passed.

| Legacy stage | Shown as |
|---|---|
| `assess` | Assess |
| `define`, `refine`, `plan` | Specify |
| `breakdown`, `implement` | Build |
| `verify`, `ship` | Ship |

### Decisions an agent took for you

An agent that resolves a requirement question itself records the decision
with `compass issue decision add`, or `--from-ledger` for the requirements
review. The `autonomy` setting decides what `compass next` does then:

| `autonomy` | `compass next` |
|---|---|
| `controlled` | Stops at assess and specify while a decision is unconfirmed. |
| `balanced` | Stops at specify, when the scenarios owe a person's approval. |
| `autonomous` | Lists the decisions below its usual line and does not wait. They stay open. |

A stop reads `Waiting at the specify checkpoint: 2 decision(s) to confirm`,
and the lines below list each decision with its resolution.

- Confirm them all: `compass evidence approve --decisions --approver <you>
  --role <role>`.
- Reopen one: `compass issue decision set <id> --status reopened --reason
  "<why>"`. A reopened decision keeps the checkpoint waiting.

### The stage 2 and 3 reviews

On an issue the four-layer acceptance strategy applies to, `build` and
`ship` each end with a review from the `atdd` skill
([checkpoints](https://github.com/ayeo-io/compass/blob/main/docs/checkpoints.md)). When a stage is done and its review has no
outcome, `compass next` says so:

| Case | `compass next` |
|---|---|
| `controlled` | First line: `Waiting at the build checkpoint: the stage 2 review has no outcome`, with the `compass evidence request --checkpoint build` command |
| Another `autonomy` value | Its usual line, and the `compass issue checkpoint add` command that records the review as skipped |
| After `/compass:reject <n> <reason>` | Names that stage again, with your reason, until a new outcome is recorded |

The ship review is due once every gate has passed: `next:` then names
`compass evidence request --checkpoint ship`. An issue assessed before the
path has these reviews at its legacy `implement` and `verify` hand-offs.

### Entry checks and waits

- With the capability `entry-exit-evaluation` on, the line names the entry
  and exit checks of the current stage that are not met, after `entry not
  met:` ([entry and exit evaluation](https://github.com/ayeo-io/compass/blob/main/docs/entry-exit-evaluation.md)). No `dor-*`
  check is named for a path issue.
- An issue at build that waits for another issue ends its line with the
  wait: `... | blocked: waits for b to reach done`. The pre-tool hook then
  refuses production-code edits. A dependency that `compass next` cannot
  judge is left out of the line, and `compass issue lint` names it
  ([issue dependencies](https://github.com/ayeo-io/compass/blob/main/docs/issue-dependencies.md)).

## The rail

In a terminal, `compass next` shows the issue's stages as a rail, with the
current stage marked:

```text
delivery · fix-retry-header
Assess ✓ → Specify ✓ → Build ● → Ship ○

Build [gate: verify.correctness] | next: write the tests and the code, then
compass quick-fix finish -m "<commit message>" -- <test command>
```

Piped output, and any run inside Claude Code, keeps the one-line form.

| Variable | Effect |
|---|---|
| `NO_COLOR` | Removes the color. |
| `COMPASS_COLOR=never` | Uses the ASCII markers `[x] [>] [ ] [-]` and no color. |
| `COMPASS_COLOR=always` | Shows the rail even when the output is piped. `NO_COLOR` still removes the color. |

The current stage is the first stage that the records do not show as done:

| Stage | Done when |
|---|---|
| Assess | `delivery_approach` and `evidence_required` are set. |
| Specify | Each scenario has an id, an intent and a declared test, and the `specify` checkpoint has an outcome where it is listed. |
| Build | Each scenario that is not `verifiable: narrative` has a red, then a green. |
| Ship | The issue is closed. |

On an issue assessed before the path, a path stage shows as skipped only
when every legacy stage it maps to is skipped.

## The status line

Compass can show the current issue in Claude Code's status line:

```text
compass · fix-login-redirect · delivery · Build · gates 1/3 · TRC-002 red
```

The last field says the second traced criterion has a failing test on
record. The line names the same stage as `compass next`. Only you see it,
not the model, so it costs no tokens.

Add it to your Claude Code settings file, your own or the project's. A
plugin cannot add it for you:

```json
{
  "statusLine": {
    "type": "command",
    "command": "~/.claude/plugins/data/compass-compass/compass-statusline"
  }
}
```

- That file is a launcher in the plugin's data folder, which Claude Code
  keeps across plugin updates. Each session start points it at the installed
  version, so the setting does not need a change.
- A plugin loaded with `--plugin-dir` keeps its launcher under
  `~/.claude/plugins/data/compass-inline/`.
- `/compass:init` offers to add the entry. It shows the change and writes it
  only when you say yes.
- Outside a Compass project, the line is empty.
- The line fits the terminal width that Claude Code passes in `COLUMNS`, and
  assumes 80 columns when it is not set.
