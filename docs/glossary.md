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

**Appears in:** `manifest.yml evidence[].id`, `gates[].evidence`, `verification-report.md`

**Related:** `quality-gate`, `evidence`

### `FU-`

Follow-up id. Work this issue deferred to ship fast and still owes - the hotfix's promoted scenario, a de-scoped artifact. Not "any outstanding work": a newly found defect gets its own issue named by slug. A follow-up may carry target_task, naming the issue whose ship it blocks.

**Refers to:** One piece of work this issue deferred and still owes.

**Appears in:** `manifest.yml follow_ups[].id`, `verification-report.md`

**Related:** `follow-up`, `definition-of-done`

### `INT-`

Intent id. The "why" end of the traceability chain - the outcome the work is meant to produce, sourced from intent.md's desired outcome, the UI contract, or the issue description. A goal, not a requirement; the requirement is the scenario.

**Refers to:** A stated desired outcome.

**Appears in:** `intent.md`, `acceptance-criteria.md`, `manifest.yml scenarios[].intent`

**Related:** `TRC`, `intent`

### `LP-`

Lesson proposal. A lesson held in `lessons-pending.yml` in the project's `.compass` folder until someone runs `compass lesson accept`. `compass retro --lessons` proposes, and the model is told to propose rather than add.

**Refers to:** One pending proposal.

**Appears in:** `lessons-pending.yml`, `compass lesson list`

**Related:** `LS`

### `LS-`

Lesson. One rule in `lessons.yml` in the project's `.compass` folder that a person in this project had to repeat, injected into later sessions when it applies always. `compass lesson` adds, lists and removes them.

**Not:** A guardrail or a routing rule. A lesson is advice: no check reads it, and a guardrail always wins over it.

**Refers to:** One lesson in the project's lessons file.

**Appears in:** `lessons.yml`, `compass lesson list`

**Related:** `LP`, `guardrail`

### `PX-`

Position exemption. One entry in `scan.position_exemptions` naming a position the vocabulary scan does not read - a source comment, a machine key - together with the reason a string in that position cannot reach a user. The scan reads every position by default, so a PX- entry is the only way a position is excluded.

**Not:** A surface exemption. `scan.exempt` names whole FILES the scan skips; a PX- entry names a POSITION within a file that is scanned.

**Refers to:** One position exemption: the positions it names, and the reason a string there cannot reach a user.

**Appears in:** governance/terminology.yml, tests/test_terminology.py

### `RG-`

The retired spelling of RP-. Kept in archived records, which keep the id that fired.

**Refers to:** A routing policy rule. Same referent as RP-.

**Appears in:** `.compass/work/ (archive)`

**Related:** `RP`

### `RP-`

Routing policy rule. One rule in routing-policy.yml that biases or constrains the computed delivery approach. RP-SHAPE and RP-ADV are soft - they bias the candidate. RP-FLOOR, RP-CAP, RP-GATE and RP-ROLE are hard - they constrain the result. RP-REQUIRE attaches a gate without raising a minimum.

**Not:** A guardrail. `guardrail` means one of the five hard rules cleared with evidence; a routing rule constrains which delivery approach you end up with. The prefix said RG- until 3.0.0, which is why this distinction needs stating.

**Refers to:** One rule in the routing policy.

**Appears in:** `routing-policy.yml`, `delivery-approach.md`, `manifest.yml policy_rules_fired[].id`

**Related:** `routing-policy`, `delivery-approach`, `guardrail`

### `RR-`

Review rule. One rule in governance/review-rules.yml that a reviewer applies to the files it names, with the incident that justifies it and what not to flag. `compass review-rule list` prints the rules that match a change.

**Not:** A routing policy rule (RP-), which shapes the delivery approach, or a guardrail, which is cleared with evidence. A review rule guides a reviewer's judgement of a change.

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

Sizing up incoming work: risk, familiarity, size, and goal - producing an issue type, labels, and a delivery approach. The human judgement step; everything after it is mechanism. Named for what it produces: the stage writes an `assessment:` block, the flag is --assessment, and the policy section is assessment_vocabulary.

