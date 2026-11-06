# Glossary

Every word and every id prefix Compass uses, with what it means.

**This page is generated** from `governance/terminology.yml`. Edit that
file, not this one - a drift guard fails the build if the two disagree.

## Codes

The short ids that appear in artifacts. If you have met one in a spec or
a pull request and wondered what it was, it is here.

### `ADR-`

Architecture decision record. A DD- promoted to a standing decision about the system rather than about one issue - it outlives the issue and constrains later ones.

**Refers to:** One numbered file under architecture/decisions/.

**Appears in:** `architecture/decisions/`

**Related:** `DD`

### `BF-`

The retired spelling of FU-. Still read by the Definition-of-Done tag parser so archived verification reports keep resolving.

**Refers to:** A follow-up. Same referent as FU-.

**Appears in:** `.compass/work/ (archive)`

**Related:** `FU`

### `CLM-`

Claim id. A public statement the product marketer intends to make. Every claim must trace to a passing scenario before the issue ships; the claims gate blocks on it.

**Refers to:** One planned public claim.

**Appears in:** `positioning.md`, `launch-readiness.md`, `manifest.yml claims[].id`

**Related:** `TRC`, `launch-readiness`

### `DD-`

Design decision. Numbered within one technical-design.md: what was chosen, what was rejected, and why. A decision with no alternative recorded is not yet a decision.

**Refers to:** One decision inside a single issue's technical design.

**Appears in:** `technical-design.md`

**Related:** `ADR`, `design`

### `EV-`

Evidence id. Identifies one typed record in the issue's evidence registry that clears a quality gate. One record can clear several gates. The accepted types are fixed by guardrails.yml; a gate that needs a mechanical type cannot be cleared with a written note.

**Refers to:** One typed evidence record.

**Appears in:** `manifest.yml evidence[].id`, `gates[].evidence`, `verification-report.md (archive)`

**Related:** `quality-gate`, `evidence`

### `FU-`

Follow-up id. Work this issue deferred to ship fast and still owes - the hotfix's promoted scenario, a de-scoped artifact. Not "any outstanding work": a newly found defect gets its own issue named by slug. A follow-up may carry target_task, naming the issue whose ship it blocks.

**Refers to:** One piece of work this issue deferred and still owes.

**Appears in:** `manifest.yml follow_ups[].id`, `verification-report.md (archive)`

**Related:** `follow-up`, `definition-of-done`

### `INT-`

Intent id. The "why" end of the traceability chain - the outcome the work is meant to produce, sourced from intent.md's desired outcome, the UI contract, or the issue description. A goal, not a requirement; the requirement is the scenario.

**Refers to:** A stated desired outcome.

**Appears in:** `intent.md`, `acceptance-criteria.md`, `manifest.yml scenarios[].intent`

**Related:** `TRC`, `intent`

### `LP-`

Lesson proposal. A lesson held in `lessons-pending.yml` in the project's `.compass` folder until someone runs `compass lesson accept`. The model is told to propose rather than add.

**Refers to:** One pending proposal.

**Appears in:** `lessons-pending.yml`, `compass lesson list`

**Related:** `LS`

### `LS-`

Lesson. One rule in `lessons.yml` in the project's `.compass` folder that a person in this project had to repeat, injected into later sessions when it applies always. `compass lesson` adds, lists and removes them. A lesson is advice: no check reads it, and a guardrail always wins over it.

**Refers to:** One lesson in the project's lessons file.

**Appears in:** `lessons.yml`, `compass lesson list`

**Related:** `LP`, `guardrail`

### `PX-`

Position exemption. One entry in `scan.position_exemptions` naming a position the vocabulary scan does not read - a source comment, a machine key - together with the reason a string in that position cannot reach a user. The scan reads every position by default, so a PX- entry is the only way a position is excluded. A PX- entry names a position within a file that is scanned; `scan.exempt` separately names whole files the scan skips.

**Refers to:** One position exemption: the positions it names, and the reason a string there cannot reach a user.

**Appears in:** governance/terminology.yml, tests/test_terminology.py

### `RG-`

The retired spelling of RP-. Kept in archived records, which keep the id that fired.

**Refers to:** A routing policy rule. Same referent as RP-.

**Appears in:** `.compass/work/ (archive)`

**Related:** `RP`

### `RP-`

