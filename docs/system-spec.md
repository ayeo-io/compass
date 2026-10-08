<!-- DERIVED FILE - do not hand-edit; `compass _derive-system-spec` rebuilds it from the scenarios in each landed issue's manifest.yml - edit the scenario there and in the issue's acceptance-criteria.md -->

# System Specification (derived)

> `compass _derive-system-spec` builds this file from the `scenarios:` block of each landed issue's `.compass/work/<slug>/manifest.yml`.
> **Do not hand-edit** - the next derivation overwrites it.
> Edit the source: the scenario in that manifest, and its prose in the issue's `acceptance-criteria.md` under `docs/compass/<created>-<slug>/`.

## Current Behaviour

### bdd-adapters-and-skill-length (landed )

- `TRC-A1` each runner should have a worked project
- `TRC-A2` each adapter should run the extracted feature and pass
- `TRC-A3` every adapter should share the same four documented steps
- `TRC-A4` the tag selector should know every shipped runner
- `TRC-B1` every adapter should be exercised by a CI job
- `TRC-B2` an adapter whose runner is absent should skip loudly, never silently pass
- `TRC-C1` the review skill should be within its stated length

### cli-module-split (landed )

- `TRC-A1` the entry point should be thin
- `TRC-A2` the modules should follow the groupings the code already had
- `TRC-A3` the package should import cleanly on its own
- `TRC-B1` the public verb surface should be identical
- `TRC-B2` the whole test suite should pass unchanged
- `TRC-B3` loading the CLI by file path should still work
- `TRC-B4` every command should still run end to end
- `TRC-F1` a circular import should be impossible by construction
- `TRC-F2` no function should be renamed, merged or split by this task

### compass-self-architecture (landed )

- `TRC-A1` system-context.md exists with the canonical sections
- `TRC-A2` relations.md documents the call graph between framework components
- `TRC-A3` ownership.md documents what each component must and must not do
- `TRC-B1` architecture/decisions/ contains an ADR per principle (clustered or 1:1)
- `TRC-B2` ADRs follow the template structure (frontmatter + 5 sections)
- `TRC-B3` architecture/decisions/README.md is a usable index
- `TRC-B4` At least one ADR demonstrates substantive alternatives + negative consequences
- `TRC-C1` frame_load_architecture returns the new artifacts and ADRs
- `TRC-C2` SHA-256 is recorded per artifact (deterministic mechanism)
- `TRC-C3` Architect-lens cites Compass's own ADRs on a framework task
- `TRC-D1` CLAUDE.md notes Compass itself ships an architecture/
- `TRC-D2` CLAUDE.md does not claim unbuilt features
- `TRC-E1` Existing test suite still passes (161+ tests)
- `TRC-E2` Projects without architecture/ still no-op cleanly
- `TRC-E3` compass check still passes 10/10
- `TRC-E4` Lint count does not regress
- `TRC-X1` Malformed ADR frontmatter fails Frame loudly
- `TRC-X2` ADRs with status: proposed are loaded but flagged

### cross-task-architectural-integrity (landed )

- `TRC-A1` Frame loads architecture/ into the task's working context
- `TRC-A2` Frame degrades gracefully when architecture/ is absent
- `TRC-A3` compass adr new <slug> creates a numbered ADR file
- `TRC-A4` Compass ships templates for the architecture artifacts
- `TRC-A5` invariants.yml is loaded by mechanism when present
- `TRC-A5b` Frame proceeds normally when invariants.yml is absent
- `TRC-B1` /compass:roundtable can convene the architect-lens
- `TRC-B2` Spec-author consults the architect-lens for boundary-touching tasks
- `TRC-B3` Plan flags new service interactions for architect review
- `TRC-B4` Architect-lens flags missing architecture/ without blocking
- `TRC-B5` Architect-lens findings persist on disk
- `TRC-C1` Stop-hook nudges when scope-bloat phrases appear in devlog
- `TRC-C2` Stop-hook stays silent when no scope-bloat is detected
- `TRC-C3` Stop-hook stays silent when a reframe has already been filed
- `TRC-C4` Roundtable doc requires reframe on boundary or migration decisions
- `TRC-C5` compass calibration surfaces absorbed mis-frames
- `TRC-C6` Flow digest includes calibration's reframe-debt
- `TRC-D1` rework-scan reports nothing when changed_files don't conflict
- `TRC-D2` rework-scan detects file added by A and deleted by B
- `TRC-D3` rework-scan detects a public-surface symbol added then removed
- `TRC-D4` rework-scan detects a migration created then dropped
- `TRC-D5` Flow digest absorbs rework-scan
- `TRC-D6` rework-scan detects the canonical add-then-delete pair
- `TRC-E1` Unchecked DoD with no evidence and no backfill fails Land
- `TRC-E2` Unchecked DoD backed by typed evidence passes
- `TRC-E3` Unchecked DoD enumerated as owed_backfill passes Land but blocks the next sibling
- `TRC-E4` USER TO APPLY devlog notes no longer clear DoD
- `TRC-E5` human-approval evidence is accepted for human-actionable DoD items
- `TRC-E6` guardrails.yml registers the new DoD check
- `TRC-F1` Frame remains mandatory, unchanged
- `TRC-F2` The guardrail count is still five
- `TRC-F3` Adaptive routing is unchanged
- `TRC-F4` Flow still advises, never gates
- `TRC-F5` Architect-lens does not fork the spec
- `TRC-G1` Compass ships governance/signals.yml with default patterns
- `TRC-X1` Malformed invariants.yml fails Frame loudly
- `TRC-X2` rework-scan handles a corrupt task.yml gracefully
- `TRC-X3` Stop-hook regex must not produce false positives on common devlog content
- `TRC-X4` Typed DoD does not break tasks that have empty DoD
- `TRC-X5` Bootstrap - spec-author does not invoke architect-lens that doesn't exist yet

### executable-bdd-and-richer-plans (landed )

- `TRC-A1` extraction should produce a feature file a BDD runner can read
- `TRC-A2` extraction should be byte-for-byte deterministic
- `TRC-A3` each extracted scenario should carry its traceability id as a tag
- `TRC-A4` the extracted Feature should name the task it came from
- `TRC-A5` extraction should resolve the current task when none is named
- `TRC-A6` the new verb should appear in the documented CLI surface
- `TRC-A7` a configured features directory should override the default location
- `TRC-A8` the shipped config template should document the new keys
- `TRC-B1` the reference adapter should run an extracted feature end to end
- `TRC-B2` the adapter README should show every step of the wire-up
- `TRC-B3` a scenario with no step definition should fail loudly
- `TRC-B4` the adapter should be proved by a run, never by a skip
- `TRC-C1` the plan template should offer the five optional sections
- `TRC-C2` each optional section should state its own inclusion rule
- `TRC-C3` the existing plan sections should survive unchanged
- `TRC-C4` the planner's section choice should scale with the route
- `TRC-C5` a named pattern should require a stated reason
- `TRC-C6` the writing guide should carry a worked plan
- `TRC-D1` the superseded skill should be gone
- `TRC-D2` nothing should point at the deleted skill
- `TRC-D3` the specification skill should state what it leaves to Clarify
- `TRC-D4` the clarify command should state the same split from its side
- `TRC-E1` a created worktree should carry the task's artifacts
- `TRC-E2` a builder in a seeded worktree should be able to resolve its task
- `TRC-E3` re-running the swarm should not clobber a builder's work
- `TRC-G1` a command that fails to run should not be recorded as a red
- `TRC-G2` a run that collects no tests should not be recorded as a red
- `TRC-G3` a genuinely failing test should still be recorded as a red
- `TRC-F1` a spec with no gherkin fences should fail loudly
- `TRC-F2` a malformed gherkin fence should fail loudly
- `TRC-F3` a title that drifts between the heading and the fence should be caught
- `TRC-F4` extraction should not modify anything it did not create
- `TRC-F5` a project that opted into nothing should see no change
- `TRC-F6` the framework should grow by artifacts and skills only
- `TRC-F7` the skill count should not grow on net

### governance-drift-detection (landed )

- `TRC-A1` the shipped governance should declare a version that has moved
- `TRC-A2` changing governance content without bumping its version should fail
- `TRC-A3` a project behind the framework's governance version should be told
- `TRC-B1` missing floors and strategies should be named individually
- `TRC-B2` missing guardrail checks should be named individually
- `TRC-B3` a waived rule should read as deliberate, not as drift
- `TRC-B4` a waiver without a reason should be refused
- `TRC-B5` waiving a rule the framework does not ship should be refused
- `TRC-B6` drift should be advisory by default
- `TRC-B7` a project may opt into failing on drift
- `TRC-B8` the waived block should be declared in the schema
- `TRC-C1` route evaluate should report which policy it read
- `TRC-C2` a drifted project's route output should say so
- `TRC-C3` the route template should carry a provenance field
- `TRC-D1` a guardrail the project omits should be reported
- `TRC-D2` a guardrail that genuinely does not apply should still read as skipped
- `TRC-F1` a project with current governance should see no drift report
- `TRC-F2` a project with no local governance should not be compared to itself
- `TRC-F3` a project ahead of the framework should not be reported as drifted
- `TRC-F4` an unreadable framework policy should not break the lint
- `TRC-F5` drift detection should not change any computed route
- `TRC-F6` the framework should grow by artifacts and checks only
- `TRC-F7` the evidence types the CLI writes should be accepted by the task schema

### hook-fails-open-on-broken-vendor (landed )

- `TRC-1` the hook blocks an edit it cannot check
- `TRC-2` the hook says why it could not check
- `TRC-3` control: the hook still blocks when it can read the spine
- `TRC-4` the guarded-surface decision fails closed too

### living-spec-and-process-impact (landed )

- `TRC-A1` a stale derived spec should fail a check
- `TRC-A2` a current derived spec should pass
- `TRC-A3` the committed spec should cover every landed task
- `TRC-B1` the generator should normalise house style on write
- `TRC-B2` the derived file should pass the repository's own style test
- `TRC-F1` the derivation should stay a derived artifact
- `TRC-F2` a project with no landed tasks should not be broken by the check

### phase-2-skills-check-and-cli-split (landed )

- `TRC-A1` the skill should state a method, in order
- `TRC-A2` three failed fixes should send the engineer back to Frame
- `TRC-A3` the skill should be reachable from where the failure happens
- `TRC-B1` a suggestion should be checked against the code before it is acted on
- `TRC-B2` the skill should shape disagreement rather than forbid it
- `TRC-B3` the skill should be short enough to be read at the moment of use
- `TRC-C1` the check should be registered and implemented
- `TRC-C2` a project that has wired no runner should pass with a stated reason
- `TRC-C3` every scenario bound to a collected step definition should pass
- `TRC-C4` a scenario the runner never ran should be named
- `TRC-C5` a stale runner result should not be read as success
- `TRC-C6` the check should be advisory unless the route promotes it
- `TRC-F1` a project that opted into nothing should see no change
- `TRC-F2` adding the check should not change any existing task's result
- `TRC-F3` the framework should grow by artifacts and checks only

### release-3-3-0 (landed )

- `TRC-001` every version location carries 3.3.0 and the suite is green

### v2-artifact-renames (landed )

- `TRC-A1` the template set carries the v2 names plus the two new intake templates
- `TRC-A2` the resolver prefers v2 names and accepts v1
- `TRC-A3` readers resolve both naming generations of issue directories
- `TRC-A4` extracted runnable Gherkin is named acceptance-criteria.feature
- `TRC-A5` repository validation knows the v2 template inventory

### version-bump-1-0-0 (landed )

- `TRC-1` Every published version surface reports 1.0.0

### voice-audition-standing (landed )

- `TRC-A1` the strategy records permanence and the calibration sample
- `TRC-A2` the strategy states its own test and its own failure mode
- `TRC-B1` the reviewer's clarity dimension finds the audition without knowing it exists
- `TRC-F1` no new mechanism is introduced

### comparison-requirements (landed 2026-05-25)

- `TRC-A1` coherent artifacts pass cleanly
- `TRC-A2` a scenario with no upstream intent is flagged as orphaned
- `TRC-A3` route disagreement between route.md and task.yml is flagged
- `TRC-A4` claim with no backing scenario is flagged
- `TRC-A5` same artifacts and policy yield the same verdict
- `TRC-A6` analyze opens no network or model client on its decision path
- `TRC-A7` incoherence on a route below the analyze-gate threshold warns but does not block Land
- `TRC-A8` incoherence on a route that earns the analyze gate blocks Land
- `TRC-A9` analyze is never promoted to a gate globally
- `TRC-A10` an artifact a route legitimately omits is not flagged
- `TRC-A11` analyze reports only coherence findings, not evidence findings
- `TRC-A12` analyze gate promotion is driven by routing-policy, not hard-coded in the CLI
- `TRC-A13` analyze completes within the interactive latency target
- `TRC-B1` a landed behaviour change accretes into the system spec
- `TRC-B2` a pure Spike contributes nothing to the system spec
- `TRC-B3` re-deriving from unchanged scenarios produces no diff
- `TRC-B4` a superseding change updates the prior behaviour and archives the prior
- `TRC-B4a` archived-behaviour appendix preserves the trace back to the prior task
- `TRC-B5` a greenfield project Lands with no pre-existing system spec
- `TRC-B6` introducing the living spec adds no new phase or gate
- `TRC-B7` every entry in the system spec traces to a landed scenario
- `TRC-B8` the derivation is not the sole source of truth
- `TRC-B9` a hand-edit to the spec is silently overwritten by the next Land
- `TRC-B10` the derived spec carries a "DERIVED FILE" header
- `TRC-B11` a landed task is the source-of-truth for the living spec via task.yml.status
- `TRC-C1` asking the agent to build something triggers Frame without naming it
- `TRC-C2` explicit invocation of a Compass command still works
- `TRC-C3` an exploratory request still gets framed (as a Spike)
- `TRC-C4` next reports the upcoming phase and gate in one line
- `TRC-C5` next states which phases are optional on this route
- `TRC-C6` next on a completed task reports nothing remains
- `TRC-C7` next writes no new task state
- `TRC-C8` next derives its answer only from task.yml and the route
- `TRC-C9` next on a task with no Frame reports that Frame is needed
- `TRC-C10` next returns under the interactive latency target
- `TRC-D1` the five-point mental model gains zero new top-level concepts
- `TRC-D2` only two new CLI verbs are added across the three candidates
- `TRC-D3` no fixed-tier ladder is shipped
- `TRC-D4` the five roles remain lenses on one shared spec
- `TRC-D5` pipeline phases still flex by route
- `TRC-D6` phases and gates remain enforced
- `TRC-D7` TDD remains a strategy that Spike suspends
- `TRC-D8` every new capability functions on a bare repo with no /compass:init
- `TRC-D9` route composition stays byte-identical across runs
- `TRC-D10` the determinism boundary holds - no model call after readings on any code path
- `TRC-F1` analyze on a malformed task.yml exits non-zero with a structured error
- `TRC-F2` derivation handles two landed tasks with conflicting scenarios deterministically
- `TRC-F3` invisible triggering does not re-frame an already-framed task
- `TRC-F4` analyze on a task that has not yet been framed reports clearly
- `TRC-F5` a hand-edit to task.yml made by a tool is caught by analyze
- `TRC-F6` next on a task whose route.md is missing reports the missing artifact

### make-receipt-render (landed 2026-05-26)

- `TRC-A1` a landed Standard task with typed evidence renders the canonical receipt
- `TRC-A2` the rendered receipt fits within a single terminal screen
- `TRC-B1` the receipt labels each evidence type with its name and type-specific minimal fields
- `TRC-C1` a pass gate cleared by wrong-typed evidence is rendered as type-mismatch
- `TRC-C2` a pass gate with no evidence id is rendered as unsupported
- `TRC-C3` a task with a failed gate renders the failure prominently
- `TRC-C4` a task with owed backfills is rendered as owing
- `TRC-D1` a not-yet-landed task is labeled in-progress, not rendered as a final receipt
- `TRC-D2` a schema-1.0 task.yml (pre-status field) renders without error
- `TRC-D3` a missing task slug fails cleanly
- `TRC-E1` rendering the receipt mutates nothing on disk

### friction-loop (landed 2026-06-04)

- `TRC-A1` an optional friction block validates against the task schema
- `TRC-A2` Land derives a friction entry from a recorded reframe
- `TRC-A3` Land derives a friction entry from absorbed reframe-debt
- `TRC-A4` the author's optional answer is recorded as a human-sourced entry
- `TRC-A5` recording no friction is a valid, common Land
- `TRC-B1` recurring friction is grouped by category and proposed change
- `TRC-B2` a one-off friction item stays below the recurrence threshold
- `TRC-B3` the friction view emits machine-readable JSON
- `TRC-F1` friction capture never blocks Land
- `TRC-F2` the friction view is read-only and never auto-tunes governance
- `TRC-F3` a task.yml without a friction block stays valid and behaviour is unchanged

### framework-field-feedback (landed 2026-06-23)

- `TRC-R1-1` scenarios-have-tests flags a narrative scenario as FAIL on the current code (baseline)
- `TRC-R1-2` A documented narrative scenario with no test clears the check
- `TRC-R1-3` A non-narrative scenario with no test still fails scenarios-have-tests
- `TRC-R1-4` A narrative scenario with an empty When/Then body still fails (documented, not anything-goes)
- `TRC-R1-5` A narrative scenario carrying an incidental command is assessed on documentation, not the command
- `TRC-R2-1` A failing test piped to tail records a false green today (baseline)
- `TRC-R2-2` pipefail/argv hardening turns the masked failure into a real red
- `TRC-R2-3` A legitimate non-piped command still records green unchanged
- `TRC-R2-4` The detect-and-warn heuristic fires on a pager/filter final stage
- `TRC-R2-5` Output-token cross-check catches a green that lacks a pass token
- `TRC-R3-1` A corpus-shaped scenario fails task lint while passing compass check today (baseline)
- `TRC-R3-2` After the schema fix, the corpus scenario shape passes task lint
- `TRC-R3-3` A plain-string intent still passes task lint after the widening
- `TRC-R3-4` A numeric intent still fails task lint after the widening
- `TRC-R3-5` A list intent with a non-string element still fails task lint
- `TRC-R4-1` Today's grep false-positives on a did-not-fire note and caps to 1 (baseline)
- `TRC-R4-2` Cap read from task.yml gives the correct uncapped value despite the prose
- `TRC-R4-3` A genuinely critical task still caps to 1
- `TRC-R4-4` Integration/verify streams are not counted as worktrees
- `TRC-R4-F1` task.yml missing the readings block fails loudly, never a silent cap
- `TRC-R5-1` An auto-formatter rewrite makes the commit no-op and HEAD does not move (baseline)
- `TRC-R5-2` Pre-commit-clean-then-commit advances HEAD (happy path)
- `TRC-R5-3` A no-op commit is detected, hook fixes re-staged, and the retry advances HEAD
- `TRC-R5-4` HEAD is always verified to have advanced
- `TRC-R5-F1` HEAD still unmoved after the retry → Land ERRORS loudly
- `TRC-R5-F2` Nothing-to-commit is distinguished from a stash-rollback no-op
- `TRC-R6-1` A wrong-type gate-evidence mismatch surfaces only at compass check today (baseline)
- `TRC-R6-2` A task with two wrong-type gates already reports both, as one joined string (baseline)
- `TRC-R6-3` compass gate pass rejects wrong-type evidence at write time with the accepted-type list
- `TRC-R6-4` compass gate pass accepts a correct-type evidence and flips the gate to pass
- `TRC-R6-5` compass check reports ALL gate-evidence mismatches in one enumerated pass
- `TRC-R6-6` The seeded gates block carries each gate's accepted evidence types as a comment
- `TRC-R7-1` A coverage-gated micro-run refuses green today (baseline)
- `TRC-R7-2` The micro-run neutralises the project coverage floor and records green
- `TRC-R7-3` The full-suite coverage gate at Verify is unaffected
- `TRC-R7-4` A non-pytest micro-run is left untouched by the coverage logic
- `TRC-R7-5` A configured test_micro_command takes precedence when present
- `TRC-R8-1` A wiring change with no unit red is blocked today (baseline)
- `TRC-R8-2` tdd-red --verified-by typecheck records the guard and allows the edit
- `TRC-R8-3` The verified-by guard is tied to the scenario's acceptance at Verify
- `TRC-R8-4` A plain tdd-red with no real failure and no --verified-by is still rejected
- `TRC-R8-5` --verified-by rejects an unrecognised kind
- `TRC-R8-6` A verified-by guard that does not actually fail is rejected
- `TRC-R9-1` task.yml blocks below readings are hand-authored today (baseline)
- `TRC-R9-2` compass scenario add writes a well-formed entry that passes task lint
- `TRC-R9-3` compass changed-file add traces a production file to a scenario
- `TRC-R9-4` compass evidence add appends a typed registry entry
- `TRC-R9-5` A mutator rejects a duplicate id rather than silently overwriting
- `TRC-R9-6` A mutator rejects malformed input with non-zero exit and no write
- `TRC-R9-7` compass gate pass is the shared R6/R9 command and is schema-valid
- `TRC-R10-1` regression-baseline is a named, registered soft strategy (S6)
- `TRC-R10-2` routing-policy surfaces regression-baseline when touches is shared/critical
- `TRC-R10-3` Verify expects baseline + post-change test-run evidence on a shared-surface task
- `TRC-R10-4` The Build phase prompts for the baseline capture up front
- `TRC-R10-5` Backward-compat - an absent baseline never blocks Land
- `TRC-R10-6` Backward-compat - guardrail count and gate set unchanged by S6

### field-feedback-2026-07 (landed 2026-07-27)

- `TRC-A1` TRC-A1
- `TRC-A2` TRC-A2
- `TRC-A3` TRC-A3
- `TRC-B1` TRC-B1
- `TRC-B2` TRC-B2
- `TRC-B3` TRC-B3
- `TRC-B4` TRC-B4
- `TRC-C1` TRC-C1
- `TRC-C2` TRC-C2
- `TRC-C3` TRC-C3
- `TRC-C4` TRC-C4
- `TRC-C5` TRC-C5
- `TRC-F1` TRC-F1
- `TRC-F2` TRC-F2

### no-compass-refs-in-product-code (landed 2026-07-27)

- `TRC-A1` TRC-A1
- `TRC-A2` TRC-A2
- `TRC-A3` TRC-A3
- `TRC-A4` TRC-A4

### ci-runs-test-suite (landed 2026-07-29)

- `SCN-001` the CI workflow runs the test suite

### readable-specs-and-flow (landed 2026-08-03)