**Not:** # vocabulary-scan: allow - naming the retired stage name is the point # of this field; the reader needs to know which word this replaced. NOT triage. Triage means sorting BETWEEN cases by urgency, which is what `compass flow` does across issues - this stage sizes up ONE piece of work. The retired command name was /compass:triage.

**Related:** `delivery-approach`, `label`, `issue-type`, `assessment`

### assessment

The four-dimension judgement the assess stage produces - risk, familiarity, size and goal, plus the domain labels. It is the only judgement field in the issue manifest; everything below it is computed from it deterministically.

**Not:** A choice of process. The assessment is read; `compass approach evaluate` computes the delivery approach from it.

**Related:** `assess`, `delivery-approach`, `router`

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

An issue type: a defect in existing behaviour, not live-urgent. Starts from a bug report; the failing reproduction test is written before the fix.

**Not:** A live incident, which is fixed through the hotfix delivery approach.

**Related:** `bug-report`, `issue-type`, `hotfix`

### bug-report

The intake for a bug fix: observed behaviour, expected behaviour, reproduction steps.

**Related:** `bug`

### canary

Releasing to a small slice of traffic/users first, watching SLIs.

**Related:** `rollout-plan`, `sli`

### capability

A named switch for new blocking behaviour, off in the shipped default.

**Related:** `lock`

### catalogue

One of the eight maps of configuration entries keyed by id: `dimensions`, `stages`, `approaches`, `rules`, `checks`, `gates`, `artifacts` and `vocabulary`. An id is stable; a display name lives in the `vocabulary` catalogue.

**Related:** `layer`, `overlay`, `generation`

### check

One test that Compass runs against an issue's work and reports as pass, fail or skipped. A guardrail is made of checks, a gate is cleared by evidence, and an obligation is anything the configuration asks for, such as a check, a gate, an artifact or a stage mode.

**Related:** `guardrail`, `quality-gate`, `evidence`, `obligation`

### classifier

The component that compares two configurations by their obligations.

**Related:** `obligation`, `lock`

### close-reason

Why an issue is done: completed (the work shipped), not-planned (it will not be built) or duplicate (another issue holds the work, and the record names it). Only completed counts as finished work.

**Related:** `workflow-state`, `issue`

### definition-of-done

The gate before shipping: acceptance criteria pass, applicable guardrails clear, every box backed by evidence.

**Also:** DoD

**Related:** `quality-gate`, `evidence`

### definition-of-ready

The gate between requirements and plan/implementation: acceptance criteria exist, ambiguities resolved, intent.md reviewed where one exists. Trivially satisfied for a quick fix.

**Also:** DoR

**Related:** `quality-gate`, `workflow-state`

### delivery-approach

The chosen shape for an issue: which artifacts exist, which gates apply, solo or parallel. Deterministic - same assessment plus same policy always gives the same approach.

**Related:** `assess`, `quality-gate`

### design

The DESIGNER's stage and its command, /compass:design. It produces the UI contract (ui-contract.md) - scenarios written Given/When/Then that flow into the acceptance criteria, not mockup annotations. The word reads as UI work to most people, which is why the designer has it.

**Not:** NOT the engineering design. That is the plan stage (/compass:plan), whose output is technical-design.md: the rule is that `design` names the UI contract and `plan` names the technical design, never the other way round. Also NOT the CLI verb: the placeholder scan is `compass plan lint`. Its retired spelling was kept as a hidden second name through 3.x and removed at 4.0.0 (ADR-024); it is now an unknown verb.

**Related:** `plan`, `technical-design`, `delivery-approach`

### design-doc

The high-level design (HLD): approach, system context, components, interfaces, data model, cross-cutting concerns - with sequence diagrams, named design patterns, and illustrative code where they add clarity.

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

### feature

An issue type: a self-contained change with its own acceptance criteria that does not warrant a full intent document. Unqualified "feature" always means this issue type.

**Not:** A feature file (the Gherkin artifact) - always say 'feature file'.

**Related:** `issue-type`, `feature-file`

### feature-file

A Gherkin file grouping the scenarios for one capability (the `Feature:` keyword). The extraction target for executable acceptance criteria.