Routing policy rule. One rule in routing-policy.yml that biases or constrains the computed delivery approach. RP-SHAPE and RP-ADV are soft - they bias the candidate. RP-FLOOR, RP-CAP, RP-GATE and RP-ART are hard - they constrain the result. RP-ART is an artifact rule: it reads the documents on disk, such as positioning.md or intent.md. RP-REQUIRE attaches a gate without raising a minimum. A routing rule constrains which delivery approach an issue ends up with; a guardrail is one of the five hard rules cleared with evidence.

**Refers to:** One rule in the routing policy.

**Appears in:** `routing-policy.yml`, `delivery-approach.md`, `manifest.yml policy_rules_fired[].id`

**Related:** `routing-policy`, `delivery-approach`, `guardrail`

### `RR-`

Review rule. One rule in governance/review-rules.yml that a reviewer applies to the files it names, with the incident that justifies it and what not to flag. `compass review-rule list` prints the rules that match a change. A review rule guides a reviewer's judgment of a change.

**Refers to:** One rule in the review rules file.

**Appears in:** `review-rules.yml`, `review findings`

**Related:** `RP`, `guardrail`

### `RS-`

The retired spelling of RP- for the soft rules. Same replacement, same reason.

**Refers to:** A routing policy rule. Same referent as RP-.

**Appears in:** `.compass/work/ (archive)`

**Related:** `RP`

### `SCN-`

The retired spelling of TRC-. Still present in shipped examples and read wherever TRC- is. TRC- is canonical because the parser's anchor is the literal keyword `traceability id:`, and because SCN- presumes every traced item is a Given/When/Then - a non-functional requirement can be traceable and testable without being a scenario.

**Refers to:** The traced item. Same referent as TRC-.

**Appears in:** `examples/`

**Related:** `TRC`

### `TRC-`

Traceability id. The join key of the traceability chain: code traces to a TRC- id, which traces to an INT- id. It names the chain, not one node on it - changed_files, claims, evidence records and Definition-of-Done tags all point at it.

**Refers to:** The traced item, normally a scenario.

**Appears in:** `acceptance-criteria.md`, `manifest.yml scenarios[].id`

**Related:** `INT`, `EV`, `SCN`

## Terms

### acceptance-criteria

The collective term: the set of scenarios for an issue. Executable where a BDD runner is configured.

**Related:** `scenario`, `definition-of-done`

### adr

Architecture decision record: one real decision, the alternatives considered, the consequences. Only written when there was a decision.

**Related:** `design-doc`

### assess

Sizing up incoming work: risk, familiarity, size, and goal - producing an issue type, labels, and a delivery approach. The human judgment step; everything after it is mechanism. Named for what it produces: the stage writes an `assessment:` block, the flag is --assessment, and the policy section is assessment_vocabulary. This stage sizes up one piece of work; `compass flow` sorts between issues by urgency.

**Related:** `delivery-approach`, `label`, `issue-type`, `assessment`

### assessment

The four-dimension judgment the assess stage produces - risk, familiarity, size and goal, plus the domain labels. It is the only judgment field in the issue manifest; everything below it is computed from it deterministically. The assessment is read; `compass approach evaluate` computes the delivery approach from it.

**Related:** `assess`, `delivery-approach`, `router`

### audience

The one line in an artifact's catalog entry that says who reads the document and what the reader decides from it. 9.0.0 removed the catalog from the live default (ADR-091); a frozen preset and a stored generation still hold it.

**Related:** `delivery-approach`, `technical-design`

### backlog

Two senses, both standard: the workflow state an issue starts in, and the list of deferred slices and follow-ups. Context disambiguates, as it does on every real team.

**Related:** `workflow-state`, `follow-up`

### blocked

A flag, not a state - an issue is blocked while in-progress or in-review. Carries a reason.

**Related:** `workflow-state`

### board-column

A user-defined view column (Design, UAT, Staging...). Maps to exactly one workflow state so gates keep firing regardless of board shape.

**GitHub:** Project column / status field

**Related:** `workflow-state`

### bug

An issue type: a defect in existing behavior, not live-urgent. Starts from a bug report; the failing reproduction test is written before the fix. A live incident is fixed through the hotfix delivery approach instead.

**Related:** `bug-report`, `issue-type`, `hotfix`

### bug-report

The intake for a bug fix: observed behavior, expected behavior, reproduction steps. Compass wrote it as bug-report.md until 9.0.0 removed the document (ADR-091).

**Related:** `bug`

### build

The path stage that records a red for each scenario, then the code, then a green. The guardrail `G1` (tested before it lands) is judged here. On an issue assessed before 9.0.0, the breakdown and implement stages show as build. A v1 manifest used the same word for the implement stage and still reads that way.