- `TRC-A1` the Summary should be the first thing a cold reader meets
- `TRC-A2` the Summary should carry exactly the three named fields
- `TRC-A3` Summary length should scale with the route
- `TRC-A4` adding the Summary should leave the scenario machinery untouched
- `TRC-A5` the spec-author should be told to write the Summary during Specify
- `TRC-A6` a filled Summary should be a condition of leaving Clarify
- `TRC-B1` the self-review should list exactly the four scans
- `TRC-B2` each scan should say concretely what it looks for
- `TRC-B3` the self-review should be fixed inline, not re-reviewed
- `TRC-B4` the self-review should complement Clarify rather than replace it
- `TRC-B5` on a collapsed-Clarify route the self-check should be recorded on disk
- `TRC-C1` the check should name the prohibited phrases
- `TRC-C1b` an incomplete work unit should be reported
- `TRC-C2` an advisory hit should be reported without failing the command
- `TRC-C2b` the skill should tell the planner how to judge what the check reports
- `TRC-C3` the check result should be recorded as judgement, not as evidence
- `TRC-C4` the check should not introduce a sixth guardrail
- `TRC-C5` the check should not fire on prose that quotes it
- `TRC-C6` the check should stay advisory on every route
- `TRC-C7` the new subcommand should appear in the documented CLI surface
- `TRC-D1` Specify should close by inviting a cold-reader review
- `TRC-D2` the Clarify and Plan hand-offs should be symmetric with Specify's
- `TRC-D3` each hand-off prompt should be written in exactly one file
- `TRC-E1` the guide should show S7 applied to four kinds of artifact
- `TRC-E2` each worked example should show the weak version beside the improved one
- `TRC-E3` the guide should name what Compass deliberately does not adopt
- `TRC-E4` the guide should be reachable from the docs a new reader opens
- `TRC-F1` specs written before this change should keep passing
- `TRC-F2` the self-review should treat the Summary fields as placeholders to scan
- `TRC-F3` the self-review should record why no subagent critic is used
- `TRC-F4` every file this task adds or changes should pass house style

### release-script-portable-tar (landed 2026-08-03)

- `SCN-001` the release script packages a tarball on this platform
- `SCN-002` dev-only state is excluded without stripping the worked examples
- `SCN-003` untracked local files never ship

### record-keeping-integrity (landed 2026-08-03)

- `TRC-A1` a test id whose file does not exist should be reported
- `TRC-A2` a test id naming a function the file does not contain should be reported
- `TRC-A3` a test id that resolves should pass
- `TRC-A4` a narrative scenario should be exempt from the resolution check
- `TRC-A7` a task that has not yet claimed correctness should not be checked
- `TRC-A8` a landed task should not be re-checked
- `TRC-A5` the check should register under G1 without adding a guardrail
- `TRC-A6` policy lint should accept the new check
- `TRC-B1` a second friction note should not destroy the first
- `TRC-B2` re-running the capture should not duplicate derived entries
- `TRC-B3` capturing nothing should still record nothing
- `TRC-C1` the review-dimensions table should record who assessed each dimension
- `TRC-C2` the template should say what to write in that column
- `TRC-F1` tasks already on disk should keep passing
- `TRC-F2` a task.yml written before this change should still load
- `TRC-F3` every file this task changes should pass house style

### version-bump-1-7-0 (landed 2026-08-03)

- `TRC-1` every published surface should report 1.7.0

### v2-terminology-freeze (landed 2026-08-06)

- `TRC-A1` the vocabulary file parses and carries its three sections
- `TRC-A2` every term states its meaning
- `TRC-A3` every ban carries a replacement and a context
- `TRC-A4` the scan config declares its three lists
- `TRC-B1` a banned usage in a fixture is flagged
- `TRC-B2` an innocent usage of the same words is not flagged
- `TRC-C1` a pending surface may still carry banned terms
- `TRC-C2` a surface removed from pending must be clean
- `TRC-C3` the pending list only ever shrinks
- `TRC-C4` the repository scan is green on day one
- `TRC-F1` a pending entry that names no real surface is rejected
- `TRC-F2` an exempt path is never scanned

### v2-implementation-plan (landed 2026-08-06)

- `TRC-A1` the implementation plan document is reviewable and complete

### v2-terminology-dangling-refs (landed 2026-08-07)

- `TRC-A1` every related term is defined

### v2-prd-and-freeze-adr (landed 2026-08-07)

- `TRC-A1` the v2 PRD exists in the v2 register with all required sections
- `TRC-A2` the vocabulary freeze is recorded as an accepted, indexed decision record

### v2-session-instructions (landed 2026-08-07)

- `TRC-A1` CLAUDE.md is clean v2 register and operationally exact
- `TRC-A2` AGENTS.md is clean v2 register with the adapter contract intact
- `TRC-A3` the compass-runtime skill carries the stage-to-command mapping in the v2 register
- `TRC-B1` code-quoted machine identifiers stay legal on scanned markdown

### v2-template-prose (landed 2026-08-07)

- `TRC-A1` the templates speak the v2 register and templates/ is enforced, never pending again
- `TRC-A2` the follow-up ban tolerates its live machine forms (tag, CLI verb, spine key)
- `TRC-A3` the archive sweeps exclude issues the spine says have not started

### v2-machine-spine (landed 2026-08-07)

- `TRC-A1` the evaluator writes a v2 spine
- `TRC-A2` a 1.x spine is still readable by normalisation
- `TRC-A3` the repository archive speaks schema 2.0
- `TRC-A4` the archive carries v2 artifact names
- `TRC-A5` the artifact-name fallback is retired
- `TRC-A6` the spine template speaks v2 and is scanned
- `TRC-A7` the policy keys speak v2

### retire-route-md-alias (landed 2026-08-07)

- `TRC-1` the archive sweep has no in-flight exemption
- `TRC-2` an issue with only delivery-approach.md passes the pre-tool hook

### v2-command-renames (landed 2026-08-07)

- `TRC-1` the command set carries the v2 names
- `TRC-2` each renamed v1 command is a redirect stub
- `TRC-3` the vocabulary carries the command names and a version bump
- `TRC-4` commands and the plugin manifests are enforced surfaces
- `TRC-5` no live instruction surface points at a dead command name
- `TRC-6` the ruling conditions hold

### v2-cli-voice (landed 2026-08-07)

- `TRC-1` the v2 verbs exist and work
- `TRC-2` a retired verb fails loudly and legibly
- `TRC-3` the --issue flag with --task tolerated
- `TRC-4` follow-up states are outstanding and resolved with 1.x readable
- `TRC-5` CLI output speaks v2 change-type names and the receipt shows overrides
- `TRC-6` the vocabulary carries receipt, the amended follow-up, and a bump
- `TRC-7` the cli surface is enforced and widened
- `TRC-8` the compass-backfill tolerance is re-tightened

### v2-skills-prose (landed 2026-08-07)

- `TRC-1` skills is an enforced surface
- `TRC-2` agents is a scanned enforced never-pending surface
- `TRC-3` the worktree-swarm skill carries the stash rule
- `TRC-4` the lens ban catches the concept not the agent identifiers

### v2-docs-prose (landed 2026-08-08)

- `TRC-1` the ratchet reaches zero
- `TRC-2` the delivery-approach reference docs carry v2 names
- `TRC-3` the worked examples carry v2 change-type names
- `TRC-4` the remaining docs are enforced surfaces
- `TRC-5` the install refusal points at the plugin-dir path

### v2-docs-prose-2 (landed 2026-08-08)

- `TRC-1` the ratchet reaches zero
- `TRC-2` the four deferred docs are enforced and clean

### v2-migrate (landed 2026-08-08)

- `TRC-1` dry run reports and writes nothing
- `TRC-2` apply migrates a v1 tree to v2
- `TRC-3` a second apply is a no-op
- `TRC-4` the mapping lives in the exempt data file

### v2-release (landed 2026-08-08)

- `TRC-1` the version is 2.0.0 in every guarded location
- `TRC-2` desired-state graduates and is enforced

### human-voice (landed 2026-08-09)

- `TRC-A1` the reference should live under an existing skill and open with the principle
- `TRC-A2` every before/after pair should be a real passage from the work archive
- `TRC-A3` the tells list should name all nine tells and say which a string can find
- `TRC-A4` no rewritten passage should still carry a tell
- `TRC-B1` the root instruction files should carry a short voice paragraph
- `TRC-B2` the three talkiest stages should each point at the reference
- `TRC-B3` the tells should live in one place, so a later edit cannot leave a stale copy
- `TRC-C1` a real requirements review from the archive should become the canonical worked example
- `TRC-C2` the original should stay readable beside the rewrite
- `TRC-C3` the requirements-review template should show a decision recorded in a human voice
- `TRC-D1` the clarity dimension should name the tells as judgement, not as a rule
- `TRC-D2` the tell check should name the file and line of each hit
- `TRC-D3` a clean set of artifacts should get a stated result, not silence
- `TRC-F1` a tell that is found should block nothing
- `TRC-F2` the exhibits should not be read as defects
- `TRC-F3` nothing about how Compass behaves should change
- `TRC-F4` every file this issue writes should clear house style and the frozen vocabulary

### zero-friction-install (landed 2026-08-10)

- `TRC-A1` a first triage completes with no Python package installed
- `TRC-A2` no CLI verb exits on a missing dependency
- `TRC-A3` the acceptance-before-code hook check runs instead of failing open
- `TRC-A4` integration records the landing rather than warning it could not
- `TRC-A5` the session-end signal scan runs rather than returning empty
- `TRC-A6` the repository check runs the policy lint rather than skipping it
- `TRC-A7` preparing a swarm reads the cap rather than refusing
- `TRC-G1` the bundled copy is the one used, whatever the machine has
- `TRC-G2` the shipped version is the documented version
- `TRC-G3` the bundled library carries its licence and its attribution
- `TRC-D1` nothing shipped tells a user or an adopter to install PyYAML
- `TRC-D3` the copyable CI workflow runs with no dependency step
- `TRC-D4` the install smoke test asserts the zero-install path
- `TRC-D5` no test requires the removed instruction to still exist
- `TRC-D6` no document claims Compass has no dependencies
- `TRC-E1` the decision is recorded with the alternative it beat
- `TRC-F4` an issue already in flight continues unchanged across the upgrade
- `TRC-F5` jsonschema stays optional and unchanged
- `TRC-F6` the distributed plugin actually contains the bundled copy
- `TRC-F7` recording acceptance for a second scenario does not destroy the first one's evidence

### derive-spec-multi-intent (landed 2026-08-10)

- `TRC-1` a scenario that serves two intents answers for both
- `TRC-2` the single-intent form is unchanged

### tests-survive-shallow-clone (landed 2026-08-10)

- `TRC-1` the pinned assertions run where the history is absent

### fresh-eyes-verify-sweeps (landed 2026-08-11)

- `TRC-A1` the strategy states the trigger, the staffing rule, and the method
- `TRC-A2` the strategy states the prohibition, the evidence, and carries the file's own conventions
- `TRC-B1` the verify stage guidance points at the strategy without repeating it
- `TRC-F1` no new mechanism is introduced

### adr-013-context-tense (landed 2026-08-11)

- `TRC-1` no public file claims an outside user
- `TRC-2` no public file attaches a duration to a user
- `TRC-3` the guard catches the defect it was written for

### s9-primary-record (landed 2026-08-12)

- `TRC-C1` the entry states the primary-record rule and defines what a primary record is
- `TRC-C2` the entry carries the ADR-013 worked example and warns the nearest document is often a summary

### archive-quote-verification (landed 2026-08-12)

- `TRC-1` a fabricated quote fails even without the archive
- `TRC-2` an unaltered quote is accepted, and the report names what went unverified
- `TRC-3` a genuine quote passes by direct verification
- `TRC-4` a mismatched quote fails, not skips, when the archive is present
- `TRC-5` the regeneration path refuses an unverified hash

### sweep-respects-queued (landed 2026-08-12)

- `TRC-1` a not-yet-started issue does not fail the sweep
- `TRC-2` the sweep still names what it did not check
- `TRC-3` an in-flight issue is still checked

### spine-schema-reassessment-keys (landed 2026-08-12)

- `TRC-1` a recorded re-assessment lints clean
- `TRC-2` the keys are declared, not merely tolerated

### smoke-test-version-drift (landed 2026-08-12)

- `TRC-1` every documented banner matches what the CLI prints
- `TRC-2` the banner uses current vocabulary

### smoke-test-speaks-v2 (landed 2026-08-12)

- `TRC-1` the document describes v2 behaviour
- `TRC-2` the document is scanned for the frozen vocabulary

### version-guard-covers-all (landed 2026-08-12)

- `TRC-1` every published location reports the declared version
- `TRC-2` the guard has a case for every published location
- `TRC-3` no constant nothing reads

### ci-lints-every-issue (landed 2026-08-12)

- `TRC-1` a malformed spine fails the sweep whatever its status
- `TRC-2` a well-formed not-yet-started issue still does not fail
- `TRC-3` the summary reports what was and was not checked

### quote-verifier-rejects-unparsed (landed 2026-08-12)

- `TRC-1` an unparsed span is a failure
- `TRC-2` update refuses to record an unparsed span
- `TRC-3` a well-formed span still verifies

### tests-that-can-fail (landed 2026-08-12)

- `TRC-1` the version guard compares every location it names
- `TRC-2` the validate guard fails when the lint is skipped
- `TRC-3` the tell-scope guard fails when nothing was found
- `TRC-4` the reference-location guard fails on a new skill directory
- `TRC-5` the header scan proves how many modules it read

### mutation-proof-standing (landed 2026-08-12)

- `TRC-1` the strategy states the method and the reason
- `TRC-2` the verify guidance points at the strategy
- `TRC-3` the id set admits the new strategy deliberately

### rehearsal-recordings (landed 2026-08-13)

- `RR-1` the script is the eight-shot re-cut
- `RR-2` the post-3.0.0 shots are marked pending and listed for re-check
- `RR-3` the Part 0 corrections are folded in
- `RR-4` the token figures are filed with their caveat and stay internal
- `RR-5` the cold-reader test heads the next cycle's experiment list
- `RR-6` measure-before-arguing is in the operating model
- `RR-7` the new guard can fail

### rehearsal-cli-defects (landed 2026-08-13)

- `RCD-A1` the hook finds the project from a subdirectory
- `RCD-A2` an unresolvable project root fails closed, not open
- `RCD-A3` the message names the real cause
- `RCD-A4` a genuine triage-has-not-run still says so
- `RCD-B1` design lint defaults to the live artifact filename
- `RCD-B2` the not-found message names the path actually used
- `RCD-C1` a nested test id resolves
- `RCD-C2` a test name ending in a non-word character resolves
- `RCD-C3` a genuinely missing test still fails the check
- `RCD-D1` the current-issue pointer is in shipping scope
- `RCD-D2` an unrelated staged file is still refused
- `RCD-E1` compass check's header names the computed approach
- `RCD-E2` the cross-issue board names each computed approach
- `RCD-F1` no retired slash command remains
- `RCD-F2` a retired CLI verb is an unknown verb
- `RCD-F3` a retired flag is an unknown flag
- `RCD-F4` the migrator keeps its v1-to-v2 mapping
- `RCD-G1` a v1 name in a Python single-token literal is caught
- `RCD-G2` a v1 name in a markdown code span or fenced block is caught
- `RCD-G3` the hooks directory is a scanned surface
- `RCD-G4` the archive is exempt and unedited
- `RCD-G5` the tightened guard can fail
- `RCD-H1` the version is consistent across every location

### strategy-rulings-2026-08 (landed 2026-08-13)

- `SR-1` conventional comments is a shipped default
- `SR-2` the label guard cannot pass on a partial list
- `SR-3` conventional commits is a project strategy only
- `SR-4` semantic versioning is stated
- `SR-5` prefer-open-technologies is filed, not adopted
- `SR-6` S7 names the surfaces it governs

### scan-the-remaining-surfaces (landed 2026-08-13)

- `SS-1` the four surfaces are scanned
- `SS-2` a JSON schema's prose is read, its contract is not
- `SS-3` the machine contract is untouched
- `SS-4` the guard can fail on each new surface

### id-prefix-vocabulary-and-glossary (landed 2026-08-13)

- `GL-A1` traceability, intent and navigator are defined
- `GL-B1` every id prefix in use is defined
- `GL-B2` the guard fails on an undefined prefix
- `GL-C1` the glossary page is derived, not hand-written
- `GL-C2` drift between source and page fails the build
- `GL-C3` compass terminology renders a code
- `GL-D1` routing ids are RP- and kinds are distinct
- `GL-D2` the evaluator is unchanged by the rename
- `GL-D3` the archive keeps the id that fired
- `GL-E1` the follow-up surfaces match the schema
- `GL-E2` the parser still reads the retired tag

### pr-50-review-findings (landed 2026-08-13)

- `PRF-1` the enforcement path exempts by anchored name
- `PRF-2` the session-end hook reads the spine
- `PRF-3` the scan reads the hook's own messages
- `PRF-4` an explicit project root is trusted
- `PRF-6` the tests that could not fail can now fail
- `PRF-7` the suite passes on a clean clone
- `PRF-5` the warners say when they cannot find the project

### consolidate-trc-and-scn-prefixes (landed 2026-08-13)

- `EX-1` the samples use the current vocabulary
- `EX-2` the canonical id prefix is used throughout
- `EX-3` every sample still passes its own checks
- `EX-4` the guard can fail

### configurable-enforced-set (landed 2026-08-13)

- `SCN-A1` a project can add a file type
- `SCN-A2` a path-shaped glob works too
- `SCN-A3` a project that configures nothing is unaffected
- `SCN-A4` a project cannot exempt what the framework enforces
- `SCN-B1` the block names the rule that matched
- `SCN-B2` a built-in match says so
- `SCN-C1` Compass's own shell scripts are enforced
- `SCN-F1` an unreadable config does not block
- `SCN-F2` test files stay exempt whatever the config says

### g5-trigger-matches-statement (landed 2026-08-13)

- `SCN-A1` a critical-blast-radius task requires a human approval
- `SCN-A2` a critical task with a recorded approval clears G5
- `SCN-A3` the domain trigger is unchanged
- `SCN-A4` a task matching neither condition still skips G5
- `SCN-B1` any_of matches when one clause matches
- `SCN-B2` any_of fails when no clause matches
- `SCN-B3` any_of composes with sibling keys as an AND
- `SCN-C1` a landed task without an approval is reported, not failed
- `SCN-F1` the published guarantee matches the trigger
- `SCN-F2` governance carries a new version

### honest-acceptance-for-config-and-refactor (landed 2026-08-13)

- `SCN-A1` a validation acceptance permits the edit
- `SCN-A2` a refactor acceptance requires a green baseline first
- `SCN-A3` an unrecognised kind is refused
- `SCN-B1` a validation acceptance records the validator's output
- `SCN-B2` a failing validator does not close the acceptance
- `SCN-B3` a refactor must run the same command it baselined
- `SCN-B4` a refactor with an unchanged source tree is refused
- `SCN-B5` a refactor that preserved behaviour is recorded
- `SCN-C1` the hook names which marker permitted the edit
- `SCN-C2` an acceptance does not survive into the next task
- `SCN-F1` the recorded evidence satisfies the existing checks
- `SCN-F2` the anti-pattern is named where authors will meet it

### hook-bash-write-bypass (landed 2026-08-13)

- `SCN-A1` a redirect into a source file is blocked with no red on record
- `SCN-A2` an in-place edit of a source file is blocked
- `SCN-A3` an inline interpreter script that writes a source file is blocked
- `SCN-A4` the same command is allowed once a red is on record
- `SCN-B1` a read-only command is allowed
- `SCN-B2` writing a test file is allowed
- `SCN-B3` a redirect to a non-code destination is allowed
- `SCN-B4` a command that reverts to committed state is allowed
- `SCN-C1` a path exempt for Edit is exempt for Bash
- `SCN-C2` the Spike route suspends the check for Bash too
- `SCN-F1` an undetectable write is a documented limit, not a silent one
- `SCN-F2` the hook adds no meaningful cost to ordinary commands

### release-blockers-2026-08 (landed 2026-08-13)

- `SCN-01` the repo check must ignore files git does not track
- `SCN-02` enforcement must not switch itself off based on the checkout path
- `SCN-03` a seeded worktree must not inherit another builder's red
- `SCN-04` a BDD run must record which scenarios it actually bound
- `SCN-05` every BDD adapter example must have the test files it declares
- `SCN-06` every shipped route example must pass its own checks
- `SCN-07` the behave adapter must report its bound scenarios correctly
- `SCN-08` a CI job that runs a Python tool must install Python first
- `SCN-09` an example's declared tests must point at real files
- `SCN-10` a Spike route must still report an owed backfill
- `SCN-11` landing must not be recorded over gates that have not passed
- `SCN-12` a receipt must not report a clean land over pending gates
- `SCN-13` the analyze summary must agree with the findings above it
- `SCN-14` a lint must report a malformed file, not crash on it
- `SCN-15` the onboarding transcript must match what the CLI prints
- `SCN-16` documented commands must exist
- `SCN-17` a different test command must not read as a rerun-to-green

### hook-enforces-g2 (landed 2026-08-13)

- `SCN-A1` a full Specify with no scenarios blocks a code edit
- `SCN-A2` scenarios present allow the edit
- `SCN-A3` routes without a full Specify are unaffected
- `SCN-A4` a Spike suspends the G2 check
- `SCN-B1` the message names the guardrail and the remedy
- `SCN-B2` a test file stays editable
- `SCN-F1` an unreadable spine does not block
- `SCN-F2` G2 is checked before the red

### hotfix-1-8-1-false-blocks-and-land-scope (landed 2026-08-13)

- `SCN-A1` a read-only open is allowed
- `SCN-A2` a path named inside written prose is not the write target
- `SCN-A3` an inline script that opens a source file for writing is still blocked
- `SCN-A4` a heredoc that writes a source file is still blocked
- `SCN-B1` the post-hook retry re-stages only the task's files
- `SCN-B2` an out-of-scope staged path aborts the commit
- `SCN-B3` a task that declares nothing is not silently widened
- `SCN-F1` the 1.8.0 detection scenarios keep passing

### sha-pin-workflow-actions (landed 2026-08-13)

- `SCN-001` Third-party actions in the self-check workflow are SHA-pinned

### spine-records-the-truth (landed 2026-08-13)

- `SCN-A1` a re-frame that changes gates but not the route name is logged
- `SCN-A2` a re-frame with no material change is not logged
- `SCN-A3` each entry records what changed
- `SCN-A4` each entry carries a kind
- `SCN-A5` calibration counts only judgement re-frames
- `SCN-B1` a raw log declared as test-run is refused at write time
- `SCN-B2` a real run record is accepted
- `SCN-B3` a missing file is refused
- `SCN-B4` types with no shape contract are unaffected
- `SCN-C1` a scenario may record what supersedes it
- `SCN-C2` superseded_by must name a scenario that exists
- `SCN-F1` task.yml files written before this keep working

### status-vocabulary (landed 2026-08-13)

- `SCN-A1` the new statuses validate
- `SCN-A2` an unknown status is still rejected
- `SCN-A3` a parked task can record why and when
- `SCN-B1` set-status writes the field
- `SCN-B2` set-status refuses a value outside the vocabulary
- `SCN-B3` landing through set-status still respects the gates
- `SCN-C1` flow separates parked work from active work
- `SCN-C2` calibration excludes parked and abandoned
- `SCN-C3` the living spec still derives only from landed tasks
- `SCN-F1` a task.yml with no status still behaves as active
- `SCN-F2` landed is the only privileged value

### swarm-script-strips-markdown (landed 2026-08-13)

- `TRC-1` swarm.sh strips markdown punctuation from the branch-name cell

### trace-rot-detection (landed 2026-08-13)

