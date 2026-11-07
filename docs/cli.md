# The CLI

A person runs the path with the slash commands, and each slash command
calls the CLI. `/compass:assess` runs `compass quick-fix start` or `compass
approach evaluate`, and `/compass:ship` runs `compass check`. Each verb that
writes a record of the issue ends with a `next:` line, which names the one
command to run next. The CLI does the checks as a program,
so a check is more than an instruction to the agent.

Every verb describes itself: `compass <verb> --help` says what it does and
what the result means. This page gives one line per verb; `--help` gives the
detail.

```text
compass init               make this directory a Compass project - create .compass/
compass approach evaluate  the assessment -> the evidence the change owes, deterministically
compass approach show      the three-line decision view: approach, evidence, files
compass approach render    the path and the spike as one HTML table
compass bdd extract        acceptance criteria -> a runnable .feature
compass bdd verify         record which scenarios the runner actually ran
compass check              run the guardrail checks against the manifest and evidence
compass issue raised-by    record the issue this one was found in, and where: specify, build, ship, review, ci or after-landing (an 8.x stage name still reads, counted at its path stage)
compass issue decision add record a decision an agent took for the person (--from-ledger reads the requirements review)
compass issue decision set reopen such a decision; it stays unconfirmed and the checkpoint keeps waiting
compass issue checkpoint add  record a hand-off the autonomy setting passed (--outcome skipped --by <agent>)
compass ci                 the full mechanical gate suite, for continuous integration
compass tdd-red            run a test, assert it FAILS, record the red
compass tdd-green          run a test, assert it PASSES, record the green
compass isolation record   run the suite in parallel and each scenario's tests twice, and record the exit codes
compass layering record    run the project's layering test and record the run
compass waiver add         waive one check on one issue, with a reason; it excuses nothing until a person approves it
compass waiver withdraw    remove an unapproved waiver, or mark an approved one withdrawn
compass policy lint        lint compass.yml as settings, or the governance copy of a project without one, and warn (L-SETTING-REMOVED) on each key 9.0.0 removed, such as approaches or extends
compass policy show        the check set, its digest and the tighten-only settings applied (--issue adds the issue's policy: block and waivers)
compass review-rule list   the review rules that apply to the changed files
compass issue lint         structurally validate an issue manifest
compass issue diagnose     explain one run from its own records: stages, timeline, deviations
compass issue use          make an issue the current one, for this session
compass issue migrate      bring older issue directories up to the current schema, and settle the artifact status of done issues; --config pins an issue's configuration to the installed check versions
compass issue status set   backlog, or done with --close-reason completed | not-planned | duplicate
compass issue status remove  end a backlog hold; the state then follows the records
compass issue blocked set  flag an in-progress or in-review issue as blocked, with a reason
compass issue blocked remove  clear the blocked flag
compass issue depends add  record an issue this one waits for, with --reason and --until; build is blocked until it is met
compass issue depends remove  stop waiting for an issue
compass issue link set     link an issue to its GitHub issue (--github) or to its pull request (--pr), whose merge commit becomes land_commit and whose approving reviews become the ship approval
compass acceptance start   open an honest record where there is no natural red
compass acceptance record  close it with what was observed
compass adr new            create the next numbered decision record
compass flow               every issue by state, what is blocked and stale (--json), and the periodic digest (--digest)
compass next               which stage of the path this issue reached, and the next command
compass follow-up add      record a follow-up the issue owes, linked to its GitHub issue (--github, required on a path issue)
compass follow-up resolve  settle an owed follow-up; on an issue assessed before 9.0.0 an unresolved one blocks shipping
compass ship-commit        commit exactly the files the issue recorded (--release-note: the issue's release line)
compass release notes      the release lines of the issues completed since a git reference (--since)
compass gate pass          mark a gate passed, validating the evidence type
compass scenario add       add a scenario to the manifest
compass scenario descope   record a failure mode no scenario covers, and why
compass scenario tests set replace the tests a scenario declares
compass changed-file add   trace a changed file to the scenario that asked for it
compass evidence add       append a typed evidence record; with --type spike-conclusion, --decision and --next-issue record how a spike closes
compass evidence request   ask a person for an approval; the request names the form, the approver and the scope
compass evidence approve   record a person's approval of a human check, the sign-off on an irreversible change (--guardrail), the decisions agents took (--decisions), a checkpoint hand-off (--checkpoint) or the change at ship (--ship)
compass evidence review    record a judgment against a judged check
compass terminology        what a term means here, from the frozen vocabulary
compass quick-fix start    assess and record a change of any size, with its first scenario, in one call
compass quick-fix finish   trace, check and gate a change in one call; refuses while other evidence is owed
compass decision record    write a settled product decision; the decider comes from git
compass decision list      each decision's date, slug and outcome, newest first
compass decision show      print one decision
compass decision check     fail when a decision at a base ref was changed or removed
compass lesson add         record a project lesson now; who added it comes from git
compass lesson propose     hold a lesson for acceptance (how the model adds one)
compass lesson accept      turn a pending proposal into a lesson
compass lesson list        each lesson and each pending proposal
compass lesson remove      delete one lesson
compass lesson decline     drop a pending proposal; its text stays in the file as a record
compass record sync        copy the delivery record to its own repository (ADR-031)
compass record restore     bring the delivery record back into this project
```

## `compass flow`

`compass flow` prints every issue under `.compass/work/`, grouped by state:
in progress, stale evidence, in review, ready, backlog, done in the last
seven days, closed without delivery, a stored status Compass does not set,
and the folders it cannot place, each with its reason. It is advisory: it
changes no issue state and always exits 0 inside a Compass project. Outside
one it refuses, as every other verb does. `--work-root` reads another folder
of issues.

- `compass flow --json` prints the same rows as data. The keys are additive
  within a major version, and a test pins the full key set
  (`tests/test_flow_board.py`). Every row has `depends_on`, a list with one
  object for each entry of the issue's `depends_on`
  (`docs/issue-dependencies.md`). 9.0.0 removed the `friction` key and the
  summary's friction line, because nothing records friction any more
  (ADR-093). It also removed the `readiness` key, because nothing measures
  the repository any more (ADR-093).
- `compass flow --digest` prints a dated list of the backlog, oldest first,
  and flags a queued issue that waited too long.

`board()` in `cli/compass_pkg/flow.py` builds the rows once, from one read of
each manifest through the parse cache (ADR-049). The approach, state, stage,
gate count and documents of a row come from `issue_detail.detail`
(`cli/compass_pkg/issue_detail.py`). The evidence check for an in-progress
issue works out the hash of the files its test record was made on, which can
write loose objects to the repository's object store. `git gc` removes them
after its prune period.

9.0.0 removed the HTML board page and the commands and the option that wrote
it (ADR-093). It also removed the `readiness` verb and the `--readiness` flag
of `compass init` (ADR-093): nothing measures the repository. A command line
that names one fails to parse with a line naming ADR-093.
