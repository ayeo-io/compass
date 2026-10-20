# The CLI

The slash commands are the pipeline; the CLI is the mechanism underneath them.
`/compass:assess` runs `compass approach evaluate`, `/compass:verify` runs
`compass check`. It is what makes the checks real rather than aspirational.

Every verb describes itself: `compass <verb> --help` says what it does and
what the result means. This page gives one line per verb; `--help` gives the
detail.

```text
compass init               make this directory a Compass project - create .compass/ (--readiness: then measure and list the absent signals; /compass:init passes it)
compass approach evaluate  the assessment -> the delivery approach, deterministically
compass approach show      the three-line decision view: approach, gates, files
compass approach render    every delivery approach as one HTML table
compass bdd extract        acceptance criteria -> a runnable .feature
compass bdd verify         record which scenarios the runner actually ran
compass check              run the guardrail checks against the manifest and evidence
compass analyze            where an issue's artifacts disagree with each other
compass retro              is triage systematically over- or under-sizing the process?
compass retro --lineage    how many issues were found in another, and how many before it landed
compass retro --decisions  how many decisions agents took for the person were confirmed, changed or never confirmed
compass issue raised-by    record the issue this one was found in, and where
compass spec sync          merge main, resolving only conflicts in the derived living spec
compass issue friction     record friction the agent observed, with evidence and a fix
compass issue decision add record a decision an agent took for the person (--from-ledger reads the requirements review)
compass issue decision set reopen such a decision; it stays unconfirmed and the checkpoint keeps waiting
compass issue checkpoint add  record a hand-off the autonomy setting passed (--outcome skipped --by <agent>)
compass ci                 the full mechanical gate suite, for continuous integration
compass tdd-red            run a test, assert it FAILS, record the red
compass tdd-green          run a test, assert it PASSES, record the green
compass policy lint        structurally validate the governance YAML
compass policy show        every resolved configuration field, with its source layer
compass preset init        scaffold a team preset repository
compass preset test        run a preset's fixtures and check its locks
compass review-rule list   the review rules that apply to the changed files
compass policy diff        compare two configurations: what one accepts that the other does not
compass policy migrate     turn copied governance and the old settings file into a compass.yml
compass policy migrate --words  rewrite compass.yml and policy-test fixtures in the 6.0.0 words
compass policy update      move the project to another shipped default major, re-approving waivers
compass plan lint          scan a technical design for placeholder phrases
compass intent ingest      read a brief that already exists, by path or https URL
compass issue lint         structurally validate an issue manifest
compass issue receipt      one screen: assessment, approach, gates, evidence
compass issue diagnose     explain one run from its own records: stages, timeline, deviations
compass issue use          make an issue the current one, for this session
compass issue configure    propose, preview, discard or recover a change to one issue's own configuration
compass issue migrate      bring older issue directories up to the current schema, and settle the artifact status of done issues; --config pins an issue's configuration to the installed check versions
compass issue render       rewrite the rendered blocks of an issue's documents and the project index from its records; --all for every issue
compass issue artifact set set a document's status in the review pack
compass issue artifact-path  where one of an issue's documents is
compass issue template show  the skeleton of a document kind from the catalog, at a depth; --depth lightweight | thorough
compass issue status set   backlog, or done with --close-reason completed | not-planned | duplicate
compass issue status remove  end a backlog hold; the state then follows the records
compass issue blocked set  flag an in-progress or in-review issue as blocked, with a reason
compass issue blocked remove  clear the blocked flag
compass issue depends add  record an issue this one waits for, with --reason and --until; implement is blocked until it is met
compass issue depends remove  stop waiting for an issue
compass issue link set     link an issue to its GitHub issue, to write its labels and page there (opt in)
compass issue github sync  write an issue's labels, and its page when switched on, to its linked GitHub issue now
compass issue subtask      record, resume and package a multiagent run's subtasks
compass acceptance start   open an honest record where there is no natural red
compass acceptance record  close it with what was observed
compass adr new            create the next numbered decision record
compass rework-scan        add-then-delete patterns across issues
compass flow               blockers, owed follow-ups, the periodic digest
compass board render       write the delivery board as one page and open it (--no-open, --out, --worktrees)
compass board refresh      rewrite that page in place, without opening a browser
compass readiness          measure whether the repository is fit for unattended agent work (--json, --fix-list)
compass next               which stage this issue reached, and what comes next
compass follow-up add      record a follow-up the issue owes
compass follow-up resolve  settle an owed follow-up
compass ship-commit        commit exactly the files the issue recorded (--release-note: the issue's release line)
compass release notes      the release lines of the issues completed since a git reference (--since)
compass gate pass          mark a gate passed, validating the evidence type
compass scenario add       add a scenario to the manifest
compass scenario descope   record a failure mode no scenario covers, and why
compass scenario tests set replace the tests a scenario declares
compass changed-file add   trace a changed file to the scenario that asked for it
compass evidence add       append a typed evidence record
compass evidence request   ask a person for an approval; the request names the form, the approver and the scope
compass evidence approve   record a person's approval of a human check, the sign-off on an irreversible change (--guardrail), a document (--artifact), the decisions agents took (--decisions) or a checkpoint hand-off (--checkpoint)
compass evidence review    record a judgment against a judged check
compass terminology        what a term means here, from the frozen vocabulary
compass quick-fix start    assess, evaluate and record a quick fix in one call
compass quick-fix finish   trace, check, gate and ship a quick fix in one call
compass decision record    write a settled product decision; the decider comes from git
compass decision list      each decision's date, slug and outcome, newest first
compass decision show      print one decision
compass decision check     fail when a decision at a base ref was changed or removed
compass lesson add         record a project lesson now; who added it comes from git
compass lesson propose     hold a lesson for acceptance (how the model adds one)
compass lesson accept      turn a pending proposal into a lesson
compass lesson list        each lesson and each pending proposal
compass lesson remove      delete one lesson
compass lesson decline     drop a pending proposal; retro will not propose it again
compass run                run the implement or verify stage of one issue unattended (ADR-030)
compass record sync        copy the delivery record to its own repository (ADR-031)
compass record restore     bring the delivery record back into this project
```