- `SCN-A1` a missing changed_files path fails a task claiming correctness
- `SCN-A2` the message offers the new path when git knows the rename
- `SCN-A3` a task that has not yet claimed correctness is not failed
- `SCN-B1` a landed task with a rotted trace is reported, not failed
- `SCN-B2` a clean task says what it verified
- `SCN-C1` no new check name appears in governance
- `SCN-F1` a deliberately deleted file is not trace rot
- `SCN-F2` a project outside git still gets the check

### stale-active-issue-sweep (landed 2026-08-13)

- `SW-1` no issue claims to be in flight when it is not
- `SW-2` a status change is justified by evidence
- `SW-3` nothing is marked landed without its gates
- `SW-4` the archive still lints and checks clean

### identifiers-and-vocabulary-in-printed-output (landed 2026-08-13)

- `TRC-A1` the identifier-expansion rule is stated where agent speech is governed
- `TRC-A2` the receipt prints a scenario's title beside its id
- `TRC-A3` a printed identifier is never truncated
- `TRC-A4` the identifier check can fail
- `TRC-B1` the approach evaluator prints no retired vocabulary name
- `TRC-B2` the printed-output scan can fail
- `TRC-B3` the spine keys and the computed approach are unchanged
- `TRC-C1` neither receipt branch calls a routing rule a guardrail
- `TRC-D1` compass check counts clearances that checked nothing apart from verified ones
- `TRC-D2` a real pass is not miscounted
- `TRC-E1` a shared policy-rule effect is printed once

### dry-run-2-rulings (landed 2026-08-14)

- `TRC-A1` triage states permitted parallel streams and no topology
- `TRC-A2` the stream ceiling is an integer, not a sentence
- `TRC-A3` an uncapped approach permits more than one stream
- `TRC-B1` a passing check summary prints no denominator
- `TRC-B2` a failing check summary keeps its denominator
- `TRC-C1` suite-passed does not present a binding as coverage
- `TRC-C2` a skipped test does not count as a resolving test
- `TRC-C3` an ordinary test still resolves
- `TRC-D1` YAML values are scanned for retired vocabulary
- `TRC-D2` every position exemption names its reason
- `TRC-D3` the widened scan can fail in the newly covered position

### cucumber-13-drops-vulnerable-uuid (landed 2026-08-14)

- `CU-1` the cucumber-js adapter declares no vulnerable uuid dependency

### field-feedback-hook-scope-and-restage (landed 2026-08-14)

- `FF-1` the hook allows a code file outside the project
- `FF-2` the hook still blocks a code file inside the project
- `FF-3` the re-stage does not widen the commit beyond what was staged
- `FF-4` the issue's artifact directory is still re-staged
- `FF-5` no obscure word appears in user-facing text

### plain-language-3-2-0 (landed 2026-08-16)

- `TRC-A1` published launch copy should be under version control
- `TRC-A9` a file declaring its own exclusions should not be tracked as publication copy
- `TRC-A2` an em dash in published copy should fail the guard
- `TRC-A3` the filesystem fallback should not be used where git works
- `TRC-A8` falling back to the filesystem should announce itself
- `TRC-A4` build noise should stay out of the scan
- `TRC-A5` the guard's docstring should record that the omission was silent
- `TRC-A6` an en dash should not be flagged
- `TRC-B1` "seam" used for code structure should be flagged
- `TRC-B2` "seam" used for anything else should not be flagged
- `TRC-B3` the ban should name what to write instead
- `TRC-B4` a rare word quoted from a tool should survive the ban
- `TRC-B7` the shipped list should say what is true today, not what is intended
- `TRC-B5` "un-conflate" should be gone from governance
- `TRC-C1` the strategy should state the order, with real pairs
- `TRC-C2` a bare code in human-facing output should be counted
- `TRC-C3` a code with its meaning in front of it should not be counted
- `TRC-C7` the meaning arriving after the code should still be counted
- `TRC-C4` a non-zero count should report rather than block
- `TRC-C11` governance prose should be scanned for bare codes, not exempt by path
- `TRC-C5` the reviewer should be told to look for this
- `TRC-C8` an entry that is only an identifier should not have to gloss itself
- `TRC-C9` a derivation failure should name what changed and what was expected
- `TRC-C10` an empty gloss registry should fail loudly, never report zero
- `TRC-C12` the claims gate should say it checks traceability, not truth
- `TRC-C15` every screen printing a fired rule should put the meaning first
- `TRC-C6` the first run should record a starting count
- `TRC-D1` the title rule should name the shapes it refuses
- `TRC-D2` the body template should say what a reviewer needs
- `TRC-D3` a commit title should be held to the same rule
- `TRC-D5` a search reporting zero should have been proved able to find something
- `TRC-D6` the correction rule should say which places take a correction and which take a note
- `TRC-D4` a correction should not leave the record contradicting itself
- `TRC-E1` a sentence of thirty-one words or more should be reported
- `TRC-E2` the long-sentence report should never fail a build
- `TRC-G1` no em dash should remain in published copy
- `TRC-G2` no structural use of "seam" should remain
- `TRC-G3` the living spec's stale title should be fixed by re-deriving it
- `TRC-X3` a banned word should never be fixed by deleting the identifier
- `TRC-X4` repairing a banned word should not paraphrase a quoted tool string

### claims-match-what-is-proved (landed 2026-08-22)

- `TRC-A1` an incomplete project governance directory should be refused rather than quietly replaced
- `TRC-A2` the refusal should name the file it found and the file it expected
- `TRC-A3` a project that has said nothing about governance should still use the shipped defaults silently
- `TRC-A4` a complete project governance directory should still be used
- `TRC-A5` the documentation should state that project governance replaces the shipped defaults
- `TRC-A6` an incomplete governance directory outside the project should not stop work inside it
- `TRC-B1` the promise should not say a test ran when only a command exited zero
- `TRC-B2` the promise should read the same in every place it is made
- `TRC-B3` the safety contract should state what a green record does not establish
- `TRC-B4` every guarantee should name the mechanism that backs it
- `TRC-C1` the guide should say that project governance is executable code
- `TRC-C2` the guide should not offer pull-request review as the execution boundary
- `TRC-C3` the guide should point at the work that closes the gap
- `TRC-D1` a guarantee with no backing mechanism should fail the check
- `TRC-D2` a backing mechanism that does not exist should fail the check
- `TRC-F1` a project governance directory missing its guardrails should be refused the same way
- `TRC-F2` narrowing the promise should not weaken what the check actually enforces

### public-docs-tell-the-truth (landed 2026-08-22)

- `TRC-A1` no published file should misspell the word the framework renamed to
- `TRC-A2` the safety contract should be titled for the release it describes
- `TRC-A3` the security guide should not deny a distribution channel the project publishes on
- `TRC-A4` a document should not point at files that do not exist
- `TRC-A5` a live architecture artifact should not describe a retired stage as current
- `TRC-A6` a message the CLI prints should not tell a user to run a stage that no longer exists
- `TRC-B1` a retired stage name alone in a table cell should be caught
- `TRC-B2` a retired stage name alone in a bold run should be caught
- `TRC-B3` every retired stage name should be bound to the label shape, not only Frame
- `TRC-B4` the scan should report the count it found, not only that it found some
- `TRC-B5` a retired stage name used mid-sentence should be caught
- `TRC-C1` a retired word used as an ordinary verb should not be caught
- `TRC-C2` a bold run that begins with a retired word but continues into a sentence should not be caught
- `TRC-C3` the tolerance fixture should carry every shape the patterns must walk past
- `TRC-C4` widening the patterns should not change what the scan reports on today's clean surfaces
- `TRC-D1` no live surface should carry a retired stage name
- `TRC-D2` a repair should not change what an agent is instructed to do
- `TRC-D3` history should stay exempt and stay honest
- `TRC-E1` a claim about every failure message should be checked or withdrawn
- `TRC-E2` a narrowed guarantee should still name its backing mechanism
- `TRC-F1` the decay rule should say what it asks of the reader
- `TRC-F2` the launch article should read as publication copy throughout

### project-commands-are-a-trust-boundary (landed 2026-08-22)

- `TRC-A1` a project command should not run unless the project has opted in
- `TRC-A2` a project that has opted in should have its command run
- `TRC-A3` the report should distinguish disabled from nothing declared
- `TRC-B1` a command should be refused when the CI environment says the contribution is untrusted
- `TRC-B2` the repository must not be able to switch the refusal off
- `TRC-B3` detection should not depend on one CI provider
- `TRC-B4` an ordinary local run should not be treated as untrusted
- `TRC-C1` a project should be able to name a script instead of writing a shell string
- `TRC-C2` a script path outside the project should be refused
- `TRC-C3` the shell form should keep working, and say what it costs
- `TRC-D1` the reference workflow should declare the token permissions it needs
- `TRC-D2` Compass's own workflow should follow the same posture
- `TRC-D3` the security guide should say what a project must decide about untrusted pull requests
- `TRC-E1` a project whose command stops running should be told
- `TRC-E2` the guarantee about declared guardrails should still hold
- `TRC-B5` an unrecognised CI provider should be refused rather than trusted

### tdd-green-unbound-record (landed 2026-08-23)

- `TRC-A1` recording a scenario-bound green leaves the unbound green intact
- `TRC-A2` recording a scenario-bound acceptance leaves the unbound acceptance intact
- `TRC-A3` no evidence-writing verb overwrites a path the registry names
- `TRC-A4` the unbound record can still be re-recorded deliberately
- `TRC-B1` a recorded run carries an identity unique to that run
- `TRC-B2` re-recording the same command produces a different identity
- `TRC-B3` the registry entry stores the identity of the run it was created from
- `TRC-C1` a citation whose record has been replaced is reported
- `TRC-C2` a citation that matches its record is not reported
- `TRC-C3` the report names the evidence id, the path, and what changed
- `TRC-D1` a record written before this change does not fail the check
- `TRC-D2` an unverifiable record is reported as unverifiable, not as verified

### docs-describe-the-old-evidence-path (landed 2026-08-23)

- `TRC-A1` no published surface claims a green is always written to the shared path
- `TRC-A2` the documentation names both forms and says which is written when
- `TRC-A3` a worked example shows the path a reader will actually see
- `TRC-B1` the guard fails when a surface reintroduces the old claim
- `TRC-C1` every CLI module's banner describes what the verbs actually write

### agent-speech-is-unchecked (landed 2026-08-23)

- `TRC-A1` the always-loaded instructions state the four-part reply shape
- `TRC-A2` the shape carries its three rules
- `TRC-A3` the length tension is resolved rather than left open
- `TRC-B1` a worked list gives each leaky term its plain-English form
- `TRC-B2` the list covers every term the cold reader named
- `TRC-C1` the rule is attached to a moment, not stated as advice
- `TRC-D1` the headings tell distinguishes a label from an answer
- `TRC-D2` no instruction tells a session both to use and to avoid reply headings
- `TRC-A4` the portable instructions carry the shape too

### the-human-front-door (landed 2026-08-23)

- `TRC-A1` a registered artifact declares its kind, path, status and reason
- `TRC-A2` an omitted artifact records why it was omitted
- `TRC-A3` the schema refuses an entry that explains nothing
- `TRC-B1` a registered path resolves ahead of the flat filename
- `TRC-B2` an issue with no registry still resolves its artifacts
- `TRC-B3` an artifact that resolves by neither route is reported, not silently absent
- `TRC-B4` every landed issue still resolves after the change
- `TRC-C1` the dashboard names the decision required and where to start
- `TRC-C2` it lists every registered artifact with its status and why it exists
- `TRC-C3` it lists what was deliberately omitted, with reasons
- `TRC-C4` it carries no raw evidence
- `TRC-D1` a dashboard that no longer matches the spine is reported as stale
- `TRC-D2` a drifted dashboard fails the check rather than warning
- `TRC-D3` the currency check is wired into a guardrail
- `TRC-E1` the instructions tell a stage to link evidence rather than paste it
- `TRC-C5` the dashboard can be generated and checked from the CLI
- `TRC-C6` the pack separates a document that exists from one still owed
- `TRC-C7` a document's status can be moved, and an omission recorded
- `TRC-F1` the evaluator computes the artifact set from the assessment
- `TRC-F2` a trivial atomic change earns almost nothing
- `TRC-F3` a policy rule can add an artifact the way it adds a gate
- `TRC-F4` the same assessment computes the same artifact set every time

### the-terminal-output-contract (landed 2026-08-24)

- `TRC-A1` a stage hand-off fits on one screen
- `TRC-A2` the hand-off says what was decided and what to read
- `TRC-A3` a hand-off with nothing to decide is shorter, not padded
- `TRC-A4` at most three key choices and three concerns
- `TRC-A5` the budget cannot be met by making the lines longer
- `TRC-A6` the gate verdict keeps its guidance one flag away
- `TRC-B1` a report opens with a summary a reader can stop at
- `TRC-B2` a report's own detail is never truncated by the contract
- `TRC-C1` every verb accepts every mode flag
- `TRC-C2` quiet prints nothing on success
- `TRC-C3` json is the machine mode and carries no prose
- `TRC-C4` evidence-out writes the raw capture rather than printing it
- `TRC-C5` verbose is where detail goes, not where the contract is escaped
- `TRC-C6` every verb declares which contract it is under
- `TRC-C7` evidence-out on a verb with nothing to capture
- `TRC-D1` an identifier survives compression with its meaning attached
- `TRC-D2` the meaning still comes before the code
- `TRC-D3` retired vocabulary stays out of printed strings
- `TRC-D4` an expected string is updated only when the test's intent still holds
- `TRC-E1` a verb prints past its budget and the guard says which one
- `TRC-E2` the budget guard fails when the budget is breached

### adaptive-artifact-composition (landed 2026-08-24)

- `TRC-A1` the template asks the four questions and no others
- `TRC-A2` a threat with no scenario is visibly unfinished
- `TRC-A3` the fourth question is answered by evidence, not by assertion
- `TRC-B1` the template records when the rollback was last rehearsed
- `TRC-B2` the evidence type stops accepting a plan as a rollback
- `TRC-B3` a rollback plan with no rehearsal date is caught
- `TRC-C1` the design template offers a cross-cutting concerns section
- `TRC-C2` the skill that governs the optional sections knows about it
- `TRC-D1` every document kind the policy names has a template
- `TRC-D2` no document was added that nothing asks for
- `TRC-D3` both templates stay shorter than the framework's own PRD

### the-vocabulary-rename (landed 2026-08-25)

- `TRC-A1` a command, its key and its artifact name the same thing
- `TRC-A2` the designer's command is design again
- `TRC-A3` every overloaded word carries a glossary entry
- `TRC-A4` the planning stage answers to plan in the CLI too
- `TRC-A5` no live surface sends the engineering stage to /compass:design
- `TRC-B1` a spine written before the rename still reads
- `TRC-B2` a document written before the rename still resolves
- `TRC-B3` both spellings are accepted before any caller switches
- `TRC-B4` the retired commands answer with a pointer
- `TRC-B5` a document written after the rename resolves under its new name
- `TRC-B6` the current filename wins when both are present
- `TRC-B7` the design lint still reads a landed issue's design
- `TRC-B8` a policy floor written with a retired stage key still applies
- `TRC-C1` the map carries the stage keys
- `TRC-C2` migrate rewrites a stale reference
- `TRC-C3` a dry run writes nothing and says what it would do
- `TRC-C4` a stopped migration says what it did and what remains
- `TRC-C5` migrate refuses a many-to-one filename collision
- `TRC-C6` migrate repoints the spine at the files it renamed
- `TRC-D1` a ban never points at a banned replacement
- `TRC-D2` governance files are scanned for retired vocabulary
- `TRC-D3` the acceptance-criteria guardrail reads the current stage key
- `TRC-D4` no term is both defined and banned
- `TRC-D5` the code-position scan knows this rename
- `TRC-E1` the rename is not counted as done while a surface still says the old word
- `TRC-E2` the guard fails when handed nothing
- `TRC-E3` the coherence check reads the stage table the template writes
- `TRC-E4` every citation into the archive opens

### ingest-an-existing-brief (landed 2026-08-25)

- `ING-A1` a local file becomes intent.md
- `ING-A2` the source may be called anything
- `ING-A3` a URL becomes intent.md
- `ING-A4` a source that is not there fails before anything is written
- `ING-B1` the document is reshaped, not copied
- `ING-B2` a gap becomes a question, not a TBD
- `ING-B3` nothing is invented
- `ING-B4` a person can decline every question and still get an intent.md
- `ING-C1` an ingested brief says where it came from
- `ING-C2` the reshaping is auditable
- `ING-D1` an authenticated source is refused with a way forward
- `ING-D2` no network, no silent failure
- `ING-D3` a redirect is followed, and provenance names where it landed
- `ING-D4` a URL that is not https is refused
- `ING-E1` the fidelity gate reports which human the material came from

### ci-fails-a-queued-issue-for-being-queued (landed 2026-08-26)

- `CIQ-A1` a queued issue is not asked for an assessment it cannot have

### cli-verbs-do-not-describe-themselves (landed 2026-08-26)

- `CLIV-A1` every verb says what it does

### no-status-for-work-done-elsewhere (landed 2026-08-26)

- `DEL-A1` a landed issue with a pointer passes without its own record
- `DEL-A2` the same issue without the pointer still fails
- `DEL-A3` several entries are all checked
- `DEL-A4` an absorbed issue that was never assessed still lints
- `DEL-B1` a pointer at an issue that does not exist fails
- `DEL-B2` a pointer at an issue that has not landed fails
- `DEL-B3` a pointer at an issue with no record of its own fails
- `DEL-B4` a pointer is only meaningful on a landed issue
- `DEL-B5` a pointer the named issue does not acknowledge fails
- `DEL-C1` a delivered issue stops being recorded as abandoned
- `DEL-C2` retro counts them as delivered
- `DEL-C3` an issue that was decided against stays abandoned
- `DEL-D1` a commit entry resolves and says what it did
- `DEL-D2` a commit that does not resolve fails
- `DEL-D3` a commit with no explanation fails
- `DEL-D4` without git, the commit form declines rather than passes

### docs-slimming-pass (landed 2026-08-26)

- `DOC-A1` every drift guard passes on the slimmed documents
- `DOC-A2` no document claims more than governance does
- `DOC-A3` a guard taught a new shape can still fail
- `DOC-A4` a retired guard says what stopped being covered

### set-status-does-not-name-the-issue (landed 2026-08-26)

- `SSN-A1` set-status names the issue in both outcomes
- `SSN-A2` a landed_by entry still reads its own key

### name-the-issue-record (landed 2026-08-27)

- `NIR-A1` the term is governed like every other
- `NIR-A2` the name needs no gloss
- `NIR-B1` no live surface carries the retired word
- `NIR-B2` the old name survives only where history needs it
- `NIR-C1` the file, the CLI and the module agree
- `NIR-D1` a file written under the old name still loads
- `NIR-D2` the migrator moves the archive
- `NIR-E1` the freeze ceremony is paid

### instruction-volume (landed 2026-08-27)

- `IV-A1` the resident cost is bounded
- `IV-A2` a quick fix reads what a quick fix needs
- `IV-B1` strategies is not in the per-issue read
- `IV-C1` no skill loads whole to answer one question
- `IV-C2` a split skill says where its parts are
- `IV-D1` every frontmatter parses

### session-bootstrap (landed 2026-08-27)

- `SB-A1` a session in a Compass project starts with the contract
- `SB-A2` the contract is short enough to always carry
- `SB-A3` the contract is silent outside a Compass project
- `SB-B1` the contract exists once
- `SB-B2` the two Claude Code documents share no sentence
- `SB-B3` the runtime-neutral document is left alone
- `SB-B4` the contract names every agent that exists
- `SB-C1` plugin-shipped paths resolve from any directory
- `SB-C2` project governance still wins where a project has its own
- `SB-D1` a source install registers the same hook
- `SB-D2` the portability mapping names the new adapter feature
- `SB-D3` a source install enforces what the plugin enforces

### version-guard-cannot-see-a-historical-version (landed 2026-08-27)

- `VGH-A1` an exemption carries its reason
- `VGH-A2` the exemption list cannot grow quietly
- `VGH-A3` the historical reference is exempt and still says 3.3.0

### vocabulary-debt (landed 2026-08-27)

- `VOC-A1` every file the approaches index names exists
- `VOC-B1` no document says a shipped rename is still pending
- `VOC-C1` the deep dive names the gates the policy staples
- `VOC-C2` the deep dive does not claim scoped gates are immovable

### anthropic-aligned-vocabulary (landed 2026-08-28)

- `TRC-A1` A retired concept word is reported by the vocabulary scan
- `TRC-A2` Every retired concept word has a ban entry naming its replacement
- `TRC-A3` The scanned surfaces are free of the retired concept words
- `TRC-A4` An ordinary use of a retired word is not reported
- `TRC-B1` A new manifest records orchestration rather than topology
- `TRC-B2` An existing manifest written with topology still loads
- `TRC-B3` A retired topology word is read as the ceiling it always implied
- `TRC-B4` The parallel-work ceiling is named for the unit it counts
- `TRC-B5` The architecture gate is named for what it checks
- `TRC-B6` A route shape declares a ceiling rather than an orchestration
- `TRC-B7` The project config names multiagent work by its new name
- `TRC-B8` Who integrates is decided by the number of subtasks
- `TRC-B9` A rename is not reported as new mechanism
- `TRC-C1` A renamed command is invocable under its new name
- `TRC-C2` A retired command name still resolves
- `TRC-C3` The three role agents are named after their role
- `TRC-C4` The lens carve-out is removed once the identifiers are gone
- `TRC-C5` The assessment agent is named for what it does
- `TRC-C6` A renamed skill is discoverable under its new name
- `TRC-D1` The glossary defines each term this rename introduces
- `TRC-D2` The glossary is regenerated rather than hand-edited
- `TRC-D3` Retiring a frozen term is recorded as a decision
- `TRC-D4` A decision record keeps the words it was decided in
- `TRC-F1` A replacement that misreads the source meaning is rejected
- `TRC-F2` A key rename that silently drops data fails the build
- `TRC-F3` A ban with no working pattern is caught before it ships
- `TRC-F4` A loose pattern that reports neighbouring text fails the suite

### printed-output-guard-coverage (landed 2026-08-28)

- `TRC-A1` No printed string names a retired verb or value
- `TRC-A2` The walk reaches far more than the two commands it replaces
- `TRC-A3` A planted retired name is reported

### pre-tool-hook-misses-worktree-red (landed 2026-08-28)

- `TRC-A1` A red in the worktree allows an edit in the worktree
- `TRC-A2` A red in the session does not unlock a worktree
- `TRC-A3` A call naming no file still resolves from the session

### what-compass-owes-an-unobserved-adopter (landed 2026-08-28)