**Related:** `path`, `scenario`, `evidence`

### canary

Releasing to a small slice of traffic/users first, watching SLIs.

**Related:** `rollout-plan`, `sli`

### candidate

The build an outer-loop green ran against: a deployed build, named by its build id, or a local build, named by the tree id of the code it was built from. The record says which.

**Related:** `outer-loop`, `client-interface`

### capability

A named switch for new blocking behavior, off in the shipped default.

**Related:** `lock`

### catalog

One of the nine maps of configuration entries keyed by id: `dimensions`, `stages`, `approaches`, `rules`, `checks`, `gates`, `artifacts`, `readiness` and `vocabulary`. An id is stable; a display name lives in the `vocabulary` catalog.

**Also:** catalogue <!-- us-english-scan: allow - old term, read until 9.0.0 -->

**Related:** `layer`, `overlay`, `generation`

### check

One test that Compass runs against an issue's work and reports as pass, fail or skipped. A guardrail is made of checks, a gate is cleared by evidence, and an obligation is anything the configuration asks for, such as a check, a gate, an artifact or a stage mode.

**Related:** `guardrail`, `quality-gate`, `evidence`, `obligation`

### checkpoint-outcome

What happened at one checkpoint stage hand-off, recorded in the manifest's `checkpoint_outcomes` as the stage, the outcome, who and when. The outcome is `waited` when a person answered the hand-off with `compass evidence approve --checkpoint`, which also writes a `checkpoint-approval` record holding their answer, or `skipped` when an agent went on because the autonomy setting passed the hand-off, recorded with `compass issue checkpoint add`. A `checkpoint-approval` record clears no gate and no human check. `compass ship-commit` refuses a judged issue that lists a checkpoint with no outcome, and `compass issue diagnose` shows the outcomes of one issue.

**Related:** `decision-taken`, `evidence`, `issue`

### classifier

The component that compares two configurations by their obligations.

**Related:** `obligation`, `lock`

### client-interface

The interface a real client uses to reach the system under test, such as an API, a web interface or a command line. A protocol driver speaks to exactly one.

**Related:** `candidate`, `test-layer`

### close-reason

Why an issue is done: completed (the work shipped), not-planned (it will not be built) or duplicate (another issue holds the work, and the record names it). Only completed counts as finished work.

**Related:** `workflow-state`, `issue`

### decision-taken

A requirement decision an agent took for the person: the question, the resolution, which agent took it and at which stage. It is recorded in the manifest's `decisions_taken`, shown to the person at the next checkpoint on `balanced` and `controlled` autonomy, and confirmed as a set by one `compass evidence approve --decisions`. Changing one reopens it and the checkpoint keeps waiting. It is distinct from a decision record in `governance/decisions/`, which a person makes about the product.

**Related:** `requirements-review`, `evidence`

### definition-of-done

The gate before shipping: acceptance criteria pass, applicable guardrails clear, every box backed by evidence.

**Also:** DoD

**Related:** `quality-gate`, `evidence`

### definition-of-ready

The gate between requirements and plan/implementation: acceptance criteria exist, ambiguities resolved, the criteria checked against the intent. Trivially satisfied for a quick fix.

**Also:** DoR

**Related:** `quality-gate`, `workflow-state`

### delivery-approach

The chosen shape for an issue: the weight of each stage and the gates that apply, recorded in the manifest. Since 9.0.0 it names no documents (ADR-091). Deterministic - same assessment plus same policy always gives the same approach. `full` is the name of the heaviest delivery approach and is not a stage mode: its stages run `thorough`, and the old mode word `full` reads as `thorough` until 9.0.0.

**Related:** `assess`, `quality-gate`

### design

The DESIGNER's stage and its command, /compass:design. It produces the UI contract (ui-contract.md) - scenarios written Given/When/Then that flow into the acceptance criteria, not mockup annotations. The word reads as UI work to most people, which is why the designer has it. `design` names the UI contract and never the engineering design. Before 9.0.0 the engineering design was the plan stage (/compass:plan).

**Related:** `plan`, `technical-design`, `delivery-approach`

### design-doc

The high-level design (HLD): approach, system context, components, interfaces, data model, cross-cutting concerns - with sequence diagrams, named design patterns, and illustrative code where they add clarity. The technical design was Compass's HLD until 9.0.0 removed it (ADR-091).

**Also:** HLD

**Related:** `lld`, `adr`, `operability`