**Not:** The feature issue type - unqualified 'feature' means the issue type.

**Related:** `scenario`, `step`, `acceptance-criteria`

### feature-flag

A runtime switch decoupling deploy from release.

**Related:** `rollout-plan`

### first-slice

The 80/20 cut recorded in intent.md: the slice of an initiative that ships first because it delivers most of the value, with what deliberately waits stated beside it. The design and the work breakdown follow the first slice, not the whole document.

**Related:** `intent`, `slice`, `initiative`

### follow-up

Work owed after an expedited ship (the hotfix's promoted scenario, the optional postmortem). Tracked with a state pair: outstanding (not yet discharged) and resolved. An issue with an outstanding follow-up does not fully close; `compass follow-up resolve` discharges one.

**Not:** v1 called this a 'backfill', with states 'owed' and 'paid'.

**Related:** `hotfix`, `backlog`

### generation

A stored, numbered copy of the resolved configuration that an issue runs against, so the issue keeps the rules it started with.

**Related:** `catalogue`, `layer`

### guardrail

A hard rule cleared with evidence; a failed guardrail stops the work. Few by design. Plain statement of the five: every change lands with a passing test that covers it; acceptance criteria exist before the code is written; every change traces to a stated reason; claims need evidence; a human signs off on the irreversible.

**Related:** `strategy`, `quality-gate`, `evidence`

### hotfix

A delivery approach for a live-incident fix, expedited: reproduce, fix, ship, then pay the follow-up (promote the reproduction into proper acceptance criteria; optional postmortem).

**Related:** `delivery-approach`, `incident`, `follow-up`, `postmortem`

### incident

The intake that triggers a hotfix: what broke in production, impact, severity. SRE sense of the word.

**Related:** `hotfix`, `postmortem`

### initiative

A body of work that delivers several outcomes across milestones and needs an intent document. Owns intent.md, the technical design, the first-slice (80/20) decision, and the rollout strategy.

**Not:** An epic, which is one outcome within one milestone under one intent.

**GitHub:** Project

**Related:** `epic`, `milestone`, `intent`, `slice`

### intent

Two related things, and the entry covers both deliberately. (1) The document: intent.md, the originator's statement of what is wanted and why, AUTHORED at the intake stage or INGESTED from a brief that already exists - it does not presume authorship. (2) The goal it carries: the outcome a change is meant to produce, the "why" end of the traceability chain, carrying the INT- ids that scenarios trace back to. The document holds the goals, which is why one name serves both. As a document it carries problem, users, goals, non-goals, success signals, constraints, open questions, and the first slice (the 80/20 cut) - iterated through review before the design is built. User stories are welcome inside it as a format; acceptance criteria are derived from them. As a goal it is sourced from intent.md's desired outcome, the UI contract, or the issue description - a goal, not a requirement: the functional requirement is the scenario.

**Not:** A restatement of the request. "Add a CSV export" is a request; "let finance self-serve" is the intent, and it may need filters and permissions the request never mentioned.

**Also:** The product owner's entry point, `/compass:intent`, captures it.

**Related:** `first-slice`, `scenario`, `traceability`

### issue

The atomic tracked unit of work: one assessed piece of work, one delivery approach, shipping as one PR or a small PR series. Carries a type, labels, and a workflow state.

**Not:** A 'task' used as another word for an issue - say issue. 'task' names one issue type.

**GitHub:** Issue

**Related:** `sub-issue`, `issue-type`, `label`, `workflow-state`

### issue-type

The kind of work an issue is: feature, bug or task. The delivery approach, not the type, decides which artifacts exist and which gates apply. A quick fix, a hotfix and a spike are not issue types: quick fix, hotfix and spike are delivery approaches. No manifest field records the type yet.

**GitHub:** Issue type

**Related:** `issue`, `feature`, `bug`, `task`, `assess`, `delivery-approach`, `label`

### label

A plain-word tag on an issue carrying classification and risk surface. Local-first (strings in the issue file); synced 1:1 with GitHub labels when connected. Labels never track workflow state.

**GitHub:** Label

**Related:** `label-rule`, `issue`

### label-rule

The deterministic consequence of a label, declared in policy: security/payments/personal-data/migration needs a security review, user-facing needs a rollout plan, breaking-change needs human sign-off, and ops-surface needs the operability section. Assess suggests labels, the human confirms; the rules then apply mechanically.

**Related:** `label`, `quality-gate`

### layer

One source of configuration: the shipped preset, a team parent, the project file or the issue. Layers merge in order, and each states only what it changes.

**Related:** `catalogue`, `overlay`, `preset`, `project-file`

### lld

Low-level design: optional per-component detail on initiative-scale work only. Empty is a valid state.

**Related:** `design-doc`

### lock

A mark on an entry that refuses a change from a lower layer that would loosen it, or that the classifier cannot compare. Tightening stays allowed.

**Related:** `waiver`, `classifier`

### manifest

The machine-readable file at the root of an issue directory, `.compass/work/<issue-slug>/manifest.yml`. It holds the assessment, the computed delivery approach, the stages and gates, the scenarios, the evidence registry and the changed files, and it points at the prose artifacts beside it. Every command reads it; `compass check` checks the guardrails against it.

**Not:** Not the prose artifacts it points at, and not "spine" - a metaphor that needed explaining each time it was used. A manifest is what a package.json, a Cargo.toml or a Kubernetes manifest is: a machine-readable list of what a thing contains.

**GitHub:** none

**Related:** `issue`, `evidence`, `scenario`, `acceptance-criteria`

### milestone

A release checkpoint, not a level in the work hierarchy: a coherent bundle of delivered issues with a review point. Every milestone leaves the system releasable.

**GitHub:** Milestone

**Related:** `initiative`, `issue`

### obligation

Anything the configuration asks for at an assessment: a stage mode, a check on an entry or exit list, a gate, an artifact, a checkpoint or a ceiling.

**Related:** `classifier`, `stage-mode`

### operability

The design section answering "what tells us this works in production?": the SLIs/SLOs the change affects, the alerts that watch them, runbook updates where the ops surface changes. Required by the ops-surface label rule; always present on initiatives.

**Related:** `sli`, `slo`, `runbook`

### overlay

A layer file that states only its differences from its parent, so it holds the changes and not a copy of the parent.

**Related:** `layer`, `preset`

### pin

The `#<sha>` suffix on a git `extends:`, which names the parent commit a project runs against.

**Related:** `layer`, `preset`

### plan

The engineering design stage: the command /compass:plan, the machine key `plan` in a manifest's stages block, the `plan-authoring` skill, the `planner` agent, and the CLI verb `compass plan lint`. Its output is technical-design.md.

**Not:** NOT a schedule or a project plan - Compass has no such artifact. NOT the delivery approach either, which is computed at the assess stage and recorded in delivery-approach.md. `plan.md` was this artifact's v1 filename and is retired; a name that was retired can come back for the thing it best describes.

**Related:** `technical-design`, `delivery-approach`, `design`

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

### quality-gate

A check that must pass before an issue moves state. Which gates apply depends on the issue type and labels.

**Related:** `workflow-state`, `definition-of-ready`, `definition-of-done`

### quick-fix

A delivery approach for a small, low-risk change on familiar ground. Produces a test and a PR - nothing else exists for it.

**Related:** `delivery-approach`

### receipt

The per-issue proof summary rendered from the manifest and the evidence registry: the assessment, the delivery approach, the gates and what cleared them - one screen, shareable as-is.

**Not:** Evidence - evidence is the typed records that clear gates; the receipt is the read-only summary that cites them.

**Related:** `evidence`, `quality-gate`

### requirements-review

The review pass that hardens requirements before plan or implementation: ambiguities resolved into recorded decisions, contradictions and gaps closed, intent.md reviewed where one exists. Satisfying it is # vocabulary-scan: allow - a note recording what v1 called this, which # is what someone reading an old record needs to look it up. what makes an issue ready. v1 called this "Clarify".

**Related:** `intent`, `definition-of-ready`, `acceptance-criteria`

### retrospective-signal

Compass's cross-issue self-check: is assess consistently over- or under-sizing the process? Advisory, surfaced in retro language. v1 called this "calibration".

**Related:** `dora-metrics`, `assess`

### rollback-plan

The recorded way back if the change misbehaves in production.

**Related:** `rollout-plan`

### rollout-plan

How the change reaches users safely: feature flags, canary or incremental rollout, and the rollback plan. Required by label rule on user-facing work; always present on initiatives.

**Related:** `feature-flag`, `canary`, `rollback-plan`

### router

The agent that runs assess: reads the four assessment dimensions, hands them to the CLI, and writes the delivery-approach record. It assesses; it does not choose a process. Named for what it does - Anthropic's platform docs call this shape "Routing", classifying input and directing it to a specialised path - and for the file it runs, routing-policy.yml.

**Not:** A decision-maker about process weight. The approach is computed from the assessment by `compass approach evaluate`, which is the determinism boundary.

**Related:** `assess`, `assessment`, `delivery-approach`

### runbook

Operational how-to for the service. Updated as an initiative-scale output when the ops surface changes.

**Related:** `operability`

### scenario

The atomic unit of acceptance: one behaviour, one Given/When/Then, one executable test. Everything traces to scenarios.

**Related:** `feature-file`, `step`, `acceptance-criteria`

### settings-key

A top-level key of `compass.yml` that configures the CLI instead of the process.

**Related:** `project-file`

### ship

Merging and releasing the change: the PR lands, follow-ups are # vocabulary-scan: allow - a note recording what v1 called this. recorded, the derived system spec is regenerated. v1 called this "Land".

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

### spike

A delivery approach for time-boxed exploration whose output is knowledge, not shipped code. Records the question, the timebox, and a conclusion: discard, graduate (a fresh issue owns any real work), or defer. Nothing ships from a spike.

**Related:** `delivery-approach`

### stage-mode

How a stage runs for an issue, such as `collapsed`. It is the `mode` field of a stage.

**Not:** Not the adoption setting, which is a separate key in the project file.

**Related:** `catalogue`

### step

A single Given/When/Then line, bound to a step definition in the project's codebase.

**Related:** `scenario`

### strategy

A strong default you can step off with a recorded reason. Assessed by a reviewer, never mechanically blocking. TDD and BDD are strategies; the outcomes they serve are guardrails.

**Related:** `guardrail`

### sub-issue

The breakdown unit within an issue or initiative. A slice is tracked as a sub-issue.

**GitHub:** Sub-issue

**Related:** `issue`, `slice`

### task

An issue type: work that changes nothing a user sees, such as upkeep, a refactor or a migration step.

**Not:** Another word for an issue. Any piece of tracked work is an issue; the type says what kind.

**Related:** `issue-type`, `issue`

### technical-design

The engineering plan for one issue: the approach, the design decisions as ADR-style notes, the governance check, and the independent work units. Written at the planning stage (/compass:plan) as technical-design.md.

**Not:** NOT the designer's work. That is the UI contract (ui-contract.md), from /compass:design. `design` alone named a command, an artifact, an artifact kind, a CLI verb and a role, and was the only overloaded word in this framework with no entry here. NEVER abbreviate this to TDD: in this repository TDD is red-green-refactor and nothing else.

**Related:** `technical-design`, `delivery-approach`

### traceability

The chain that makes a change accountable: code traces to a TRC- id, which traces to an INT- id. Maintained as the work happens, not reconstructed at the end. It is one of the five guardrails, and the thing the `TRC-` prefix is named after.

**Not:** A report produced at the end. A chain assembled after the fact records what someone remembered, not what happened.

**Related:** `scenario`, `intent`, `acceptance-criteria`

### waiver

A recorded departure from a parent's value, with a reason and an approver.

**Related:** `lock`

### workflow-state

The fixed semantic lifecycle Compass owns: backlog, ready, in-progress, in-review, done. Gates attach to the transitions; transitions are earned (evidence), not dragged. A person sets only backlog (a hold) and done (closed, with a close reason); Compass derives the other states from the issue's records. Board columns are a user-defined projection - every custom column maps to exactly one state.

**Related:** `quality-gate`, `board-column`, `blocked`, `close-reason`