- `TRC-A1` The decision names an observable quantity
- `TRC-A2` Publication is refused as evidence of adoption
- `TRC-A3` The revival condition is readable from the record alone
- `TRC-A4` The record says what it adds beyond the release
- `TRC-B1` The supersession is navigable in both directions
- `TRC-B2` Every link in the decisions index resolves
- `TRC-B3` Inv-8 resolves to a record that is not superseded
- `TRC-C1` ADR-006 is not superseded
- `TRC-C2` Inv-8's two promises are stated separately
- `TRC-C3` The archive rule is untouched
- `TRC-D1` The retired slash commands no longer exist
- `TRC-D2` The hidden CLI alias no longer resolves
- `TRC-D3` Read-side migration survives, for the archive's reason
- `TRC-D4` The vocabulary has one value per concept again
- `TRC-D5` A stale exemption fails the build
- `TRC-D6` The release that carries the removal says so
- `TRC-D7` Nothing is left over from the removal
- `TRC-D8` Every list of the governance files names all of them
- `TRC-F1` A record that only restates the existing schedule is refused
- `TRC-F2` A revival condition nobody can observe is refused
- `TRC-F3` Orphaning Inv-8 fails the change

### release-gate-greps-the-old-manifest-filename (landed 2026-08-30)

- `TRC-A1` The examples check names the file that exists
- `TRC-F1` A check that cannot pass is refused

### set-status-reason-writes-an-invalid-manifest (landed 2026-08-30)

- `TRC-A1` A reason on any status leaves the manifest valid
- `TRC-A2` The recorded reason says which transition it belongs to
- `TRC-F1` A key the schema forbids is refused

### reframe-is-documented-but-does-not-exist (landed 2026-08-30)

- `TRC-A1` No shipped document teaches a flag the CLI rejects
- `TRC-A2` Nothing promises the retired spelling still works
- `TRC-F1` A guard that reads no flags is refused

### stale-command-names-in-shipped-prose (landed 2026-08-30)

- `TRC-A1` No shipped document names a slash command that does not exist
- `TRC-B1` The safety contract names one start version
- `TRC-F1` A guard that reads no commands is refused

### allow-marker-supplies-its-own-reason (landed 2026-08-30)

- `TRC-A1` A marker with no reason is refused
- `TRC-A2` A marker with a real reason still exempts
- `TRC-B1` The guards that honour the marker share its definition

### decay-rule-imperative-check-cannot-fail (landed 2026-08-30)

- `TRC-A1` The action check reads the rule body, not its own anchor
- `TRC-A2` The rule still passes when it does state an action

### exemptions-that-exclude-nothing (landed 2026-08-30)

- `TRC-A1` No exemption excludes nothing
- `TRC-A2` The grandfather list is empty
- `TRC-B1` A file that must not be scanned is checked directly

### reassessment-log-drops-reading-only-changes (landed 2026-08-30)

- `TRC-A1` A corrected reading is logged when the approach does not move
- `TRC-A2` The reason is not discarded
- `TRC-B1` A first write records no re-assessment

### docs-compass-artifacts (landed 2026-09-11)

- `TRC-A1` A registered document outside the issue directory resolves
- `TRC-A2` A registered path is anchored to the project, not to the caller
- `TRC-A3` An issue with no registry resolves exactly as it does today
- `TRC-A4` The schema says where a registered path is measured from
- `TRC-B1` A written document lands under a dated issue directory
- `TRC-B2` Machine state stays where the CLI keeps it
- `TRC-B3` Creating the docs directory is reported, never silent
- `TRC-B4` A reading command still does not create anything
- `TRC-C1` A reader finds a relocated document
- `TRC-C2` No reader builds its own path to a document
- `TRC-C3` A missed reader is caught by the test, not by a user
- `TRC-C4` The verification report is found where the registry says
- `TRC-C5` A missed reader turns a guardrail check red, never green
- `TRC-D1` The pre-tool hook accepts a relocated delivery-approach record
- `TRC-D2` The pre-tool hook still blocks when assessment really has not run
- `TRC-D3` The stop hook reads the three documents it warns about
- `TRC-E1` Migration moves the documents and writes the registry
- `TRC-E2` The dry run changes nothing
- `TRC-E3` An unmigrated issue keeps working untouched
- `TRC-E4` The shipped examples show the new layout
- `TRC-F1` A quick fix reads one command and one skill
- `TRC-F2` A quick fix writes only the delivery-approach record
- `TRC-F3` Two skills merge into their neighbours
- `TRC-F4` The framework's own documents are off the adopter's path
- `TRC-F5` The resident cost is measured and pinned
- `TRC-G1` A document registered at a path that does not exist
- `TRC-G2` A half-finished migration is not mistaken for a finished one
- `TRC-G3` The same document in both places
- `TRC-G4` A registered path that climbs out of the project
- `TRC-E5` An older install is not locked out by the move

### bare-pytest-fails-on-two-tests (landed 2026-09-11)

- `BPF-1` A bare pytest run passes on a clean checkout

### queued-issues-read-as-landed (landed 2026-09-11)

- `QRL-1` An issue still in flight has its declared tests checked

### rehearsal-guard-fails-on-a-neighbour (landed 2026-09-11)

- `RGN-1` A recorded rehearsal passes whatever words surround it

### claude-md-plain-english (landed 2026-09-11)

- `PE-1` CLAUDE.md tells a session to write plain English with no idiom or metaphor

### plain-english-full-rules (landed 2026-09-11)

- `PFR-1` CLAUDE.md and AGENTS.md carry the full plain-English rules

### prose-breaks-the-writing-style (landed 2026-09-23)

- `PBW-A1` No retired v1 word survives in prose, a comment or a test docstring
- `PBW-A2` The shorter word stands where the word is not an identifier
- `PBW-A3` The spelling is British
- `PBW-A4` "artifact" is the only spelling
- `PBW-A5` No idiom from the table survives
- `PBW-A6` No citation points at a path git does not distribute
- `PBW-A7` A bare code carries its meaning or goes
- `PBW-A8` Every file and command a comment names exists
- `PBW-A9` No sentence is left broken by an earlier find-and-replace
- `PBW-A10` A stated count matches the thing it counts
- `PBW-B1` A document leads with the point
- `PBW-B2` Each sentence makes one point
- `PBW-B3` A set of items is a vertical list
- `PBW-B4` "must", "can" and "do not" say which is which
- `PBW-B5` The actor is named before the action
- `PBW-B6` A document describes the state now
- `PBW-B7` No document holds a changelog, a version banner or a dated count
- `PBW-B8` No document states a fact its source contradicts
- `PBW-C1` A comment states what the code does
- `PBW-C2` A comment gives its reason before its detail
- `PBW-C3` A CLI module's header describes that module
- `PBW-C4` A copied block is fixed the same way in every file that holds it
- `PBW-C5` A test docstring says what the file tests and cites its issue by slug
- `PBW-D1` Every identifier keeps its spelling
- `PBW-D2` The frozen vocabulary still names the words it bans
- `PBW-D3` The archive quotes are unchanged
- `PBW-D4` The deliberately bad text survives
- `PBW-D5` Every CLI module keeps its DEPENDENCY: line
- `PBW-D6` A test that pinned the old wording changes in the same commit
- `PBW-D7` The help text in scripts/release.sh stays inside its printed range
- `PBW-D8` The excluded files are untouched
- `PBW-D9` The case study and the launch article keep their form
- `PBW-E1` Each sweep reports a planted breach
- `PBW-E2` A result of zero is believed only after the sweep has reported
- `PBW-E3` A sweep is never loosened to clear a report
- `PBW-E4` No changed file alters behaviour
- `PBW-F1` A prose edit that changes behaviour is refused
- `PBW-F2` An out-of-scope defect folded into a batch is refused
- `PBW-F3` An edit that adds an em dash or an attribution line is refused
- `PBW-F4` A rewrite that swaps one idiom for another is refused
- `PBW-F5` An edit made from a stale line number is refused
- `PBW-F6` A batch that cannot show its sweeps ran is refused
- `PBW-F7` A rewritten instruction still instructs the same behaviour
- `PBW-F8` A clarity review that read less than the sampling rule is refused
- `PBW-F9` A batch that does not record its changed files is refused

### release-5-0-0 (landed 2026-09-24)

- `REL-1` every published surface reports 5.0.0
- `REL-2` the removal guard accepts a later major
- `REL-3` the upgrade notes name the removed skills

### contract-facts (landed 2026-09-24)

- `CF-1` The injected contract names docs/compass as the home of an issue's documents

### validate-scan-vs-archive (landed 2026-09-24)

- `VSA-1` validate.sh skips an issue's own documents and still fails a broken reference in a living file

### unbound-green-needs-no-red (landed 2026-09-24)

- `UGR-1` An issue whose only evidence is an unbound green fails suite-passed
- `UGR-2` One red of either binding satisfies the rule
- `UGR-3` An acceptance record stands in for a red
- `UGR-4` An issue with no scenarios is not asked for a red
- `UGR-5` An issue created before the cutoff keeps its result
- `UGR-6` The bound-green refusal names acceptance, not the bypass
- `UGR-7` An unbound green with no red does not claim a red
- `UGR-8` The governance text states the rule

### red-record-identity-cutoff (landed 2026-09-24)

- `RIC-1` An unstamped red written since the cutoff does not unlock
- `RIC-2` An unstamped red written before the cutoff still unlocks
- `RIC-3` A project with no cutoff behaves as today
- `RIC-4` A stamped red is judged by its digest in every project
- `RIC-5` compass init declares the cutoff for a new project
- `RIC-6` suite-passed applies the same identity rule
- `RIC-7` The hook has no identity rule of its own
- `RIC-8` The safety contract states the cutoff

### hook-failure-matrix (landed 2026-09-24)

- `HFM-1` Every reader that cannot run refuses and names itself
- `HFM-2` With no python3 the refusal says so
- `HFM-3` A config that does not parse does not unguard code_globs
- `HFM-4` A missing approach record is still reported as missing
- `HFM-5` The safety contract scopes the worktree redirect gap
- `HFM-6` The hooks use no retired word or tool name

### reach-counts-move-with-every-test (landed 2026-09-25)

- `RCM-1` A new file with prose leaves the reach test green
- `RCM-2` A new file with no prose fails the reach test, naming the rule
- `RCM-3` A widened reach fails the reach test, naming the rule

### validate-help-prints-headings-only (landed 2026-09-25)

- `VHP-1` validate.sh --help prints both exit codes and every check

### created-date-can-be-backdated (landed 2026-09-25)

- `CDB-1` A backdated issue with evidence dated after the cutoff gets the rule
- `CDB-2` An issue created and worked before the cutoff keeps its result

### acceptance-declared-after-the-work (landed 2026-09-25)

- `ADW-1` An acceptance declared after the first green does not satisfy suite-passed
- `ADW-2` An acceptance declared before any green counts
- `ADW-3` An acceptance record with no declared_at counts as today
- `ADW-4` compass acceptance record carries declared_at

### coverage-flag-with-autoload-off (landed 2026-09-25)

- `CFA-1` A command that turns the plugin off gets no coverage flag
- `CFA-2` The variable in the calling environment gets no flag
- `CFA-3` A command where the plugin loads keeps the flag

### pointer-path-traversal (landed 2026-09-25)

- `CTP-1` A pointer holding a path makes the hook refuse
- `CTP-2` The CLI refuses a slug holding a path
- `CTP-3` An ordinary slug behaves as today

### code-globs-as-a-string (landed 2026-09-25)

- `CGS-1` code_globs of the wrong shape refuses and names the config
- `CGS-2` A list of strings behaves as today

### facts-drift-guard (landed 2026-09-25)

- `FDG-1` The deep dive's gate counts match the evaluator
- `FDG-2` The immovable list and never_skip match the policy, and verify.claims is not called immovable
- `FDG-3` The contract's document home matches the CLI's naming rule
- `FDG-4` The derived-spec header names the real command and input
- `FDG-5` Every registered claim is found exactly once

### evidence-binding (landed 2026-09-25)

- `EVB-1` A test record names the tree it ran on
- `EVB-2` A green for a changed tree fails at ship
- `EVB-3` Before ship a stale green is a note, not a failure
- `EVB-4` An edit to an ignored path does not make a green stale
- `EVB-5` A landed issue is checked against the commit that landed it
- `EVB-6` Records without a tree are not judged
- `EVB-7` The safety contract states the boundary

### orchestrator-loop-hardening (landed 2026-09-25)

- `OLH-1` A dispatch records its subtask
- `OLH-2` A subtask's progress is recorded
- `OLH-3` An interrupted run resumes losing nothing
- `OLH-4` A budget overrun is a finding
- `OLH-5` A review package is a file cut from the base commit
- `OLH-6` A coaching reviewer brief is refused
- `OLH-7` The agent and skill prose state each adopted rule
- `OLH-8` A rehearsal interrupted mid-review and mid-integration resumes
- `OLH-9` Each half of the review catches its own seeded defect

### claims-called-immovable-elsewhere (landed 2026-09-25)

- `CCI-1` No shipped Markdown file calls verify.claims immovable

### red-for-a-module-not-yet-written (landed 2026-09-25)

- `RSF-1` A red for a project module not yet written is recorded as an import red
- `RSF-2` An ordinary failing assertion is still a red
- `RSF-3` Any other collection error is refused
- `RSF-4` A run that hides a collection error, or where no test failed, is refused; the skill names the import red

### changes-id-misses-unlisted-files (landed 2026-09-25)

- `CUF-1` A declared test changed after the green fails the landed check
- `CUF-2` The tested files landing pass, whatever HEAD does next
- `CUF-3` A record built before the change is judged as built

### retro-weighs-only-retired-route-names (landed 2026-09-25)

- `RWC-1` Current route names count up and down, and weigh the same as retired ones
- `RWC-2` A route with no weight is unweighed, not sideways
- `RWC-3` Retro prints no retired name for assessment

### red-through-a-shell-wrapper (landed 2026-09-25)

- `DSW-1` py.test is recognised and gets the pytest rule
- `DSW-2` A bash -c pipeline around pytest is judged by pytest's report
- `DSW-3` A runner that writes no report is marked exit-code

### devlog-logs-edits-outside-the-project (landed 2026-09-25)

- `DLO-1` An edit outside the project is not logged
- `DLO-2` An edit inside the project is logged relative to it
- `DLO-3` A relative path is judged by where it resolves; the no-project message names the devlog

### dispatch-protocol (landed 2026-09-25)

- `DPR-1` A multiagent issue must record its run
- `DPR-2` The scripts find an issue's documents through the registry
- `DPR-3` A staged map is provisioned one wave at a time
- `DPR-4` A conflict in Compass's records does not stop integration
- `DPR-5` The protocol document answers every step
- `DPR-6` Run 1 is recorded
- `DPR-7` Only ship-commit marks an issue landed

### changed-file-keeps-one-scenario (landed 2026-09-25)

- `CKS-1` A repeated scenario flag records every value
- `CKS-2` A later add keeps the earlier scenarios

### rerun-check-misses-script-changes (landed 2026-09-25)

- `RSE-1` A green after a script edit is not a re-run
- `RSE-2` A green with nothing changed is still a re-run

### map-cells-reach-git-unchecked (landed 2026-09-25)

- `MCC-1` A subtask id that could leave the worktree root is refused
- `MCC-2` A branch git would not accept is refused

### merge-overwrites-an-ignored-record (landed 2026-09-25)

- `MIR-1` A branch that committed an ignored record is refused
- `MIR-2` A branch with no ignored record merges

### tree-id-misses-a-same-second-edit (landed 2026-09-25)

- `TSE-1` A same-size edit in the same second changes the tree id

### check-does-not-compare-record-with-map (landed 2026-09-25)

- `CRM-1` A mapped subtask the record lacks fails the check
- `CRM-2` subtask next lists a mapped subtask not yet dispatched
- `CRM-3` With no map the check judges the record as before

### multiagent-scripts-still-say-ship (landed 2026-09-25)

- `DSS-1` No script says integration lands or happens at ship
- `DSS-2` multiagent.sh names the order of waves and --no-clean
- `DSS-3` integrate.sh says no regression ran when none did
- `DSS-4` The protocol's landing command runs as written

### tr-range-fails-on-linux (landed 2026-09-25)

- `DTR-1` No tr set in the scripts reads differently on Linux

### skill-prose-pressure-tests (landed 2026-09-27)

- `SPT-1` A run is recorded under either condition
- `SPT-2` Six scenarios cover the failure modes
- `SPT-3` Behaviours are scored from actions and artifacts
- `SPT-4` The releasing guide requires a run
- `SPT-5` The pilot and one measured change are on record

### source-hash-skips-nested-records (landed 2026-09-27)

- `SHN-1` An edit under a nested .compass/ changes the source hash
- `SHN-2` An edit under the project root's .compass/ does not

### red-without-a-test-unlocks-edits (landed 2026-09-27)

- `RWT-1` A silent red naming no test is refused
- `RWT-2` Reds that print or name a declared test still record

### eval-judge-gaps (landed 2026-09-27)

- `EJG-1` EJG-1
- `EJG-2` EJG-2
- `EJG-3` EJG-3
- `EJG-4` EJG-4
- `EJG-5` EJG-5
- `EJG-6` EJG-6
- `EJG-7` EJG-7
- `EJG-8` EJG-8

### subtask-cost-keeps-last-try-only (landed 2026-09-27)

- `SCT-1` Two tries keep both costs and their total
- `SCT-2` A second cost for the same try replaces it

### feature-route-omits-the-map (landed 2026-09-27)

- `FRM-1` A feature assessment earns and registers the map
- `FRM-2` Every multiagent route earns the map

### eval-gaps-after-d30 (landed 2026-09-27)

- `EGA-1` EGA-1
- `EGA-2` EGA-2
- `EGA-3` EGA-3
- `EGA-4` EGA-4
- `EGA-5` EGA-5
- `EGA-6` EGA-6
- `EGA-7` EGA-7

### comparison-suite (landed 2026-09-28)

- `CMP-1` CMP-1
- `CMP-2` CMP-2
- `CMP-3` CMP-3
- `CMP-4` CMP-4
- `CMP-5` CMP-5
- `CMP-6` CMP-6

### eval-gaps-after-d33 (landed 2026-09-28)

- `EGB-1` EGB-1
- `EGB-2` EGB-2
- `EGB-3` EGB-3
- `EGB-4` EGB-4
- `EGB-5` EGB-5
- `EGB-6` EGB-6
- `EGB-7` EGB-7
- `EGB-8` EGB-8

### resident-footprint-diet (landed 2026-09-28)

- `RFD-1` Resident text at or under 900 words
- `RFD-2` Triggering tests pass unchanged

### quick-fix-overhead (landed 2026-09-28)

- `QFO-1` start records the whole assessment in one call
- `QFO-2` start stops when the approach is not a quick fix
- `QFO-3` start refuses an unreasoned or unknown dimension
- `QFO-4` finish traces, checks, passes the three gates and lands
- `QFO-5` finish refuses and passes nothing on any unmet condition
- `QFO-6` the command and skill teach the two verbs
- `QFO-7` a re-run costs at most twice R1
- `QFO-8` the breakdown gives calls and tokens by step

### quick-fix-finish-gaps (landed 2026-09-28)

- `QFG-1` a second finish reuses the covering green and commits
- `QFG-2` finish works from a subdirectory
- `QFG-3` ship-commit refuses a stale green for the issue's files
- `QFG-4` the safety contract states both limits

### quick-fix-tests-need-a-git-identity (landed 2026-09-28)

- `QGI-1` Given HOME points at an empty directory, when the quick-fix verb tests run, then every finish test commits and passes

### finish-commits-unrelated-untracked-files (landed 2026-09-29)