### dora-metrics

Lead time, deployment frequency, change failure rate, MTTR - what the process-impact telemetry measures to ask whether the process itself pays off.

**Related:** `retrospective-signal`

### epic

A group of related issues that deliver one outcome, within one milestone, under one intent. Larger than an issue and smaller than an initiative. Compass defines the word and no command or field records an epic yet.

**Related:** `issue`, `initiative`, `milestone`

### error-budget

The unreliability an SLO allows. Paces rollout speed on initiatives: budget spent means slow down.

**Related:** `slo`, `rollout-plan`

### evidence

A recorded, typed artifact that clears a gate: a test run, a review, a sign-off. A claim without evidence clears nothing.

**Related:** `guardrail`, `definition-of-done`

### evidence-required

The list in a path issue's manifest of the evidence the change needs before it ships, such as `scenarios`, `red-before-green` and `suite-green`. Assess computes it from the assessment and the configuration in force. The gates, the acceptance strategy block and the checkpoints come from it, and a manifest that has it is read as a path issue.

**Related:** `path`, `assess`, `evidence`, `quality-gate`

### feature

An issue type: a self-contained change with its own acceptance criteria that does not warrant a full intent document. Unqualified "feature" always means this issue type. The Gherkin artifact is always called a "feature file".

**Related:** `issue-type`, `feature-file`

### feature-file

A Gherkin file grouping the scenarios for one capability (the `Feature:` keyword). The extraction target for executable acceptance criteria.

**Related:** `scenario`, `step`, `acceptance-criteria`

### feature-flag

A runtime switch decoupling deploy from release.

**Related:** `rollout-plan`

### first-slice

The 80/20 cut that intent.md recorded until 9.0.0 removed that document (ADR-091): the slice of an initiative that ships first because it delivers most of the value, with what deliberately waits stated beside it. The design and the work breakdown follow the first slice, not the whole intent.

**Related:** `intent`, `slice`, `initiative`

### follow-up