- `FUU-1` Given an untracked file present before `quick-fix start` that nobody t
- `FUU-2` Given a tracked file already modified before `quick-fix start` that no
- `FUU-3` Given a file present before `start` that the agent then traced with `c
- `FUU-4` Given a new source file created after `start` and a new test file the
- `FUU-5` Given an issue with no record of its start state, when `finish` runs w
- `FUU-6` Given any successful `finish`, when it prints its hand-off, then the h

### finish-and-ship-commit-edges (landed 2026-09-29)

- `FSE-1` Given a fix that creates a file whose name has a space, a quote or a n
- `FSE-2` Given a quick fix started with a local file present, when it lands, th
- `FSE-3` Given a successful `finish`, when it prints its hand-off, then the fil
- `FSE-4` the safety contract states the three limits

### ship-commit-judges-the-staged-files (landed 2026-09-29)

- `SJS-1` Given an issue whose gates have passed, when the staged copy of an iss
- `SJS-3` Given a multiagent issue whose files are already committed, when a lat
- `SJS-4` Given a staged name holding `[`, `*` or `?`, or starting with `-`, whe
- `SJS-2` Given a green recorded with one argument list, when `finish` runs with
- `SJS-5` Given a quick fix whose files the agent committed before `finish`, whe
- `SJS-6` Given a landed quick fix, when it lands, then its start record is gone

### ship-commit-follow-ups (landed 2026-09-29)

- `SCF-1` Given a git pre-commit hook that stages an untested copy of an issue f
- `SCF-2` Given pre-commit set up, a tested copy staged and an untested edit on
- `SCF-3` Given a hook that rewrites an issue file with untested content and fai
- `SCF-5` Given names starting with `-` or holding `*` or `?`, when `ship-commit
- `SCF-6` Given `docs/safety-contract.md`, then it states that a traced symlink
- `SCF-4` a green without argv is reused on its joined command

### green-digest-and-hook-scope (landed 2026-09-29)

- `GDH-1` Given a green record edited after it was written, its stored digest le
- `GDH-2` Given a git pre-commit hook that stages a file outside the issue's sco
- `GDH-3` Given a tracked file that matches `.gitignore`, traced by an issue and
- `GDH-4` Given the safety contract and the post-commit refusal, then the contra

### land-refusal-advice (landed 2026-09-29)

- `LRA-1` Given a refusal from ship-commit or finish, when its advice is followed, then the refusal clears

### refusal-template (landed 2026-09-29)

- `RTP-1` Given the refusal registry, when each reason code is rendered with fix
- `RTP-2` Given every rendered `Fix:` line, then none suggests dropping `--scena
- `RTP-3` Given each cell of the hook failure matrix, when the hook refuses, the
- `RTP-4` Given the registry, then `docs/refusal-codes.md` lists every code with
- `RTP-5` no printed string names a retired word
- `RTP-6` the measured eval run is compared with the baseline

### judge-sees-quick-fix-start (landed 2026-09-29)

- `JSQ-1` Given a session that ran compass quick-fix start before its first code edit, when the rule judge scores it, then it passes

### refusal-template-follow-ups (landed 2026-09-29)

- `RTF-1` Given a python3 that fails and prints something, when the hook refuses
- `RTF-2` Given the registry's Fix lines, then `python-missing` says 3.10+, each
- `RTF-3` Given a template parameter longer than 20 words at run time, when a re
- `RTF-4` Given the guards, then the call-site test finds a code only as an argu
- `RTF-6` Given the texts, then `docs/refusal-codes.md` does not claim the CLI r
- `RTF-5` no script prints triage, and the scan covers scripts

### printed-wording-sweep (landed 2026-09-30)

- `TRC-001` Given the CLI, hooks and scripts, when their string literals are scanned, then none uses an idiom from the writing-style table or "accretion", the scan fails on a planted breach, the no-reason re-assessment warning names `reassessments`, and the README and five-minutes guide name Python 3.10 or later

### comparison-scenarios-that-discriminate (landed 2026-09-30)

- `CSD-1` Each new scenario has every field, its seed's tests pass, and its hidden tests fail on the seed
- `CSD-2` A correct change passes each new scenario's hidden tests
- `CSD-3` A careless change passes the seed's tests and fails the hidden tests
- `CSD-4` Each prompt reads as a real request, and two do not state the rule their hidden tests check
- `CSD-5` A published report gives each condition's hidden-test result per new scenario and says whether they differed

### reframe-to-reassessment (landed 2026-09-30)

- `RRA-1` reframe is a banned term, bound to a pattern that flags a planted use
- `RRA-2` No scanned surface uses reframe except a marked compatibility line
- `RRA-3` retro, flow, approach evaluate and the stop hook say re-assessment

### retro-counts-policy-corrections (landed 2026-09-30)

- `TRC-001` Given one judgement re-assessment and one policy correction, each moving standard to expedition, when compass retro runs, then it reports 1 up and 0 down

### compare-names-the-compass-commit (landed 2026-09-30)

- `TRC-001` Given a compass run record with compass_commit and no framework block, when the comparison report is built, then it shows that commit

### small-change-read-as-unmapped (landed 2026-09-30)

- `SCU-1` A small, contained greenfield change is a quick fix; unmapped still gets the heavier process
- `SCU-2` A heavier quick-fix start names the dimension that blocked it
- `SCU-3` Re-run of the edge-case and refactor comparison runs under Compass: no session ends without code

### quick-fix-start-drops-labels (landed 2026-10-01)

- `QFL-1` Given `quick-fix start --labels auth` on a small, contained change, then the manifest records `labels: [auth]` and the approach is not a quick fix.
- `QFL-2` Given that change, then `compass check` treats the human sign-off guardrail as applicable.
- `QFL-3` Given no `--labels`, then the labels are empty and the result is unchanged; a malformed label is refused before anything is written.

### quick-fix-message-edges (landed 2026-10-01)

- `TRC-001` Given a 45-character slug and a cross-cutting change, when quick-fix start computes a heavier process, then no line passes 100 characters, nothing is cut, and each rule's id and kind share a line

### claude-review-workflow (landed 2026-10-01)

- `TRC-001` Given the review workflow, when it is read, then every action is pinned to a commit, contents are read-only, and no allowed tool can commit or push

### eval-gaps-after-d34 (landed 2026-10-01)

- `TRC-001` Given a hidden test run that skipped a test and exited 1, when the harness corrects its counts, then it leaves them alone, and corrects only a collection error that exited 2
- `TRC-002` A comparison corrects a record against the hidden-test count its own run recorded

### system-spec-split (landed 2026-10-01)

- `TRC-001` Given the landed issues, when the spec is derived, then docs/system-spec.md holds only current behaviour under 4,000 words with a pointer, and docs/system-spec-archive.md holds every archived section unchanged

### claude-review-federation (landed 2026-10-01)

- `TRC-001` Given the review workflow, when it is read, then it authenticates with the federation rule, organisation and service account variables, and no step uses an API key or OAuth token

### one-entry-point (landed 2026-10-01)

- `ONE-1` Given `commands/go.md`, then it runs `compass init`, assesses with `compass quick-fix start`, shows `compass approach summary`, and continues into the
- `ONE-2` Given an assessed issue, when `compass approach summary` runs, then it prints exactly three lines: the approach, its gates, and where the issue's file
- `ONE-3` Given a pre-tool hook block on an assessed issue, then one line for that issue and `hook_blocks` is appended to `.compass/interruptions.log`, and the
- `ONE-4` Given a failing `compass check`, then one `check_failures` line is appended to the log and the issue folder is untouched; a `compass ci` sweep does no
- `ONE-5` Given issues with interruptions, then `compass retro` reports their totals.
- `ONE-6` Given a fresh repository, when a session types `/compass:go` with a small change, then it lands a quick fix; measured in an eval run (spend asked for

### claude-review-workspace (landed 2026-10-01)

- `TRC-001` Given the review workflow, when it is read, then it passes anthropic_workspace_id from the ANTHROPIC_WORKSPACE_ID repository variable

### status-line (landed 2026-10-01)

- `SL-A` Given no Compass project, or garbage on stdin, then `bin/compass-statusline` prints nothing, writes nothing to stderr and exits 0.
- `SL-B` Given an issue with a red on record for its scenario, then the line shows `compass`, the slug, the approach, the stage, the gates cleared out of those
- `SL-C` Given an unparseable manifest, then the line is empty, stderr is empty and the exit code is 0.
- `SL-D` Given any issue, then the stage on the line is the one `compass next` reports, and the line shows no stage when `compass next` reports none.
- `SL-E` Given a narrow terminal (COLUMNS), then fields drop right to left and the slug is cut last.
- `SL-F` Given `bin/compass-statusline`, then it does not load the full CLI, and a run takes under 0.25 s (median of 7).

### review-verdict (landed 2026-10-01)

- `TRC-001` Given the review workflow, when it is read, then the review returns its verdict as structured output and a later step fails the job unless the verdict is PASS

### progress-rail (landed 2026-10-02)

- `RL-A` Given stdout is a terminal and neither CLAUDECODE nor NO_COLOR is set, when compass next runs on an issue in progress, then the line after the header is a rail of the route's stages with exactly one current marker.
- `RL-B` Given stdout is a pipe, when compass next runs, then its output matches the golden file captured before the rail, byte for byte, for every route in the fixtures.
- `RL-C` Given a route that skips or collapses a stage, when the rail is shown, then that stage is shown with the skipped marker, not left out.
- `RL-D` Given CLAUDECODE is set, when compass next runs with stdout a terminal, then its output is today's output, byte for byte.
- `RL-E` Given NO_COLOR, then the rail has no colour codes; given COMPASS_COLOR=never, then it uses ASCII markers; given COMPASS_COLOR=always, then the rail shows when piped, unless CLAUDECODE is set.
- `RL-F` Given a terminal narrower than the rail, then the rail wraps between stages and no line is wider than the terminal.
- `RL-G` Given an issue in progress, then the rail is followed by a Next line naming the command for the current stage.
- `RL-H` Given the status line, then it fits its line with the shared renderer, so width fitting lives in one module.

### next-never-leaves-assess (landed 2026-10-02)

- `NS-A` Given an issue with its approach record and no other record, when compass next runs, then it reports Define.
- `NS-B` Given the acceptance criteria registered as draft, and no later record, then it reports Refine on a route that runs refine. Given the requirements review registered as well, then it reports Plan on a route that runs plan. Given scenarios and no later record on a route that collapses refine and plan and skips breakdown, then it reports Implement.
- `NS-C` Given the technical design registered, and no subtask, distribution map or test record, then it reports Breakdown on a route that runs breakdown. Given a subtask or the distribution map recorded, then it reports Implement.
- `NS-D` Given a red on record and no green, or test evidence for some scenarios but not all, then it reports Implement.
- `NS-E` Given test evidence for every scenario that needs one and a gate not passed, then it reports Verify, even when no design or breakdown record exists.
- `NS-F` Given every gate passed and the issue not landed, then it reports Ship. Given status: landed, then it reports all phases complete.
- `NS-G` Given a current_phase key in the manifest, then it reports that stage, whatever the records show.
- `NS-H` Given any issue in NS-A to NS-F, then the status line's stage and the rail's current marker name the same stage as compass next.
- `NS-I` Given a manifest whose artifacts, evidence, scenarios or subtasks is not a list, or whose ids are not strings, then compass next still prints a stage and exits 0, and the status line still prints its line.

### next-crashes-on-mistyped-manifest (landed 2026-10-02)

- `TRC-001` Given a manifest whose gates is not a list, whose stages is not a mapping, or whose stage weight is not a string, When compass next runs, Then it prints a stage and exits 0 with nothing on stderr, and the status line prints its line

### status-line-gate-count-and-width (landed 2026-10-02)

- `TRC-001` Given a manifest with one cleared gate and one malformed gate entry, When the status line runs, Then it shows gates 1/2

### release-5-1-0 (landed 2026-10-02)

- `TRC-001` Given the release intends 5.1.0, When the version tests run, Then every version location reads 5.1.0

### refine-never-clears-on-a-feature (landed 2026-10-02)

- `TRC-001` Given a feature issue with its acceptance criteria registered and no technical design, When compass next runs, Then it reports Plan; and given an initiative issue with its criteria registered and no requirements review, Then it reports Refine

### faster-suite-and-release (landed 2026-10-02)

- `FS-A` Given pytest-xdist is installed, when make test runs, then the suite runs on parallel workers. Given it is not installed, then make test runs the suite in series, as before.
- `FS-B` Given the local issue archive, when the suite is collected, then the two archive sweeps in test_phase2_invariants.py and test_record_keeping_integrity.py are one test per issue, each named after its issue. Given no archive, then they skip as before.
- `FS-C` Given compass ci --since <ref>, then it lints every manifest, fully checks every issue in flight and every issue landed after <ref>, and reports the rest as lint-only. Given no --since, then compass ci checks exactly what it checked before.
- `FS-D` Given make ci in this repository, then it runs compass ci --since the latest release tag. Given COMPASS_FULL_ARCHIVE=1, then make ci checks every issue.
- `FS-E` Given pytest-xdist is installed, when scripts/release.sh runs its test step, then it runs the suite on parallel workers. Given it is not installed, then it runs in series, as before.
- `FS-F` Given the CI self-check job, then it installs pytest-xdist and runs the suite on parallel workers.
- `FS-G` Given docs/releasing.md, then it says how to install pytest-xdist, and names COMPASS_FULL_ARCHIVE=1 as the full-archive check to run before a release.

### release-5-2-0 (landed 2026-10-02)

- `TRC-001` Given the release intends 5.2.0, When the version tests run, Then every version location reads 5.2.0

### ship-restales-a-traced-living-spec (landed 2026-10-02)

- `TRC-001` Given a quick fix whose working tree also changes docs/system-spec.md and docs/system-spec-archive.md, When quick-fix finish runs, Then it traces neither file and the issue's changed files are only its own

### owning-doc-router (landed 2026-10-02)

- `TRC-001` Given a doc under docs/ that the docs/README.md index does not list, or a path in its owning-docs table that does not exist, When the suite runs, Then a test fails naming it

### parallel-ci-flakes (landed 2026-10-02)

- `TRC-001` Given the suite runs on parallel workers, When make test or CI runs it, Then tests marked serial, including the two timing tests, run in a second pass on their own

### decisions-ledger (landed 2026-10-02)

- `DL-A` Given compass decision record <slug>, then it writes a new entry from the template, dated today, with Decided by taken from git config compass.decidedBy, else git config user.name. It refuses an existing slug, and refuses when git has neither name set. There is no option to set Decided by.
- `DL-B` Given compass decision list, then it prints each entry's date, slug and the first line of its decision, newest first. Given compass decision show <slug>, then it prints that entry.
- `DL-C` Given compass decision check --base <ref>, then it fails, naming the entry, when an entry that exists at the ref is changed or removed. A new entry passes. A ref git cannot resolve fails loudly.
- `DL-D` Given compass ci --since <ref> in a project with governance/decisions/, then it runs the history check against that ref. Without --since, it says the history check was skipped and why.
- `DL-E` Given the reviewer agent and the governance-check skill, then each says to read governance/decisions/ before recommending a rename, a wording change or a reversal, and to report a collision as "settled by <path>".
- `DL-F` Given the verb surface, then decision is in the CLI's baseline and in the README's CLI surface block.
- `DL-G` Given governance/decisions/, then it holds at least ten entries, each a decision the maintainer made on record and confirmed in their own words.

### review-rules-as-data (landed 2026-10-02)

- `RV-A` Given compass policy review-rules --changed-files hooks/pre-tool.sh, then it prints each rule whose patterns match that file, including the hook rules, and no rule scoped only to templates or the adopter's reading path.
- `RV-B` Given --rules PATH, then it reads that file instead of the project's, so CI can pass the base branch's copy. Given a project with no rules file, then it says so and exits 0. It reads the project's own governance/, never the shipped copy.
- `RV-C` Given compass policy lint and a rules file with a malformed or repeated id, an unknown enforces id, no patterns, a rule over 150 words or no incident, then it fails and names the rule and the field.
- `RV-D` Given agents/reviewer.md, then it says to run compass policy review-rules --changed-files, to report a finding under the RR- id it breaks, and not to flag what a rule's allowed list permits.
- `RV-E` Given governance/review-rules.yml, then it holds at least ten rules, each with an incident naming a pull request, issue or commit a reader can open.
- `RV-F` Given the verb surface, then policy review-rules is in verb_help.py, the README's CLI block and compass policy --help. The top-level verb set does not change.

### ci-review-reads-review-rules (landed 2026-10-02)

- `RB-A` Given a pull request, then the CI review's prompt holds the review rules that match its changed files, taken with the CLI from the base branch

### rules-step-file-cap (landed 2026-10-02)

- `RC-A` Given a pull request with more changed files than the files API lists, then the review's rules step fails rather than reviewing with a partial rule set

### rules-step-count-message (landed 2026-10-02)

- `RD-A` Given the rules step's file count does not match, then its message names the cause it can tell apart: a missing count, the 3,000-file limit, or a count from before a newer push

### python-dependency-said-early (landed 2026-10-02)

- `PY-A` Given an opted-in project and no python3 on the PATH, when a session starts, then the hook prints valid JSON with a systemMessage for the person and additionalContext for the model, each saying Compass needs Python 3.10 or later, that edits will be refused until it is installed, and how to fix it.
- `PY-B` Given an opted-in project and a python3 older than 3.10, when a session starts, then the hook says the same and names the version it found.
- `PY-C` Given a repository that never opted in, when a session starts without python3, then the hook prints nothing and exits 0, as now.
- `PY-D` Given scripts/install.sh on a machine without python3 3.10+, then it says so before it finishes, names what will not work, and still installs. With it, it names the version found.
- `PY-E` Given docs/safety-contract.md, then it has a table of what each hook and the CLI do without python3 3.10+, and the table's pre-tool row matches the hook's python-missing refusal.
- `PY-F` Given ADR-028, then it records the single-file CLI decision with the measured size and startup cost.

### adr-new-row-in-the-table (landed 2026-10-02)

- `AN-A` Given an ADR index with sections after its table, then compass adr new puts the new row, as a link, right after the last ADR row

### adapter-contract-gate (landed 2026-10-02)

- `AC-A` Given schemas/adapter-contract.yml, then every capability in docs/portability.md has a row, every adapter has a full, partial or none cell with a path, an adapter directory without a column fails, and a new negative-identity check in cli/ or hooks/ fails the scan

### session-diagnosis (landed 2026-10-02)

- `SD-A` Given a landed issue, when compass issue diagnose runs, then it lists each stage the route ran, with the record that shows it ran and its path, and each gate with its status and evidence.
- `SD-B` Given an issue's records, then the report gives a timeline of every dated record: reds, greens, subtask dispatches, review rounds, reassessments, hook refusals and failed checks from .compass/interruptions.log, and the landing, oldest first, each with its path.
- `SD-C` Given a stage the route ran that has no record, a red dated after its scenario's green, a green in an issue with no red at all, a review round that failed, or a landed issue's gate not passed, then the report lists each as a deviation, naming the scenario, stage or gate. A solo breakdown, a spike's missing red and an unfinished issue's later stages are not deviations.
- `SD-D` Given any issue, then the report ends with the questions its records cannot answer, including edits the hook refused, time between records, and what was said in the session.
- `SD-E` Given the verb surface, then issue diagnose is in verb_help.py, the README's CLI block and compass issue --help. The top-level verb set does not change.

### diagnose-output-edges (landed 2026-10-02)

- `DE-A` Given a landed_by mapping, an unbound green, an early omission or an issue landed through another, then compass issue diagnose prints the value, (unbound), no false deviation, and that the records are in the other issue

### project-lessons (landed 2026-10-02)

- `PL-A` Given compass lesson add "<rule>", then it writes a lesson to the lessons file with added_by from git config compass.decidedBy, else user.name; there is no option to set it. An exact repeat is refused; a rule that contains an existing one replaces it and records superseded.
- `PL-B` Given a rule that names a guardrail id from governance/guardrails.yml, a model id or a tool version, or --source verify, then add and propose refuse it with the reason; a near-miss sentence is accepted.
- `PL-C` Given compass lesson propose "<rule>", then it writes to the pending lessons file only, and compass lesson accept <id> moves it to lessons.yml.
- `PL-D` Given compass lesson list and compass lesson remove <id>, then list prints each lesson and each pending proposal, marking on_topic lessons "stored, not yet surfaced", and remove deletes one lesson.
- `PL-E` Given five always lessons and one on_topic lesson, when a session starts, then the injected context holds the five after the operating contract under [Project lessons], with a line saying they cannot override a guardrail, and not the on_topic one.
- `PL-F` Given always lessons over 150 words, then the injected block holds at most 150 words, oldest first, cut between lessons, and a frame line names how many were shown and how many omitted.
- `PL-G` Given the same friction observation in three distinct issues, then compass retro --lessons writes one pending proposal with source: friction, and does not write lessons.yml.
- `PL-H` Given a lesson that says a gate passes, then compass check gives the same result as without it.
- `PL-I` Given the verb surface, then lesson is in the CLI baseline, the README's CLI block, verb_help.py and each frozen verb list, and ADR-029 records the decision. The 900-word resident test passes unchanged.

### lesson-proposal-decline (landed 2026-10-02)

- `LD-A` Given a pending lesson proposal, then compass lesson decline removes it and records its text, so compass retro --lessons does not propose it again

### failure-modes-in-define (landed 2026-10-02)

- `FM-A` Given commands/define.md and skills/bdd-specification/SKILL.md, then each asks the author which input classes and failure modes the brief implies that no scenario covers, says each answer becomes a scenario or a recorded de-scope, and gives two worked examples.
- `FM-B` Given compass scenario descope "<mode>" --reason "<why>", then it appends the mode, the reason and the date to the manifest's failure_modes_descoped, and the manifest still passes compass issue lint. It refuses an empty mode or reason, and a mode already recorded.
- `FM-C` Given an issue with de-scoped failure modes, then agents/verifier.md tells the verifier to list each in the verification report, and templates/verification-report.md has a section for them.
- `FM-D` Given the verb surface, then scenario descope is in verb_help.py, the README's CLI block and compass scenario --help. The top-level verb set does not change.

### titles-checked-before-ship (landed 2026-10-02)

- `TC-A` Given a scenario title naming a missing file path or an eval scenario or behaviour id, then compass scenario add and quick-fix start refuse it before it can reach the living spec

### queue-ageing-signal (landed 2026-10-02)

- `QA-A` Given queued issues, then compass flow --digest lists each with its age and flags those older than the threshold that carry a recommendation heading or a label a routing rule names, and the release guide asks which queued issues touch the release

### spec-derive-keeps-missing-issues (landed 2026-10-02)

- `SK-A` Given a committed living spec that names an issue missing from the local archive, then deriving it refuses and names the issue instead of dropping its scenarios

### status-line-launcher (landed 2026-10-02)

- `SL-A` Given a session start with CLAUDE_PLUGIN_DATA set, then a launcher named compass-statusline exists there and runs the current plugin root's status line script, passing stdin through.
- `SL-B` Given a second session start from a different plugin root, then the launcher is rewritten to the new root; from the same root, the file is left unchanged, with the same modification time.
- `SL-C` Given CLAUDE_PLUGIN_DATA unset or not writable, then session start exits as before and its output is byte-identical; with it set, the output to the model is unchanged too.
- `SL-D` Given the launcher's target is missing, then the launcher prints nothing and exits 0.
- `SL-E` Given the setup helper and a settings file with no statusLine, then it shows the diff and writes nothing without --apply, and writes the entry with it.
- `SL-F` Given a settings file whose statusLine does not name Compass, then the file is left byte-identical, with or without --apply, and the helper says how to combine the two.
- `SL-G` Given a settings file whose statusLine names a versioned Compass path, then the helper offers the launcher path as the replacement and writes it only with --apply.
- `SL-H` Given the init command and the quickstart, then init has a status line step that runs even when its first step stops for existing governance, and asks before applying; the quickstart gives the launcher path and no longer says to edit the path after each upgrade.

### clickable-paths (landed 2026-10-03)

- `CP-A` Given a project, when tdd-red, tdd-green, flow --digest, adr new, issue lint and ci run, then none of them prints the project's absolute path; each path is relative to the project root.
- `CP-B` Given a scenario defined on a line of the acceptance criteria, when tdd-red or tdd-green runs for it, then the output names that file as path:line.
- `CP-D` Given the verbs CP-A runs, with their output piped, then it carries no escape code of any kind.

### errors-print-relative-paths (landed 2026-10-03)

- `EP-A` Given an error naming a project file, or compass approach evaluate's Read line, then the path is printed relative to the project root

### issue-overview (landed 2026-10-03)

- `IO-A` Given an issue's scenarios and its red and green records, then the page has one table row per scenario with its title, a red mark, a green mark and its evidence path, using ✓ and ○.
- `IO-B` Given the same issue, then the page has a Mermaid flowchart from each intent to its scenarios, tests and evidence, and a scenario with a red but no green is styled as open.
- `IO-C` Given more than 25 scenarios, then the flowchart shows a summary node instead of every scenario, and the table still lists them all.
- `IO-D` Given a green recorded after the page was written, then compass check fails the page as stale and names compass issue dashboard as the fix.
- `IO-E` Given the status line, then it names the gates passed out of the gates required.

### release-5-3-0 (landed 2026-10-03)

- `RL-A` Given Compass 5.3.0, then every location that carries the version says 5.3.0

### loop-ceilings (landed 2026-10-03)

- `LC-A` Given the shipped routing policy, then an issue's ceilings resolve from loop_ceilings rules with RP- ids, the lowest matching limit wins, and a policy without the rules gives no ceiling and a drift report naming the missing ids.
- `LC-B` Given a subtask whose builder reported the same error three times, when another attempt is asked for, then the update refuses it and names the repeated error, and subtask next lists the subtask as refused.
- `LC-C` Given a subtask at its attempt ceiling, when another attempt is asked for, then the update refuses it and names the ceiling and its rule id.
- `LC-D` Given a multiagent issue whose subtask has more review rounds than its ceiling, then compass check fails it until a stop reason is recorded with an evidence file, and a subtask stopped that way passes without being done.
- `LC-E` Given an issue created before the ceilings existed, then compass check judges it as before, whatever its counts.
- `LC-F` Given a run at its replan ceiling, when another replan is recorded, then subtask replan refuses it and names the ceiling.

### headless-runner (landed 2026-10-03)

- `HR-A` Given a project, then compass run exits 2 and starts no session when the project has no .compass, the issue does not exist, the stage is not build or verify, no stop file is given, claude cannot be found, or a ceiling flag is out of range or above its policy ceiling.
- `HR-B` Given sessions that change the records but never finish the stage, when the run reaches its cycle ceiling, then it exits 4, records a stopped run with a stop reason naming the ceiling and the run record, and the issue is not landed.
- `HR-C` Given a stop file, present at the start or appearing during the run, then the runner starts no further session and exits 4 with the stop file as the reason.
- `HR-D` Given a run whose stage is done, every gate passing for verify or every scenario green for build, then it exits 0 with the outcome done, and a session that lands the issue stops the run.
- `HR-E` Given a session whose error output carries a credential, then the run record, the manifest and the printed output hold the text with the credential redacted.
- `HR-F` Given any run, then each cycle starts a new claude -p session that resumes nothing, loads the Compass plugin, names the stage's command, says it is unattended, and forbids landing, pushing and merging.
- `HR-G` Given sessions that change nothing on disk, then the run stops after the repeated-error ceiling's number of cycles without progress, and a manifest it cannot read stops it too.
- `HR-H` Given a run that passes its minute ceiling during a session, then the session is ended and the run stops with the minute ceiling as the reason.
- `HR-I` Given the eval harness, then it starts claude through the same launcher function compass run uses.
- `HR-J` Given the change, then a decision record states the exception to the rule that Compass launches nothing, as proposed; a reference workflow runs only when started by hand; and the owning doc says the live CI acceptance is not met.

### run-record-edges (landed 2026-10-03)

- `RRE-1` Given an interrupted run, a run whose last session finishes the stage but breaks the runs key, or a manifest with an empty runs key, then the run record's outcome and reason match the exit code, and a run starts on the empty key.

### accept-adr-030 (landed 2026-10-03)

- `AA-1` Given the maintainer accepted ADR-030 on 2026-10-03, then its status, its index row and the owning doc say accepted, and the test pins accepted.

### archive-sample (landed 2026-10-03)

- `AS-A` Given the local archive, then the sample builder copies a fixed list of landed and abandoned issues with their layout, replaces local and private paths, recomputes the digest of each record it changed, and gives the same files when run twice.
- `AS-B` Given the sample, then compass check passes for every issue in it, run from the sample's root.
- `AS-C` Given the sample, then a test fails if any file in it holds a local absolute path, a private planning path, an email address or a credential shape.
- `AS-D` Given a clean checkout with no local archive, then the tests that read the archive's shape read the sample and run, and with the full-archive switch set they read the real archive.
- `AS-E` Given a clean checkout, then the living-spec currency and archive citation tests skip naming the full-archive switch, run when it is set, and the release guide says to set it.
- `AS-F` Given the sample, then the self-architecture tests read the issue's real name, and the readable-specs test reads older acceptance criteria without a Summary, so neither returns early on a stale name.

### run-session-issue (landed 2026-10-03)

- `SI-A` Given an environment variable that names one issue and a pointer that names another, then the pre-tool hook judges an edit by the issue the variable names.
- `SI-B` Given the variable, then a CLI command run without an explicit issue works on that issue, and an explicit issue still wins.
- `SI-C` Given the variable names no issue or a path, then the hook and the CLI refuse it as they refuse a bad pointer, without falling back to the pointer.
- `SI-D` Given compass run, then every session it starts has the variable set to the run's issue, and the pointer file is unchanged by the run.
- `SI-E` Given the variable, then the post-tool and stop hooks, the receipt and the status line read the same issue the pre-tool hook does.

### run-cost-ceiling (landed 2026-10-03)

- `RC-1` Given a run whose sessions report their cost, then each session gets the money left as its budget, and the run stops with exit 4 once the total reaches the cost ceiling the policy sets.

### run-session-tools (landed 2026-10-03)

- `ST-1` Given compass run, then each session is allowed the file tools, Skill and the compass CLI, is denied landing, pushing, merging and starting another run, and the run record keeps each session's last message.

### run-demo-in-ci (landed 2026-10-03)

- `RD-1` Given the demo quick fix, then a manually started workflow runs compass run on it in CI, authenticated by federation with no stored key, and keeps the run record.

### delivery-record (landed 2026-10-03)

- `DR-A` Given a configured record, then record sync adds and updates its paths in the record repository, redacting credentials, commits naming the project's HEAD and pushes; it deletes only with prune, refuses a full sync from a linked worktree and any path outside the project or into git's folder.
- `DR-B` Given no record in the config, then record sync says none is configured and exits 0, and ship is unchanged.
- `DR-C` Given a configured record, then ship-commit syncs it after a landing, and a failed sync makes ship exit non-zero naming the fix.
- `DR-D` Given a fresh clone and the record repository, then record restore copies the record's paths back, refuses to overwrite a differing file without force, and reports what it restored.
- `DR-E` Given the change, then a decision record states the choice of a second private repository, and the restore drill has been run once from a fresh clone.

### record-sync-gaps (landed 2026-10-03)

- `RG-1` Given a record holding a .gitignore or a submodule entry, then sync still records every file or refuses the submodule, a restore that copies nothing says why, and the clone runs with LFS filters off.

### pointer-lease (landed 2026-10-03)

- `CL-A` Given a session that edited under one issue, when another session moves the pointer, then that session's next code edit is refused naming both issues and the command to confirm.
- `CL-B` Given that refusal, then compass issue use run in the session sets the pointer and lets its edits through on the issue it names.
- `CL-C` Given the session that moved the pointer, then its own edits are not refused, because issue use and quick-fix start record the new issue for the calling session.
- `CL-D` Given the session-issue variable, no session id, or a session record older than 12 hours, then the hook refuses nothing for a moved pointer.

### session-table-tidy (landed 2026-10-03)

- `ST2-1` Given the session table, then concurrent writes keep every record, stale records are dropped when it is written, the table is ignored by git in any project, and a pointer-moved refusal is counted against the session's own issue.

### grep-q-under-pipefail (landed 2026-10-03)

- `GQ-1` Given a script that sets pipefail, then it never pipes into grep -q, because a grep that exits at its first match can fail the pipe and turn a found line into a missing one.

### finish-traces-compass-files (landed 2026-10-03)

- `FT-1` Given a quick fix that changes a tracked file under .compass, such as the project config, then finish traces and commits it with one run, while untracked issue state under .compass stays out.

### go-confirms-on-the-heavier-route (landed 2026-10-03)

- `GC-1` Given a heavier route started by /compass:go, then go and assess agree that the approach summary already shown is the confirmation, and go does not stop at assess step 7 to wait for one.

### unmapped-small-change-advisory (landed 2026-10-03)

- `UA-1` Given an atomic or small change with trivial or contained risk on unmapped ground, when it is assessed, then it gets the mapped route, the unmapped floor does not fire, and behaviour-mapping is advice.
- `UA-2` Given quick-fix start on a small, contained, unmapped change, then the quick fix starts and its approach record names behaviour-mapping as advice.

### retro-transitions-split-by-old-names (landed 2026-10-03)

- `RT-1` Given re-assessments recorded under retired and current route names, when compass retro runs, then each transition appears once under its current names with the counts summed.

### autonomy-setting (landed 2026-10-03)

- `AU-1` Given no autonomy setting, when an assessment is evaluated, then the manifest's checkpoints follow the balanced column of the policy's checkpoint table.
- `AU-2` Given one assessment under each of the three autonomy values, when it is evaluated, then only the checkpoints differ; the route, stages, gates and rules fired stay the same.
- `AU-3` Given an autonomy value that is not one of the three, when an assessment is evaluated, then it is refused with the setting and the allowed values named.
- `AU-4` Given an issue, when approach summary runs, then it still prints three lines and the first names the checkpoints that wait or says none do.
- `AU-5` Given the assess, define, refine and plan commands, then each hand-off waits only when its stage is a listed checkpoint, and otherwise shows the hand-off and logs the skip.
- `AU-6` Given a checkpoint table that names something other than the four checkpoint stages, when the policy is linted, then it is refused.

### checkpoint-table-gaps (landed 2026-10-03)

- `CT-1` Given a checkpoint table that leaves out a value or a route, then that case waits at every hand-off the route runs, and a misspelt or repeated route key is refused.

### stops-and-cost-per-condition (landed 2026-10-03)

- `SC-1` Given eval session records, when the comparison report is built, then each cell and the summary show the hook blocks and check failures each condition met, and a record without them shows not recorded.

### headless-doc-after-the-demo (landed 2026-10-03)

- `HD-1` Given the CI demo workflow exists and has run, then the headless-runner doc does not say the live acceptance is unmet, and says what the demo covers and that each run costs money.

### release-5-4-0 (landed 2026-10-03)

- `RL-A` Given the expected version is 5.4.0, then every published location carries 5.4.0.

### ci-review-manual-only (landed 2026-10-03)

- `CR-1` Given the Claude review workflow, then it starts only by hand and never on a pull request event.

### review-fix-rebinds-land-commit (landed 2026-10-03)

- `RB-1` Given a landed issue whose files a review fix changes, when its green is re-recorded and ship-commit runs for it with nothing staged, then land_commit names the fix commit and compass check passes; without the new green it is refused.

### premium-scenario-classes (landed 2026-10-03)

- `PS-1` Given each of the four new scenarios, then it has a seed, a hidden test, a real-request prompt, the standard reply, and a reference that passes both test sets.
- `PS-2` Given each of the four new scenarios, when its careless change is applied, then the seed's own tests pass and the hidden tests fail.
- `PS-3` Given the two scenarios that start from earlier work, then each condition finds it in its usual place and every record states the rule the hidden test checks.
- `PS-4` Given the eval readme, then it states the decision rule for the run that uses these scenarios before any run.

### red-for-an-unknown-scenario (landed 2026-10-03)

- `US-1` Given an issue whose manifest has no scenario X, when tdd-red or tdd-green runs with scenario X, then it is refused, writes no record, and names compass scenario add.

### eval-record-quotes-a-template (landed 2026-10-03)

- `QT-1` Given the eval scenario records for other frameworks, then none holds a sentence copied from that framework's own templates, and their file layout and heading form are unchanged.

### well-architected-strategy (landed 2026-10-03)

- `WA-1` Given the well-architected register and strategy, then the register lists the three frameworks with sources, pillars and a review date that lint checks, and the strategy, its rationale and the planning texts name it as advice.

### named-patterns-strategy (landed 2026-10-03)

- `NP-1` Given the named-patterns strategy, then it asks a design to name its patterns and any it rejected, the reviewer checks both a novel structure where a pattern fits and a pattern where none is needed, and it stays advice.

### quality-static-signals (landed 2026-10-03)

- `QS-1` Given a run record and its scenario, when the final code is rebuilt from the seed and the diff, then the measures cover changed Python files outside tests, and a diff that does not apply gives no measure.
- `QS-2` Given a before and after version of a file, then complexity added, duplicated lines and lint findings are counted as the design states.
- `QS-3` Given records for several conditions, then the comparison report shows the three measures per cell and per condition, and not recorded where none exists.
- `QS-4` Given a diff with unusual paths, deleted or unparsable files, or a git environment pointing elsewhere, then the rebuild measures exactly the right files and touches nothing outside its directory.

### migrate-map-parsed-once (landed 2026-10-03)

- `MM-1` Given many manifests read in one process, then the migrate map is parsed once, and parsed again only when its path or contents change.

### upgrade-from-5-0-0 (landed 2026-10-03)

- `UP-1` Given a project and an issue made with the 5.0.0 CLI, when the working tree's CLI reads them, then every manifest loads and compass check gives the same gate-by-gate verdict.

### delivery-board (landed 2026-10-03)

- `DB-1` Given an issue in progress, then its board row shows its route, current stage, gates passed out of total, and whether its newest test record still matches its files.
- `DB-2` Given in-progress issues whose evidence is stale and parked issues, then each appears in its own section, apart from the issues moving normally.
- `DB-3` Given queued and landed issues, then the board shows the queue with age and signal, what landed in the last seven days, and the most common friction among them.
- `DB-4` Given the flow command with an html file named, then it writes one self-contained page with the same sections and rows, every value escaped.
- `DB-5` Given this repository's manifests, then the flow board stays within the speed bound its test sets.
- `DB-6` Given a manifest whose fields have the wrong types, then the board lists it as unreadable and still renders every other issue.

### contribution-guide (landed 2026-10-03)

- `CG-1` Given the contribution guide, then it names the required CI check, how review works with the automatic review off, the review rules file, the code owners and the house rules, and every path it names exists.

### title-times-a-user (landed 2026-10-03)

- `TT-1` Given a scenario title that attaches a duration to a user or claims an outside user, then scenario add refuses it when it is recorded, using the same patterns the public-copy check applies.

### rival-names-never-committed (landed 2026-10-04)

- `RN-1` Given the tracked tree, when the gate scans every tracked file's text and every tracked path against the committed hashes, then it finds no rival name.
- `RN-2` Given a name planted in a tracked file, a tracked path, a commit message and a pull request body, then the gate fails on each, and its output gives the place but never the name.
- `RN-3` Given the order file's own name, which ends with one rival's alias, then the gate passes it; the same scan without the allowed compound fails, so the exemption is what passes it.
- `RN-4` Given no names key, when the harness is asked for a rival condition, then it stops with a message naming the missing key, and bare and compass runs still work; given a key, a rival condition builds its copy from the key's pinned source.
- `RN-5` Given a record path holding names and a project that configures a names key, when the record syncs, then the record holds codes only and the gate passes over the synced copy; when the configured key is missing, sync refuses with exit 2 and sends nothing.
- `RN-6` Given a pull request, then CI runs the gate over the text of its commit messages, title and body.
- `RN-7` Given CLAUDE.md, the house rules and the plugin's writing guidance, then each states the rule and the code convention.
- `RN-8` Given the key, then the committed hash file is exactly what the generator writes from it, so the gate covers every entry in the key.
- `RN-9` Given the published comparison runs after the sweep, then every number in them is unchanged and each carries one line saying rival products appear as codes and the maintainer holds the key.

### harness-containment-under-root (landed 2026-10-04)

- `HC-1` Given an eval run, then every session runs without writing bytecode, a compass run as root is refused unless its plugin copy is on a read-only mount or --allow-root is given, each record names the uid, Python version and whether it ran as root, and the comparison report states those and how many runs were not contained.

### commit-msg-name-check (landed 2026-10-04)

- `CM-1` Given the commit-msg hook is installed, then a commit whose message names a rival product is refused before it is made, a clean message commits, and the refusal names no product.

### check-accepts-a-staged-deletion (landed 2026-10-04)

- `SD-1` Given a traced file whose deletion is staged but not yet committed, then the traceability check counts its absence as the change; a traced file missing from disk with no deletion staged or committed is still reported.

### terminology-test-shares-a-folder (landed 2026-10-04)

- `TV-1` Given the terminology tests running in parallel workers, then each worker scans its samples in a folder of its own, so no worker removes another's folder.

### tokens-per-stage-interactive (landed 2026-10-04)

- `TS-1` Given a Claude Code transcript, then the reader gives each request's time, model and token counts once, though the transcript can repeat a request over several lines (taking the first line's time and the highest count per field), and it includes the session's subagent transcripts by their own times.
- `TS-2` Given a quick fix finished in a Claude Code session, with or without `--no-commit`, then its manifest records the input, output and cache tokens spent in its assess and implement stages, taken from that session''s transcript between the times the manifest records for the stage boundaries, and records verify and ship as not measured.
- `TS-3` Given a quick fix finished outside Claude Code, or with a transcript that cannot be read, then the finish succeeds as before and the manifest says why no tokens were recorded.
- `TS-4` Given a model whose price the project configures, then each stage also records its cost; given none, cost is "not recorded", never a guessed price.
- `TS-6` Given one session that works on two issues, then each issue's assess window starts after the other issue's last boundary in that session, and a stage whose window overlaps the other issue's is marked shared.
- `TS-7` Given a transcript whose messages hold a sentence of text, then nothing the reader returns or the manifest records contains that sentence, a path or an error message; a reason for not recording comes from a fixed list.
- `TS-5` Given eval records whose manifests carry tokens per stage, then the comparison report shows each condition's tokens per stage.

### premium-run (landed 2026-10-04)

- `PR-1` Given the 4 October comparison run, then its document is on record with every condition and scenario, the decision rule's verdict for each of the four careful-process scenarios, the cost per condition, the tokens per stage, and what it does not show.

### directory-listing-prep (landed 2026-10-04)

- `DL-1` Given the plugin as the directory receives it, then the icon is under the 5 MiB per-file limit and still square, and the README lists everything Compass runs on the machine, sends and fetches.

### slug-names-an-eval-scenario (landed 2026-10-04)

- `SN-1` Given an issue slug that contains an eval scenario or behaviour id, then quick-fix start and approach evaluate refuse it before writing anything, and a slug that names none is accepted.

### quick-fix-token-breakdown (landed 2026-10-04)

- `TB-1` Given two Compass quick-fix sessions and their no-framework pairs from the 4 October run, then the breakdown is on record: resident load per request, each source's share of the tokens read, and the request counts, with how they were measured and what they do not show.

### keep-the-stop-before-a-breaking-change (landed 2026-10-04)

- `KS-1` Given the comparison run found Compass stopped to warn of a change that would break a hidden consumer, then the decisions ledger records the maintainer's decision to keep that stop at its measured cost, with its evidence.

### repoint-to-ayeo-io (landed 2026-10-04)

- `RA-1` Given the repository now lives at ayeo-io/compass, then no tracked file names the old address as the repository, the plugin manifests name the new one, and the marketplace owner is the organisation.

### quick-fix-shows-settled-decisions (landed 2026-10-04)

- `SD-1` Given a project whose decisions ledger holds entries, then quick-fix start lists each live entry's slug and first decision sentence, newest first and capped with a count of the rest, leaves out superseded entries, and adds nothing when the ledger is empty.

### resumed-quick-fix-lands-in-one-command (landed 2026-10-04)

- `RQ-1` Given a quick fix resumed by a session that did not start it, then the resume command names the red and quick-fix finish as the way to land it, and quick-fix finish lands it in one call with no start record.

### correct-token-breakdown-categories (landed 2026-10-04)

- `CB-1` Given the published breakdown, then it carries a dated correction saying shell calls that ran compass also read files in the same call, so the Compass CLI share is an upper bound, and what those calls read.

### docs-site (landed 2026-10-04)

- `DS-1` Given mkdocs.yml and the docs workflow, then the site lists the five core pages and the pages they link to, every listed page exists, every relative link on them stays inside the site, the build tool is pinned and used only in CI, and the site is published from main only.

### trim-quick-fix-context (landed 2026-10-04)

- `TC-1` Given the session-start contract, then it is at most 2,250 characters, from 2,517, and still holds a pinned phrase for each of its rules - assess first, never skip assessment, trigger on intent, the five guardrails, guardrails hard and strategies soft, evidence not assertion, state on disk, the numbered stages, the instruction to use the CLI, the statement that there are five guardrails, where to look and writing for no context - and deleting any one of them fails the test.
- `TC-2` Given `--help` for `quick-fix start`, `quick-fix finish`, `tdd-red` and `tdd-green`, then each, printed at 80 columns, is within a budget set from the rewrite (2,600 characters for `quick-fix start`, 1,500 for `quick-fix finish`, 1,450 for `tdd-red`, 1,250 for `tdd-green`) and still lists every option it accepted before.

### quote-the-plugin-root-in-hooks (landed 2026-10-04)

- `HQ-1` Given the plugin installed under a path that contains a space, then each of the four hook commands in hooks.json runs its own script, because each quotes the plugin root.

### plugin-display-name (landed 2026-10-04)

- `PN-1` Given the plugin manifests, then the plugin keeps the name compass, its display name is Compass Adaptive Spec-Driven Development, and its author is ayeo.io in both manifests.

### release-5-5-0 (landed 2026-10-04)

- `RV-1` Given the release is 5.5.0, then VERSION, the CLI, both plugin manifests and the install smoke test all say 5.5.0 and the version guard agrees.

### docs-site-home-page (landed 2026-10-04)

- `DH-1` Given the docs site, then its root serves a home page, index.md, that is first in the navigation and links only to pages in the site.

### docs-table-code-wraps (landed 2026-10-04)

- `DT-1` Given a docs page with a table cell holding inline code such as /compass:intent, When the site renders it at desktop width, Then the code stays on one line rather than breaking mid-word

### evaluate-and-check-apply-the-schema (landed 2026-10-04)

- `SK-1` Given an issue manifest whose assessment holds a key the manifest schema does not allow, such as risk_reason, When compass approach evaluate --write or compass check runs on it, Then each refuses and names the unknown key and the allowed keys, as issue lint does, with or without jsonschema installed

### colour-hides-an-import-red (landed 2026-10-04)

- `CL-1` Given FORCE_COLOR is set in the environment, When compass tdd-red runs a test that imports a project module not yet written, Then it records an import red, and the eval harness reads each test's outcome from coloured pytest output

### seed-walk-skips-pytest-cache (landed 2026-10-04)

- `SW-1` Given another test's pytest run has made a pytest-cache-files folder inside a scenario seed, When the scenario-file walks in tests/test_eval_scenarios.py list the files to scan, Then they skip that folder and .pytest_cache, so a folder deleted mid-walk cannot fail them

### pytest-bdd-adapter-tests-run (landed 2026-10-04)

- `PB-1` Given pytest-bdd is installed, When the reference-adapter end-to-end test and the pytest-bdd case of the all-adapters test run, including under make test with plugin autoload off, Then both pass, and the bdd-adapter CI job runs them and fails if either skips

### friction-phase-takes-v2-stages (landed 2026-10-04)

- `FP-1` Given an issue whose friction entry names a current stage such as implement, When compass issue lint runs with jsonschema installed, Then it passes; and Compass writes and loads friction phases in the current stage names, mapping a retired name such as frame to assess

### entry-point-cap-measures-code (landed 2026-10-04)

- `EC-1` Given cli/compass holds the shebang, build_parser and main, When a verb is registered in build_parser, Then the entry-point guard still passes; and when logic is added outside build_parser, or a loop or a new function is added, Then it fails

### ship-commit-takes-a-message-file (landed 2026-10-04)

- `SF-1` Given a commit message in a file, When compass ship-commit -F <file> runs with staged changes, Then it commits with that message and verifies HEAD advanced; and giving both -m and -F, or neither, is refused

### archive-citation-in-adapter-readme (landed 2026-10-04)

- `AC-1` Given a checkout with the full archive but without the adapter's generated feature file, When the archive citation guard runs with COMPASS_FULL_ARCHIVE=1, Then the README's mention of the file bdd extract writes is treated as illustrative and the guard passes

### trace-checks-scenario-ids (landed 2026-10-04)

- `TS-1` Given an issue with scenarios TRC-1 and TRC-2, When compass changed-file add or compass evidence add is given a scenario id the issue does not define, or several ids in one quoted string, Then it refuses, names the issue's scenarios and writes nothing

### one-fired-rule-formatter-shared (landed 2026-10-04)

- `FR-1` Given a fired policy rule with a rationale, an id and a kind, When approach evaluate prints its summary or verbose view and issue receipt prints the receipt, Then each line is exactly what it is today, and all three come from one shared formatter

### nothing-inspected-is-not-pass (landed 2026-10-04)

- `NI-1` Given an issue where some checks have nothing to inspect and one fails, When compass check runs in the verbose and default views, Then those checks are labelled NOTHING TO CHECK rather than PASS, and the failing verdict counts only checks that inspected something and names how many had nothing to check

### printed-route-wording (landed 2026-10-04)

- `RW-1` Given an issue, When approach evaluate --verbose --write, gate pass on an unknown gate, check with no gates and retro print their output, Then none of it says route, candidate shape or phases where it means the delivery approach or its stages

### map-counts-agree (landed 2026-10-04)

- `MC-1` Given a distribution map whose subtask table lists a different number of rows from the Final subtask count after caps it states, When multiagent.sh provisions it, Then it refuses, names both numbers and creates nothing; and a map whose counts agree, or that states no number, is provisioned as before

### suite-from-a-clean-clone (landed 2026-10-04)

- `CC-1` Given a checkout with gitignored local state such as .compass/work, When make test-clean runs, Then it clones the committed HEAD into a temporary folder, runs the suite there without that state, and removes the folder afterwards

### supply-chain-pins (landed 2026-10-04)

- `SP-1` Given the workflows in .github/workflows and the copyable files in ci/, When a test reads every uses: line and every package install, Then each action is pinned by a full commit SHA, each pip install reads a requirements file of exact versions or pins inline with ==, and the cucumber-js job installs with npm ci from its lockfile

### release-5-6-0 (landed 2026-10-05)

- `RL-1` Given the release procedure's seven version locations and the version test's expected version, When each is bumped to 5.6.0, Then the version consistency and coverage tests pass and compass --version prints 5.6.0

### lint-excuses-unassessed-abandoned (landed 2026-10-05)

- `LA-1` Given an issue with status abandoned and no assessment block, When compass issue lint runs, Then it does not demand an assessment; and an active issue with no assessment is still refused

### security-policy-and-templates (landed 2026-10-05)

- `CF-1` Given the repository root and .github, When a contributor looks for a security policy, a code of conduct and issue templates, Then SECURITY.md points to GitHub private vulnerability reporting and names the supported version, CODE_OF_CONDUCT.md adopts the Contributor Covenant 2.1 with conduct@ayeo.io as the contact, and bug and feature templates ask for the Compass version

### record-triage-decisions (landed 2026-10-05)

- `TD-1` Given the maintainer's choices of 5 October on issues #100, #105, #116 and #121, When the decisions ledger is read, Then each has an entry by jed72 with its decision, its reason and the issue it answers

### harness-root-sanctioned-path (landed 2026-10-05)

- `HR-A` Given the harness runs as root with --session-user naming an unprivileged user, then each session runs as that user, owns its working folder, cannot write the plugin copy or the checkout, and the record states its uid.
- `HR-B` Given a root run with Compass installed and no sanctioned path, then it is refused before any session, naming --session-user and a read-only mount first and --allow-root last.
- `HR-C` Given --allow-root where CI or COMPASS_UNATTENDED is set, then the run is refused before any session.
- `HR-D` Given --session-user naming root or an unknown user, then the run is refused before any session and names the problem.
- `HR-E` Given --session-user while the harness is not root, then the run is refused.
- `HR-F` Given a run that is not as root and has no --session-user, then sessions start as before and session_uid equals the harness's uid.
- `HR-G` Given a root run with a session user, then git and the test command in the session's folder run as that user, so code the session wrote never runs as root.
- `HR-H` Given a session that replaced a file in its folder with a link outside it, then the harness's own reads and writes there do not follow the link.
- `HR-I` Given a session that left a process running, then the harness ends the session user's processes before it touches the folder again.
- `HR-J` Given a real root run with a real unprivileged session user, then the run is contained and the session's edit is in the diff.

### retired-terms-from-terminology (landed 2026-10-05)

- `TRC-001` Given a retired_in_output block in governance/terminology.yml, When the printed-output guard builds its patterns, Then it scans for every name in the block and holds no hand-written list

### review-page-stale-reminder (landed 2026-10-05)

- `TRC-001` Given an issue whose review page matched its manifest, When a verb that writes the manifest leaves the page stale, Then the verb prints one line naming compass issue dashboard, and prints none when the page is still current or there is no page

### mutation-proof-register (landed 2026-10-05)

- `MPR-1` Given a shipped check with no register entry, when the register test runs, then it fails naming the check
- `MPR-2` Given a register entry missing a required field, when the register test runs, then it fails naming the check and the field
- `MPR-3` Given a register entry for a check that no longer exists, when the register test runs, then it fails naming the entry
- `MPR-4` Given the shipped checks cannot be read or are empty, when the register test runs, then it fails rather than passing
- `MPR-5` Given each shipped check, when the register is read, then its entry names a failing-input test and a passing control that exist
- `MPR-6` Given the change lands, then nothing under governance changes and the project guardrail list stays empty

### harness-post-session-walks (landed 2026-10-05)

- `PSW-1` Given a session that planted a folder where a hidden test is copied, When the run finishes, Then the record says not contained and names the path, instead of the run ending with an error
- `PSW-2` Given a session that replaced .compass with a link, when the run lists its compass files, then it lists nothing and never walks the link

### adr-projects-add-checks-as-data (landed 2026-10-05)

- `TRC-001` Given the maintainer approved the configurable-framework recommendation on 2026-10-05 When a reader opens architecture/decisions/README.md Then ADR-002 shows superseded by ADR-033, ADR-010 shows accepted, Inv-2 and Inv-3 carry the new wording, and the ledger holds both decisions

### keep-docs-specs-untracked (landed 2026-10-05)

- `TRC-001` Given a technical spec written to docs/specs/ When git status runs Then the file is ignored and git ls-files lists nothing under docs/specs/

### harness-session-user-hardening (landed 2026-10-05)

- `SUH-2` Given a session user with running processes or a link in its watched Claude configuration, when a run starts, then it is refused naming what was found
- `SUH-3` Given a session user with a crontab or a queued at job, when the harness checks it, then the run is refused naming which
- `SUH-4` Given a run that changed the contents, permissions or type of the session user's watched Claude configuration, when the record is written, then it lists the changed paths
- `SUH-5` Given any run with a session user, when it ends, then the harness has modified nothing in the session user's home
- `SUH-6` Given the three places that start a process as the session user, when their arguments are built, then they come from one helper
- `SUH-1` Given a session that leaves a process holding its output open, when the call ends, then the harness ends it and records the run as not contained

### one-name-per-route (landed 2026-10-05)

- `RN-2` Given the shipped routing policy, when it is read, then route_shapes and every route reference use the five route names
- `RN-3` Given the checkpoint routes, the lint route check and the schema, when compared with route_shapes, then they match
- `RN-4` Given a manifest with an unknown delivery approach, when the issue is linted, then the value is reported
- `RN-5` Given the retro over the archive, when it runs before and after the rename, then the counts are the same with no translation left
- `RN-6` Given the approach documents, when the rename lands, then regular and full replace the old files and no link is broken
- `RN-7` Given the decisions of 5 October on routing, when this lands, then each is a decision entry
- `RN-1` Given a policy or manifest with an old route name, when it is read, then it maps to the new name with one warning and the same approach

### lean-assess (landed 2026-10-05)

- `LA-1` Given commands/assess.md, When its size and the procedure file are checked, Then assess is at most 2,500 characters, names the procedure file for heavier routes and --reassess, and the procedure keeps every step

### repository-autonomy (landed 2026-10-05)

- `RA-1` Given this repository's .compass/config.yml, When an issue on the regular or full approach is evaluated, Then no checkpoint waits for a person

### finish-honours-acceptance (landed 2026-10-05)

- `FA-1` Given a quick fix that recorded an acceptance of kind refactor and no red, When quick-fix finish runs, Then it records the green, passes the three gates and finishes

### stage-tokens-in-report (landed 2026-10-05)

- `ST-1` Given eval records whose manifests measured assess and implement and whose session total is known, When the comparison report is built, Then each cell shows assess, implement, and verify and ship as the remainder, and a cell whose mean assess exceeds its mean implement is flagged

### ledger-listing-cap (landed 2026-10-05)

- `TC-3` Given a ledger whose entries have very long first sentences, When quick-fix start lists the settled decisions, Then each line and the whole listing stay within their character budgets and every line still names its entry

### acceptance-timing-gaps (landed 2026-10-05)

- `AT-1` Given a refactor acceptance recorded with no edit in a repository with no pytest cache, When compass acceptance record runs, Then it refuses because the source tree has not changed

### lineage (landed 2026-10-06)

- `LN-1` Given a landed issue, when an issue is created with `quick-fix start --raised-by <it> --found-at review`, or `compass issue raised-by <it> --found-at review` runs on an existing issue, then the manifest carries `raised_by` with that issue and `found_at: review`, and `compass issue lint` accepts it.
- `LN-2` Given `--raised-by` names no issue in the project, or `--found-at` is not one of define, plan, implement, verify, review, ci, after-landing, or only one of the two flags is given, when either verb runs, then it exits non-zero and writes nothing. A manifest whose `raised_by` has an unknown `found_at` fails `compass issue lint`.
- `LN-3` Given three issues raised at review and one raised after-landing, when `compass retro --lineage` runs, then it reports three found before landing and one after, counts by `found_at`, names chains of three or more and the parents with the most children, and exits 0. With no raised issues it says so and exits 0.
- `LN-5` Given issue C raised from B, which was raised from A, when C's `raised_by` is recorded, then one line names A as the root and points at `S14` in `governance/strategies.md`. A second-level issue prints no such line.

### delivery-board-midnight-flake (landed 2026-10-06)

- `DM-1` Given the clock moves one day on between the test module loading and board() running, When the queue age test runs, Then it still reports the age it set up

### retro-skips-list-manifest (landed 2026-10-06)

- `RL-1` Given one manifest under .compass/work written as a YAML list, When compass retro runs, Then it exits 0, reports the other issues and names the skipped manifest

### late-validation-acceptance (landed 2026-10-06)

- `LV-1` Given a quick fix whose files changed after quick-fix start, staged or not, When acceptance start --kind validation runs, Then it refuses and names the files; declared before the change, the same work records and finishes

### session-user-follow-ups (landed 2026-10-06)

- `SF-1` Given a root eval run with --session-user, When a run changes a folder's mode, installs a job, or leaves an oversized file, or a call is held and the kill-all fails, Then the record or the next run's check shows it, and the call's readers and pipes are closed

### check-mutation-runner (landed 2026-10-06)

- `CM-1` Given the mutation-proof register, When the runner breaks each check to always pass and then always fail in a copy of the checkout, Then each fails test and each restores test goes red, a weakened, skipped or uncollected test is reported by name with a non-zero exit, and the checkout is unchanged

### decisions-2026-10-06 (landed 2026-10-06)

- `DE-1` Given the decisions of 5 and 6 October 2026, When governance/decisions/ is read, Then entries record that old route names stay readable until 7.0.0, B39 folds into PRD 22, A16 waits for PRD 19 and this repository may hold a settings-only compass.yml, each superseding what it replaces

### approach-diagram (landed 2026-10-06)

- `RD-1` Given the shipped policy and `--autonomy balanced`, when `compass approach diagram` runs, then the regular row marks define and plan as stops for a person, the quick-fix row marks none, and every cell names its weight as a word.
- `RD-2` Given no `--autonomy`, when it runs, then it uses the project's `autonomy:` setting; an unknown value is refused, naming the values.
- `RD-3` Given a project with its own `governance/routing-policy.yml`, when it runs, then the diagram shows that policy, read through the same route names as the evaluator.
- `RD-5` Given any render, then it names the three ways work comes back: a reassessment, a refusal from the pre-tool hook and a failed `compass check`.
- `RD-6` Given `docs/approach-diagram.html`, when the suite runs, then a test fails when it differs from a fresh render of the shipped policy under `balanced`, and two renders are byte-identical.

### doc-scans-read-tracked-files (landed 2026-10-06)

- `DS-1` Given a repository with one tracked and one untracked document, When the document scans list their files, Then only the tracked document is listed

### harness-read-only-bind-mount (landed 2026-10-06)

- `RM-1` Given the harness running as root on Linux, When it prepares its plugin copy, Then it bind-mounts the copy read-only before any session, records that it did, removes the mount at the end, and falls back to the refusal when the mount fails

### quick-fix-finish-captures-friction (landed 2026-10-06)

- `QF-1` Given a quick fix whose manifest records a re-assessment, When quick-fix finish runs, Then the manifest's friction list holds the derived entry; with no signal, no friction key is written and no extra line is printed

### mutation-runner-tidy (landed 2026-10-06)

- `MT-1` Given the mutation runner, When --check names no register entry, Then it exits non-zero naming the id; and when a test stays green its output is shown

### living-spec-conflicts (landed 2026-10-06)

- `LS-1` Given a git project where an issue is landed in local records, is not named in the spec committed at HEAD and its `land_commit` is not reachable from HEAD, when the spec is derived, then its scenarios are left out; an issue named in HEAD's spec, or whose `land_commit` is reachable, is kept.
- `LS-2` Given a branch that conflicts with its base only in the two derived spec files, when `compass issue refresh-spec --base <ref>` runs, then the base is merged, the base's spec is taken, the spec is re-derived with the branch's own issue and committed, and no conflict is left.
- `LS-3` Given a merge that also conflicts in another file, when `compass issue refresh-spec` runs, then it aborts the merge, leaves the branch as it was and names the other files.
- `LS-4` Given the decision, then an architecture decision record states the new selection rule and how it narrows ADR-008's "reconstructible from landed issues alone".

### session-compliance (landed 2026-10-06)

- `CS-1` Given issues whose records carry a session id and that session's transcript, when `compass retro --compliance` runs, then each judge behaviour gets sessions, pass, fail, undecided, a pass rate over decided sessions and a 95% Wilson interval, and each failing session is named by issue id and tool-call index; `--json` prints the same; `--days N` and `--issue` narrow it.
- `CS-2` Given a transcript that no issue's records name, when the report runs, then it is counted as unmatched and never assigned to an issue by time or path.
- `CS-3` Given a transcript with tool calls, results and a hook refusal, when the adapter reads it, then it yields the run-record shape the judge reads (tool calls with name, input, output, error flag), and no other module reads the transcript format; a session that is not Claude Code is reported as `not-claude-code`.
- `CS-5` Given a session in which the pre-tool hook refused a write to a path and a later call writes that path through a shape the hook does not classify (for example `python3 script.py`), when it is scored, then the behaviour for writing around a hook refusal fails at that call's index; with no later write, it passes.
- `CS-6` Given a transcript seeded with a unique secret string, when the report runs in text and JSON, then the string appears in no output and no file the command writes.
- `CS-9` Given the report, then `compass check` does not read it and no gate depends on it.
- `CS-10` Given a behaviour failing in three or more distinct issues in the window, when the report runs, then it writes a pending lesson with `source: compliance` naming the behaviour and the issues, and nothing takes effect until `compass lesson accept`.

### refresh-spec-message-when-up-to-date (landed 2026-10-06)

- `TRC-001` Given a branch already up to date with its base whose derived spec is stale, when compass issue refresh-spec runs, then it commits the re-derived spec with a message that names no merge

### configuration-decision-records (landed 2026-10-06)

- `DR-1` Each structural decision of the configuration foundation is a proposed ADR with a rejected alternative, listed in the index
- `DR-2` Each product decision of 5 and 6 October 2026 for the configurable framework has a ledger entry
- `DR-3` No record cites a private planning path or names a rival product
- `DR-4` The vocabulary amendment names the approaches catalogue, the adoption setting and every new term

### finish-runs-the-suite-once (landed 2026-10-06)

- `TRC-001` Given a quick fix with two scenarios, each with a red on record, when quick-fix finish runs, then the test command runs once and each scenario gets its own green record

### agent-recorded-friction (landed 2026-10-06)

- `TRC-001` Given an issue, when the agent runs compass issue friction with a category, phase, an existing evidence path and a fix, then a source: agent entry is added; a fourth note, a repeated category and phase, a missing fix or an unknown evidence path is refused
- `TRC-002` Given agent and person friction, when compass retro --friction runs, then agent entries are counted in their own column and never merged with person or derived entries
- `TRC-003` Given the same friction in three issues from agent notes only, when lessons are proposed, then none is proposed; with one person entry for it, one is
- `TRC-004` Given a note about a guardrail-backed step, when it is recorded, then it is accepted, reported as guardrail, not changeable by friction, and never counts toward a lesson or a recurring cluster
- `TRC-005` Given the instruction to record agent friction, then it adds at most 40 words to resident context and resident context stays under its ceiling

### finish-shows-a-failed-derive (landed 2026-10-06)

- `TRC-001` Given a committed living spec that names an issue whose records are missing, when quick-fix finish lands a fix, then its output says the living spec was not re-derived and names compass issue refresh-spec

### compat-routing-baseline (landed 2026-10-06)

- `TRC-001` Given the 5.6.0 evaluator, when the routing baseline is captured, then every one of the 1,200 assessments and every label subset over the four named labels has a recorded result, the test passes on today's code, and it fails when one shipped default changes

### compat-hook-corpus (landed 2026-10-06)

- `TRC-001` Given the 5.6.0 pre-tool hook, when the hook corpus is captured, then each recorded tool call gets the recorded decision and refusal code, including both reads of .compass/config.yml, and the test fails when one decision changes

### advisory-mode-wording (landed 2026-10-06)

- `TRC-001` Given a project after compass init, when a person reads the mode comment in .compass/config.yml, then it says advisory mode stops checks and CI from failing and that the pre-tool hook still blocks code edits without a failing test, instead of saying nothing blocks

### compat-command-corpus (landed 2026-10-06)

- `TRC-001` Given the 5.6.0 CLI, when the command corpus is captured, then each recorded invocation exits as recorded, and the test fails when one exit code changes

### compat-archive-baseline (landed 2026-10-06)

- `TRC-001` Given the archive sample at 5.6.0, when the archive baseline is captured, then every check's verdict on every sampled issue is recorded, issue lint and issue receipt exit 0 on each, the test passes on today's code, and it fails when one verdict changes

### atomic-io (landed 2026-10-06)

- `TRC-001` Given atomic_io, when a file is written and the process fails before the rename, then the old file is intact and no temporary file is left; a YAML file with a duplicate key is refused with its line; equal data gives equal canonical JSON and digests

### cli-refusal-consistency (landed 2026-10-06)

- `TRC-001` Given each of the inconsistent refusals the command corpus found, when it runs, then it exits 2, names the real problem and the flag it has, writes to stderr, and the corpus entry records the new exit on purpose

### catalogue-spec (landed 2026-10-06)

- `CS-1` Given the field table, then it names the eight catalogues, each catalogue's fields with their type, merge kind and compare kind, the obligation fields the clas
- `CS-2` Given a layer document, when it is checked, then an unknown top-level key, an unknown catalogue field, an id that breaks the id pattern, a settings key in a pa
- `CS-3` Given a dimension entry, when it is checked, then a type outside `ordered-enum`, `enum` and `set`, an ordered dimension without `tighter:`, and `at_least:` on
- `CS-4` Given `when: { risk: { at_least: cross-cutting } }`, when an assessment is matched, then cross-cutting and critical match and trivial and contained do not; eve
- `CS-5` Given the committed JSON Schema for compass.yml in the schemas folder, then it equals the schema generated from the field table

### layers-and-merge (landed 2026-10-06)

- `LM-1` A project file loads with its layer keys and settings keys split
- `LM-2` A layer digest covers the layer keys only
- `LM-3` The chain runs parent, project, issue and refuses a settings key in a parent
- `LM-4` Entry operations add, set, replace and remove
- `LM-5` Field operations inside set on scalars, lists and maps
- `LM-6` Provenance names the layer and operation of every field
- `LM-7` Bad targets and bad entries are refused by code
- `LM-8` Misused list and map operations are refused by code
- `LM-9` An operation or field a layer may not use is refused
- `LM-10` Removing an entry something refers to names each referrer
- `LM-11` One error reports every fault in a layer and inputs stay unchanged

### settings-reader-python (landed 2026-10-06)

- `SR-1` Given the same settings in `.compass/config.yml` or in `compass.yml`, when each Python reader runs (adoption mode, autonomy, drift strictness, record
- `SR-2` Given a missing or broken settings file, when each reader runs, then it behaves as it did at 5.6.0 (the design's table: enforced, balanced or a refus
- `SR-4` Given the fold-in test, when one reader is left reading `.compass/config.yml` directly, then the test fails; and no module but `project_settings.py`
- `SR-5` The compatibility contracts 1 to 6 still pass, apart from any entry this change alters on purpose with its reason.
- `SR-3` Given a project after compass init, then a state file in the .compass folder holds initialised and records_signed_since, no settings file is written, and the cutoff and the hook's explanation still read from it

### vocabulary-catalogue (landed 2026-10-06)

- `VC-1` A display name comes from the vocabulary and a project layer changes it
- `VC-2` An alias resolves to its id
- `VC-3` A name or alias that collides with another entry fails
- `VC-4` A vocabulary key that names nothing fails
- `VC-5` The ban scan covers display names
- `VC-6` The terminology file says how a project adds names
- `VC-7` The terms the accepted vocabulary decision defines are in the glossary

### settings-reader-hook (landed 2026-10-06)

- `SH-1` Given code_globs in compass.yml, the hook blocks a matching path as for the old file; compass.yml wins; an unreadable file blocks naming the file; no file allows an unlisted path
- `SH-2` Given initialised in state.yml or only the old file, the first refusal says who initialised the project; a broken record adds nothing
- `SH-3` Given worktree root, cap or test command in compass.yml, multiagent.sh and integrate.sh read them there; old file keeps its values; compass.yml wins
- `SH-4` Given a new project, init writes state.yml and no .compass/config.yml; an old-file project is untouched
- `SH-5` Given an unreadable settings file, the refusal and its doc name the file the hook read
- `SH-6` Given the fold-in test, a hook or script naming the old file in any spelling, or reading it with compass.yml present, fails it
- `SH-7` Given the recorded hook corpus, every decision matches unchanged, and again with settings moved to compass.yml and state.yml
- `SH-8` Given prose that says where a setting is read or what init writes, then it matches the CLI: init writes no settings file, and a setting is read from compass.yml or the old file without one
- `SH-9` Given compass.yml, the scripts read only the documented paths (multiagent.worktree_root, multiagent.max_worktrees, project.test_command); the old file keeps the any-depth lookup; an unreadable settings file stops both scripts with exit 1 naming the file
- `SH-10` Given a project with neither settings file, the hook starts no Python for the code_globs read; the names of the two files live in one allow-listed helper pinned equal to project_settings

### eval-judge-guards-compass-yml (landed 2026-10-07)

- `TRC-001` Given an eval session transcript that edits compass.yml, When the judge checks protected files, Then it reports the edit as touching a protected file, as it does for .compass/config.yml

### both-settings-files-present (landed 2026-10-07)

- `BS-1` Given both files and a recognised compass.yml, an old file that holds a settings key makes the hook refuse with settings-conflict and the CLI raise the same text
- `BS-2` Given both files and a compass.yml with no schema, the old file is read, a warning goes to stderr once, and the hook decides as for the old file alone
- `BS-3` Given both files, a recognised compass.yml and an old file with only state keys, compass.yml is read with no refusal and no warning
- `BS-4` Given only compass.yml, with or without schema, it is read and nothing warns
- `BS-5` Given a broken file beside the other, the reader refuses naming the broken file
- `BS-6` Given more than five conflicting keys, the text lists five in file order and says and N more
- `BS-7` Given a conflict, compass check and every reader that used to ignore an unreadable file fail with the conflict text
- `BS-8` Given the registry, settings-conflict follows the three-line shape and is listed in the generated refusal codes
- `BS-9` Given the recorded hook corpus with settings moved to compass.yml with schema, every decision matches

### default-preset-data (landed 2026-10-07)

- `DP-1` Today's two policy files convert to the committed preset, and a planted policy change breaks the match
- `DP-2` The preset is named default at version 6.0.0 with capabilities off and checks as a parent layer
- `DP-3` Stage modes carry the ruled ranks on the depth ladder and no rank elsewhere
- `DP-4` Exactly the entries of the shipped lock set are locked, with the human sign-off hard-locked
- `DP-5` The adapter reads old key names, leaves its input unchanged and is read by nothing yet
- `DP-6` Every reference in the preset resolves and the evidence types match the guardrails file

### check-registry (landed 2026-10-07)

- `CR-1` The registry holds one versioned entry per built-in check and CHECK_FNS is derived from it
- `CR-2` The registry answers the installed version and major of an implementation
- `CR-3` Each implementation has a verdict-only corpus seeded from its mutation proof, and a test runs each seed
- `CR-4` The lock file build rule fails on a changed verdict digest without a major bump
- `CR-5` Policy lint refuses a check naming an impl the registry does not hold

### governance-drift-is-a-settings-key (landed 2026-10-07)

- `TRC-001` Given a compass.yml with schema: 1 and governance_drift: strict, When the project layer is checked and loaded, Then it is accepted and governance_drift is read as a setting, not a layer key

### rival-gate-new-key (landed 2026-10-07)

- `TRC-001` Given a non-UTF-8 file pinned by blob hash and path, when the gate scans the tree, then it passes the file's content; given any change to the file, a UTF-8 file, a path, or a stale pin, then the gate still fails or reports

### generated-legacy-views (landed 2026-10-07)

- `GV-1` The two views equal the generator's output byte for byte; a stale view names the regenerate command
- `GV-2` A generated header says generated and names the command; preset, sidecar and template changes change the text
- `GV-3` The mutation-proof register and the plain-language derivation read the preset
- `GV-4` Preset digests are pinned and a changed preset file fails naming the digest file
- `GV-5` The generator script writes, is idempotent, and --check fails on a stale view

### obligations (landed 2026-10-07)

- `OB-1` The preset, through the adapter, routes the whole compatibility grid as today's policy does, and a planted preset change breaks the replay
- `OB-2` The evaluator lifts by rank when given ranks, and by today's fixed set when not
- `OB-3` Obligations name every fact the design lists and equal the evaluator's answers, and every compared field is a fact or a lock footprint
- `OB-4` A refused assessment is a Refused outcome with the evaluator's reason, counted as the baseline counts it, and a configuration fault still raises
- `OB-5` An issue layer picks the candidate, overrides base modes, then floors, caps and role rules apply and floors win
- `OB-6` Checks are active by when and capabilities, severity follows blocking_when, guardrail gates apply by ships and when
- `OB-7` The preset's on_skipped values give today's verdicts on the archive sample, apart from the landed_by relaxations
- `OB-8` The evaluator called as today answers as before, nothing else reads the new module, and it declares its dependencies

### ready-and-done-as-data (landed 2026-10-07)

- `RD-1` The seven Definition of Ready items are human checks equal to the template text, listed as the plan stage's entry
- `RD-2` The seven Definition of Done items are human checks equal to the template text, listed as the verify stage's exit
- `RD-3` The 14 checks require the off capability, are blocking, and carry on_skipped; no other stage has a list
- `RD-4` The generated views do not name the human checks and stay unchanged
- `RD-5` A drifted template item, missing check, reordered list or wrong kind is named by the guard
- `RD-6` A spike owes none of the 14 checks while the capability is off
- `RD-7` A stray line in a template section is refused
- `RD-8` The preset file headers do not claim the adapter wrote the files once

### stable-ids (landed 2026-10-07)

- `SI-1` stable_ids.py imports nothing and its ids equal the default preset
- `SI-2` The scanner finds an id in five positions and skips text
- `SI-3` No module outside stable_ids.py holds an approach id or a gate id in a scanned position
- `SI-4` Legacy approach names and routing.py approach ids live only in stable_ids.py
- `SI-5` The allow list names a reason, matches a line, and a stale entry fails
- `SI-6` The stage-id literals left in each module equal the recorded count
- `SI-7` The rebuilt maps equal today's values and core.py stays within its cap

### classifier (landed 2026-10-07)

- `CL-1` The grid: union domains, grouped classes, named labels and subsets, the cap of eight
- `CL-2` Points combine into equivalent, tightening, loosening or incomparable; refusals are outcomes
- `CL-3` Each field compares by the kind the field table gives it
- `CL-4` The first looser, tighter or mixed point is named with field, parent and child; early exit
- `CL-5` The grouped grid equals the full grid, and the atoms cover every read
- `CL-6` The verdict has complete, stable, pinned JSON
- `CL-7` The benchmark, the module's declarations, the owning doc and the unchanged core

### waivers (landed 2026-10-07)

- `WV-1` A waiver is found with its id, scope, operation and fields, and its shape is checked
- `WV-2` The approvers come from the layer above, and no owner fails
- `WV-3` An issue waiver's approval is a matching human-approval record
- `WV-4` The covered revision is derived and each waived field's parent value is recorded
- `WV-5` A moved revision invalidates a waiver only when a waived field's parent value changed
- `WV-6` Attribution classifies the residual layer and excuses only waived entries
- `WV-7` A waiver that excuses nothing is reported as unneeded
- `WV-8` The module declares its dependencies, is pure, is unused and has an owning doc

### locks (landed 2026-10-07)

- `LK-1` Locks are read from layer documents and the shipped preset gives the ADR lock set
- `LK-2` The footprint of a locked check, gate, stage, rule set or approach
- `LK-3` A lock allows tightening and refuses loosening and each indirect route on a check
- `LK-4` A lock on a gate, stage, rule set or approach refuses removal and moves
- `LK-5` A waiver, a hard lock and the label cap: what a lock refuses regardless
- `LK-6` An unlock needs the project layer, the owner's waiver and a lock that is not hard
- `LK-7` Conformance is conformant, or non-conformant naming each unlocked entry
- `LK-8` Check, the receipt and the summary print the conformance line and nothing else changes
- `LK-9` The module declares its dependencies and owning doc, and core stays in bounds

### unlock-uses-the-waiver-check (landed 2026-10-07)

- `TRC-001` Given a project unlock whose waiver has an approved_on date in the future, When the lock chain is enforced, Then the unlock is refused and the entry stays locked

### policy-lint (landed 2026-10-07)

- `PL-1` A project with no compass.yml and the framework repository keep the legacy lint
- `PL-2` Per-layer faults are reported and stop the lint before the merge
- `PL-3` Every merge code of the first refused layer is reported
- `PL-4` The merged configuration is checked as a whole
- `PL-5` Lock refusals are reported and an evaluator fault is reported once
- `PL-6` An unexcused loosening is an error and waivers are checked
- `PL-7` A vocabulary change is its own warning
- `PL-8` The text output, the options and the exit codes
- `PL-9` Lint --json has a pinned, deterministic shape
- `PL-10` Effective prints every resolved field with source and waiver
- `PL-11` Effective --json has a pinned, deterministic shape
- `PL-12` Both verbs are documented, in the command corpus and within the line caps

### classifier-speed (landed 2026-10-07)

- `CS-1` The evaluator routes without copying the policy
- `CS-2` A stored classification is reused when both configurations and the classifier version are unchanged
- `CS-3` The benchmark pair keeps its verdict and counts and the benchmark prints CPU seconds
- `CS-4` The lock scan classifies only the label sites a footprint can read
- `CS-5` The footprint scan gives the full scan's refusals on every lock case and route
- `CS-6` A ninth label no locked entry reads is not refused
- `CS-7` The classifier has a public scan with a point callback and locks read no private name

### policy-diff (landed 2026-10-07)

- `PD-1` The references resolve to configurations or exit 2
- `PD-2` The classification is the classifier's own JSON
- `PD-3` The grid is replayed and each changed point is listed
- `PD-4` The label combinations are replayed and the cap skips them
- `PD-5` The archive's assessments are replayed
- `PD-6` --open lists the open issues and the waivers a change affects
- `PD-7` The exit codes and --exit-code
- `PD-8` --json has a pinned, deterministic shape
- `PD-9` The text output
- `PD-10` The verb is documented, registered, in the command corpus and within the caps

### generation-store (landed 2026-10-07)

- `GS-1` effective_for reads live with no generation, refuses generation 0, resolves live with no issue
- `GS-2` A generation holds the four files and the complete marker with the contents ADR-036 names
- `GS-3` A commit writes the files, then the marker, then the manifest, under an exclusive lock
- `GS-4` An interrupted commit leaves the manifest on generation n and a named leftover state
- `GS-5` A commit equal to generation n commits nothing and says no change
- `GS-6` A commit refuses a complete-unreferenced target, overwrites an incomplete one, keeps proposed.yml
- `GS-7` Every file the store writes is written atomically and leaves no temporary file
- `GS-8` effective_for returns the stored generation after the project file changes, and refuses a broken one
- `GS-9` Generation directories are classified as current, superseded, proposal, incomplete, complete-unreferenced or broken
- `GS-10` The manifest schema and template accept generation and config
- `GS-11` approach evaluate --write commits generation 1, says no change on a repeat, commits 2 on a change
- `GS-12` compass check writes results.yml for an issue with a generation and refuses a broken one
- `GS-13` compass ci reports generation states and fails on a broken one
- `GS-14` Only effective imports generation and the reader modules import no resolver module
- `GS-15` An issue with no generation gets no generation files and the compatibility contracts pass
- `GS-16` The bench script, DEPENDENCY headers, owning-doc row and core.py line cap hold
- `GS-17` A commit refuses a symbolic link, a landed issue and a rejected compass.yml, and its messages name only commands that exist
- `GS-18` The command writes the manifest atomically and every file keeps the previous mode or the umask
- `GS-19` A rejected compass.yml during quick-fix start leaves no issue folder behind
- `GS-20` Folder states, verdict merging and overwrite rules hold on the edge cases
- `GS-21` Only classify and effective import obligations, on any import form
- `GS-22` EffectiveView.evaluator_policy returns the evaluator's policy from the resolved configuration

### lock-proof-under-xdist (landed 2026-10-07)

- `TRC-001` Given the count of compared lock cases is partial because pytest-xdist split the file When test_cs_5 runs inside a worker Then it skips instead of failing, and outside a worker it still requires at least 70

### layer-non-text-key (landed 2026-10-07)

- `TRC-001` A non-text key anywhere in a layer is refused with L-KEY-NOT-TEXT naming its path and telling the person to quote it

### policy-migrate (landed 2026-10-08)

- `PM-1` A dry run prints the compass.yml it would write and changes no file
- `PM-2` An unchanged copy migrates to an empty overlay and classifies equivalent
- `PM-3` A changed copy migrates to exactly its differing entries and classifies equivalent
- `PM-4` A loosening gets unapproved waiver stubs and blocks apply with exit 1
- `PM-5` Settings fold into compass.yml, state goes to state.yml, and nothing is dropped silently
- `PM-6` Apply copies the sources, writes compass.yml last and keeps the governance files
- `PM-7` A compass.yml, the framework repository or a lone governance file is refused with exit 2
- `PM-8` An interrupted apply finishes on the next run
- `PM-9` A project with nothing to migrate exits 0 and writes nothing
- `PM-10` The json output has fixed keys, is deterministic and is pinned by an example
- `PM-11` The owning doc, README row, help text and command corpus exist
- `PM-12` A table of shipped releases is data, and holds every tagged release
- `PM-13` policy-migrate review round, group 13
- `PM-14` policy-migrate review round, group 14
- `PM-15` policy-migrate review round, group 15
- `PM-16` policy-migrate review round, group 16
- `PM-17` policy-migrate review round, group 17
- `PM-18` policy-migrate review round, group 18
- `PM-19` No member of the compressed archive of shipped releases holds a rival name

### effective-readers (landed 2026-10-08)

- `EF-1` The reader helper returns the stored view, a live view for a project with a compass.yml, nothing for a legacy project and refuses generation 0
- `EF-2` The accessors of the shipped default's generation equal what the governance files hold
- `EF-3` compass check judges an issue by its generation after the governance files change or compass.yml is deleted
- `EF-4` A check with a custom id and the command-passes implementation runs its command from the generation
- `EF-5` Gate evidence requirements come from the generation in gate pass, the evidence check and the receipt
- `EF-6` approach evaluate on an issue with a generation computes from the generation
- `EF-7` Loop ceilings come from the generation
- `EF-8` Readers with no issue read the live effective configuration of a project with a compass.yml
- `EF-9` compass check prints the generation, the parent version and a pending config change
- `EF-10` An issue with no generation reads the governance files and prints what it printed before
- `EF-11` Every read of a governance policy file is in a function that asks the effective view first
- `EF-12` The approach diagram of a project with a compass.yml renders the effective configuration

### sigint-tests-under-load (landed 2026-10-08)

- `TRC-001` Given a loaded machine, when a run is interrupted, then the tests wait for the session to start before signalling

### schema-descriptions (landed 2026-10-08)

- `TRC-001` Given the compass schema, when a test walks every node, then each node has a non-empty description

### policy-update-default (landed 2026-10-08)

- `UP-1` already on the target major: nothing to do, nothing written
- `UP-2` a bump with no waiver changes only the integer after @
- `UP-3` a target not shipped, older, a foreign extends or no file exits 2
- `UP-4` an affected waiver is listed and the move refused without a terminal
- `UP-5` yes never re-approves a waiver
- `UP-6` terminal re-approval writes the integer and the approval in one write
- `UP-7` an approver outside the allowed list is refused
- `UP-8` declining refuses and writes nothing
- `UP-9` a waiver whose field is unchanged stays valid
- `UP-10` a dropped entry or an unresolvable file is refused
- `UP-11` a failed write leaves the file as it was
- `UP-12` the update shows the classification and the replay counts
- `UP-13` no terminal and no yes shows the plan and exits 1
- `UP-14` json equals the pinned example and never prompts
- `UP-15` an edit the command cannot make exactly exits 2 before writing
- `UP-16` help, doc, verb description and corpus state the behaviour

### check-severity-from-generation (landed 2026-10-08)

- `CS-1` Given a generation with an advisory check, when it fails, then the run passes and shows the failure as advisory
- `CS-2` Given a blocking check, when it fails, then the run fails
- `CS-3` Given on_skipped fail and nothing to check, then the run fails and says why
- `CS-4` Given on_skipped pass and nothing to check, then the check counts as a pass
- `CS-5` Given on_skipped not-applicable and nothing to check, then it is counted apart as before
- `CS-6` Given a blocking_when that does not match, an advisory severity is shown as advisory with the condition
- `CS-7` Given the shipped preset and an existing issue, then the verdicts are unchanged
- `CS-8` The JSON shape of an advisory failure is documented and pinned
- `CS-9` Given an issue with no generation, then check behaves as before
- `CS-10` Given a landed_by relaxation on a shipped check with on_skipped fail, the verdict is unchanged
- `CS-11` Given a spike with an advisory guardrail check that fails, then the run passes and shows the failure as advisory

### impl-refusal (landed 2026-10-08)

- `IR-1` A major difference refuses only that check
- `IR-2` The refusal names what to do
- `IR-3` A minor or patch difference is not refused
- `IR-4` A resolver or schema major difference refuses the run
- `IR-5` A refused check is reported as refused and records no result
- `IR-6` A verdict change without a major bump fails the build
- `IR-7` The lock file holds a version and a verdict digest per implementation
- `IR-8` migrate-config pins the installed versions and invalidates old results
- `IR-9` migrate-config refuses a landed issue
- `IR-10` migrate-config commits nothing when already pinned
- `IR-11` migrate-config adopts an issue with no generation
- `IR-12` The coverage page is derived and kept current

### signal-hold-all-threads (landed 2026-10-08)

- `TRC-001` Given other threads exist, when an interrupt arrives while the session is created, then the session is ended

### configure-and-reassess (landed 2026-10-08)

- `CR-1` configure writes the proposal and leaves the manifest as it was
- `CR-2` the preview lists fields, classification, assessment effect, invalidations and the next step; exit 0, 1 or 2
- `CR-3` the JSON has the documented keys in order and equals the pinned example
- `CR-4` discard removes a proposal or leftover above the current generation and never the current or older
- `CR-5` commit adopts a whole unreferenced folder only when a fresh resolution gives the same files
- `CR-6` a reassess interrupted after each step is resolved by commit or discard
- `CR-7` reassess commits the pending proposal, refuses a stale one, and reset-config drops the overlay
- `CR-8` a reassessments entry carries the generation it moved from and to
- `CR-9` records statuses carry forward and a waiver whose parent value changed is invalidated and reverted
- `CR-10` the unreferenced-folder refusal names the folder and both commands, and every named command exists
- `CR-11` help, owning doc, assess command and command corpus describe the verb
- `CR-12` configure refuses a landed issue, a symbolic link and a folder that is not a proposal

### artifact-graph-lint (landed 2026-10-08)

- `TRC-001` Given an artifacts catalogue, When it is linted, Then a bookkeeping artifact used as an input or a dependency on a directory is reported with a code, level, path and group
- `TRC-002` Given a dependency on a directory, When linted, Then it is reported with code, level, path and group
- `TRC-003` Given a dangling or cyclic depends_on, When linted, Then each is reported with its path and the cycle path
- `TRC-004` Given the shipped preset, When linted, Then it is clean and the bookkeeping description follows the design

### issue-layer-reaches-evaluator (landed 2026-10-08)

- `TRC-001` Given an issue config that sets a stage mode When approach evaluate writes Then the manifest stages hold the mode

### issue-layer-at-its-point (landed 2026-10-08)

- `TRC-001` Given a delivery issue under the shipped default, When it configures --route regular on a quick-fix assessment, Then the proposal is accepted because the layer is judged at the issue's own assessment
- `IP-1` Given a delivery issue, When it configures --route spike, Then a lock refuses it at the issue's own point
- `IP-2` Given a spike-assessed issue, When it configures --route full, Then a lock refuses it because spike.conclude is lost
- `IP-3` Given a quick-fix assessed issue under the shipped default, When it configures --route regular, Then the proposal is accepted and a reassess commits it
- `IP-4` Given a regular issue, When it configures --route full, Then it is refused as incomparable on the subtask ceiling
- `IP-5` Given a quick-fix issue where refine is collapsed, When it sets refine=collapsed, Then it is accepted; on a regular issue it is refused without a waiver
- `IP-6` Given an issue with a route pick and an unchanged configuration, When its stored assessment becomes a spike and it is reassessed, Then the reassess is refused
- `IP-7` Given a project layer, When it is linted, Then it is still judged over the whole grid
- `IP-8` Given a proposal that loosens the issue's layer, When the preview is built, Then its classification names the issue's own assessment as the first point
- `IP-9` Given a route pick that is mixed at the issue's own assessment, When it is refused, Then the refusal names every looser or incomparable field

### git-parents (landed 2026-10-08)

- `GP-1` A git extends parses strictly and a spelling outside the form is refused
- `GP-2` A remote ref with no sha is refused and git is not run
- `GP-3` A pinned sha that is not cached is fetched into the cache with seen.yml
- `GP-4` A fetched commit that does not match the pin is refused and not cached
- `GP-5` Check and offline read the cache only
- `GP-6` A symlink in the fetched tree is refused
- `GP-7` A cache that leaves .compass is refused
- `GP-8` Git runs with an argument list, a restricted environment and no shell
- `GP-9` A parent is data only: settings key, unlock and unknown impl fail lint
- `GP-10` Policy effective shows the parent as the source of its fields
- `GP-11` A parent that names a git parent is refused
- `GP-12` versions.yml records the parent ref, sha, version and digest
- `GP-13` A moved pin does not change an open issue
- `GP-14` A short sha resolves only against one cached commit
- `GP-15` The owning doc, help, finding codes and corpus describe the parent
- `GP-16` README and security.md say the git fetch happens and when
- `GP-17` The cache is keyed by repository and sha
- `GP-18` The docs say what environment git sees and that the user's credential helper runs
- `GP-19` A partial fetch reads only the root compass.yml entry
- `GP-20` Guards that the first plants missed are pinned by tests
- `GP-21` A failed read caches nothing and a cache write race is safe
- `GP-22` A waiver in a git parent is checked against the parent's own owner

### living-spec-supersession (landed 2026-10-08)

- `TRC-001` Given two landed issues that share an intent id, when the living spec is derived, then each issue's scenario stays current

### entry-exit-evaluation (landed 2026-10-08)

- `EE-1` With the capability off no reader shows a list
- `EE-2` The Definition of Done is not owed by an approach that does not ship
- `EE-3` A human check is a tick in the issue's checklist
- `EE-4` A skipped list gives the verdict on_skipped names
- `EE-5` A list is due by the current stage
- `EE-6` A deterministic check in a list runs its implementation
- `EE-7` Kinds this increment does not evaluate fail closed; advisory does not fail
- `EE-8` compass check reports and counts the list rows
- `EE-9` compass next names the unmet entry checks
- `EE-10` The receipt shows each list and its state
- `EE-11` The existing Definition of Done check keeps running
- `EE-12` The preset, help text and owning doc describe the lists
- `EE-13` A project stage list and an unknown check are handled
- `EE-14` A check whose when does not match is not listed

### parent-states (landed 2026-10-08)

- `TRC-001` Given a project pinned to a cached parent whose compass.yml is unchanged and no newer commit is known When the parent state is read Then it is up to date
- `TRC-002` Given a pin whose ref has another commit fetched last When the parent state is read Then it is stale
- `TRC-003` Given a cached compass.yml edited after the fetch When the parent state is read Then it is locally modified and the lint fails
- `TRC-004` Given a stale parent whose cached compass.yml was edited When the parent state is read Then it is both
- `TRC-005` Given a parent in each of the four states When policy lint runs Then each state has its own code at its own level
- `TRC-006` Given a parent in each of the four states When approach summary runs Then it prints one line with the state
- `TRC-007` Given a cached parent that seen.yml holds no digest for When the parent state is read Then it is locally modified
- `TRC-008` Given a parent that is not cached When approach summary runs Then it prints the cause on wrapped lines and fetches nothing
- `TRC-009` Given a project with no git parent When approach summary runs Then it still prints three lines
- `TRC-010` Given a seen.yml that cannot be read When a command reads the parent state Then it counts as edited and no command crashes
- `TRC-011` Given a project compass.yml that cannot be read When approach summary runs Then it prints no traceback
- `TRC-012` Given a seen.yml whose digests entry is not a mapping When a parent is fetched Then the record is rewritten and nothing crashes

### parent-chains (landed 2026-10-08)

- `PC-1` A chain of two pinned parents loads furthest first
- `PC-2` A chain of three loads and a fourth is refused
- `PC-3` A commit named twice in a chain is a cycle
- `PC-4` Every parent in a chain is data only
- `PC-5` Effective names the nearest parent that wrote each field
- `PC-6` versions.yml lists every parent furthest first
- `PC-7` An uncached ancestor is refused by readers that do not fetch
- `PC-8` The docs describe the chain, the depth limit and the cycle code
- `PC-9` A parent's waiver answers to that parent's owner at every depth