Work owed after an expedited ship (the hotfix's promoted scenario, the optional postmortem). Tracked with a state pair: outstanding (not yet discharged) and resolved. An issue with an outstanding follow-up does not fully close; `compass follow-up resolve` discharges one.

**Related:** `hotfix`, `backlog`

### four-layer-acceptance-strategy

The strategy numbered `S17`. A change to behavior a real client can observe is accepted through four test layers: an executable specification in Given/When/Then, a domain-specific language that each line calls once, a protocol driver for one client interface, and the system under test. It applies unless the change's acceptance is of kind validation or refactor, and a project can turn it off with a recorded reason.

**Related:** `strategy`, `outer-loop`, `inner-loop`, `test-layer`

### generation

A stored, numbered copy of the resolved configuration that an issue runs against, so the issue keeps the rules it started with.

**Related:** `catalog`, `layer`

### guardrail

A hard rule cleared with evidence; a failed guardrail stops the work. Few by design. Plain statement of the five: every change lands with a passing test that covers it; acceptance criteria exist before the code is written; every change traces to a stated reason; claims need evidence; a human signs off on the irreversible.

**Related:** `strategy`, `quality-gate`, `evidence`

### hotfix

The setting `urgency: live-defect` on the assessment, for a fix to a defect that is live. It adds `reproduce-first` to the evidence required: the first scenario is the reproduction, and its red is recorded before anything else. It also adds the regression, security and Definition of Done evidence. After the ship, the follow-up promotes the reproduction into proper acceptance criteria, with an optional postmortem. Before 9.0.0 the hotfix was a delivery approach, and an issue assessed then keeps that approach.

**Related:** `evidence-required`, `incident`, `follow-up`, `postmortem`

### incident

The intake that triggers a hotfix: what broke in production, impact, severity. SRE sense of the word. Compass wrote it as incident.md until 9.0.0 removed the document (ADR-091).

**Related:** `hotfix`, `postmortem`

### initiative

A body of work that delivers several outcomes across milestones and needs an intent document. Owns intent.md, the technical design, the first-slice (80/20) decision, and the rollout strategy.

**GitHub:** Project

**Related:** `epic`, `milestone`, `intent`, `slice`

### inner-loop

The unit-level red, green, refactor loop of strategy `S2`, run inside the outer loop while the code that makes a scenario pass is written.

**Related:** `outer-loop`

### intent

The outcome a change is meant to produce: the "why" end of the traceability chain, carrying the INT- ids that scenarios trace back to. The originator states it - problem, users, outcome, constraints - AUTHORED at the intake stage or INGESTED from a brief that already exists, so it does not presume authorship. The define stage writes it into the Summary and Intent links of acceptance-criteria.md. Until 9.0.0 it was also a document, intent.md, which 9.0.0 removed (ADR-091); older issues still hold one, and Compass does not read it. An intent is a goal, not a requirement: the functional requirement is the scenario. It goes further than the request: "Add a CSV export" is a request; "let finance self-serve" is the intent, and it may need filters and permissions the request never mentioned.

**Also:** The product owner's entry point, `/compass:intent`, captures it.

**Related:** `first-slice`, `scenario`, `traceability`

### isolation-proof

A record, written only by its command, that the issue's acceptance tests passed when run in parallel and when each scenario's tests ran twice, so no scenario depends on another or on the order they run in.

**Related:** `layering-record`, `outer-loop`

### issue

The atomic tracked unit of work: one assessed piece of work, one delivery approach, shipping as one PR or a small PR series. Carries a type, labels, and a workflow state.

**GitHub:** Issue

**Related:** `sub-issue`, `issue-type`, `label`, `workflow-state`

### issue-page

The README of an issue's documents folder, `docs/compass/<created>-<slug>/README.md`, which `compass issue render` wrote from the issue's records until 9.0.0 removed it (ADR-091). An older archive can still hold one; nothing writes or reads it now.

**Related:** `rendered-block`, `project-index`

### issue-type

The kind of work an issue is: feature, bug or task. The delivery approach, not the type, decides which artifacts exist and which gates apply. A quick fix, a hotfix and a spike are not issue types: quick fix, hotfix and spike are delivery approaches. No manifest field records the type yet.

**GitHub:** Issue type

**Related:** `issue`, `feature`, `bug`, `task`, `assess`, `delivery-approach`, `label`

### item-record

A record in the manifest that meets an item of the Definition of Done or the Definition of Ready: evidence with `meets`, a person's approval of the check, a follow-up that `defers` it, or a page tick that `compass issue migrate` read from an older document. A command writes each one. An item with none of them is open.

**Related:** `definition-of-done`, `definition-of-ready`, `page-tick`

### label

A plain-word tag on an issue carrying classification and risk surface. Local-first (strings in the issue file). Compass writes them to the linked GitHub issue only when the project sets github_labels in compass.yml; with it off, no label leaves the issue file. Compass never reads a GitHub label back into the issue file. Domain labels never track workflow state. The status labels Compass writes do: status:<state>, and on close status:done with close:<reason>.

**GitHub:** Label

**Related:** `label-rule`, `issue`

### label-rule

The deterministic consequence of a label, declared in policy: security/payments/personal-data/migration needs a security review, user-facing needs a rollout plan, breaking-change needs human sign-off, and ops-surface needs the operability section. Assess suggests labels, the human confirms; the rules then apply mechanically.

**Related:** `label`, `quality-gate`

### layer

One source of configuration: the shipped preset, a team parent, the project file or the issue. Layers merge in order, and each states only what it changes.

**Related:** `catalog`, `overlay`, `preset`, `project-file`

### layering-record

A record, written only by its command, of the project's layering test: the test that checks each test layer calls only the layer below it. Compass reads the record and never the project's code.

**Related:** `isolation-proof`, `test-layer`

### lld

Low-level design: the signatures, contracts, file plan and tests of one work unit, in its own document, `low-level-design/U<n>.md`. The planner wrote one per unit of the technical design's Work units table until 9.0.0 removed both documents (ADR-091). Older issues still hold them.

**Related:** `design-doc`, `word_ceiling`

### lock

A mark on an entry that refuses a change from a lower layer that would loosen it, or that the classifier cannot compare. Tightening stays allowed.

**Related:** `waiver`, `classifier`

### manifest

The machine-readable file at the root of an issue directory, `.compass/work/<issue-slug>/manifest.yml`. It holds the assessment, the computed delivery approach, the stages and gates, the scenarios, the evidence registry and the changed files, and it points at the prose artifacts beside it. Every command reads it; `compass check` checks the guardrails against it. It is what a package.json, a Cargo.toml or a Kubernetes manifest is: a machine-readable list of what a thing contains.

**GitHub:** none

**Related:** `issue`, `evidence`, `scenario`, `acceptance-criteria`

### milestone

A release checkpoint, not a level in the work hierarchy: a coherent bundle of delivered issues with a review point. Every milestone leaves the system releasable.

**GitHub:** Milestone

**Related:** `initiative`, `issue`

### not-an-artifact-list

The file names and patterns in an issue's documents folder that are documents of no kind, such as `README.md` and the review briefs. The migrate leaves them in place, and `compass issue lint` does not report them. 9.0.0 removed the catalog from the live default (ADR-091); a frozen preset and a stored generation still hold it.

**Related:** `audience`, `sections`

### obligation

Anything the configuration asks for at an assessment: a stage mode, a check on an entry or exit list, a gate, an artifact, a checkpoint or a ceiling.

**Related:** `classifier`, `stage-mode`

### operability

The design section answering "what tells us this works in production?": the SLIs/SLOs the change affects, the alerts that watch them, runbook updates where the ops surface changes. Required by the ops-surface label rule; always present on initiatives.

**Related:** `sli`, `slo`, `runbook`

### outer-loop

The acceptance loop of the four-layer acceptance strategy: the scenarios fail before the code is written and then pass through a client interface against a named candidate. It wraps the inner loop.

**Related:** `inner-loop`, `candidate`, `client-interface`

### overlay

A layer file that states only its differences from its parent, so it holds the changes and not a copy of the parent.

**Related:** `layer`, `preset`

### page-tick

A ticked box that `compass issue migrate` read from a document written before the item records existed, kept in the manifest's `page_ticks`. The Definition of Done and Ready blocks count it as met. No other check reads it, so it is never an approval.

**Related:** `item-record`

### path

The four stages a delivery issue runs, in order: assess, specify, build and ship. The stages are fixed in code and have no modes, so the manifest of a path issue has no `stages:` map. A spike runs assess, build and ship. An issue assessed before 9.0.0 keeps its delivery approach and its stages, and each of its stages shows as a path stage.

**Related:** `assess`, `specify`, `build`, `ship`, `evidence-required`

### pin

The `#<sha>` suffix on a git `extends:`, which names the parent commit a project runs against.

**Related:** `layer`, `preset`

### plan

The machine key `plan` in an archived issue's stages block: the engineering design stage of the eight stages before 9.0.0. 9.0.0 removed the stage, its command /compass:plan and the `plan-authoring` skill (ADR-092); an archived issue keeps the key, and Compass reads it as the specify stage of the path. The stage wrote technical-design.md until 9.0.0 removed that document (ADR-091).

**Related:** `path`, `technical-design`, `design`

### postmortem

Blameless incident review - an optional follow-up artifact on a hotfix.

**Related:** `incident`, `follow-up`

### pr

The unit of landing code. Small, trunk-based PRs preferred.

**GitHub:** Pull request

**Related:** `issue`, `ship`

### preset

A named, versioned parent layer. `default` is the only preset Compass ships.

**Related:** `layer`, `overlay`

### project-file

`compass.yml` at the project root, the one file a person edits.

**Related:** `layer`, `settings-key`

### project-index

The README.md directly in the folder `docs/compass`, which listed every issue once, in a table for its state, until 9.0.0 removed the render (ADR-091). An older checkout can still hold one; nothing writes or reads it now. `compass board render` shows every issue.

**Related:** `rendered-block`, `issue-page`

### quality-gate

A check that must pass before an issue moves state. Which gates apply comes from the delivery approach and the label rules.

**Related:** `workflow-state`, `definition-of-ready`, `definition-of-done`

### quick-fix

`/compass:quick-fix`, the short form of `/compass:go` for a change the person already knows is small: start, red, finish. The evidence-required line says what the change owes. Before 9.0.0 the quick fix was a delivery approach for a small, low-risk change, and an issue assessed then keeps that approach.

**Related:** `path`, `evidence-required`, `delivery-approach`

### readiness-floor

The readiness signals whose `required_for_autonomous` is true. A project with every one of them present can run `autonomy: autonomous`.

**Related:** `readiness-signal`, `readiness-summary`

### readiness-record

The per-checkout file in which a project's readiness measurement is kept: each readiness signal's result and implementation version, when and at which commit it was measured, and the digest of the settings file. Compass never commits it.

**Related:** `readiness-signal`, `readiness-summary`

### readiness-signal

One binary fact about a repository, such as "a lint command is declared and exits 0". An entry of the `readiness` catalog, it is either `present` or `absent` and carries a one-line reason.

**Related:** `readiness-floor`, `readiness-record`, `catalog`

### readiness-summary

The `readiness:` key of an issue's manifest, written by every `approach evaluate --write`: the score, whether the floor is met and which signals are absent, or `not-measured` with the reason. It sits outside the generation's digests.

**Related:** `readiness-record`, `readiness-floor`

### receipt

The one-screen summary of an issue that `compass issue receipt` printed until 9.0.0 removed it (ADR-091): the assessment, the delivery approach, the gates and the evidence that cleared them. Older records and decision records still name it. `compass approach show` lists an issue's gates and `compass check` judges its evidence.

**Related:** `evidence`, `quality-gate`

### rendered-block

The lines between `<!-- compass:render KIND -->` and `<!-- /compass:render -->` in an issue's document, which `compass issue render` wrote from the manifest and the evidence until 9.0.0 removed it (ADR-091). A document written before then can still hold them, so every digest of a document and every reader of its text leaves the lines inside a block out. Nothing writes or checks a block now.

**Related:** `issue-page`, `verification-note`, `project-index`, `item-record`

### required-when

A condition in an artifact's catalog entry. The document is owed only when the condition holds. The one condition was a minimum number of subtasks, so the distribution map was owed from two subtasks. 9.0.0 removed the catalog from the live default (ADR-091); a frozen preset and a stored generation still hold it.

**Related:** `audience`, `delivery-approach`

### requirements-review

The review pass that hardens requirements before plan or implementation: ambiguities resolved into recorded decisions, contradictions and gaps closed, the criteria checked against the intent. Satisfying it is what makes an issue ready. It wrote requirements-review.md until 9.0.0 removed that document (ADR-091); the decisions and the Definition of Ready items are its record now.

**Related:** `intent`, `definition-of-ready`, `acceptance-criteria`

### retrospective-signal

Compass's cross-issue self-check: is assess consistently over- or under-sizing the process? Advisory, surfaced in retro language.

**Related:** `dora-metrics`, `assess`

### review-round

One review of an issue's work by a reviewer who did not write it. Rounds count from 1. Until 9.0.0 each round was its own document, `review-<n>.md`, and its own entry in the artifact registry; 9.0.0 removed both (ADR-091).

**Related:** `requirements-review`, `audience`

### rollback-plan

The recorded way back if the change misbehaves in production. Compass owed one as rollback-plan.md on migrations work until 9.0.0 removed the document and its rule (ADR-091).

**Related:** `rollout-plan`

### rollout-plan

How the change reaches users safely: feature flags, canary or incremental rollout, and the rollback plan. Required by label rule on user-facing work; always present on initiatives.

**Related:** `feature-flag`, `canary`, `rollback-plan`

### router

The agent that runs assess: reads the four assessment dimensions, hands them to the CLI, and records the delivery approach in the manifest. It assesses; it does not choose a process. Named for what it does - Anthropic's platform docs call this shape "Routing", classifying input and directing it to a specialized path - and for the file it runs, routing-policy.yml. The approach is computed from the assessment by `compass approach evaluate`, which is the determinism boundary.

**Related:** `assess`, `assessment`, `delivery-approach`

### runbook

Operational how-to for the service. Updated as an initiative-scale output when the ops surface changes.

**Related:** `operability`

### scenario

The atomic unit of acceptance: one behavior, one Given/When/Then, one executable test. Everything traces to scenarios.

**Related:** `feature-file`, `step`, `acceptance-criteria`

### sections

The headings of an artifact's document, in order, for each depth the document can be written at (`lightweight` and `thorough`). It is a field of the artifact's catalog entry. A document that is one rendered block has an empty list. The acceptance criteria are read through the last shipped catalog when the configuration declares none. 9.0.0 removed the catalog from the live default (ADR-091); a frozen preset and a stored generation still hold it.

**Related:** `audience`, `rendered-block`

### settings-key

A top-level key of `compass.yml` that configures the CLI instead of the process.

**Related:** `project-file`

### ship

Merging and releasing the change: the PR lands, follow-ups are recorded and the issue is marked done.

**Related:** `pr`, `rollout-plan`

### sli

Service level indicator - a measured signal of service health (latency, error rate, availability).

**Related:** `slo`, `operability`

### slice

An independently shippable vertical cut of a feature or initiative, with its own acceptance criteria and its own PR. The bar: every slice leaves the system releasable.

**Related:** `sub-issue`, `milestone`

### slo

Service level objective - the target an SLI must meet. Implies an error budget.

**Related:** `sli`, `error-budget`

### specify

The path stage that writes the scenarios, in `acceptance-criteria.md` or a `.feature` file, and declares the test for each one. The guardrails `G2` (acceptance defined before it is built) and `G3` (traceability holds) are judged here. On an issue assessed before 9.0.0, the define, refine and plan stages show as specify. A v1 manifest used the same word for the define stage and still reads that way.

**Related:** `path`, `scenario`, `acceptance-criteria`

### spike

A delivery approach for time-boxed exploration whose output is knowledge, not shipped code. Records the question, the timebox, and a conclusion: discard, graduate (a fresh issue owns any real work), or defer. Nothing ships from a spike.

**Related:** `delivery-approach`

### stage-mode

How a stage runs for an issue, such as `collapsed`. It is the `mode` field of a stage.

**Related:** `catalog`

### stands-for

The name the industry uses for the kind of document an artifact is, such as `hld` for the technical design. It is a field of the artifact's catalog entry. 9.0.0 removed the catalog from the live default (ADR-091); a frozen preset and a stored generation still hold it.

**Related:** `audience`, `technical-design`

### step

A single Given/When/Then line, bound to a step definition in the project's codebase.

**Related:** `scenario`

### strategy

A strong default you can step off with a recorded reason. Most are assessed by a reviewer. A strategy can carry blocking checks that a recorded step-off makes advisory; they sit outside every guardrail. TDD and BDD are strategies; the outcomes they serve are guardrails.

**Related:** `guardrail`, `four-layer-acceptance-strategy`

### sub-issue

The breakdown unit within an issue or initiative. A slice is tracked as a sub-issue.

**GitHub:** Sub-issue

**Related:** `issue`, `slice`

### task

An issue type: work that changes nothing a user sees, such as upkeep, a refactor or a migration step. Any piece of tracked work is an issue; the type says what kind.

**Related:** `issue-type`, `issue`

### technical-design

The engineering plan for one issue: the approach, the design decisions as ADR-style notes, the governance check, and the independent work units. The planning stage (/compass:plan) wrote it as technical-design.md until 9.0.0 removed the document (ADR-091) and the stage (ADR-092). Older issues still hold one. The designer's work is the UI contract (ui-contract.md), from /compass:design. In this repository TDD is red-green-refactor and nothing else, so this artifact is never abbreviated to TDD.

**Related:** `technical-design`, `delivery-approach`

### temporary-worktree

The detached Git worktree of HEAD that a readiness measurement creates in the system temp folder to run the project's commands. It is removed when the measurement ends.

**Related:** `readiness-record`

### test-layer

One of the four layers of the four-layer acceptance strategy: specification, domain-specific language, protocol driver or system under test. The word `layer` alone names a configuration source.

**Related:** `four-layer-acceptance-strategy`, `layer`, `layering-record`

### traceability

The chain that makes a change accountable: code traces to a TRC- id, which traces to an INT- id. Maintained as the work happens, not reconstructed at the end. It is one of the five guardrails, and the thing the `TRC-` prefix is named after.

**Related:** `scenario`, `intent`, `acceptance-criteria`

### verification-note

A quick fix's one-screen record of what was checked: the scenario, its test, the red and green records, each gate with its status and the files changed. It was one rendered block, which `compass quick-fix finish` wrote and approved until 9.0.0 removed it (ADR-091). An older quick fix still holds one.

**Related:** `rendered-block`, `quick-fix`

### voluntary-kind

A document kind that no delivery approach, rule or `every_approach` flag names, so nothing owes it. A person registered it when it was written, and a reassessment never superseded it. `review` was one. 9.0.0 removed document registration (ADR-091).

**Related:** `required-when`, `review-round`

### waiver

A recorded departure from a parent's value, with a reason and an approver.

**Related:** `lock`

### word_ceiling

The word limit a document kind carried in the artifacts catalog, per depth, such as 4,000 words for a thorough technical design. Words were counted from the visible text only: rendered blocks and HTML comments did not count. The check `design-within-word-ceiling` refused a technical design over 1.5 times its limit until 9.0.0 removed the check and the live catalog (ADR-091). A frozen preset and a stored generation still hold the limits.

**Related:** `lld`, `design-doc`

### workflow-state

The fixed semantic lifecycle Compass owns: backlog, ready, in-progress, in-review, done. Gates attach to the transitions; transitions are earned (evidence), not dragged. A person sets only backlog (a hold) and done (closed, with a close reason); Compass derives the other states from the issue's records. Board columns are a user-defined projection - every custom column maps to exactly one state.

**Related:** `quality-gate`, `board-column`, `blocked`, `close-reason`
