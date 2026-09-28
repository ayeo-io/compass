<!-- DERIVED FILE - do not hand-edit; `compass _derive-system-spec` rebuilds it from the scenarios in each landed issue's manifest.yml - edit the scenario there and in the issue's acceptance-criteria.md -->

# System Specification (derived)

> `compass _derive-system-spec` builds this file from the `scenarios:` block of each landed issue's `.compass/work/<slug>/manifest.yml`.
> **Do not hand-edit** - the next derivation overwrites it.
> Edit the source: the scenario in that manifest, and its prose in the issue's `acceptance-criteria.md` under `docs/compass/<created>-<slug>/`.

## Current Behaviour

### the parser still reads the retired tag

- **Scenario id:** `GL-E2`
- **Intent:** `DOC-DRIFT`
- **Source issue:** `id-prefix-vocabulary-and-glossary`
- **Landed:** 2026-08-13

### the guard can fail on each new surface

- **Scenario id:** `SS-4`
- **Intent:** `GAP-1`
- **Source issue:** `scan-the-remaining-surfaces`
- **Landed:** 2026-08-13

### the archive still lints and checks clean

- **Scenario id:** `SW-4`
- **Intent:** `HYGIENE`
- **Source issue:** `stale-active-issue-sweep`
- **Landed:** 2026-08-13

### A same-size edit in the same second changes the tree id

- **Scenario id:** `TSE-1`
- **Intent:** `INT-1`
- **Source issue:** `tree-id-misses-a-same-second-edit`
- **Landed:** 2026-09-25

### Backward-compat - guardrail count and gate set unchanged by S6

- **Scenario id:** `TRC-R10-6`
- **Intent:** `INT-10`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### A multiagent issue must record its run

- **Scenario id:** `DPR-1`
- **Intent:** `INT-2`
- **Source issue:** `dispatch-protocol`
- **Landed:** 2026-09-25

### The scripts find an issue's documents through the registry

- **Scenario id:** `DPR-2`
- **Intent:** `INT-3`
- **Source issue:** `dispatch-protocol`
- **Landed:** 2026-09-25

### A staged map is provisioned one wave at a time

- **Scenario id:** `DPR-3`
- **Intent:** `INT-4`
- **Source issue:** `dispatch-protocol`
- **Landed:** 2026-09-25

### Only ship-commit marks an issue landed

- **Scenario id:** `DPR-7`
- **Intent:** `INT-5`
- **Source issue:** `dispatch-protocol`
- **Landed:** 2026-09-25

### the hook still blocks a code file inside the project

- **Scenario id:** `FF-2`
- **Intent:** `INT-57`
- **Source issue:** `field-feedback-hook-scope-and-restage`
- **Landed:** 2026-08-14

### the issue's artifact directory is still re-staged

- **Scenario id:** `FF-4`
- **Intent:** `INT-58`
- **Source issue:** `field-feedback-hook-scope-and-restage`
- **Landed:** 2026-08-14

### Run 1 is recorded

- **Scenario id:** `DPR-6`
- **Intent:** `INT-6`
- **Source issue:** `dispatch-protocol`
- **Landed:** 2026-09-25

### A budget overrun is a finding

- **Scenario id:** `OLH-4`
- **Intent:** `INT-7`
- **Source issue:** `orchestrator-loop-hardening`
- **Landed:** 2026-09-25

### The agent and skill prose state each adopted rule

- **Scenario id:** `OLH-7`
- **Intent:** `INT-8`
- **Source issue:** `orchestrator-loop-hardening`
- **Landed:** 2026-09-25

### compass gate pass is the shared R6/R9 command and is schema-valid

- **Scenario id:** `TRC-R9-7`
- **Intent:** `INT-9`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### the identifier check can fail

- **Scenario id:** `TRC-A4`
- **Intent:** `INT-F0`
- **Source issue:** `identifiers-and-vocabulary-in-printed-output`
- **Landed:** 2026-08-13

### the spine keys and the computed approach are unchanged

- **Scenario id:** `TRC-B3`
- **Intent:** `INT-F1`
- **Source issue:** `identifiers-and-vocabulary-in-printed-output`
- **Landed:** 2026-08-13

### neither receipt branch calls a routing rule a guardrail

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-F2`
- **Source issue:** `identifiers-and-vocabulary-in-printed-output`
- **Landed:** 2026-08-13

### a real pass is not miscounted

- **Scenario id:** `TRC-D2`
- **Intent:** `INT-F5`
- **Source issue:** `identifiers-and-vocabulary-in-printed-output`
- **Landed:** 2026-08-13

### a shared policy-rule effect is printed once

- **Scenario id:** `TRC-E1`
- **Intent:** `INT-F8`
- **Source issue:** `identifiers-and-vocabulary-in-printed-output`
- **Landed:** 2026-08-13

### the widened scan can fail in the newly covered position

- **Scenario id:** `TRC-D3`
- **Intent:** `INT-R2`
- **Source issue:** `dry-run-2-rulings`
- **Landed:** 2026-08-14

### an uncapped approach permits more than one stream

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-R3`
- **Source issue:** `dry-run-2-rulings`
- **Landed:** 2026-08-14

### a failing check summary keeps its denominator

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-R4`
- **Source issue:** `dry-run-2-rulings`
- **Landed:** 2026-08-14

### an ordinary test still resolves

- **Scenario id:** `TRC-C3`
- **Intent:** `INT-R5`
- **Source issue:** `dry-run-2-rulings`
- **Landed:** 2026-08-14

### the cucumber-js adapter declares no vulnerable uuid dependency

- **Scenario id:** `CU-1`
- **Intent:** `INT-SEC`
- **Source issue:** `cucumber-13-drops-vulnerable-uuid`
- **Landed:** 2026-08-14

### no obscure word appears in user-facing text

- **Scenario id:** `FF-5`
- **Intent:** `INT-WORD`
- **Source issue:** `field-feedback-hook-scope-and-restage`
- **Landed:** 2026-08-14

### traceability, intent and navigator are defined

- **Scenario id:** `GL-A1`
- **Intent:** `MISSING-TERMS`
- **Source issue:** `id-prefix-vocabulary-and-glossary`
- **Landed:** 2026-08-13

### compass terminology renders a code

- **Scenario id:** `GL-C3`
- **Intent:** `NO-CODE-DICTIONARY`
- **Source issue:** `id-prefix-vocabulary-and-glossary`
- **Landed:** 2026-08-13

### the new guard can fail

- **Scenario id:** `RR-7`
- **Intent:** `PRACTICE`
- **Source issue:** `rehearsal-recordings`
- **Landed:** 2026-08-13

### a genuine triage-has-not-run still says so

- **Scenario id:** `RCD-A4`
- **Intent:** `REH-1`
- **Source issue:** `rehearsal-cli-defects`
- **Landed:** 2026-08-13

### the not-found message names the path actually used

- **Scenario id:** `RCD-B2`
- **Intent:** `REH-2`
- **Source issue:** `rehearsal-cli-defects`
- **Landed:** 2026-08-13

### a genuinely missing test still fails the check

- **Scenario id:** `RCD-C3`
- **Intent:** `REH-3`
- **Source issue:** `rehearsal-cli-defects`
- **Landed:** 2026-08-13

### an unrelated staged file is still refused

- **Scenario id:** `RCD-D2`
- **Intent:** `REH-5`
- **Source issue:** `rehearsal-cli-defects`
- **Landed:** 2026-08-13

### compass check's header names the computed approach

- **Scenario id:** `RCD-E1`
- **Intent:** `REH-6`
- **Source issue:** `rehearsal-cli-defects`
- **Landed:** 2026-08-13

### the guard can fail

- **Scenario id:** `EX-4`
- **Intent:** `REVIEW`
- **Source issue:** `consolidate-trc-and-scn-prefixes`
- **Landed:** 2026-08-13

### the Part 0 corrections are folded in

- **Scenario id:** `RR-3`
- **Intent:** `RULE-2`
- **Source issue:** `rehearsal-recordings`
- **Landed:** 2026-08-13

### the token figures are filed with their caveat and stay internal

- **Scenario id:** `RR-4`
- **Intent:** `RULE-3`
- **Source issue:** `rehearsal-recordings`
- **Landed:** 2026-08-13

### the cold-reader test heads the next cycle's experiment list

- **Scenario id:** `RR-5`
- **Intent:** `RULE-4`
- **Source issue:** `rehearsal-recordings`
- **Landed:** 2026-08-13

### the version is consistent across every location

- **Scenario id:** `RCD-H1`
- **Intent:** `RULE-5`
- **Source issue:** `rehearsal-cli-defects`
- **Landed:** 2026-08-13

### the label guard cannot pass on a partial list

- **Scenario id:** `SR-2`
- **Intent:** `RULE-S1`
- **Source issue:** `strategy-rulings-2026-08`
- **Landed:** 2026-08-13

### conventional commits is a project strategy only

- **Scenario id:** `SR-3`
- **Intent:** `RULE-S2`
- **Source issue:** `strategy-rulings-2026-08`
- **Landed:** 2026-08-13

### semantic versioning is stated

- **Scenario id:** `SR-4`
- **Intent:** `RULE-S3`
- **Source issue:** `strategy-rulings-2026-08`
- **Landed:** 2026-08-13

### prefer-open-technologies is filed, not adopted

- **Scenario id:** `SR-5`
- **Intent:** `RULE-S4`
- **Source issue:** `strategy-rulings-2026-08`
- **Landed:** 2026-08-13

### S7 names the surfaces it governs

- **Scenario id:** `SR-6`
- **Intent:** `RULE-S5`
- **Source issue:** `strategy-rulings-2026-08`
- **Landed:** 2026-08-13

### the hooks directory is a scanned surface

- **Scenario id:** `RCD-G3`
- **Intent:** `SWEEP`
- **Source issue:** `rehearsal-cli-defects`
- **Landed:** 2026-08-13

### the archive keeps the id that fired

- **Scenario id:** `GL-D3`
- **Intent:** `WRONG-PREFIX`
- **Source issue:** `id-prefix-vocabulary-and-glossary`
- **Landed:** 2026-08-13

---

## Archived Behaviour

> These scenarios were superseded by a later-landed scenario with the same intent id.

### every version location carries 3.3.0 and the suite is green _(archived)_

- **Scenario id:** `TRC-001`
- **Intent:** `INT-1`
- **Source issue:** `release-3-3-0`
- **Landed:** 

### the hook blocks an edit it cannot check _(archived)_

- **Scenario id:** `TRC-1`
- **Intent:** `INT-1`
- **Source issue:** `hook-fails-open-on-broken-vendor`
- **Landed:** 

### Every published version surface reports 1.0.0 _(archived)_

- **Scenario id:** `TRC-1`
- **Intent:** `INT-1`
- **Source issue:** `version-bump-1-0-0`
- **Landed:** 

### the hook says why it could not check _(archived)_

- **Scenario id:** `TRC-2`
- **Intent:** `INT-2`
- **Source issue:** `hook-fails-open-on-broken-vendor`
- **Landed:** 

### control: the hook still blocks when it can read the spine _(archived)_

- **Scenario id:** `TRC-3`
- **Intent:** `INT-1`
- **Source issue:** `hook-fails-open-on-broken-vendor`
- **Landed:** 

### the guarded-surface decision fails closed too _(archived)_

- **Scenario id:** `TRC-4`
- **Intent:** `INT-1`
- **Source issue:** `hook-fails-open-on-broken-vendor`
- **Landed:** 

### each runner should have a worked project _(archived)_

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `bdd-adapters-and-skill-length`
- **Landed:** 

### the entry point should be thin _(archived)_

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `cli-module-split`
- **Landed:** 

### system-context.md exists with the canonical sections _(archived)_

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `compass-self-architecture`
- **Landed:** 

### Frame loads architecture/ into the task's working context _(archived)_

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### extraction should produce a feature file a BDD runner can read _(archived)_

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### the shipped governance should declare a version that has moved _(archived)_

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `governance-drift-detection`
- **Landed:** 

### a stale derived spec should fail a check _(archived)_

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `living-spec-and-process-impact`
- **Landed:** 

### the skill should state a method, in order _(archived)_

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `phase-2-skills-check-and-cli-split`
- **Landed:** 

### the template set carries the v2 names plus the two new intake templates _(archived)_

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `v2-artifact-renames`
- **Landed:** 

### the strategy records permanence and the calibration sample _(archived)_

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `voice-audition-standing`
- **Landed:** 

### each adapter should run the extracted feature and pass _(archived)_

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `bdd-adapters-and-skill-length`
- **Landed:** 

### the modules should follow the groupings the code already had _(archived)_

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `cli-module-split`
- **Landed:** 

### relations.md documents the call graph between framework components _(archived)_

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `compass-self-architecture`
- **Landed:** 

### Frame degrades gracefully when architecture/ is absent _(archived)_

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### extraction should be byte-for-byte deterministic _(archived)_

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### changing governance content without bumping its version should fail _(archived)_

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `governance-drift-detection`
- **Landed:** 

### a current derived spec should pass _(archived)_

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `living-spec-and-process-impact`
- **Landed:** 

### three failed fixes should send the engineer back to Frame _(archived)_

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `phase-2-skills-check-and-cli-split`
- **Landed:** 

### the resolver prefers v2 names and accepts v1 _(archived)_

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `v2-artifact-renames`
- **Landed:** 

### the strategy states its own test and its own failure mode _(archived)_

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `voice-audition-standing`
- **Landed:** 

### every adapter should share the same four documented steps _(archived)_

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `bdd-adapters-and-skill-length`
- **Landed:** 

### the package should import cleanly on its own _(archived)_

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `cli-module-split`
- **Landed:** 

### ownership.md documents what each component must and must not do _(archived)_

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `compass-self-architecture`
- **Landed:** 

### compass adr new <slug> creates a numbered ADR file _(archived)_

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### each extracted scenario should carry its traceability id as a tag _(archived)_

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### a project behind the framework's governance version should be told _(archived)_

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `governance-drift-detection`
- **Landed:** 

### the committed spec should cover every landed task _(archived)_

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `living-spec-and-process-impact`
- **Landed:** 

### the skill should be reachable from where the failure happens _(archived)_

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `phase-2-skills-check-and-cli-split`
- **Landed:** 

### readers resolve both naming generations of issue directories _(archived)_

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `v2-artifact-renames`
- **Landed:** 

### the tag selector should know every shipped runner _(archived)_

- **Scenario id:** `TRC-A4`
- **Intent:** `INT-1`
- **Source issue:** `bdd-adapters-and-skill-length`
- **Landed:** 

### Compass ships templates for the architecture artifacts _(archived)_

- **Scenario id:** `TRC-A4`
- **Intent:** `INT-1`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### the extracted Feature should name the task it came from _(archived)_

- **Scenario id:** `TRC-A4`
- **Intent:** `INT-1`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### extracted runnable Gherkin is named acceptance-criteria.feature _(archived)_

- **Scenario id:** `TRC-A4`
- **Intent:** `INT-1`
- **Source issue:** `v2-artifact-renames`
- **Landed:** 

### invariants.yml is loaded by mechanism when present _(archived)_

- **Scenario id:** `TRC-A5`
- **Intent:** `INT-1`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### extraction should resolve the current task when none is named _(archived)_

- **Scenario id:** `TRC-A5`
- **Intent:** `INT-1`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### repository validation knows the v2 template inventory _(archived)_

- **Scenario id:** `TRC-A5`
- **Intent:** `INT-1`
- **Source issue:** `v2-artifact-renames`
- **Landed:** 

### Frame proceeds normally when invariants.yml is absent _(archived)_

- **Scenario id:** `TRC-A5b`
- **Intent:** `INT-1`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### the new verb should appear in the documented CLI surface _(archived)_

- **Scenario id:** `TRC-A6`
- **Intent:** `INT-1`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### a configured features directory should override the default location _(archived)_

- **Scenario id:** `TRC-A7`
- **Intent:** `INT-1`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### the shipped config template should document the new keys _(archived)_

- **Scenario id:** `TRC-A8`
- **Intent:** `INT-2`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### every adapter should be exercised by a CI job _(archived)_

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-2`
- **Source issue:** `bdd-adapters-and-skill-length`
- **Landed:** 

### the public verb surface should be identical _(archived)_

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-2`
- **Source issue:** `cli-module-split`
- **Landed:** 

### architecture/decisions/ contains an ADR per principle (clustered or 1:1) _(archived)_

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-2`
- **Source issue:** `compass-self-architecture`
- **Landed:** 

### /compass:roundtable can convene the architect-lens _(archived)_

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-2`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### the reference adapter should run an extracted feature end to end _(archived)_

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-2`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### missing floors and strategies should be named individually _(archived)_

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-1`
- **Source issue:** `governance-drift-detection`
- **Landed:** 

### the generator should normalise house style on write _(archived)_

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-2`
- **Source issue:** `living-spec-and-process-impact`
- **Landed:** 

### a suggestion should be checked against the code before it is acted on _(archived)_

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-2`
- **Source issue:** `phase-2-skills-check-and-cli-split`
- **Landed:** 

### the reviewer's clarity dimension finds the audition without knowing it exists _(archived)_

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-1`
- **Source issue:** `voice-audition-standing`
- **Landed:** 

### an adapter whose runner is absent should skip loudly, never silently pass _(archived)_

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-2`
- **Source issue:** `bdd-adapters-and-skill-length`
- **Landed:** 

### the whole test suite should pass unchanged _(archived)_

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-2`
- **Source issue:** `cli-module-split`
- **Landed:** 

### ADRs follow the template structure (frontmatter + 5 sections) _(archived)_

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-2`
- **Source issue:** `compass-self-architecture`
- **Landed:** 

### Spec-author consults the architect-lens for boundary-touching tasks _(archived)_

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-2`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### the adapter README should show every step of the wire-up _(archived)_

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-2`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### missing guardrail checks should be named individually _(archived)_

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-1`
- **Source issue:** `governance-drift-detection`
- **Landed:** 

### the derived file should pass the repository's own style test _(archived)_

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-2`
- **Source issue:** `living-spec-and-process-impact`
- **Landed:** 

### the skill should shape disagreement rather than forbid it _(archived)_

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-2`
- **Source issue:** `phase-2-skills-check-and-cli-split`
- **Landed:** 

### loading the CLI by file path should still work _(archived)_

- **Scenario id:** `TRC-B3`
- **Intent:** `INT-2`
- **Source issue:** `cli-module-split`
- **Landed:** 

### architecture/decisions/README.md is a usable index _(archived)_

- **Scenario id:** `TRC-B3`
- **Intent:** `INT-2`
- **Source issue:** `compass-self-architecture`
- **Landed:** 

### Plan flags new service interactions for architect review _(archived)_

- **Scenario id:** `TRC-B3`
- **Intent:** `INT-2`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### a scenario with no step definition should fail loudly _(archived)_

- **Scenario id:** `TRC-B3`
- **Intent:** `INT-2`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### a waived rule should read as deliberate, not as drift _(archived)_

- **Scenario id:** `TRC-B3`
- **Intent:** `INT-2`
- **Source issue:** `governance-drift-detection`
- **Landed:** 

### the skill should be short enough to be read at the moment of use _(archived)_

- **Scenario id:** `TRC-B3`
- **Intent:** `INT-2`
- **Source issue:** `phase-2-skills-check-and-cli-split`
- **Landed:** 

### every command should still run end to end _(archived)_

- **Scenario id:** `TRC-B4`
- **Intent:** `INT-2`
- **Source issue:** `cli-module-split`
- **Landed:** 

### Architect-lens flags missing architecture/ without blocking _(archived)_

- **Scenario id:** `TRC-B4`
- **Intent:** `INT-2`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### At least one ADR demonstrates substantive alternatives + negative consequences _(archived)_

- **Scenario id:** `TRC-B4`
- **Intent:** `INT-3`
- **Source issue:** `compass-self-architecture`
- **Landed:** 

### the adapter should be proved by a run, never by a skip _(archived)_

- **Scenario id:** `TRC-B4`
- **Intent:** `INT-2`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### a waiver without a reason should be refused _(archived)_

- **Scenario id:** `TRC-B4`
- **Intent:** `INT-2`
- **Source issue:** `governance-drift-detection`
- **Landed:** 

### Architect-lens findings persist on disk _(archived)_

- **Scenario id:** `TRC-B5`
- **Intent:** `INT-2`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### waiving a rule the framework does not ship should be refused _(archived)_

- **Scenario id:** `TRC-B5`
- **Intent:** `INT-2`
- **Source issue:** `governance-drift-detection`
- **Landed:** 

### drift should be advisory by default _(archived)_

- **Scenario id:** `TRC-B6`
- **Intent:** `INT-5`
- **Source issue:** `governance-drift-detection`
- **Landed:** 

### a project may opt into failing on drift _(archived)_

- **Scenario id:** `TRC-B7`
- **Intent:** `INT-5`
- **Source issue:** `governance-drift-detection`
- **Landed:** 

### the waived block should be declared in the schema _(archived)_

- **Scenario id:** `TRC-B8`
- **Intent:** `INT-2`
- **Source issue:** `governance-drift-detection`
- **Landed:** 

### the review skill should be within its stated length _(archived)_

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-3`
- **Source issue:** `bdd-adapters-and-skill-length`
- **Landed:** 

### frame_load_architecture returns the new artifacts and ADRs _(archived)_

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-4`
- **Source issue:** `compass-self-architecture`
- **Landed:** 

### Stop-hook nudges when scope-bloat phrases appear in devlog _(archived)_

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-3`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### the plan template should offer the five optional sections _(archived)_

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-3`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### route evaluate should report which policy it read _(archived)_

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-3`
- **Source issue:** `governance-drift-detection`
- **Landed:** 

### the check should be registered and implemented _(archived)_

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-3`
- **Source issue:** `phase-2-skills-check-and-cli-split`
- **Landed:** 

### SHA-256 is recorded per artifact (deterministic mechanism) _(archived)_

- **Scenario id:** `TRC-C2`
- **Intent:** `INT-4`
- **Source issue:** `compass-self-architecture`
- **Landed:** 

### Stop-hook stays silent when no scope-bloat is detected _(archived)_

- **Scenario id:** `TRC-C2`
- **Intent:** `INT-3`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### each optional section should state its own inclusion rule _(archived)_

- **Scenario id:** `TRC-C2`
- **Intent:** `INT-3`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### a drifted project's route output should say so _(archived)_

- **Scenario id:** `TRC-C2`
- **Intent:** `INT-3`
- **Source issue:** `governance-drift-detection`
- **Landed:** 

### a project that has wired no runner should pass with a stated reason _(archived)_

- **Scenario id:** `TRC-C2`
- **Intent:** `INT-3`
- **Source issue:** `phase-2-skills-check-and-cli-split`
- **Landed:** 

### Architect-lens cites Compass's own ADRs on a framework task _(archived)_

- **Scenario id:** `TRC-C3`
- **Intent:** `INT-4`
- **Source issue:** `compass-self-architecture`
- **Landed:** 

### Stop-hook stays silent when a reframe has already been filed _(archived)_

- **Scenario id:** `TRC-C3`
- **Intent:** `INT-3`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### the existing plan sections should survive unchanged _(archived)_

- **Scenario id:** `TRC-C3`
- **Intent:** `INT-3`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### the route template should carry a provenance field _(archived)_

- **Scenario id:** `TRC-C3`
- **Intent:** `INT-3`
- **Source issue:** `governance-drift-detection`
- **Landed:** 

### every scenario bound to a collected step definition should pass _(archived)_

- **Scenario id:** `TRC-C3`
- **Intent:** `INT-3`
- **Source issue:** `phase-2-skills-check-and-cli-split`
- **Landed:** 

### Roundtable doc requires reframe on boundary or migration decisions _(archived)_

- **Scenario id:** `TRC-C4`
- **Intent:** `INT-3`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### the planner's section choice should scale with the route _(archived)_

- **Scenario id:** `TRC-C4`
- **Intent:** `INT-3`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### a scenario the runner never ran should be named _(archived)_

- **Scenario id:** `TRC-C4`
- **Intent:** `INT-3`
- **Source issue:** `phase-2-skills-check-and-cli-split`
- **Landed:** 

### compass calibration surfaces absorbed mis-frames _(archived)_

- **Scenario id:** `TRC-C5`
- **Intent:** `INT-3`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### a named pattern should require a stated reason _(archived)_

- **Scenario id:** `TRC-C5`
- **Intent:** `INT-3`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### a stale runner result should not be read as success _(archived)_

- **Scenario id:** `TRC-C5`
- **Intent:** `INT-3`
- **Source issue:** `phase-2-skills-check-and-cli-split`
- **Landed:** 

### Flow digest includes calibration's reframe-debt _(archived)_

- **Scenario id:** `TRC-C6`
- **Intent:** `INT-3`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### the writing guide should carry a worked plan _(archived)_

- **Scenario id:** `TRC-C6`
- **Intent:** `INT-3`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### the check should be advisory unless the route promotes it _(archived)_

- **Scenario id:** `TRC-C6`
- **Intent:** `INT-3`
- **Source issue:** `phase-2-skills-check-and-cli-split`
- **Landed:** 

### CLAUDE.md notes Compass itself ships an architecture/ _(archived)_

- **Scenario id:** `TRC-D1`
- **Intent:** `INT-6`
- **Source issue:** `compass-self-architecture`
- **Landed:** 

### rework-scan reports nothing when changed_files don't conflict _(archived)_

- **Scenario id:** `TRC-D1`
- **Intent:** `INT-4`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### the superseded skill should be gone _(archived)_

- **Scenario id:** `TRC-D1`
- **Intent:** `INT-4`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### a guardrail the project omits should be reported _(archived)_

- **Scenario id:** `TRC-D1`
- **Intent:** `INT-4`
- **Source issue:** `governance-drift-detection`
- **Landed:** 

### rework-scan detects file added by A and deleted by B _(archived)_

- **Scenario id:** `TRC-D2`
- **Intent:** `INT-4`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### CLAUDE.md does not claim unbuilt features _(archived)_

- **Scenario id:** `TRC-D2`
- **Intent:** `INT-6`
- **Source issue:** `compass-self-architecture`
- **Landed:** 

### nothing should point at the deleted skill _(archived)_

- **Scenario id:** `TRC-D2`
- **Intent:** `INT-4`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### a guardrail that genuinely does not apply should still read as skipped _(archived)_

- **Scenario id:** `TRC-D2`
- **Intent:** `INT-4`
- **Source issue:** `governance-drift-detection`
- **Landed:** 

### rework-scan detects a public-surface symbol added then removed _(archived)_

- **Scenario id:** `TRC-D3`
- **Intent:** `INT-4`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### the specification skill should state what it leaves to Clarify _(archived)_

- **Scenario id:** `TRC-D3`
- **Intent:** `INT-4`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### rework-scan detects a migration created then dropped _(archived)_

- **Scenario id:** `TRC-D4`
- **Intent:** `INT-4`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### the clarify command should state the same split from its side _(archived)_

- **Scenario id:** `TRC-D4`
- **Intent:** `INT-4`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### Flow digest absorbs rework-scan _(archived)_

- **Scenario id:** `TRC-D5`
- **Intent:** `INT-4`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### rework-scan detects the canonical add-then-delete pair _(archived)_

- **Scenario id:** `TRC-D6`
- **Intent:** `INT-4`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### Existing test suite still passes (161+ tests) _(archived)_

- **Scenario id:** `TRC-E1`
- **Intent:** `INT-5`
- **Source issue:** `compass-self-architecture`
- **Landed:** 

### Unchecked DoD with no evidence and no backfill fails Land _(archived)_

- **Scenario id:** `TRC-E1`
- **Intent:** `INT-5`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### a created worktree should carry the task's artifacts _(archived)_

- **Scenario id:** `TRC-E1`
- **Intent:** `INT-6`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### Projects without architecture/ still no-op cleanly _(archived)_

- **Scenario id:** `TRC-E2`
- **Intent:** `INT-5`
- **Source issue:** `compass-self-architecture`
- **Landed:** 

### Unchecked DoD backed by typed evidence passes _(archived)_

- **Scenario id:** `TRC-E2`
- **Intent:** `INT-5`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### a builder in a seeded worktree should be able to resolve its task _(archived)_

- **Scenario id:** `TRC-E2`
- **Intent:** `INT-6`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### compass check still passes 10/10 _(archived)_

- **Scenario id:** `TRC-E3`
- **Intent:** `INT-5`
- **Source issue:** `compass-self-architecture`
- **Landed:** 

### Unchecked DoD enumerated as owed_backfill passes Land but blocks the next sibling _(archived)_

- **Scenario id:** `TRC-E3`
- **Intent:** `INT-5`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### re-running the swarm should not clobber a builder's work _(archived)_

- **Scenario id:** `TRC-E3`
- **Intent:** `INT-6`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### Lint count does not regress _(archived)_

- **Scenario id:** `TRC-E4`
- **Intent:** `INT-5`
- **Source issue:** `compass-self-architecture`
- **Landed:** 

### USER TO APPLY devlog notes no longer clear DoD _(archived)_

- **Scenario id:** `TRC-E4`
- **Intent:** `INT-5`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### human-approval evidence is accepted for human-actionable DoD items _(archived)_

- **Scenario id:** `TRC-E5`
- **Intent:** `INT-5`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### guardrails.yml registers the new DoD check _(archived)_

- **Scenario id:** `TRC-E6`
- **Intent:** `INT-5`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### a circular import should be impossible by construction _(archived)_

- **Scenario id:** `TRC-F1`
- **Intent:** `INT-3`
- **Source issue:** `cli-module-split`
- **Landed:** 

### Frame remains mandatory, unchanged _(archived)_

- **Scenario id:** `TRC-F1`
- **Intent:** `INT-6`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### a spec with no gherkin fences should fail loudly _(archived)_

- **Scenario id:** `TRC-F1`
- **Intent:** `INT-1`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### a project with current governance should see no drift report _(archived)_

- **Scenario id:** `TRC-F1`
- **Intent:** `INT-5`
- **Source issue:** `governance-drift-detection`
- **Landed:** 

### the derivation should stay a derived artifact _(archived)_

- **Scenario id:** `TRC-F1`
- **Intent:** `INT-3`
- **Source issue:** `living-spec-and-process-impact`
- **Landed:** 

### a project that opted into nothing should see no change _(archived)_

- **Scenario id:** `TRC-F1`
- **Intent:** `INT-4`
- **Source issue:** `phase-2-skills-check-and-cli-split`
- **Landed:** 

### no new mechanism is introduced _(archived)_

- **Scenario id:** `TRC-F1`
- **Intent:** `INT-1`
- **Source issue:** `voice-audition-standing`
- **Landed:** 

### no function should be renamed, merged or split by this task _(archived)_

- **Scenario id:** `TRC-F2`
- **Intent:** `INT-2`
- **Source issue:** `cli-module-split`
- **Landed:** 

### The guardrail count is still five _(archived)_

- **Scenario id:** `TRC-F2`
- **Intent:** `INT-6`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### a malformed gherkin fence should fail loudly _(archived)_

- **Scenario id:** `TRC-F2`
- **Intent:** `INT-1`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### a project with no local governance should not be compared to itself _(archived)_

- **Scenario id:** `TRC-F2`
- **Intent:** `INT-5`
- **Source issue:** `governance-drift-detection`
- **Landed:** 

### a project with no landed tasks should not be broken by the check _(archived)_

- **Scenario id:** `TRC-F2`
- **Intent:** `INT-1`
- **Source issue:** `living-spec-and-process-impact`
- **Landed:** 

### adding the check should not change any existing task's result _(archived)_

- **Scenario id:** `TRC-F2`
- **Intent:** `INT-4`
- **Source issue:** `phase-2-skills-check-and-cli-split`
- **Landed:** 

### Adaptive routing is unchanged _(archived)_

- **Scenario id:** `TRC-F3`
- **Intent:** `INT-6`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### a title that drifts between the heading and the fence should be caught _(archived)_

- **Scenario id:** `TRC-F3`
- **Intent:** `INT-1`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### a project ahead of the framework should not be reported as drifted _(archived)_

- **Scenario id:** `TRC-F3`
- **Intent:** `INT-5`
- **Source issue:** `governance-drift-detection`
- **Landed:** 

### the framework should grow by artifacts and checks only _(archived)_

- **Scenario id:** `TRC-F3`
- **Intent:** `INT-4`
- **Source issue:** `phase-2-skills-check-and-cli-split`
- **Landed:** 

### Flow still advises, never gates _(archived)_

- **Scenario id:** `TRC-F4`
- **Intent:** `INT-6`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### extraction should not modify anything it did not create _(archived)_

- **Scenario id:** `TRC-F4`
- **Intent:** `INT-1`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### an unreadable framework policy should not break the lint _(archived)_

- **Scenario id:** `TRC-F4`
- **Intent:** `INT-5`
- **Source issue:** `governance-drift-detection`
- **Landed:** 

### Architect-lens does not fork the spec _(archived)_

- **Scenario id:** `TRC-F5`
- **Intent:** `INT-6`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### a project that opted into nothing should see no change _(archived)_

- **Scenario id:** `TRC-F5`
- **Intent:** `INT-5`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### drift detection should not change any computed route _(archived)_

- **Scenario id:** `TRC-F5`
- **Intent:** `INT-5`
- **Source issue:** `governance-drift-detection`
- **Landed:** 

### the framework should grow by artifacts and skills only _(archived)_

- **Scenario id:** `TRC-F6`
- **Intent:** `INT-5`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### the framework should grow by artifacts and checks only _(archived)_

- **Scenario id:** `TRC-F6`
- **Intent:** `INT-5`
- **Source issue:** `governance-drift-detection`
- **Landed:** 

### the skill count should not grow on net _(archived)_

- **Scenario id:** `TRC-F7`
- **Intent:** `INT-5`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### the evidence types the CLI writes should be accepted by the task schema _(archived)_

- **Scenario id:** `TRC-F7`
- **Intent:** `INT-5`
- **Source issue:** `governance-drift-detection`
- **Landed:** 

### Compass ships governance/signals.yml with default patterns _(archived)_

- **Scenario id:** `TRC-G1`
- **Intent:** `INT-1`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### a command that fails to run should not be recorded as a red _(archived)_

- **Scenario id:** `TRC-G1`
- **Intent:** `INT-7`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### a run that collects no tests should not be recorded as a red _(archived)_

- **Scenario id:** `TRC-G2`
- **Intent:** `INT-7`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### a genuinely failing test should still be recorded as a red _(archived)_

- **Scenario id:** `TRC-G3`
- **Intent:** `INT-7`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### Malformed ADR frontmatter fails Frame loudly _(archived)_

- **Scenario id:** `TRC-X1`
- **Intent:** `INT-4`
- **Source issue:** `compass-self-architecture`
- **Landed:** 

### Malformed invariants.yml fails Frame loudly _(archived)_

- **Scenario id:** `TRC-X1`
- **Intent:** `INT-1`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### ADRs with status: proposed are loaded but flagged _(archived)_

- **Scenario id:** `TRC-X2`
- **Intent:** `INT-4`
- **Source issue:** `compass-self-architecture`
- **Landed:** 

### rework-scan handles a corrupt task.yml gracefully _(archived)_

- **Scenario id:** `TRC-X2`
- **Intent:** `INT-4`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### Stop-hook regex must not produce false positives on common devlog content _(archived)_

- **Scenario id:** `TRC-X3`
- **Intent:** `INT-3`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### Typed DoD does not break tasks that have empty DoD _(archived)_

- **Scenario id:** `TRC-X4`
- **Intent:** `INT-5`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### Bootstrap - spec-author does not invoke architect-lens that doesn't exist yet _(archived)_

- **Scenario id:** `TRC-X5`
- **Intent:** `INT-2`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### coherent artifacts pass cleanly _(archived)_

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### an artifact a route legitimately omits is not flagged _(archived)_

- **Scenario id:** `TRC-A10`
- **Intent:** `INT-1`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### analyze reports only coherence findings, not evidence findings _(archived)_

- **Scenario id:** `TRC-A11`
- **Intent:** `INT-1`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### analyze gate promotion is driven by routing-policy, not hard-coded in the CLI _(archived)_

- **Scenario id:** `TRC-A12`
- **Intent:** `INT-5`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### analyze completes within the interactive latency target _(archived)_

- **Scenario id:** `TRC-A13`
- **Intent:** `INT-8`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### a scenario with no upstream intent is flagged as orphaned _(archived)_

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### route disagreement between route.md and task.yml is flagged _(archived)_

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### claim with no backing scenario is flagged _(archived)_

- **Scenario id:** `TRC-A4`
- **Intent:** `INT-1`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### same artifacts and policy yield the same verdict _(archived)_

- **Scenario id:** `TRC-A5`
- **Intent:** `INT-5`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### analyze opens no network or model client on its decision path _(archived)_

- **Scenario id:** `TRC-A6`
- **Intent:** `INT-5`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### incoherence on a route below the analyze-gate threshold warns but does not block Land _(archived)_

- **Scenario id:** `TRC-A7`
- **Intent:** `INT-1`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### incoherence on a route that earns the analyze gate blocks Land _(archived)_

- **Scenario id:** `TRC-A8`
- **Intent:** `INT-1`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### analyze is never promoted to a gate globally _(archived)_

- **Scenario id:** `TRC-A9`
- **Intent:** `INT-1`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### a landed behaviour change accretes into the system spec _(archived)_

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-2`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### the derived spec carries a "DERIVED FILE" header _(archived)_

- **Scenario id:** `TRC-B10`
- **Intent:** `INT-2`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### a landed task is the source-of-truth for the living spec via task.yml.status _(archived)_

- **Scenario id:** `TRC-B11`
- **Intent:** `INT-2`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### a pure Spike contributes nothing to the system spec _(archived)_

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-2`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### re-deriving from unchanged scenarios produces no diff _(archived)_

- **Scenario id:** `TRC-B3`
- **Intent:** `INT-7`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### a superseding change updates the prior behaviour and archives the prior _(archived)_

- **Scenario id:** `TRC-B4`
- **Intent:** `INT-2`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### archived-behaviour appendix preserves the trace back to the prior task _(archived)_

- **Scenario id:** `TRC-B4a`
- **Intent:** `INT-2`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### a greenfield project Lands with no pre-existing system spec _(archived)_

- **Scenario id:** `TRC-B5`
- **Intent:** `INT-6`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### introducing the living spec adds no new phase or gate _(archived)_

- **Scenario id:** `TRC-B6`
- **Intent:** `INT-4`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### every entry in the system spec traces to a landed scenario _(archived)_

- **Scenario id:** `TRC-B7`
- **Intent:** `INT-7`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### the derivation is not the sole source of truth _(archived)_

- **Scenario id:** `TRC-B8`
- **Intent:** `INT-7`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### a hand-edit to the spec is silently overwritten by the next Land _(archived)_

- **Scenario id:** `TRC-B9`
- **Intent:** `INT-2`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### asking the agent to build something triggers Frame without naming it _(archived)_

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-3`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### next returns under the interactive latency target _(archived)_

- **Scenario id:** `TRC-C10`
- **Intent:** `INT-8`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### explicit invocation of a Compass command still works _(archived)_

- **Scenario id:** `TRC-C2`
- **Intent:** `INT-3`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### an exploratory request still gets framed (as a Spike) _(archived)_

- **Scenario id:** `TRC-C3`
- **Intent:** `INT-3`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### next reports the upcoming phase and gate in one line _(archived)_

- **Scenario id:** `TRC-C4`
- **Intent:** `INT-3`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### next states which phases are optional on this route _(archived)_

- **Scenario id:** `TRC-C5`
- **Intent:** `INT-3`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### next on a completed task reports nothing remains _(archived)_

- **Scenario id:** `TRC-C6`
- **Intent:** `INT-3`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### next writes no new task state _(archived)_

- **Scenario id:** `TRC-C7`
- **Intent:** `INT-5`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### next derives its answer only from task.yml and the route _(archived)_

- **Scenario id:** `TRC-C8`
- **Intent:** `INT-5`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### next on a task with no Frame reports that Frame is needed _(archived)_

- **Scenario id:** `TRC-C9`
- **Intent:** `INT-3`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### the five-point mental model gains zero new top-level concepts _(archived)_

- **Scenario id:** `TRC-D1`
- **Intent:** `INT-4`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### the determinism boundary holds - no model call after readings on any code path _(archived)_

- **Scenario id:** `TRC-D10`
- **Intent:** `INT-5`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### only two new CLI verbs are added across the three candidates _(archived)_

- **Scenario id:** `TRC-D2`
- **Intent:** `INT-4`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### no fixed-tier ladder is shipped _(archived)_

- **Scenario id:** `TRC-D3`
- **Intent:** `INT-9`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### the five roles remain lenses on one shared spec _(archived)_

- **Scenario id:** `TRC-D4`
- **Intent:** `INT-9`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### pipeline phases still flex by route _(archived)_

- **Scenario id:** `TRC-D5`
- **Intent:** `INT-9`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### phases and gates remain enforced _(archived)_

- **Scenario id:** `TRC-D6`
- **Intent:** `INT-9`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### TDD remains a strategy that Spike suspends _(archived)_

- **Scenario id:** `TRC-D7`
- **Intent:** `INT-9`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### every new capability functions on a bare repo with no /compass:init _(archived)_

- **Scenario id:** `TRC-D8`
- **Intent:** `INT-6`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### route composition stays byte-identical across runs _(archived)_

- **Scenario id:** `TRC-D9`
- **Intent:** `INT-5`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### analyze on a malformed task.yml exits non-zero with a structured error _(archived)_

- **Scenario id:** `TRC-F1`
- **Intent:** `INT-1`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### derivation handles two landed tasks with conflicting scenarios deterministically _(archived)_

- **Scenario id:** `TRC-F2`
- **Intent:** `INT-2`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### invisible triggering does not re-frame an already-framed task _(archived)_

- **Scenario id:** `TRC-F3`
- **Intent:** `INT-3`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### analyze on a task that has not yet been framed reports clearly _(archived)_

- **Scenario id:** `TRC-F4`
- **Intent:** `INT-1`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### a hand-edit to task.yml made by a tool is caught by analyze _(archived)_

- **Scenario id:** `TRC-F5`
- **Intent:** `INT-1`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### next on a task whose route.md is missing reports the missing artifact _(archived)_

- **Scenario id:** `TRC-F6`
- **Intent:** `INT-3`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### a landed Standard task with typed evidence renders the canonical receipt _(archived)_

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `make-receipt-render`
- **Landed:** 2026-05-26

### the rendered receipt fits within a single terminal screen _(archived)_

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `make-receipt-render`
- **Landed:** 2026-05-26

### the receipt labels each evidence type with its name and type-specific minimal fields _(archived)_

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-1`
- **Source issue:** `make-receipt-render`
- **Landed:** 2026-05-26

### a pass gate cleared by wrong-typed evidence is rendered as type-mismatch _(archived)_

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-4`
- **Source issue:** `make-receipt-render`
- **Landed:** 2026-05-26

### a pass gate with no evidence id is rendered as unsupported _(archived)_

- **Scenario id:** `TRC-C2`
- **Intent:** `INT-4`
- **Source issue:** `make-receipt-render`
- **Landed:** 2026-05-26

### a task with a failed gate renders the failure prominently _(archived)_

- **Scenario id:** `TRC-C3`
- **Intent:** `INT-4`
- **Source issue:** `make-receipt-render`
- **Landed:** 2026-05-26

### a task with owed backfills is rendered as owing _(archived)_

- **Scenario id:** `TRC-C4`
- **Intent:** `INT-4`
- **Source issue:** `make-receipt-render`
- **Landed:** 2026-05-26

### a not-yet-landed task is labeled in-progress, not rendered as a final receipt _(archived)_

- **Scenario id:** `TRC-D1`
- **Intent:** `INT-2`
- **Source issue:** `make-receipt-render`
- **Landed:** 2026-05-26

### a schema-1.0 task.yml (pre-status field) renders without error _(archived)_

- **Scenario id:** `TRC-D2`
- **Intent:** `INT-3`
- **Source issue:** `make-receipt-render`
- **Landed:** 2026-05-26

### a missing task slug fails cleanly _(archived)_

- **Scenario id:** `TRC-D3`
- **Intent:** `INT-1`
- **Source issue:** `make-receipt-render`
- **Landed:** 2026-05-26

### rendering the receipt mutates nothing on disk _(archived)_

- **Scenario id:** `TRC-E1`
- **Intent:** `INT-5`
- **Source issue:** `make-receipt-render`
- **Landed:** 2026-05-26

### an optional friction block validates against the task schema _(archived)_

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `friction-loop`
- **Landed:** 2026-06-04

### Land derives a friction entry from a recorded reframe _(archived)_

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `friction-loop`
- **Landed:** 2026-06-04

### Land derives a friction entry from absorbed reframe-debt _(archived)_

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `friction-loop`
- **Landed:** 2026-06-04

### the author's optional answer is recorded as a human-sourced entry _(archived)_

- **Scenario id:** `TRC-A4`
- **Intent:** `INT-1`
- **Source issue:** `friction-loop`
- **Landed:** 2026-06-04

### recording no friction is a valid, common Land _(archived)_

- **Scenario id:** `TRC-A5`
- **Intent:** `INT-3`
- **Source issue:** `friction-loop`
- **Landed:** 2026-06-04

### recurring friction is grouped by category and proposed change _(archived)_

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-2`
- **Source issue:** `friction-loop`
- **Landed:** 2026-06-04

### a one-off friction item stays below the recurrence threshold _(archived)_

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-3`
- **Source issue:** `friction-loop`
- **Landed:** 2026-06-04

### the friction view emits machine-readable JSON _(archived)_

- **Scenario id:** `TRC-B3`
- **Intent:** `INT-2`
- **Source issue:** `friction-loop`
- **Landed:** 2026-06-04

### friction capture never blocks Land _(archived)_

- **Scenario id:** `TRC-F1`
- **Intent:** `INT-3`
- **Source issue:** `friction-loop`
- **Landed:** 2026-06-04

### the friction view is read-only and never auto-tunes governance _(archived)_

- **Scenario id:** `TRC-F2`
- **Intent:** `INT-3`
- **Source issue:** `friction-loop`
- **Landed:** 2026-06-04

### a task.yml without a friction block stays valid and behaviour is unchanged _(archived)_

- **Scenario id:** `TRC-F3`
- **Intent:** `INT-4`
- **Source issue:** `friction-loop`
- **Landed:** 2026-06-04

### scenarios-have-tests flags a narrative scenario as FAIL on the current code (baseline) _(archived)_

- **Scenario id:** `TRC-R1-1`
- **Intent:** `INT-1`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### A documented narrative scenario with no test clears the check _(archived)_

- **Scenario id:** `TRC-R1-2`
- **Intent:** `INT-1`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### A non-narrative scenario with no test still fails scenarios-have-tests _(archived)_

- **Scenario id:** `TRC-R1-3`
- **Intent:** `INT-1`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### A narrative scenario with an empty When/Then body still fails (documented, not anything-goes) _(archived)_

- **Scenario id:** `TRC-R1-4`
- **Intent:** `INT-1`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### A narrative scenario carrying an incidental command is assessed on documentation, not the command _(archived)_

- **Scenario id:** `TRC-R1-5`
- **Intent:** `INT-1`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### regression-baseline is a named, registered soft strategy (S6) _(archived)_

- **Scenario id:** `TRC-R10-1`
- **Intent:** `INT-10`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### routing-policy surfaces regression-baseline when touches is shared/critical _(archived)_

- **Scenario id:** `TRC-R10-2`
- **Intent:** `INT-10`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### Verify expects baseline + post-change test-run evidence on a shared-surface task _(archived)_

- **Scenario id:** `TRC-R10-3`
- **Intent:** `INT-10`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### The Build phase prompts for the baseline capture up front _(archived)_

- **Scenario id:** `TRC-R10-4`
- **Intent:** `INT-10`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### Backward-compat - an absent baseline never blocks Land _(archived)_

- **Scenario id:** `TRC-R10-5`
- **Intent:** `INT-10`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### A failing test piped to tail records a false green today (baseline) _(archived)_

- **Scenario id:** `TRC-R2-1`
- **Intent:** `INT-2`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### pipefail/argv hardening turns the masked failure into a real red _(archived)_

- **Scenario id:** `TRC-R2-2`
- **Intent:** `INT-2`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### A legitimate non-piped command still records green unchanged _(archived)_

- **Scenario id:** `TRC-R2-3`
- **Intent:** `INT-2`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### The detect-and-warn heuristic fires on a pager/filter final stage _(archived)_

- **Scenario id:** `TRC-R2-4`
- **Intent:** `INT-2`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### Output-token cross-check catches a green that lacks a pass token _(archived)_

- **Scenario id:** `TRC-R2-5`
- **Intent:** `INT-2`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### A corpus-shaped scenario fails task lint while passing compass check today (baseline) _(archived)_

- **Scenario id:** `TRC-R3-1`
- **Intent:** `INT-3`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### After the schema fix, the corpus scenario shape passes task lint _(archived)_

- **Scenario id:** `TRC-R3-2`
- **Intent:** `INT-3`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### A plain-string intent still passes task lint after the widening _(archived)_

- **Scenario id:** `TRC-R3-3`
- **Intent:** `INT-3`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### A numeric intent still fails task lint after the widening _(archived)_

- **Scenario id:** `TRC-R3-4`
- **Intent:** `INT-3`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### A list intent with a non-string element still fails task lint _(archived)_

- **Scenario id:** `TRC-R3-5`
- **Intent:** `INT-3`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### Today's grep false-positives on a did-not-fire note and caps to 1 (baseline) _(archived)_

- **Scenario id:** `TRC-R4-1`
- **Intent:** `INT-4`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### Cap read from task.yml gives the correct uncapped value despite the prose _(archived)_

- **Scenario id:** `TRC-R4-2`
- **Intent:** `INT-4`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### A genuinely critical task still caps to 1 _(archived)_

- **Scenario id:** `TRC-R4-3`
- **Intent:** `INT-4`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### Integration/verify streams are not counted as worktrees _(archived)_

- **Scenario id:** `TRC-R4-4`
- **Intent:** `INT-4`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### task.yml missing the readings block fails loudly, never a silent cap _(archived)_

- **Scenario id:** `TRC-R4-F1`
- **Intent:** `INT-4`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### An auto-formatter rewrite makes the commit no-op and HEAD does not move (baseline) _(archived)_

- **Scenario id:** `TRC-R5-1`
- **Intent:** `INT-5`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### Pre-commit-clean-then-commit advances HEAD (happy path) _(archived)_

- **Scenario id:** `TRC-R5-2`
- **Intent:** `INT-5`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### A no-op commit is detected, hook fixes re-staged, and the retry advances HEAD _(archived)_

- **Scenario id:** `TRC-R5-3`
- **Intent:** `INT-5`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### HEAD is always verified to have advanced _(archived)_

- **Scenario id:** `TRC-R5-4`
- **Intent:** `INT-5`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### HEAD still unmoved after the retry → Land ERRORS loudly _(archived)_

- **Scenario id:** `TRC-R5-F1`
- **Intent:** `INT-5`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### Nothing-to-commit is distinguished from a stash-rollback no-op _(archived)_

- **Scenario id:** `TRC-R5-F2`
- **Intent:** `INT-5`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### A wrong-type gate-evidence mismatch surfaces only at compass check today (baseline) _(archived)_

- **Scenario id:** `TRC-R6-1`
- **Intent:** `INT-6`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### A task with two wrong-type gates already reports both, as one joined string (baseline) _(archived)_

- **Scenario id:** `TRC-R6-2`
- **Intent:** `INT-6`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### compass gate pass rejects wrong-type evidence at write time with the accepted-type list _(archived)_

- **Scenario id:** `TRC-R6-3`
- **Intent:** `INT-6`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### compass gate pass accepts a correct-type evidence and flips the gate to pass _(archived)_

- **Scenario id:** `TRC-R6-4`
- **Intent:** `INT-6`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### compass check reports ALL gate-evidence mismatches in one enumerated pass _(archived)_

- **Scenario id:** `TRC-R6-5`
- **Intent:** `INT-6`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### The seeded gates block carries each gate's accepted evidence types as a comment _(archived)_

- **Scenario id:** `TRC-R6-6`
- **Intent:** `INT-6`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### A coverage-gated micro-run refuses green today (baseline) _(archived)_

- **Scenario id:** `TRC-R7-1`
- **Intent:** `INT-7`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### The micro-run neutralises the project coverage floor and records green _(archived)_

- **Scenario id:** `TRC-R7-2`
- **Intent:** `INT-7`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### The full-suite coverage gate at Verify is unaffected _(archived)_

- **Scenario id:** `TRC-R7-3`
- **Intent:** `INT-7`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### A non-pytest micro-run is left untouched by the coverage logic _(archived)_

- **Scenario id:** `TRC-R7-4`
- **Intent:** `INT-7`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### A configured test_micro_command takes precedence when present _(archived)_

- **Scenario id:** `TRC-R7-5`
- **Intent:** `INT-7`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### A wiring change with no unit red is blocked today (baseline) _(archived)_

- **Scenario id:** `TRC-R8-1`
- **Intent:** `INT-8`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### tdd-red --verified-by typecheck records the guard and allows the edit _(archived)_

- **Scenario id:** `TRC-R8-2`
- **Intent:** `INT-8`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### The verified-by guard is tied to the scenario's acceptance at Verify _(archived)_

- **Scenario id:** `TRC-R8-3`
- **Intent:** `INT-8`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### A plain tdd-red with no real failure and no --verified-by is still rejected _(archived)_

- **Scenario id:** `TRC-R8-4`
- **Intent:** `INT-8`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### --verified-by rejects an unrecognised kind _(archived)_

- **Scenario id:** `TRC-R8-5`
- **Intent:** `INT-8`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### A verified-by guard that does not actually fail is rejected _(archived)_

- **Scenario id:** `TRC-R8-6`
- **Intent:** `INT-8`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### task.yml blocks below readings are hand-authored today (baseline) _(archived)_

- **Scenario id:** `TRC-R9-1`
- **Intent:** `INT-9`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### compass scenario add writes a well-formed entry that passes task lint _(archived)_

- **Scenario id:** `TRC-R9-2`
- **Intent:** `INT-9`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### compass changed-file add traces a production file to a scenario _(archived)_

- **Scenario id:** `TRC-R9-3`
- **Intent:** `INT-9`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### compass evidence add appends a typed registry entry _(archived)_

- **Scenario id:** `TRC-R9-4`
- **Intent:** `INT-9`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### A mutator rejects a duplicate id rather than silently overwriting _(archived)_

- **Scenario id:** `TRC-R9-5`
- **Intent:** `INT-9`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### A mutator rejects malformed input with non-zero exit and no write _(archived)_

- **Scenario id:** `TRC-R9-6`
- **Intent:** `INT-9`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### TRC-A1 _(archived)_

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `field-feedback-2026-07`
- **Landed:** 2026-07-27

### TRC-A2 _(archived)_

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `field-feedback-2026-07`
- **Landed:** 2026-07-27

### TRC-A3 _(archived)_

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `field-feedback-2026-07`
- **Landed:** 2026-07-27

### TRC-B1 _(archived)_

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-2`
- **Source issue:** `field-feedback-2026-07`
- **Landed:** 2026-07-27

### TRC-B2 _(archived)_

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-2`
- **Source issue:** `field-feedback-2026-07`
- **Landed:** 2026-07-27

### TRC-B3 _(archived)_

- **Scenario id:** `TRC-B3`
- **Intent:** `INT-2`
- **Source issue:** `field-feedback-2026-07`
- **Landed:** 2026-07-27

### TRC-B4 _(archived)_

- **Scenario id:** `TRC-B4`
- **Intent:** `INT-2`
- **Source issue:** `field-feedback-2026-07`
- **Landed:** 2026-07-27

### TRC-C1 _(archived)_

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-3`
- **Source issue:** `field-feedback-2026-07`
- **Landed:** 2026-07-27

### TRC-C2 _(archived)_

- **Scenario id:** `TRC-C2`
- **Intent:** `INT-3`
- **Source issue:** `field-feedback-2026-07`
- **Landed:** 2026-07-27

### TRC-C3 _(archived)_

- **Scenario id:** `TRC-C3`
- **Intent:** `INT-3`
- **Source issue:** `field-feedback-2026-07`
- **Landed:** 2026-07-27

### TRC-C4 _(archived)_

- **Scenario id:** `TRC-C4`
- **Intent:** `INT-3`
- **Source issue:** `field-feedback-2026-07`
- **Landed:** 2026-07-27

### TRC-C5 _(archived)_

- **Scenario id:** `TRC-C5`
- **Intent:** `INT-3`
- **Source issue:** `field-feedback-2026-07`
- **Landed:** 2026-07-27

### TRC-F1 _(archived)_

- **Scenario id:** `TRC-F1`
- **Intent:** `INT-3`
- **Source issue:** `field-feedback-2026-07`
- **Landed:** 2026-07-27

### TRC-F2 _(archived)_

- **Scenario id:** `TRC-F2`
- **Intent:** `INT-1`
- **Source issue:** `field-feedback-2026-07`
- **Landed:** 2026-07-27

### TRC-A1 _(archived)_

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `no-compass-refs-in-product-code`
- **Landed:** 2026-07-27

### TRC-A2 _(archived)_

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `no-compass-refs-in-product-code`
- **Landed:** 2026-07-27

### TRC-A3 _(archived)_

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `no-compass-refs-in-product-code`
- **Landed:** 2026-07-27

### TRC-A4 _(archived)_

- **Scenario id:** `TRC-A4`
- **Intent:** `INT-1`
- **Source issue:** `no-compass-refs-in-product-code`
- **Landed:** 2026-07-27

### the CI workflow runs the test suite _(archived)_

- **Scenario id:** `SCN-001`
- **Intent:** `INT-1`
- **Source issue:** `ci-runs-test-suite`
- **Landed:** 2026-07-29

### the Summary should be the first thing a cold reader meets _(archived)_

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### the Summary should carry exactly the three named fields _(archived)_

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### Summary length should scale with the route _(archived)_

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### adding the Summary should leave the scenario machinery untouched _(archived)_

- **Scenario id:** `TRC-A4`
- **Intent:** `INT-5`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### the spec-author should be told to write the Summary during Specify _(archived)_

- **Scenario id:** `TRC-A5`
- **Intent:** `INT-2`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### a filled Summary should be a condition of leaving Clarify _(archived)_

- **Scenario id:** `TRC-A6`
- **Intent:** `INT-1`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### the self-review should list exactly the four scans _(archived)_

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-3`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### each scan should say concretely what it looks for _(archived)_

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-3`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### the self-review should be fixed inline, not re-reviewed _(archived)_

- **Scenario id:** `TRC-B3`
- **Intent:** `INT-3`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### the self-review should complement Clarify rather than replace it _(archived)_

- **Scenario id:** `TRC-B4`
- **Intent:** `INT-3`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### on a collapsed-Clarify route the self-check should be recorded on disk _(archived)_

- **Scenario id:** `TRC-B5`
- **Intent:** `INT-3`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### the check should name the prohibited phrases _(archived)_

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-3`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### an incomplete work unit should be reported _(archived)_

- **Scenario id:** `TRC-C1b`
- **Intent:** `INT-3`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### an advisory hit should be reported without failing the command _(archived)_

- **Scenario id:** `TRC-C2`
- **Intent:** `INT-3`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### the skill should tell the planner how to judge what the check reports _(archived)_

- **Scenario id:** `TRC-C2b`
- **Intent:** `INT-3`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### the check result should be recorded as judgement, not as evidence _(archived)_

- **Scenario id:** `TRC-C3`
- **Intent:** `INT-3`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### the check should not introduce a sixth guardrail _(archived)_

- **Scenario id:** `TRC-C4`
- **Intent:** `INT-5`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### the check should not fire on prose that quotes it _(archived)_

- **Scenario id:** `TRC-C5`
- **Intent:** `INT-5`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### the check should stay advisory on every route _(archived)_

- **Scenario id:** `TRC-C6`
- **Intent:** `INT-5`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### the new subcommand should appear in the documented CLI surface _(archived)_

- **Scenario id:** `TRC-C7`
- **Intent:** `INT-5`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### Specify should close by inviting a cold-reader review _(archived)_

- **Scenario id:** `TRC-D1`
- **Intent:** `INT-3`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### the Clarify and Plan hand-offs should be symmetric with Specify's _(archived)_

- **Scenario id:** `TRC-D2`
- **Intent:** `INT-3`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### each hand-off prompt should be written in exactly one file _(archived)_

- **Scenario id:** `TRC-D3`
- **Intent:** `INT-5`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### the guide should show S7 applied to four kinds of artifact _(archived)_

- **Scenario id:** `TRC-E1`
- **Intent:** `INT-2`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### each worked example should show the weak version beside the improved one _(archived)_

- **Scenario id:** `TRC-E2`
- **Intent:** `INT-2`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### the guide should name what Compass deliberately does not adopt _(archived)_

- **Scenario id:** `TRC-E3`
- **Intent:** `INT-4`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### the guide should be reachable from the docs a new reader opens _(archived)_

- **Scenario id:** `TRC-E4`
- **Intent:** `INT-2`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### specs written before this change should keep passing _(archived)_

- **Scenario id:** `TRC-F1`
- **Intent:** `INT-5`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### the self-review should treat the Summary fields as placeholders to scan _(archived)_

- **Scenario id:** `TRC-F2`
- **Intent:** `INT-1`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### the self-review should record why no subagent critic is used _(archived)_

- **Scenario id:** `TRC-F3`
- **Intent:** `INT-4`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### every file this task adds or changes should pass house style _(archived)_

- **Scenario id:** `TRC-F4`
- **Intent:** `INT-5`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### the release script packages a tarball on this platform _(archived)_

- **Scenario id:** `SCN-001`
- **Intent:** `INT-1`
- **Source issue:** `release-script-portable-tar`
- **Landed:** 2026-08-03

### dev-only state is excluded without stripping the worked examples _(archived)_

- **Scenario id:** `SCN-002`
- **Intent:** `INT-1`
- **Source issue:** `release-script-portable-tar`
- **Landed:** 2026-08-03

### untracked local files never ship _(archived)_

- **Scenario id:** `SCN-003`
- **Intent:** `INT-1`
- **Source issue:** `release-script-portable-tar`
- **Landed:** 2026-08-03

### a test id whose file does not exist should be reported _(archived)_

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `record-keeping-integrity`
- **Landed:** 2026-08-03

### a test id naming a function the file does not contain should be reported _(archived)_

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `record-keeping-integrity`
- **Landed:** 2026-08-03

### a test id that resolves should pass _(archived)_

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `record-keeping-integrity`
- **Landed:** 2026-08-03

### a narrative scenario should be exempt from the resolution check _(archived)_

- **Scenario id:** `TRC-A4`
- **Intent:** `INT-4`
- **Source issue:** `record-keeping-integrity`
- **Landed:** 2026-08-03

### the check should register under G1 without adding a guardrail _(archived)_

- **Scenario id:** `TRC-A5`
- **Intent:** `INT-4`
- **Source issue:** `record-keeping-integrity`
- **Landed:** 2026-08-03

### policy lint should accept the new check _(archived)_

- **Scenario id:** `TRC-A6`
- **Intent:** `INT-4`
- **Source issue:** `record-keeping-integrity`
- **Landed:** 2026-08-03

### a task that has not yet claimed correctness should not be checked _(archived)_

- **Scenario id:** `TRC-A7`
- **Intent:** `INT-4`
- **Source issue:** `record-keeping-integrity`
- **Landed:** 2026-08-03

### a landed task should not be re-checked _(archived)_

- **Scenario id:** `TRC-A8`
- **Intent:** `INT-4`
- **Source issue:** `record-keeping-integrity`
- **Landed:** 2026-08-03

### a second friction note should not destroy the first _(archived)_

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-2`
- **Source issue:** `record-keeping-integrity`
- **Landed:** 2026-08-03

### re-running the capture should not duplicate derived entries _(archived)_

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-2`
- **Source issue:** `record-keeping-integrity`
- **Landed:** 2026-08-03

### capturing nothing should still record nothing _(archived)_

- **Scenario id:** `TRC-B3`
- **Intent:** `INT-4`
- **Source issue:** `record-keeping-integrity`
- **Landed:** 2026-08-03

### the review-dimensions table should record who assessed each dimension _(archived)_

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-3`
- **Source issue:** `record-keeping-integrity`
- **Landed:** 2026-08-03

### the template should say what to write in that column _(archived)_

- **Scenario id:** `TRC-C2`
- **Intent:** `INT-3`
- **Source issue:** `record-keeping-integrity`
- **Landed:** 2026-08-03

### tasks already on disk should keep passing _(archived)_

- **Scenario id:** `TRC-F1`
- **Intent:** `INT-4`
- **Source issue:** `record-keeping-integrity`
- **Landed:** 2026-08-03

### a task.yml written before this change should still load _(archived)_

- **Scenario id:** `TRC-F2`
- **Intent:** `INT-4`
- **Source issue:** `record-keeping-integrity`
- **Landed:** 2026-08-03

### every file this task changes should pass house style _(archived)_

- **Scenario id:** `TRC-F3`
- **Intent:** `INT-4`
- **Source issue:** `record-keeping-integrity`
- **Landed:** 2026-08-03

### every published surface should report 1.7.0 _(archived)_

- **Scenario id:** `TRC-1`
- **Intent:** `INT-1`
- **Source issue:** `version-bump-1-7-0`
- **Landed:** 2026-08-03

### the vocabulary file parses and carries its three sections _(archived)_

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `v2-terminology-freeze`
- **Landed:** 2026-08-06

### every term states its meaning _(archived)_

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `v2-terminology-freeze`
- **Landed:** 2026-08-06

### every ban carries a replacement and a context _(archived)_

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `v2-terminology-freeze`
- **Landed:** 2026-08-06

### the scan config declares its three lists _(archived)_

- **Scenario id:** `TRC-A4`
- **Intent:** `INT-3`
- **Source issue:** `v2-terminology-freeze`
- **Landed:** 2026-08-06

### a banned usage in a fixture is flagged _(archived)_

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-2`
- **Source issue:** `v2-terminology-freeze`
- **Landed:** 2026-08-06

### an innocent usage of the same words is not flagged _(archived)_

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-2`
- **Source issue:** `v2-terminology-freeze`
- **Landed:** 2026-08-06

### a pending surface may still carry banned terms _(archived)_

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-3`
- **Source issue:** `v2-terminology-freeze`
- **Landed:** 2026-08-06

### a surface removed from pending must be clean _(archived)_

- **Scenario id:** `TRC-C2`
- **Intent:** `INT-3`
- **Source issue:** `v2-terminology-freeze`
- **Landed:** 2026-08-06

### the pending list only ever shrinks _(archived)_

- **Scenario id:** `TRC-C3`
- **Intent:** `INT-3`
- **Source issue:** `v2-terminology-freeze`
- **Landed:** 2026-08-06

### the repository scan is green on day one _(archived)_

- **Scenario id:** `TRC-C4`
- **Intent:** `INT-3`
- **Source issue:** `v2-terminology-freeze`
- **Landed:** 2026-08-06

### a pending entry that names no real surface is rejected _(archived)_

- **Scenario id:** `TRC-F1`
- **Intent:** `INT-3`
- **Source issue:** `v2-terminology-freeze`
- **Landed:** 2026-08-06

### an exempt path is never scanned _(archived)_

- **Scenario id:** `TRC-F2`
- **Intent:** `INT-3`
- **Source issue:** `v2-terminology-freeze`
- **Landed:** 2026-08-06

### the implementation plan document is reviewable and complete _(archived)_

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `v2-implementation-plan`
- **Landed:** 2026-08-06

### every related term is defined _(archived)_

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `v2-terminology-dangling-refs`
- **Landed:** 2026-08-07

### the v2 PRD exists in the v2 register with all required sections _(archived)_

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `v2-prd-and-freeze-adr`
- **Landed:** 2026-08-07

### the vocabulary freeze is recorded as an accepted, indexed decision record _(archived)_

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-2`
- **Source issue:** `v2-prd-and-freeze-adr`
- **Landed:** 2026-08-07

### CLAUDE.md is clean v2 register and operationally exact _(archived)_

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `v2-session-instructions`
- **Landed:** 2026-08-07

### AGENTS.md is clean v2 register with the adapter contract intact _(archived)_

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `v2-session-instructions`
- **Landed:** 2026-08-07

### the compass-runtime skill carries the stage-to-command mapping in the v2 register _(archived)_

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `v2-session-instructions`
- **Landed:** 2026-08-07

### code-quoted machine identifiers stay legal on scanned markdown _(archived)_

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-2`
- **Source issue:** `v2-session-instructions`
- **Landed:** 2026-08-07

### the templates speak the v2 register and templates/ is enforced, never pending again _(archived)_

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `v2-template-prose`
- **Landed:** 2026-08-07

### the follow-up ban tolerates its live machine forms (tag, CLI verb, spine key) _(archived)_

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `v2-template-prose`
- **Landed:** 2026-08-07

### the archive sweeps exclude issues the spine says have not started _(archived)_

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `v2-template-prose`
- **Landed:** 2026-08-07

### the evaluator writes a v2 spine _(archived)_

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `v2-machine-spine`
- **Landed:** 2026-08-07

### a 1.x spine is still readable by normalisation _(archived)_

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `v2-machine-spine`
- **Landed:** 2026-08-07

### the repository archive speaks schema 2.0 _(archived)_

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-2`
- **Source issue:** `v2-machine-spine`
- **Landed:** 2026-08-07

### the archive carries v2 artifact names _(archived)_

- **Scenario id:** `TRC-A4`
- **Intent:** `INT-2`
- **Source issue:** `v2-machine-spine`
- **Landed:** 2026-08-07

### the artifact-name fallback is retired _(archived)_

- **Scenario id:** `TRC-A5`
- **Intent:** `INT-2`
- **Source issue:** `v2-machine-spine`
- **Landed:** 2026-08-07

### the spine template speaks v2 and is scanned _(archived)_

- **Scenario id:** `TRC-A6`
- **Intent:** `INT-2`
- **Source issue:** `v2-machine-spine`
- **Landed:** 2026-08-07

### the policy keys speak v2 _(archived)_

- **Scenario id:** `TRC-A7`
- **Intent:** `INT-1`
- **Source issue:** `v2-machine-spine`
- **Landed:** 2026-08-07

### the archive sweep has no in-flight exemption _(archived)_

- **Scenario id:** `TRC-1`
- **Intent:** `INT-1`
- **Source issue:** `retire-route-md-alias`
- **Landed:** 2026-08-07

### an issue with only delivery-approach.md passes the pre-tool hook _(archived)_

- **Scenario id:** `TRC-2`
- **Intent:** `INT-1`
- **Source issue:** `retire-route-md-alias`
- **Landed:** 2026-08-07

### the command set carries the v2 names _(archived)_

- **Scenario id:** `TRC-1`
- **Intent:** `INT-1`
- **Source issue:** `v2-command-renames`
- **Landed:** 2026-08-07

### each renamed v1 command is a redirect stub _(archived)_

- **Scenario id:** `TRC-2`
- **Intent:** `INT-1`
- **Source issue:** `v2-command-renames`
- **Landed:** 2026-08-07

### the vocabulary carries the command names and a version bump _(archived)_

- **Scenario id:** `TRC-3`
- **Intent:** `INT-1`
- **Source issue:** `v2-command-renames`
- **Landed:** 2026-08-07

### commands and the plugin manifests are enforced surfaces _(archived)_

- **Scenario id:** `TRC-4`
- **Intent:** `INT-1`
- **Source issue:** `v2-command-renames`
- **Landed:** 2026-08-07

### no live instruction surface points at a dead command name _(archived)_

- **Scenario id:** `TRC-5`
- **Intent:** `INT-1`
- **Source issue:** `v2-command-renames`
- **Landed:** 2026-08-07

### the ruling conditions hold _(archived)_

- **Scenario id:** `TRC-6`
- **Intent:** `INT-1`
- **Source issue:** `v2-command-renames`
- **Landed:** 2026-08-07

### the v2 verbs exist and work _(archived)_

- **Scenario id:** `TRC-1`
- **Intent:** `INT-1`
- **Source issue:** `v2-cli-voice`
- **Landed:** 2026-08-07

### a retired verb fails loudly and legibly _(archived)_

- **Scenario id:** `TRC-2`
- **Intent:** `INT-1`
- **Source issue:** `v2-cli-voice`
- **Landed:** 2026-08-07

### the --issue flag with --task tolerated _(archived)_

- **Scenario id:** `TRC-3`
- **Intent:** `INT-1`
- **Source issue:** `v2-cli-voice`
- **Landed:** 2026-08-07

### follow-up states are outstanding and resolved with 1.x readable _(archived)_

- **Scenario id:** `TRC-4`
- **Intent:** `INT-1`
- **Source issue:** `v2-cli-voice`
- **Landed:** 2026-08-07

### CLI output speaks v2 change-type names and the receipt shows overrides _(archived)_

- **Scenario id:** `TRC-5`
- **Intent:** `INT-1`
- **Source issue:** `v2-cli-voice`
- **Landed:** 2026-08-07

### the vocabulary carries receipt, the amended follow-up, and a bump _(archived)_

- **Scenario id:** `TRC-6`
- **Intent:** `INT-1`
- **Source issue:** `v2-cli-voice`
- **Landed:** 2026-08-07

### the cli surface is enforced and widened _(archived)_

- **Scenario id:** `TRC-7`
- **Intent:** `INT-1`
- **Source issue:** `v2-cli-voice`
- **Landed:** 2026-08-07

### the compass-backfill tolerance is re-tightened _(archived)_

- **Scenario id:** `TRC-8`
- **Intent:** `INT-1`
- **Source issue:** `v2-cli-voice`
- **Landed:** 2026-08-07

### skills is an enforced surface _(archived)_

- **Scenario id:** `TRC-1`
- **Intent:** `INT-1`
- **Source issue:** `v2-skills-prose`
- **Landed:** 2026-08-07

### agents is a scanned enforced never-pending surface _(archived)_

- **Scenario id:** `TRC-2`
- **Intent:** `INT-1`
- **Source issue:** `v2-skills-prose`
- **Landed:** 2026-08-07

### the worktree-swarm skill carries the stash rule _(archived)_

- **Scenario id:** `TRC-3`
- **Intent:** `INT-1`
- **Source issue:** `v2-skills-prose`
- **Landed:** 2026-08-07

### the lens ban catches the concept not the agent identifiers _(archived)_

- **Scenario id:** `TRC-4`
- **Intent:** `INT-1`
- **Source issue:** `v2-skills-prose`
- **Landed:** 2026-08-07

### the ratchet reaches zero _(archived)_

- **Scenario id:** `TRC-1`
- **Intent:** `INT-1`
- **Source issue:** `v2-docs-prose`
- **Landed:** 2026-08-08

### the delivery-approach reference docs carry v2 names _(archived)_

- **Scenario id:** `TRC-2`
- **Intent:** `INT-1`
- **Source issue:** `v2-docs-prose`
- **Landed:** 2026-08-08

### the worked examples carry v2 change-type names _(archived)_

- **Scenario id:** `TRC-3`
- **Intent:** `INT-1`
- **Source issue:** `v2-docs-prose`
- **Landed:** 2026-08-08

### the remaining docs are enforced surfaces _(archived)_

- **Scenario id:** `TRC-4`
- **Intent:** `INT-1`
- **Source issue:** `v2-docs-prose`
- **Landed:** 2026-08-08

### the install refusal points at the plugin-dir path _(archived)_

- **Scenario id:** `TRC-5`
- **Intent:** `INT-1`
- **Source issue:** `v2-docs-prose`
- **Landed:** 2026-08-08

### the ratchet reaches zero _(archived)_

- **Scenario id:** `TRC-1`
- **Intent:** `INT-1`
- **Source issue:** `v2-docs-prose-2`
- **Landed:** 2026-08-08

### the four deferred docs are enforced and clean _(archived)_

- **Scenario id:** `TRC-2`
- **Intent:** `INT-1`
- **Source issue:** `v2-docs-prose-2`
- **Landed:** 2026-08-08

### dry run reports and writes nothing _(archived)_

- **Scenario id:** `TRC-1`
- **Intent:** `INT-1`
- **Source issue:** `v2-migrate`
- **Landed:** 2026-08-08

### apply migrates a v1 tree to v2 _(archived)_

- **Scenario id:** `TRC-2`
- **Intent:** `INT-1`
- **Source issue:** `v2-migrate`
- **Landed:** 2026-08-08

### a second apply is a no-op _(archived)_

- **Scenario id:** `TRC-3`
- **Intent:** `INT-1`
- **Source issue:** `v2-migrate`
- **Landed:** 2026-08-08

### the mapping lives in the exempt data file _(archived)_

- **Scenario id:** `TRC-4`
- **Intent:** `INT-1`
- **Source issue:** `v2-migrate`
- **Landed:** 2026-08-08

### the version is 2.0.0 in every guarded location _(archived)_

- **Scenario id:** `TRC-1`
- **Intent:** `INT-1`
- **Source issue:** `v2-release`
- **Landed:** 2026-08-08

### desired-state graduates and is enforced _(archived)_

- **Scenario id:** `TRC-2`
- **Intent:** `INT-1`
- **Source issue:** `v2-release`
- **Landed:** 2026-08-08

### the reference should live under an existing skill and open with the principle _(archived)_

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-2`
- **Source issue:** `human-voice`
- **Landed:** 2026-08-09

### every before/after pair should be a real passage from the work archive _(archived)_

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `human-voice`
- **Landed:** 2026-08-09

### the tells list should name all nine tells and say which a string can find _(archived)_

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `human-voice`
- **Landed:** 2026-08-09

### no rewritten passage should still carry a tell _(archived)_

- **Scenario id:** `TRC-A4`
- **Intent:** `INT-1`
- **Source issue:** `human-voice`
- **Landed:** 2026-08-09

### the root instruction files should carry a short voice paragraph _(archived)_

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-1`
- **Source issue:** `human-voice`
- **Landed:** 2026-08-09

### the three talkiest stages should each point at the reference _(archived)_

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-1`
- **Source issue:** `human-voice`
- **Landed:** 2026-08-09

### the tells should live in one place, so a later edit cannot leave a stale copy _(archived)_

- **Scenario id:** `TRC-B3`
- **Intent:** `INT-2`
- **Source issue:** `human-voice`
- **Landed:** 2026-08-09

### a real requirements review from the archive should become the canonical worked example _(archived)_

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-1`
- **Source issue:** `human-voice`
- **Landed:** 2026-08-09

### the original should stay readable beside the rewrite _(archived)_

- **Scenario id:** `TRC-C2`
- **Intent:** `INT-1`
- **Source issue:** `human-voice`
- **Landed:** 2026-08-09

### the requirements-review template should show a decision recorded in a human voice _(archived)_

- **Scenario id:** `TRC-C3`
- **Intent:** `INT-1`
- **Source issue:** `human-voice`
- **Landed:** 2026-08-09

### the clarity dimension should name the tells as judgement, not as a rule _(archived)_

- **Scenario id:** `TRC-D1`
- **Intent:** `INT-1`
- **Source issue:** `human-voice`
- **Landed:** 2026-08-09

### the tell check should name the file and line of each hit _(archived)_

- **Scenario id:** `TRC-D2`
- **Intent:** `INT-1`
- **Source issue:** `human-voice`
- **Landed:** 2026-08-09

### a clean set of artifacts should get a stated result, not silence _(archived)_

- **Scenario id:** `TRC-D3`
- **Intent:** `INT-1`
- **Source issue:** `human-voice`
- **Landed:** 2026-08-09

### a tell that is found should block nothing _(archived)_

- **Scenario id:** `TRC-F1`
- **Intent:** `INT-2`
- **Source issue:** `human-voice`
- **Landed:** 2026-08-09

### the exhibits should not be read as defects _(archived)_

- **Scenario id:** `TRC-F2`
- **Intent:** `INT-1`
- **Source issue:** `human-voice`
- **Landed:** 2026-08-09

### nothing about how Compass behaves should change _(archived)_

- **Scenario id:** `TRC-F3`
- **Intent:** `INT-2`
- **Source issue:** `human-voice`
- **Landed:** 2026-08-09

### every file this issue writes should clear house style and the frozen vocabulary _(archived)_

- **Scenario id:** `TRC-F4`
- **Intent:** `INT-1`
- **Source issue:** `human-voice`
- **Landed:** 2026-08-09

### a first triage completes with no Python package installed _(archived)_

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `zero-friction-install`
- **Landed:** 2026-08-10

### no CLI verb exits on a missing dependency _(archived)_

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `zero-friction-install`
- **Landed:** 2026-08-10

### the acceptance-before-code hook check runs instead of failing open _(archived)_

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `zero-friction-install`
- **Landed:** 2026-08-10

### the acceptance-before-code hook check runs instead of failing open _(archived)_

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-2`
- **Source issue:** `zero-friction-install`
- **Landed:** 2026-08-10

### integration records the landing rather than warning it could not _(archived)_

- **Scenario id:** `TRC-A4`
- **Intent:** `INT-1`
- **Source issue:** `zero-friction-install`
- **Landed:** 2026-08-10

### integration records the landing rather than warning it could not _(archived)_

- **Scenario id:** `TRC-A4`
- **Intent:** `INT-2`
- **Source issue:** `zero-friction-install`
- **Landed:** 2026-08-10

### the session-end signal scan runs rather than returning empty _(archived)_

- **Scenario id:** `TRC-A5`
- **Intent:** `INT-1`
- **Source issue:** `zero-friction-install`
- **Landed:** 2026-08-10

### the repository check runs the policy lint rather than skipping it _(archived)_

- **Scenario id:** `TRC-A6`
- **Intent:** `INT-1`
- **Source issue:** `zero-friction-install`
- **Landed:** 2026-08-10

### preparing a swarm reads the cap rather than refusing _(archived)_

- **Scenario id:** `TRC-A7`
- **Intent:** `INT-1`
- **Source issue:** `zero-friction-install`
- **Landed:** 2026-08-10

### preparing a swarm reads the cap rather than refusing _(archived)_

- **Scenario id:** `TRC-A7`
- **Intent:** `INT-2`
- **Source issue:** `zero-friction-install`
- **Landed:** 2026-08-10

### nothing shipped tells a user or an adopter to install PyYAML _(archived)_

- **Scenario id:** `TRC-D1`
- **Intent:** `INT-3`
- **Source issue:** `zero-friction-install`
- **Landed:** 2026-08-10

### the copyable CI workflow runs with no dependency step _(archived)_

- **Scenario id:** `TRC-D3`
- **Intent:** `INT-1`
- **Source issue:** `zero-friction-install`
- **Landed:** 2026-08-10

### the copyable CI workflow runs with no dependency step _(archived)_

- **Scenario id:** `TRC-D3`
- **Intent:** `INT-3`
- **Source issue:** `zero-friction-install`
- **Landed:** 2026-08-10

### the install smoke test asserts the zero-install path _(archived)_

- **Scenario id:** `TRC-D4`
- **Intent:** `INT-3`
- **Source issue:** `zero-friction-install`
- **Landed:** 2026-08-10

### the install smoke test asserts the zero-install path _(archived)_

- **Scenario id:** `TRC-D4`
- **Intent:** `INT-1`
- **Source issue:** `zero-friction-install`
- **Landed:** 2026-08-10

### no test requires the removed instruction to still exist _(archived)_

- **Scenario id:** `TRC-D5`
- **Intent:** `INT-3`
- **Source issue:** `zero-friction-install`
- **Landed:** 2026-08-10

### no document claims Compass has no dependencies _(archived)_

- **Scenario id:** `TRC-D6`
- **Intent:** `INT-4`
- **Source issue:** `zero-friction-install`
- **Landed:** 2026-08-10

### no document claims Compass has no dependencies _(archived)_

- **Scenario id:** `TRC-D6`
- **Intent:** `INT-3`
- **Source issue:** `zero-friction-install`
- **Landed:** 2026-08-10

### the decision is recorded with the alternative it beat _(archived)_

- **Scenario id:** `TRC-E1`
- **Intent:** `INT-4`
- **Source issue:** `zero-friction-install`
- **Landed:** 2026-08-10

### an issue already in flight continues unchanged across the upgrade _(archived)_

- **Scenario id:** `TRC-F4`
- **Intent:** `INT-2`
- **Source issue:** `zero-friction-install`
- **Landed:** 2026-08-10

### jsonschema stays optional and unchanged _(archived)_

- **Scenario id:** `TRC-F5`
- **Intent:** `INT-2`
- **Source issue:** `zero-friction-install`
- **Landed:** 2026-08-10

### the distributed plugin actually contains the bundled copy _(archived)_

- **Scenario id:** `TRC-F6`
- **Intent:** `INT-1`
- **Source issue:** `zero-friction-install`
- **Landed:** 2026-08-10

### recording acceptance for a second scenario does not destroy the first one's evidence _(archived)_

- **Scenario id:** `TRC-F7`
- **Intent:** `INT-6`
- **Source issue:** `zero-friction-install`
- **Landed:** 2026-08-10

### the bundled copy is the one used, whatever the machine has _(archived)_

- **Scenario id:** `TRC-G1`
- **Intent:** `INT-1`
- **Source issue:** `zero-friction-install`
- **Landed:** 2026-08-10

### the bundled copy is the one used, whatever the machine has _(archived)_

- **Scenario id:** `TRC-G1`
- **Intent:** `INT-2`
- **Source issue:** `zero-friction-install`
- **Landed:** 2026-08-10

### the shipped version is the documented version _(archived)_

- **Scenario id:** `TRC-G2`
- **Intent:** `INT-4`
- **Source issue:** `zero-friction-install`
- **Landed:** 2026-08-10

### the bundled library carries its licence and its attribution _(archived)_

- **Scenario id:** `TRC-G3`
- **Intent:** `INT-4`
- **Source issue:** `zero-friction-install`
- **Landed:** 2026-08-10

### a scenario that serves two intents answers for both _(archived)_

- **Scenario id:** `TRC-1`
- **Intent:** `INT-1`
- **Source issue:** `derive-spec-multi-intent`
- **Landed:** 2026-08-10

### the single-intent form is unchanged _(archived)_

- **Scenario id:** `TRC-2`
- **Intent:** `INT-1`
- **Source issue:** `derive-spec-multi-intent`
- **Landed:** 2026-08-10

### the pinned assertions run where the history is absent _(archived)_

- **Scenario id:** `TRC-1`
- **Intent:** `INT-1`
- **Source issue:** `tests-survive-shallow-clone`
- **Landed:** 2026-08-10

### the strategy states the trigger, the staffing rule, and the method _(archived)_

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `fresh-eyes-verify-sweeps`
- **Landed:** 2026-08-11

### the strategy states the prohibition, the evidence, and carries the file's own conventions _(archived)_

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `fresh-eyes-verify-sweeps`
- **Landed:** 2026-08-11

### the verify stage guidance points at the strategy without repeating it _(archived)_

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-1`
- **Source issue:** `fresh-eyes-verify-sweeps`
- **Landed:** 2026-08-11

### no new mechanism is introduced _(archived)_

- **Scenario id:** `TRC-F1`
- **Intent:** `INT-1`
- **Source issue:** `fresh-eyes-verify-sweeps`
- **Landed:** 2026-08-11

### no public file claims an outside user _(archived)_

- **Scenario id:** `TRC-1`
- **Intent:** `INT-1`
- **Source issue:** `adr-013-context-tense`
- **Landed:** 2026-08-11

### no public file attaches a duration to a user _(archived)_

- **Scenario id:** `TRC-2`
- **Intent:** `INT-1`
- **Source issue:** `adr-013-context-tense`
- **Landed:** 2026-08-11

### the guard catches the defect it was written for _(archived)_

- **Scenario id:** `TRC-3`
- **Intent:** `INT-1`
- **Source issue:** `adr-013-context-tense`
- **Landed:** 2026-08-11

### the entry states the primary-record rule and defines what a primary record is _(archived)_

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-1`
- **Source issue:** `s9-primary-record`
- **Landed:** 2026-08-12

### the entry carries the ADR-013 worked example and warns the nearest document is often a summary _(archived)_

- **Scenario id:** `TRC-C2`
- **Intent:** `INT-1`
- **Source issue:** `s9-primary-record`
- **Landed:** 2026-08-12

### a fabricated quote fails even without the archive _(archived)_

- **Scenario id:** `TRC-1`
- **Intent:** `INT-1`
- **Source issue:** `archive-quote-verification`
- **Landed:** 2026-08-12

### an unaltered quote is accepted, and the report names what went unverified _(archived)_

- **Scenario id:** `TRC-2`
- **Intent:** `INT-1`
- **Source issue:** `archive-quote-verification`
- **Landed:** 2026-08-12

### a genuine quote passes by direct verification _(archived)_

- **Scenario id:** `TRC-3`
- **Intent:** `INT-1`
- **Source issue:** `archive-quote-verification`
- **Landed:** 2026-08-12

### a mismatched quote fails, not skips, when the archive is present _(archived)_

- **Scenario id:** `TRC-4`
- **Intent:** `INT-1`
- **Source issue:** `archive-quote-verification`
- **Landed:** 2026-08-12

### the regeneration path refuses an unverified hash _(archived)_

- **Scenario id:** `TRC-5`
- **Intent:** `INT-1`
- **Source issue:** `archive-quote-verification`
- **Landed:** 2026-08-12

### a not-yet-started issue does not fail the sweep _(archived)_

- **Scenario id:** `TRC-1`
- **Intent:** `INT-1`
- **Source issue:** `sweep-respects-queued`
- **Landed:** 2026-08-12

### the sweep still names what it did not check _(archived)_

- **Scenario id:** `TRC-2`
- **Intent:** `INT-1`
- **Source issue:** `sweep-respects-queued`
- **Landed:** 2026-08-12

### an in-flight issue is still checked _(archived)_

- **Scenario id:** `TRC-3`
- **Intent:** `INT-1`
- **Source issue:** `sweep-respects-queued`
- **Landed:** 2026-08-12

### a recorded re-assessment lints clean _(archived)_

- **Scenario id:** `TRC-1`
- **Intent:** `INT-1`
- **Source issue:** `spine-schema-reassessment-keys`
- **Landed:** 2026-08-12

### the keys are declared, not merely tolerated _(archived)_

- **Scenario id:** `TRC-2`
- **Intent:** `INT-1`
- **Source issue:** `spine-schema-reassessment-keys`
- **Landed:** 2026-08-12

### every documented banner matches what the CLI prints _(archived)_

- **Scenario id:** `TRC-1`
- **Intent:** `INT-1`
- **Source issue:** `smoke-test-version-drift`
- **Landed:** 2026-08-12

### the banner uses current vocabulary _(archived)_

- **Scenario id:** `TRC-2`
- **Intent:** `INT-1`
- **Source issue:** `smoke-test-version-drift`
- **Landed:** 2026-08-12

### the document describes v2 behaviour _(archived)_

- **Scenario id:** `TRC-1`
- **Intent:** `INT-1`
- **Source issue:** `smoke-test-speaks-v2`
- **Landed:** 2026-08-12

### the document is scanned for the frozen vocabulary _(archived)_

- **Scenario id:** `TRC-2`
- **Intent:** `INT-1`
- **Source issue:** `smoke-test-speaks-v2`
- **Landed:** 2026-08-12

### every published location reports the declared version _(archived)_

- **Scenario id:** `TRC-1`
- **Intent:** `INT-1`
- **Source issue:** `version-guard-covers-all`
- **Landed:** 2026-08-12

### the guard has a case for every published location _(archived)_

- **Scenario id:** `TRC-2`
- **Intent:** `INT-1`
- **Source issue:** `version-guard-covers-all`
- **Landed:** 2026-08-12

### no constant nothing reads _(archived)_

- **Scenario id:** `TRC-3`
- **Intent:** `INT-1`
- **Source issue:** `version-guard-covers-all`
- **Landed:** 2026-08-12

### a malformed spine fails the sweep whatever its status _(archived)_

- **Scenario id:** `TRC-1`
- **Intent:** `INT-1`
- **Source issue:** `ci-lints-every-issue`
- **Landed:** 2026-08-12

### a well-formed not-yet-started issue still does not fail _(archived)_

- **Scenario id:** `TRC-2`
- **Intent:** `INT-1`
- **Source issue:** `ci-lints-every-issue`
- **Landed:** 2026-08-12

### the summary reports what was and was not checked _(archived)_

- **Scenario id:** `TRC-3`
- **Intent:** `INT-2`
- **Source issue:** `ci-lints-every-issue`
- **Landed:** 2026-08-12

### an unparsed span is a failure _(archived)_

- **Scenario id:** `TRC-1`
- **Intent:** `INT-1`
- **Source issue:** `quote-verifier-rejects-unparsed`
- **Landed:** 2026-08-12

### update refuses to record an unparsed span _(archived)_

- **Scenario id:** `TRC-2`
- **Intent:** `INT-1`
- **Source issue:** `quote-verifier-rejects-unparsed`
- **Landed:** 2026-08-12

### a well-formed span still verifies _(archived)_

- **Scenario id:** `TRC-3`
- **Intent:** `INT-1`
- **Source issue:** `quote-verifier-rejects-unparsed`
- **Landed:** 2026-08-12

### the version guard compares every location it names _(archived)_

- **Scenario id:** `TRC-1`
- **Intent:** `INT-1`
- **Source issue:** `tests-that-can-fail`
- **Landed:** 2026-08-12

### the validate guard fails when the lint is skipped _(archived)_

- **Scenario id:** `TRC-2`
- **Intent:** `INT-1`
- **Source issue:** `tests-that-can-fail`
- **Landed:** 2026-08-12

### the tell-scope guard fails when nothing was found _(archived)_

- **Scenario id:** `TRC-3`
- **Intent:** `INT-1`
- **Source issue:** `tests-that-can-fail`
- **Landed:** 2026-08-12

### the reference-location guard fails on a new skill directory _(archived)_

- **Scenario id:** `TRC-4`
- **Intent:** `INT-1`
- **Source issue:** `tests-that-can-fail`
- **Landed:** 2026-08-12

### the header scan proves how many modules it read _(archived)_

- **Scenario id:** `TRC-5`
- **Intent:** `INT-1`
- **Source issue:** `tests-that-can-fail`
- **Landed:** 2026-08-12

### the strategy states the method and the reason _(archived)_

- **Scenario id:** `TRC-1`
- **Intent:** `INT-1`
- **Source issue:** `mutation-proof-standing`
- **Landed:** 2026-08-12

### the verify guidance points at the strategy _(archived)_

- **Scenario id:** `TRC-2`
- **Intent:** `INT-1`
- **Source issue:** `mutation-proof-standing`
- **Landed:** 2026-08-12

### the id set admits the new strategy deliberately _(archived)_

- **Scenario id:** `TRC-3`
- **Intent:** `INT-1`
- **Source issue:** `mutation-proof-standing`
- **Landed:** 2026-08-12

### the script is the eight-shot re-cut _(archived)_

- **Scenario id:** `RR-1`
- **Intent:** `RULE-2`
- **Source issue:** `rehearsal-recordings`
- **Landed:** 2026-08-13

### the post-3.0.0 shots are marked pending and listed for re-check _(archived)_

- **Scenario id:** `RR-2`
- **Intent:** `RULE-2`
- **Source issue:** `rehearsal-recordings`
- **Landed:** 2026-08-13

### measure-before-arguing is in the operating model _(archived)_

- **Scenario id:** `RR-6`
- **Intent:** `PRACTICE`
- **Source issue:** `rehearsal-recordings`
- **Landed:** 2026-08-13

### the hook finds the project from a subdirectory _(archived)_

- **Scenario id:** `RCD-A1`
- **Intent:** `REH-1`
- **Source issue:** `rehearsal-cli-defects`
- **Landed:** 2026-08-13

### an unresolvable project root fails closed, not open _(archived)_

- **Scenario id:** `RCD-A2`
- **Intent:** `REH-1`
- **Source issue:** `rehearsal-cli-defects`
- **Landed:** 2026-08-13

### the message names the real cause _(archived)_

- **Scenario id:** `RCD-A3`
- **Intent:** `REH-1`
- **Source issue:** `rehearsal-cli-defects`
- **Landed:** 2026-08-13

### design lint defaults to the live artifact filename _(archived)_

- **Scenario id:** `RCD-B1`
- **Intent:** `REH-2`
- **Source issue:** `rehearsal-cli-defects`
- **Landed:** 2026-08-13

### a nested test id resolves _(archived)_

- **Scenario id:** `RCD-C1`
- **Intent:** `REH-3`
- **Source issue:** `rehearsal-cli-defects`
- **Landed:** 2026-08-13

### a test name ending in a non-word character resolves _(archived)_

- **Scenario id:** `RCD-C2`
- **Intent:** `REH-3`
- **Source issue:** `rehearsal-cli-defects`
- **Landed:** 2026-08-13

### the current-issue pointer is in shipping scope _(archived)_

- **Scenario id:** `RCD-D1`
- **Intent:** `REH-5`
- **Source issue:** `rehearsal-cli-defects`
- **Landed:** 2026-08-13

### the cross-issue board names each computed approach _(archived)_

- **Scenario id:** `RCD-E2`
- **Intent:** `SWEEP`
- **Source issue:** `rehearsal-cli-defects`
- **Landed:** 2026-08-13

### no retired slash command remains _(archived)_

- **Scenario id:** `RCD-F1`
- **Intent:** `RULE-5`
- **Source issue:** `rehearsal-cli-defects`
- **Landed:** 2026-08-13

### a retired CLI verb is an unknown verb _(archived)_

- **Scenario id:** `RCD-F2`
- **Intent:** `RULE-5`
- **Source issue:** `rehearsal-cli-defects`
- **Landed:** 2026-08-13

### a retired flag is an unknown flag _(archived)_

- **Scenario id:** `RCD-F3`
- **Intent:** `RULE-5`
- **Source issue:** `rehearsal-cli-defects`
- **Landed:** 2026-08-13

### the migrator keeps its v1-to-v2 mapping _(archived)_

- **Scenario id:** `RCD-F4`
- **Intent:** `RULE-5`
- **Source issue:** `rehearsal-cli-defects`
- **Landed:** 2026-08-13

### a v1 name in a Python single-token literal is caught _(archived)_

- **Scenario id:** `RCD-G1`
- **Intent:** `SWEEP`
- **Source issue:** `rehearsal-cli-defects`
- **Landed:** 2026-08-13

### a v1 name in a markdown code span or fenced block is caught _(archived)_

- **Scenario id:** `RCD-G2`
- **Intent:** `RULE-5`
- **Source issue:** `rehearsal-cli-defects`
- **Landed:** 2026-08-13

### the archive is exempt and unedited _(archived)_

- **Scenario id:** `RCD-G4`
- **Intent:** `RULE-5`
- **Source issue:** `rehearsal-cli-defects`
- **Landed:** 2026-08-13

### the tightened guard can fail _(archived)_

- **Scenario id:** `RCD-G5`
- **Intent:** `RULE-5`
- **Source issue:** `rehearsal-cli-defects`
- **Landed:** 2026-08-13

### conventional comments is a shipped default _(archived)_

- **Scenario id:** `SR-1`
- **Intent:** `RULE-S1`
- **Source issue:** `strategy-rulings-2026-08`
- **Landed:** 2026-08-13

### the four surfaces are scanned _(archived)_

- **Scenario id:** `SS-1`
- **Intent:** `GAP-1`
- **Source issue:** `scan-the-remaining-surfaces`
- **Landed:** 2026-08-13

### a JSON schema's prose is read, its contract is not _(archived)_

- **Scenario id:** `SS-2`
- **Intent:** `GAP-1`
- **Source issue:** `scan-the-remaining-surfaces`
- **Landed:** 2026-08-13

### the machine contract is untouched _(archived)_

- **Scenario id:** `SS-3`
- **Intent:** `GAP-1`
- **Source issue:** `scan-the-remaining-surfaces`
- **Landed:** 2026-08-13

### every id prefix in use is defined _(archived)_

- **Scenario id:** `GL-B1`
- **Intent:** `NO-CODE-DICTIONARY`
- **Source issue:** `id-prefix-vocabulary-and-glossary`
- **Landed:** 2026-08-13

### the guard fails on an undefined prefix _(archived)_

- **Scenario id:** `GL-B2`
- **Intent:** `NO-CODE-DICTIONARY`
- **Source issue:** `id-prefix-vocabulary-and-glossary`
- **Landed:** 2026-08-13

### the glossary page is derived, not hand-written _(archived)_

- **Scenario id:** `GL-C1`
- **Intent:** `NO-CODE-DICTIONARY`
- **Source issue:** `id-prefix-vocabulary-and-glossary`
- **Landed:** 2026-08-13

### drift between source and page fails the build _(archived)_

- **Scenario id:** `GL-C2`
- **Intent:** `NO-CODE-DICTIONARY`
- **Source issue:** `id-prefix-vocabulary-and-glossary`
- **Landed:** 2026-08-13

### routing ids are RP- and kinds are distinct _(archived)_

- **Scenario id:** `GL-D1`
- **Intent:** `WRONG-PREFIX`
- **Source issue:** `id-prefix-vocabulary-and-glossary`
- **Landed:** 2026-08-13

### the evaluator is unchanged by the rename _(archived)_

- **Scenario id:** `GL-D2`
- **Intent:** `WRONG-PREFIX`
- **Source issue:** `id-prefix-vocabulary-and-glossary`
- **Landed:** 2026-08-13

### the follow-up surfaces match the schema _(archived)_

- **Scenario id:** `GL-E1`
- **Intent:** `DOC-DRIFT`
- **Source issue:** `id-prefix-vocabulary-and-glossary`
- **Landed:** 2026-08-13

### the enforcement path exempts by anchored name _(archived)_

- **Scenario id:** `PRF-1`
- **Intent:** `REVIEW`
- **Source issue:** `pr-50-review-findings`
- **Landed:** 2026-08-13

### the session-end hook reads the spine _(archived)_

- **Scenario id:** `PRF-2`
- **Intent:** `REVIEW`
- **Source issue:** `pr-50-review-findings`
- **Landed:** 2026-08-13

### the scan reads the hook's own messages _(archived)_

- **Scenario id:** `PRF-3`
- **Intent:** `REVIEW`
- **Source issue:** `pr-50-review-findings`
- **Landed:** 2026-08-13

### an explicit project root is trusted _(archived)_

- **Scenario id:** `PRF-4`
- **Intent:** `REVIEW`
- **Source issue:** `pr-50-review-findings`
- **Landed:** 2026-08-13

### the warners say when they cannot find the project _(archived)_

- **Scenario id:** `PRF-5`
- **Intent:** `REVIEW`
- **Source issue:** `pr-50-review-findings`
- **Landed:** 2026-08-13

### the tests that could not fail can now fail _(archived)_

- **Scenario id:** `PRF-6`
- **Intent:** `REVIEW`
- **Source issue:** `pr-50-review-findings`
- **Landed:** 2026-08-13

### the suite passes on a clean clone _(archived)_

- **Scenario id:** `PRF-7`
- **Intent:** `REVIEW`
- **Source issue:** `pr-50-review-findings`
- **Landed:** 2026-08-13

### the samples use the current vocabulary _(archived)_

- **Scenario id:** `EX-1`
- **Intent:** `REVIEW`
- **Source issue:** `consolidate-trc-and-scn-prefixes`
- **Landed:** 2026-08-13

### the canonical id prefix is used throughout _(archived)_

- **Scenario id:** `EX-2`
- **Intent:** `REVIEW`
- **Source issue:** `consolidate-trc-and-scn-prefixes`
- **Landed:** 2026-08-13

### every sample still passes its own checks _(archived)_

- **Scenario id:** `EX-3`
- **Intent:** `REVIEW`
- **Source issue:** `consolidate-trc-and-scn-prefixes`
- **Landed:** 2026-08-13

### the repo check must ignore files git does not track _(archived)_

- **Scenario id:** `SCN-01`
- **Intent:** `INT-1`
- **Source issue:** `release-blockers-2026-08`
- **Landed:** 2026-08-13

### enforcement must not switch itself off based on the checkout path _(archived)_

- **Scenario id:** `SCN-02`
- **Intent:** `INT-1`
- **Source issue:** `release-blockers-2026-08`
- **Landed:** 2026-08-13

### a seeded worktree must not inherit another builder's red _(archived)_

- **Scenario id:** `SCN-03`
- **Intent:** `INT-1`
- **Source issue:** `release-blockers-2026-08`
- **Landed:** 2026-08-13

### a BDD run must record which scenarios it actually bound _(archived)_

- **Scenario id:** `SCN-04`
- **Intent:** `INT-1`
- **Source issue:** `release-blockers-2026-08`
- **Landed:** 2026-08-13

### every BDD adapter example must have the test files it declares _(archived)_

- **Scenario id:** `SCN-05`
- **Intent:** `INT-3`
- **Source issue:** `release-blockers-2026-08`
- **Landed:** 2026-08-13

### every shipped route example must pass its own checks _(archived)_

- **Scenario id:** `SCN-06`
- **Intent:** `INT-3`
- **Source issue:** `release-blockers-2026-08`
- **Landed:** 2026-08-13

### the behave adapter must report its bound scenarios correctly _(archived)_

- **Scenario id:** `SCN-07`
- **Intent:** `INT-3`
- **Source issue:** `release-blockers-2026-08`
- **Landed:** 2026-08-13

### a CI job that runs a Python tool must install Python first _(archived)_

- **Scenario id:** `SCN-08`
- **Intent:** `INT-3`
- **Source issue:** `release-blockers-2026-08`
- **Landed:** 2026-08-13

### an example's declared tests must point at real files _(archived)_

- **Scenario id:** `SCN-09`
- **Intent:** `INT-3`
- **Source issue:** `release-blockers-2026-08`
- **Landed:** 2026-08-13

### a Spike route must still report an owed backfill _(archived)_

- **Scenario id:** `SCN-10`
- **Intent:** `INT-1`
- **Source issue:** `release-blockers-2026-08`
- **Landed:** 2026-08-13

### landing must not be recorded over gates that have not passed _(archived)_

- **Scenario id:** `SCN-11`
- **Intent:** `INT-2`
- **Source issue:** `release-blockers-2026-08`
- **Landed:** 2026-08-13

### a receipt must not report a clean land over pending gates _(archived)_

- **Scenario id:** `SCN-12`
- **Intent:** `INT-2`
- **Source issue:** `release-blockers-2026-08`
- **Landed:** 2026-08-13

### the analyze summary must agree with the findings above it _(archived)_

- **Scenario id:** `SCN-13`
- **Intent:** `INT-2`
- **Source issue:** `release-blockers-2026-08`
- **Landed:** 2026-08-13

### a lint must report a malformed file, not crash on it _(archived)_

- **Scenario id:** `SCN-14`
- **Intent:** `INT-2`
- **Source issue:** `release-blockers-2026-08`
- **Landed:** 2026-08-13

### the onboarding transcript must match what the CLI prints _(archived)_

- **Scenario id:** `SCN-15`
- **Intent:** `INT-3`
- **Source issue:** `release-blockers-2026-08`
- **Landed:** 2026-08-13

### documented commands must exist _(archived)_

- **Scenario id:** `SCN-16`
- **Intent:** `INT-3`
- **Source issue:** `release-blockers-2026-08`
- **Landed:** 2026-08-13

### a different test command must not read as a rerun-to-green _(archived)_

- **Scenario id:** `SCN-17`
- **Intent:** `INT-2`
- **Source issue:** `release-blockers-2026-08`
- **Landed:** 2026-08-13

### a project can add a file type _(archived)_

- **Scenario id:** `SCN-A1`
- **Intent:** `INT-2`
- **Source issue:** `configurable-enforced-set`
- **Landed:** 2026-08-13

### a critical-blast-radius task requires a human approval _(archived)_

- **Scenario id:** `SCN-A1`
- **Intent:** `INT-1`
- **Source issue:** `g5-trigger-matches-statement`
- **Landed:** 2026-08-13

### a validation acceptance permits the edit _(archived)_

- **Scenario id:** `SCN-A1`
- **Intent:** `INT-1`
- **Source issue:** `honest-acceptance-for-config-and-refactor`
- **Landed:** 2026-08-13

### a redirect into a source file is blocked with no red on record _(archived)_

- **Scenario id:** `SCN-A1`
- **Intent:** `INT-1`
- **Source issue:** `hook-bash-write-bypass`
- **Landed:** 2026-08-13

### a critical task with a recorded approval clears G5 _(archived)_

- **Scenario id:** `SCN-A2`
- **Intent:** `INT-1`
- **Source issue:** `g5-trigger-matches-statement`
- **Landed:** 2026-08-13

### a path-shaped glob works too _(archived)_

- **Scenario id:** `SCN-A2`
- **Intent:** `INT-2`
- **Source issue:** `configurable-enforced-set`
- **Landed:** 2026-08-13

### a refactor acceptance requires a green baseline first _(archived)_

- **Scenario id:** `SCN-A2`
- **Intent:** `INT-3`
- **Source issue:** `honest-acceptance-for-config-and-refactor`
- **Landed:** 2026-08-13

### an in-place edit of a source file is blocked _(archived)_

- **Scenario id:** `SCN-A2`
- **Intent:** `INT-1`
- **Source issue:** `hook-bash-write-bypass`
- **Landed:** 2026-08-13

### a project that configures nothing is unaffected _(archived)_

- **Scenario id:** `SCN-A3`
- **Intent:** `INT-4`
- **Source issue:** `configurable-enforced-set`
- **Landed:** 2026-08-13

### the domain trigger is unchanged _(archived)_

- **Scenario id:** `SCN-A3`
- **Intent:** `INT-3`
- **Source issue:** `g5-trigger-matches-statement`
- **Landed:** 2026-08-13

### an unrecognised kind is refused _(archived)_

- **Scenario id:** `SCN-A3`
- **Intent:** `INT-2`
- **Source issue:** `honest-acceptance-for-config-and-refactor`
- **Landed:** 2026-08-13

### an inline interpreter script that writes a source file is blocked _(archived)_

- **Scenario id:** `SCN-A3`
- **Intent:** `INT-1`
- **Source issue:** `hook-bash-write-bypass`
- **Landed:** 2026-08-13

### a project cannot exempt what the framework enforces _(archived)_

- **Scenario id:** `SCN-A4`
- **Intent:** `INT-3`
- **Source issue:** `configurable-enforced-set`
- **Landed:** 2026-08-13

### a task matching neither condition still skips G5 _(archived)_

- **Scenario id:** `SCN-A4`
- **Intent:** `INT-3`
- **Source issue:** `g5-trigger-matches-statement`
- **Landed:** 2026-08-13

### the same command is allowed once a red is on record _(archived)_

- **Scenario id:** `SCN-A4`
- **Intent:** `INT-1`
- **Source issue:** `hook-bash-write-bypass`
- **Landed:** 2026-08-13

### the block names the rule that matched _(archived)_

- **Scenario id:** `SCN-B1`
- **Intent:** `INT-1`
- **Source issue:** `configurable-enforced-set`
- **Landed:** 2026-08-13

### any_of matches when one clause matches _(archived)_

- **Scenario id:** `SCN-B1`
- **Intent:** `INT-1`
- **Source issue:** `g5-trigger-matches-statement`
- **Landed:** 2026-08-13

### a validation acceptance records the validator's output _(archived)_

- **Scenario id:** `SCN-B1`
- **Intent:** `INT-1`
- **Source issue:** `honest-acceptance-for-config-and-refactor`
- **Landed:** 2026-08-13

### a read-only command is allowed _(archived)_

- **Scenario id:** `SCN-B1`
- **Intent:** `INT-3`
- **Source issue:** `hook-bash-write-bypass`
- **Landed:** 2026-08-13

### a built-in match says so _(archived)_

- **Scenario id:** `SCN-B2`
- **Intent:** `INT-1`
- **Source issue:** `configurable-enforced-set`
- **Landed:** 2026-08-13

### any_of fails when no clause matches _(archived)_

- **Scenario id:** `SCN-B2`
- **Intent:** `INT-1`
- **Source issue:** `g5-trigger-matches-statement`
- **Landed:** 2026-08-13

### a failing validator does not close the acceptance _(archived)_

- **Scenario id:** `SCN-B2`
- **Intent:** `INT-2`
- **Source issue:** `honest-acceptance-for-config-and-refactor`
- **Landed:** 2026-08-13

### writing a test file is allowed _(archived)_

- **Scenario id:** `SCN-B2`
- **Intent:** `INT-3`
- **Source issue:** `hook-bash-write-bypass`
- **Landed:** 2026-08-13

### any_of composes with sibling keys as an AND _(archived)_

- **Scenario id:** `SCN-B3`
- **Intent:** `INT-3`
- **Source issue:** `g5-trigger-matches-statement`
- **Landed:** 2026-08-13

### a refactor must run the same command it baselined _(archived)_

- **Scenario id:** `SCN-B3`
- **Intent:** `INT-3`
- **Source issue:** `honest-acceptance-for-config-and-refactor`
- **Landed:** 2026-08-13

### a redirect to a non-code destination is allowed _(archived)_

- **Scenario id:** `SCN-B3`
- **Intent:** `INT-3`
- **Source issue:** `hook-bash-write-bypass`
- **Landed:** 2026-08-13

### a refactor with an unchanged source tree is refused _(archived)_

- **Scenario id:** `SCN-B4`
- **Intent:** `INT-3`
- **Source issue:** `honest-acceptance-for-config-and-refactor`
- **Landed:** 2026-08-13

### a command that reverts to committed state is allowed _(archived)_

- **Scenario id:** `SCN-B4`
- **Intent:** `INT-3`
- **Source issue:** `hook-bash-write-bypass`
- **Landed:** 2026-08-13

### a refactor that preserved behaviour is recorded _(archived)_

- **Scenario id:** `SCN-B5`
- **Intent:** `INT-1`
- **Source issue:** `honest-acceptance-for-config-and-refactor`
- **Landed:** 2026-08-13

### a landed task without an approval is reported, not failed _(archived)_

- **Scenario id:** `SCN-C1`
- **Intent:** `INT-2`
- **Source issue:** `g5-trigger-matches-statement`
- **Landed:** 2026-08-13

### a path exempt for Edit is exempt for Bash _(archived)_

- **Scenario id:** `SCN-C1`
- **Intent:** `INT-1`
- **Source issue:** `hook-bash-write-bypass`
- **Landed:** 2026-08-13

### the hook names which marker permitted the edit _(archived)_

- **Scenario id:** `SCN-C1`
- **Intent:** `INT-4`
- **Source issue:** `honest-acceptance-for-config-and-refactor`
- **Landed:** 2026-08-13

### Compass's own shell scripts are enforced _(archived)_

- **Scenario id:** `SCN-C1`
- **Intent:** `INT-5`
- **Source issue:** `configurable-enforced-set`
- **Landed:** 2026-08-13

### an acceptance does not survive into the next task _(archived)_

- **Scenario id:** `SCN-C2`
- **Intent:** `INT-2`
- **Source issue:** `honest-acceptance-for-config-and-refactor`
- **Landed:** 2026-08-13

### the Spike route suspends the check for Bash too _(archived)_

- **Scenario id:** `SCN-C2`
- **Intent:** `INT-1`
- **Source issue:** `hook-bash-write-bypass`
- **Landed:** 2026-08-13

### an unreadable config does not block _(archived)_

- **Scenario id:** `SCN-F1`
- **Intent:** `INT-4`
- **Source issue:** `configurable-enforced-set`
- **Landed:** 2026-08-13

### the published guarantee matches the trigger _(archived)_

- **Scenario id:** `SCN-F1`
- **Intent:** `INT-4`
- **Source issue:** `g5-trigger-matches-statement`
- **Landed:** 2026-08-13

### the recorded evidence satisfies the existing checks _(archived)_

- **Scenario id:** `SCN-F1`
- **Intent:** `INT-1`
- **Source issue:** `honest-acceptance-for-config-and-refactor`
- **Landed:** 2026-08-13

### an undetectable write is a documented limit, not a silent one _(archived)_

- **Scenario id:** `SCN-F1`
- **Intent:** `INT-2`
- **Source issue:** `hook-bash-write-bypass`
- **Landed:** 2026-08-13

### test files stay exempt whatever the config says _(archived)_

- **Scenario id:** `SCN-F2`
- **Intent:** `INT-3`
- **Source issue:** `configurable-enforced-set`
- **Landed:** 2026-08-13

### governance carries a new version _(archived)_

- **Scenario id:** `SCN-F2`
- **Intent:** `INT-4`
- **Source issue:** `g5-trigger-matches-statement`
- **Landed:** 2026-08-13

### the anti-pattern is named where authors will meet it _(archived)_

- **Scenario id:** `SCN-F2`
- **Intent:** `INT-1`
- **Source issue:** `honest-acceptance-for-config-and-refactor`
- **Landed:** 2026-08-13

### the hook adds no meaningful cost to ordinary commands _(archived)_

- **Scenario id:** `SCN-F2`
- **Intent:** `INT-3`
- **Source issue:** `hook-bash-write-bypass`
- **Landed:** 2026-08-13

### Third-party actions in the self-check workflow are SHA-pinned _(archived)_

- **Scenario id:** `SCN-001`
- **Intent:** `INT-1`
- **Source issue:** `sha-pin-workflow-actions`
- **Landed:** 2026-08-13

### a full Specify with no scenarios blocks a code edit _(archived)_

- **Scenario id:** `SCN-A1`
- **Intent:** `INT-1`
- **Source issue:** `hook-enforces-g2`
- **Landed:** 2026-08-13

### a read-only open is allowed _(archived)_

- **Scenario id:** `SCN-A1`
- **Intent:** `INT-1`
- **Source issue:** `hotfix-1-8-1-false-blocks-and-land-scope`
- **Landed:** 2026-08-13

### a re-frame that changes gates but not the route name is logged _(archived)_

- **Scenario id:** `SCN-A1`
- **Intent:** `INT-1`
- **Source issue:** `spine-records-the-truth`
- **Landed:** 2026-08-13

### the new statuses validate _(archived)_

- **Scenario id:** `SCN-A1`
- **Intent:** `INT-2`
- **Source issue:** `status-vocabulary`
- **Landed:** 2026-08-13

### a missing changed_files path fails a task claiming correctness _(archived)_

- **Scenario id:** `SCN-A1`
- **Intent:** `INT-1`
- **Source issue:** `trace-rot-detection`
- **Landed:** 2026-08-13

### scenarios present allow the edit _(archived)_

- **Scenario id:** `SCN-A2`
- **Intent:** `INT-1`
- **Source issue:** `hook-enforces-g2`
- **Landed:** 2026-08-13

### a path named inside written prose is not the write target _(archived)_

- **Scenario id:** `SCN-A2`
- **Intent:** `INT-1`
- **Source issue:** `hotfix-1-8-1-false-blocks-and-land-scope`
- **Landed:** 2026-08-13

### a re-frame with no material change is not logged _(archived)_

- **Scenario id:** `SCN-A2`
- **Intent:** `INT-1`
- **Source issue:** `spine-records-the-truth`
- **Landed:** 2026-08-13

### an unknown status is still rejected _(archived)_

- **Scenario id:** `SCN-A2`
- **Intent:** `INT-5`
- **Source issue:** `status-vocabulary`
- **Landed:** 2026-08-13

### the message offers the new path when git knows the rename _(archived)_

- **Scenario id:** `SCN-A2`
- **Intent:** `INT-2`
- **Source issue:** `trace-rot-detection`
- **Landed:** 2026-08-13

### routes without a full Specify are unaffected _(archived)_

- **Scenario id:** `SCN-A3`
- **Intent:** `INT-3`
- **Source issue:** `hook-enforces-g2`
- **Landed:** 2026-08-13

### an inline script that opens a source file for writing is still blocked _(archived)_

- **Scenario id:** `SCN-A3`
- **Intent:** `INT-3`
- **Source issue:** `hotfix-1-8-1-false-blocks-and-land-scope`
- **Landed:** 2026-08-13

### each entry records what changed _(archived)_

- **Scenario id:** `SCN-A3`
- **Intent:** `INT-1`
- **Source issue:** `spine-records-the-truth`
- **Landed:** 2026-08-13

### a parked task can record why and when _(archived)_

- **Scenario id:** `SCN-A3`
- **Intent:** `INT-1`
- **Source issue:** `status-vocabulary`
- **Landed:** 2026-08-13

### a task that has not yet claimed correctness is not failed _(archived)_

- **Scenario id:** `SCN-A3`
- **Intent:** `INT-1`
- **Source issue:** `trace-rot-detection`
- **Landed:** 2026-08-13

### a Spike suspends the G2 check _(archived)_

- **Scenario id:** `SCN-A4`
- **Intent:** `INT-3`
- **Source issue:** `hook-enforces-g2`
- **Landed:** 2026-08-13

### a heredoc that writes a source file is still blocked _(archived)_

- **Scenario id:** `SCN-A4`
- **Intent:** `INT-3`
- **Source issue:** `hotfix-1-8-1-false-blocks-and-land-scope`
- **Landed:** 2026-08-13

### each entry carries a kind _(archived)_

- **Scenario id:** `SCN-A4`
- **Intent:** `INT-2`
- **Source issue:** `spine-records-the-truth`
- **Landed:** 2026-08-13

### calibration counts only judgement re-frames _(archived)_

- **Scenario id:** `SCN-A5`
- **Intent:** `INT-2`
- **Source issue:** `spine-records-the-truth`
- **Landed:** 2026-08-13

### the message names the guardrail and the remedy _(archived)_

- **Scenario id:** `SCN-B1`
- **Intent:** `INT-1`
- **Source issue:** `hook-enforces-g2`
- **Landed:** 2026-08-13

### the post-hook retry re-stages only the task's files _(archived)_

- **Scenario id:** `SCN-B1`
- **Intent:** `INT-2`
- **Source issue:** `hotfix-1-8-1-false-blocks-and-land-scope`
- **Landed:** 2026-08-13

### a raw log declared as test-run is refused at write time _(archived)_

- **Scenario id:** `SCN-B1`
- **Intent:** `INT-3`
- **Source issue:** `spine-records-the-truth`
- **Landed:** 2026-08-13

### set-status writes the field _(archived)_

- **Scenario id:** `SCN-B1`
- **Intent:** `INT-3`
- **Source issue:** `status-vocabulary`
- **Landed:** 2026-08-13

### a landed task with a rotted trace is reported, not failed _(archived)_

- **Scenario id:** `SCN-B1`
- **Intent:** `INT-3`
- **Source issue:** `trace-rot-detection`
- **Landed:** 2026-08-13

### a test file stays editable _(archived)_

- **Scenario id:** `SCN-B2`
- **Intent:** `INT-3`
- **Source issue:** `hook-enforces-g2`
- **Landed:** 2026-08-13

### an out-of-scope staged path aborts the commit _(archived)_

- **Scenario id:** `SCN-B2`
- **Intent:** `INT-2`
- **Source issue:** `hotfix-1-8-1-false-blocks-and-land-scope`
- **Landed:** 2026-08-13

### a real run record is accepted _(archived)_

- **Scenario id:** `SCN-B2`
- **Intent:** `INT-3`
- **Source issue:** `spine-records-the-truth`
- **Landed:** 2026-08-13

### set-status refuses a value outside the vocabulary _(archived)_

- **Scenario id:** `SCN-B2`
- **Intent:** `INT-3`
- **Source issue:** `status-vocabulary`
- **Landed:** 2026-08-13

### a clean task says what it verified _(archived)_

- **Scenario id:** `SCN-B2`
- **Intent:** `INT-1`
- **Source issue:** `trace-rot-detection`
- **Landed:** 2026-08-13

### a task that declares nothing is not silently widened _(archived)_

- **Scenario id:** `SCN-B3`
- **Intent:** `INT-2`
- **Source issue:** `hotfix-1-8-1-false-blocks-and-land-scope`
- **Landed:** 2026-08-13

### a missing file is refused _(archived)_

- **Scenario id:** `SCN-B3`
- **Intent:** `INT-3`
- **Source issue:** `spine-records-the-truth`
- **Landed:** 2026-08-13

### landing through set-status still respects the gates _(archived)_

- **Scenario id:** `SCN-B3`
- **Intent:** `INT-3`
- **Source issue:** `status-vocabulary`
- **Landed:** 2026-08-13

### types with no shape contract are unaffected _(archived)_

- **Scenario id:** `SCN-B4`
- **Intent:** `INT-3`
- **Source issue:** `spine-records-the-truth`
- **Landed:** 2026-08-13

### a scenario may record what supersedes it _(archived)_

- **Scenario id:** `SCN-C1`
- **Intent:** `INT-4`
- **Source issue:** `spine-records-the-truth`
- **Landed:** 2026-08-13

### flow separates parked work from active work _(archived)_

- **Scenario id:** `SCN-C1`
- **Intent:** `INT-1`
- **Source issue:** `status-vocabulary`
- **Landed:** 2026-08-13

### no new check name appears in governance _(archived)_

- **Scenario id:** `SCN-C1`
- **Intent:** `INT-4`
- **Source issue:** `trace-rot-detection`
- **Landed:** 2026-08-13

### superseded_by must name a scenario that exists _(archived)_

- **Scenario id:** `SCN-C2`
- **Intent:** `INT-4`
- **Source issue:** `spine-records-the-truth`
- **Landed:** 2026-08-13

### calibration excludes parked and abandoned _(archived)_

- **Scenario id:** `SCN-C2`
- **Intent:** `INT-1`
- **Source issue:** `status-vocabulary`
- **Landed:** 2026-08-13

### the living spec still derives only from landed tasks _(archived)_

- **Scenario id:** `SCN-C3`
- **Intent:** `INT-4`
- **Source issue:** `status-vocabulary`
- **Landed:** 2026-08-13

### the 1.8.0 detection scenarios keep passing _(archived)_

- **Scenario id:** `SCN-F1`
- **Intent:** `INT-3`
- **Source issue:** `hotfix-1-8-1-false-blocks-and-land-scope`
- **Landed:** 2026-08-13

### an unreadable spine does not block _(archived)_

- **Scenario id:** `SCN-F1`
- **Intent:** `INT-4`
- **Source issue:** `hook-enforces-g2`
- **Landed:** 2026-08-13

### task.yml files written before this keep working _(archived)_

- **Scenario id:** `SCN-F1`
- **Intent:** `INT-5`
- **Source issue:** `spine-records-the-truth`
- **Landed:** 2026-08-13

### a task.yml with no status still behaves as active _(archived)_

- **Scenario id:** `SCN-F1`
- **Intent:** `INT-5`
- **Source issue:** `status-vocabulary`
- **Landed:** 2026-08-13

### a deliberately deleted file is not trace rot _(archived)_

- **Scenario id:** `SCN-F1`
- **Intent:** `INT-3`
- **Source issue:** `trace-rot-detection`
- **Landed:** 2026-08-13

### G2 is checked before the red _(archived)_

- **Scenario id:** `SCN-F2`
- **Intent:** `INT-2`
- **Source issue:** `hook-enforces-g2`
- **Landed:** 2026-08-13

### a project outside git still gets the check _(archived)_

- **Scenario id:** `SCN-F2`
- **Intent:** `INT-1`
- **Source issue:** `trace-rot-detection`
- **Landed:** 2026-08-13

### landed is the only privileged value _(archived)_

- **Scenario id:** `SCN-F2`
- **Intent:** `INT-5`
- **Source issue:** `status-vocabulary`
- **Landed:** 2026-08-13

### swarm.sh strips markdown punctuation from the branch-name cell _(archived)_

- **Scenario id:** `TRC-1`
- **Intent:** `INT-1`
- **Source issue:** `swarm-script-strips-markdown`
- **Landed:** 2026-08-13

### no issue claims to be in flight when it is not _(archived)_

- **Scenario id:** `SW-1`
- **Intent:** `HYGIENE`
- **Source issue:** `stale-active-issue-sweep`
- **Landed:** 2026-08-13

### a status change is justified by evidence _(archived)_

- **Scenario id:** `SW-2`
- **Intent:** `HYGIENE`
- **Source issue:** `stale-active-issue-sweep`
- **Landed:** 2026-08-13

### nothing is marked landed without its gates _(archived)_

- **Scenario id:** `SW-3`
- **Intent:** `HYGIENE`
- **Source issue:** `stale-active-issue-sweep`
- **Landed:** 2026-08-13

### the identifier-expansion rule is stated where agent speech is governed _(archived)_

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-F0`
- **Source issue:** `identifiers-and-vocabulary-in-printed-output`
- **Landed:** 2026-08-13

### the receipt prints a scenario's title beside its id _(archived)_

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-F0`
- **Source issue:** `identifiers-and-vocabulary-in-printed-output`
- **Landed:** 2026-08-13

### a printed identifier is never truncated _(archived)_

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-F0`
- **Source issue:** `identifiers-and-vocabulary-in-printed-output`
- **Landed:** 2026-08-13

### the approach evaluator prints no retired vocabulary name _(archived)_

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-F1`
- **Source issue:** `identifiers-and-vocabulary-in-printed-output`
- **Landed:** 2026-08-13

### the printed-output scan can fail _(archived)_

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-F1`
- **Source issue:** `identifiers-and-vocabulary-in-printed-output`
- **Landed:** 2026-08-13

### compass check counts clearances that checked nothing apart from verified ones _(archived)_

- **Scenario id:** `TRC-D1`
- **Intent:** `INT-F5`
- **Source issue:** `identifiers-and-vocabulary-in-printed-output`
- **Landed:** 2026-08-13

### triage states permitted parallel streams and no topology _(archived)_

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-R3`
- **Source issue:** `dry-run-2-rulings`
- **Landed:** 2026-08-14

### the stream ceiling is an integer, not a sentence _(archived)_

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-R3`
- **Source issue:** `dry-run-2-rulings`
- **Landed:** 2026-08-14

### a passing check summary prints no denominator _(archived)_

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-R4`
- **Source issue:** `dry-run-2-rulings`
- **Landed:** 2026-08-14

### suite-passed does not present a binding as coverage _(archived)_

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-R5`
- **Source issue:** `dry-run-2-rulings`
- **Landed:** 2026-08-14

### a skipped test does not count as a resolving test _(archived)_

- **Scenario id:** `TRC-C2`
- **Intent:** `INT-R5`
- **Source issue:** `dry-run-2-rulings`
- **Landed:** 2026-08-14

### YAML values are scanned for retired vocabulary _(archived)_

- **Scenario id:** `TRC-D1`
- **Intent:** `INT-R2`
- **Source issue:** `dry-run-2-rulings`
- **Landed:** 2026-08-14

### every position exemption names its reason _(archived)_

- **Scenario id:** `TRC-D2`
- **Intent:** `INT-R2`
- **Source issue:** `dry-run-2-rulings`
- **Landed:** 2026-08-14

### the hook allows a code file outside the project _(archived)_

- **Scenario id:** `FF-1`
- **Intent:** `INT-57`
- **Source issue:** `field-feedback-hook-scope-and-restage`
- **Landed:** 2026-08-14

### the re-stage does not widen the commit beyond what was staged _(archived)_

- **Scenario id:** `FF-3`
- **Intent:** `INT-58`
- **Source issue:** `field-feedback-hook-scope-and-restage`
- **Landed:** 2026-08-14

### published launch copy should be under version control _(archived)_

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-3`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### an em dash in published copy should fail the guard _(archived)_

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-3`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### the filesystem fallback should not be used where git works _(archived)_

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-3`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### build noise should stay out of the scan _(archived)_

- **Scenario id:** `TRC-A4`
- **Intent:** `INT-3`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### the guard's docstring should record that the omission was silent _(archived)_

- **Scenario id:** `TRC-A5`
- **Intent:** `INT-3`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### an en dash should not be flagged _(archived)_

- **Scenario id:** `TRC-A6`
- **Intent:** `INT-3`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### falling back to the filesystem should announce itself _(archived)_

- **Scenario id:** `TRC-A8`
- **Intent:** `INT-3`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### a file declaring its own exclusions should not be tracked as publication copy _(archived)_

- **Scenario id:** `TRC-A9`
- **Intent:** `INT-3`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### "seam" used for code structure should be flagged _(archived)_

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-1`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### "seam" used for anything else should not be flagged _(archived)_

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-1`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### the ban should name what to write instead _(archived)_

- **Scenario id:** `TRC-B3`
- **Intent:** `INT-1`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### a rare word quoted from a tool should survive the ban _(archived)_

- **Scenario id:** `TRC-B4`
- **Intent:** `INT-1`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### "un-conflate" should be gone from governance _(archived)_

- **Scenario id:** `TRC-B5`
- **Intent:** `INT-5`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### the shipped list should say what is true today, not what is intended _(archived)_

- **Scenario id:** `TRC-B7`
- **Intent:** `INT-1`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### the strategy should state the order, with real pairs _(archived)_

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-2`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### an empty gloss registry should fail loudly, never report zero _(archived)_

- **Scenario id:** `TRC-C10`
- **Intent:** `INT-2`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### governance prose should be scanned for bare codes, not exempt by path _(archived)_

- **Scenario id:** `TRC-C11`
- **Intent:** `INT-1`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### the claims gate should say it checks traceability, not truth _(archived)_

- **Scenario id:** `TRC-C12`
- **Intent:** `INT-1`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### every screen printing a fired rule should put the meaning first _(archived)_

- **Scenario id:** `TRC-C15`
- **Intent:** `INT-2`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### a bare code in human-facing output should be counted _(archived)_

- **Scenario id:** `TRC-C2`
- **Intent:** `INT-2`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### a code with its meaning in front of it should not be counted _(archived)_

- **Scenario id:** `TRC-C3`
- **Intent:** `INT-2`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### a non-zero count should report rather than block _(archived)_

- **Scenario id:** `TRC-C4`
- **Intent:** `INT-2`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### the reviewer should be told to look for this _(archived)_

- **Scenario id:** `TRC-C5`
- **Intent:** `INT-2`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### the first run should record a starting count _(archived)_

- **Scenario id:** `TRC-C6`
- **Intent:** `INT-2`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### the meaning arriving after the code should still be counted _(archived)_

- **Scenario id:** `TRC-C7`
- **Intent:** `INT-2`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### an entry that is only an identifier should not have to gloss itself _(archived)_

- **Scenario id:** `TRC-C8`
- **Intent:** `INT-2`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### a derivation failure should name what changed and what was expected _(archived)_

- **Scenario id:** `TRC-C9`
- **Intent:** `INT-1`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### the title rule should name the shapes it refuses _(archived)_

- **Scenario id:** `TRC-D1`
- **Intent:** `INT-1`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### the body template should say what a reviewer needs _(archived)_

- **Scenario id:** `TRC-D2`
- **Intent:** `INT-1`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### a commit title should be held to the same rule _(archived)_

- **Scenario id:** `TRC-D3`
- **Intent:** `INT-1`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### a correction should not leave the record contradicting itself _(archived)_

- **Scenario id:** `TRC-D4`
- **Intent:** `INT-1`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### a search reporting zero should have been proved able to find something _(archived)_

- **Scenario id:** `TRC-D5`
- **Intent:** `INT-1`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### the correction rule should say which places take a correction and which take a note _(archived)_

- **Scenario id:** `TRC-D6`
- **Intent:** `INT-1`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### a sentence of thirty-one words or more should be reported _(archived)_

- **Scenario id:** `TRC-E1`
- **Intent:** `INT-4`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### the long-sentence report should never fail a build _(archived)_

- **Scenario id:** `TRC-E2`
- **Intent:** `INT-4`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### no em dash should remain in published copy _(archived)_

- **Scenario id:** `TRC-G1`
- **Intent:** `INT-5`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### no structural use of "seam" should remain _(archived)_

- **Scenario id:** `TRC-G2`
- **Intent:** `INT-5`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### the living spec's stale title should be fixed by re-deriving it _(archived)_

- **Scenario id:** `TRC-G3`
- **Intent:** `INT-5`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### a banned word should never be fixed by deleting the identifier _(archived)_

- **Scenario id:** `TRC-X3`
- **Intent:** `INT-2`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### repairing a banned word should not paraphrase a quoted tool string _(archived)_

- **Scenario id:** `TRC-X4`
- **Intent:** `INT-1`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### an incomplete project governance directory should be refused rather than quietly replaced _(archived)_

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-2`
- **Source issue:** `claims-match-what-is-proved`
- **Landed:** 2026-08-22

### the refusal should name the file it found and the file it expected _(archived)_

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-2`
- **Source issue:** `claims-match-what-is-proved`
- **Landed:** 2026-08-22

### a project that has said nothing about governance should still use the shipped defaults silently _(archived)_

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-2`
- **Source issue:** `claims-match-what-is-proved`
- **Landed:** 2026-08-22

### a complete project governance directory should still be used _(archived)_

- **Scenario id:** `TRC-A4`
- **Intent:** `INT-2`
- **Source issue:** `claims-match-what-is-proved`
- **Landed:** 2026-08-22

### the documentation should state that project governance replaces the shipped defaults _(archived)_

- **Scenario id:** `TRC-A5`
- **Intent:** `INT-2`
- **Source issue:** `claims-match-what-is-proved`
- **Landed:** 2026-08-22

### an incomplete governance directory outside the project should not stop work inside it _(archived)_

- **Scenario id:** `TRC-A6`
- **Intent:** `INT-2`
- **Source issue:** `claims-match-what-is-proved`
- **Landed:** 2026-08-22

### the promise should not say a test ran when only a command exited zero _(archived)_

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-1`
- **Source issue:** `claims-match-what-is-proved`
- **Landed:** 2026-08-22

### the promise should read the same in every place it is made _(archived)_

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-1`
- **Source issue:** `claims-match-what-is-proved`
- **Landed:** 2026-08-22

### the safety contract should state what a green record does not establish _(archived)_

- **Scenario id:** `TRC-B3`
- **Intent:** `INT-1`
- **Source issue:** `claims-match-what-is-proved`
- **Landed:** 2026-08-22

### every guarantee should name the mechanism that backs it _(archived)_

- **Scenario id:** `TRC-B4`
- **Intent:** `INT-1`
- **Source issue:** `claims-match-what-is-proved`
- **Landed:** 2026-08-22

### the guide should say that project governance is executable code _(archived)_

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-3`
- **Source issue:** `claims-match-what-is-proved`
- **Landed:** 2026-08-22

### the guide should not offer pull-request review as the execution boundary _(archived)_

- **Scenario id:** `TRC-C2`
- **Intent:** `INT-3`
- **Source issue:** `claims-match-what-is-proved`
- **Landed:** 2026-08-22

### the guide should point at the work that closes the gap _(archived)_

- **Scenario id:** `TRC-C3`
- **Intent:** `INT-3`
- **Source issue:** `claims-match-what-is-proved`
- **Landed:** 2026-08-22

### a guarantee with no backing mechanism should fail the check _(archived)_

- **Scenario id:** `TRC-D1`
- **Intent:** `INT-4`
- **Source issue:** `claims-match-what-is-proved`
- **Landed:** 2026-08-22

### a backing mechanism that does not exist should fail the check _(archived)_

- **Scenario id:** `TRC-D2`
- **Intent:** `INT-4`
- **Source issue:** `claims-match-what-is-proved`
- **Landed:** 2026-08-22

### a project governance directory missing its guardrails should be refused the same way _(archived)_

- **Scenario id:** `TRC-F1`
- **Intent:** `INT-2`
- **Source issue:** `claims-match-what-is-proved`
- **Landed:** 2026-08-22

### narrowing the promise should not weaken what the check actually enforces _(archived)_

- **Scenario id:** `TRC-F2`
- **Intent:** `INT-1`
- **Source issue:** `claims-match-what-is-proved`
- **Landed:** 2026-08-22

### no published file should misspell the word the framework renamed to _(archived)_

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `public-docs-tell-the-truth`
- **Landed:** 2026-08-22

### the safety contract should be titled for the release it describes _(archived)_

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `public-docs-tell-the-truth`
- **Landed:** 2026-08-22

### the security guide should not deny a distribution channel the project publishes on _(archived)_

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `public-docs-tell-the-truth`
- **Landed:** 2026-08-22

### a document should not point at files that do not exist _(archived)_

- **Scenario id:** `TRC-A4`
- **Intent:** `INT-1`
- **Source issue:** `public-docs-tell-the-truth`
- **Landed:** 2026-08-22

### a live architecture artifact should not describe a retired stage as current _(archived)_

- **Scenario id:** `TRC-A5`
- **Intent:** `INT-1`
- **Source issue:** `public-docs-tell-the-truth`
- **Landed:** 2026-08-22

### a message the CLI prints should not tell a user to run a stage that no longer exists _(archived)_

- **Scenario id:** `TRC-A6`
- **Intent:** `INT-1`
- **Source issue:** `public-docs-tell-the-truth`
- **Landed:** 2026-08-22

### a retired stage name alone in a table cell should be caught _(archived)_

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-2`
- **Source issue:** `public-docs-tell-the-truth`
- **Landed:** 2026-08-22

### a retired stage name alone in a bold run should be caught _(archived)_

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-2`
- **Source issue:** `public-docs-tell-the-truth`
- **Landed:** 2026-08-22

### every retired stage name should be bound to the label shape, not only Frame _(archived)_

- **Scenario id:** `TRC-B3`
- **Intent:** `INT-2`
- **Source issue:** `public-docs-tell-the-truth`
- **Landed:** 2026-08-22

### the scan should report the count it found, not only that it found some _(archived)_

- **Scenario id:** `TRC-B4`
- **Intent:** `INT-2`
- **Source issue:** `public-docs-tell-the-truth`
- **Landed:** 2026-08-22

### a retired stage name used mid-sentence should be caught _(archived)_

- **Scenario id:** `TRC-B5`
- **Intent:** `INT-2`
- **Source issue:** `public-docs-tell-the-truth`
- **Landed:** 2026-08-22

### a retired word used as an ordinary verb should not be caught _(archived)_

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-3`
- **Source issue:** `public-docs-tell-the-truth`
- **Landed:** 2026-08-22

### a bold run that begins with a retired word but continues into a sentence should not be caught _(archived)_

- **Scenario id:** `TRC-C2`
- **Intent:** `INT-3`
- **Source issue:** `public-docs-tell-the-truth`
- **Landed:** 2026-08-22

### the tolerance fixture should carry every shape the patterns must walk past _(archived)_

- **Scenario id:** `TRC-C3`
- **Intent:** `INT-3`
- **Source issue:** `public-docs-tell-the-truth`
- **Landed:** 2026-08-22

### widening the patterns should not change what the scan reports on today's clean surfaces _(archived)_

- **Scenario id:** `TRC-C4`
- **Intent:** `INT-3`
- **Source issue:** `public-docs-tell-the-truth`
- **Landed:** 2026-08-22

### no live surface should carry a retired stage name _(archived)_

- **Scenario id:** `TRC-D1`
- **Intent:** `INT-1`
- **Source issue:** `public-docs-tell-the-truth`
- **Landed:** 2026-08-22

### a repair should not change what an agent is instructed to do _(archived)_

- **Scenario id:** `TRC-D2`
- **Intent:** `INT-1`
- **Source issue:** `public-docs-tell-the-truth`
- **Landed:** 2026-08-22

### history should stay exempt and stay honest _(archived)_

- **Scenario id:** `TRC-D3`
- **Intent:** `INT-2`
- **Source issue:** `public-docs-tell-the-truth`
- **Landed:** 2026-08-22

### a claim about every failure message should be checked or withdrawn _(archived)_

- **Scenario id:** `TRC-E1`
- **Intent:** `INT-4`
- **Source issue:** `public-docs-tell-the-truth`
- **Landed:** 2026-08-22

### a narrowed guarantee should still name its backing mechanism _(archived)_

- **Scenario id:** `TRC-E2`
- **Intent:** `INT-4`
- **Source issue:** `public-docs-tell-the-truth`
- **Landed:** 2026-08-22

### the decay rule should say what it asks of the reader _(archived)_

- **Scenario id:** `TRC-F1`
- **Intent:** `INT-5`
- **Source issue:** `public-docs-tell-the-truth`
- **Landed:** 2026-08-22

### the launch article should read as publication copy throughout _(archived)_

- **Scenario id:** `TRC-F2`
- **Intent:** `INT-5`
- **Source issue:** `public-docs-tell-the-truth`
- **Landed:** 2026-08-22

### a project command should not run unless the project has opted in _(archived)_

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `project-commands-are-a-trust-boundary`
- **Landed:** 2026-08-22

### a project that has opted in should have its command run _(archived)_

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `project-commands-are-a-trust-boundary`
- **Landed:** 2026-08-22

### the report should distinguish disabled from nothing declared _(archived)_

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `project-commands-are-a-trust-boundary`
- **Landed:** 2026-08-22

### a command should be refused when the CI environment says the contribution is untrusted _(archived)_

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-2`
- **Source issue:** `project-commands-are-a-trust-boundary`
- **Landed:** 2026-08-22

### the repository must not be able to switch the refusal off _(archived)_

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-2`
- **Source issue:** `project-commands-are-a-trust-boundary`
- **Landed:** 2026-08-22

### detection should not depend on one CI provider _(archived)_

- **Scenario id:** `TRC-B3`
- **Intent:** `INT-2`
- **Source issue:** `project-commands-are-a-trust-boundary`
- **Landed:** 2026-08-22

### an ordinary local run should not be treated as untrusted _(archived)_

- **Scenario id:** `TRC-B4`
- **Intent:** `INT-2`
- **Source issue:** `project-commands-are-a-trust-boundary`
- **Landed:** 2026-08-22

### an unrecognised CI provider should be refused rather than trusted _(archived)_

- **Scenario id:** `TRC-B5`
- **Intent:** `INT-2`
- **Source issue:** `project-commands-are-a-trust-boundary`
- **Landed:** 2026-08-22

### a project should be able to name a script instead of writing a shell string _(archived)_

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-3`
- **Source issue:** `project-commands-are-a-trust-boundary`
- **Landed:** 2026-08-22

### a script path outside the project should be refused _(archived)_

- **Scenario id:** `TRC-C2`
- **Intent:** `INT-3`
- **Source issue:** `project-commands-are-a-trust-boundary`
- **Landed:** 2026-08-22

### the shell form should keep working, and say what it costs _(archived)_

- **Scenario id:** `TRC-C3`
- **Intent:** `INT-3`
- **Source issue:** `project-commands-are-a-trust-boundary`
- **Landed:** 2026-08-22

### the reference workflow should declare the token permissions it needs _(archived)_

- **Scenario id:** `TRC-D1`
- **Intent:** `INT-4`
- **Source issue:** `project-commands-are-a-trust-boundary`
- **Landed:** 2026-08-22

### Compass's own workflow should follow the same posture _(archived)_

- **Scenario id:** `TRC-D2`
- **Intent:** `INT-4`
- **Source issue:** `project-commands-are-a-trust-boundary`
- **Landed:** 2026-08-22

### the security guide should say what a project must decide about untrusted pull requests _(archived)_

- **Scenario id:** `TRC-D3`
- **Intent:** `INT-4`
- **Source issue:** `project-commands-are-a-trust-boundary`
- **Landed:** 2026-08-22

### a project whose command stops running should be told _(archived)_

- **Scenario id:** `TRC-E1`
- **Intent:** `INT-5`
- **Source issue:** `project-commands-are-a-trust-boundary`
- **Landed:** 2026-08-22

### the guarantee about declared guardrails should still hold _(archived)_

- **Scenario id:** `TRC-E2`
- **Intent:** `INT-5`
- **Source issue:** `project-commands-are-a-trust-boundary`
- **Landed:** 2026-08-22

### recording a scenario-bound green leaves the unbound green intact _(archived)_

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `tdd-green-unbound-record`
- **Landed:** 2026-08-23

### recording a scenario-bound acceptance leaves the unbound acceptance intact _(archived)_

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `tdd-green-unbound-record`
- **Landed:** 2026-08-23

### no evidence-writing verb overwrites a path the registry names _(archived)_

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `tdd-green-unbound-record`
- **Landed:** 2026-08-23

### the unbound record can still be re-recorded deliberately _(archived)_

- **Scenario id:** `TRC-A4`
- **Intent:** `INT-1`
- **Source issue:** `tdd-green-unbound-record`
- **Landed:** 2026-08-23

### a recorded run carries an identity unique to that run _(archived)_

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-2`
- **Source issue:** `tdd-green-unbound-record`
- **Landed:** 2026-08-23

### re-recording the same command produces a different identity _(archived)_

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-2`
- **Source issue:** `tdd-green-unbound-record`
- **Landed:** 2026-08-23

### the registry entry stores the identity of the run it was created from _(archived)_

- **Scenario id:** `TRC-B3`
- **Intent:** `INT-2`
- **Source issue:** `tdd-green-unbound-record`
- **Landed:** 2026-08-23

### a citation whose record has been replaced is reported _(archived)_

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-3`
- **Source issue:** `tdd-green-unbound-record`
- **Landed:** 2026-08-23

### a citation that matches its record is not reported _(archived)_

- **Scenario id:** `TRC-C2`
- **Intent:** `INT-3`
- **Source issue:** `tdd-green-unbound-record`
- **Landed:** 2026-08-23

### the report names the evidence id, the path, and what changed _(archived)_

- **Scenario id:** `TRC-C3`
- **Intent:** `INT-3`
- **Source issue:** `tdd-green-unbound-record`
- **Landed:** 2026-08-23

### a record written before this change does not fail the check _(archived)_

- **Scenario id:** `TRC-D1`
- **Intent:** `INT-4`
- **Source issue:** `tdd-green-unbound-record`
- **Landed:** 2026-08-23

### an unverifiable record is reported as unverifiable, not as verified _(archived)_

- **Scenario id:** `TRC-D2`
- **Intent:** `INT-4`
- **Source issue:** `tdd-green-unbound-record`
- **Landed:** 2026-08-23

### no published surface claims a green is always written to the shared path _(archived)_

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `docs-describe-the-old-evidence-path`
- **Landed:** 2026-08-23

### the documentation names both forms and says which is written when _(archived)_

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `docs-describe-the-old-evidence-path`
- **Landed:** 2026-08-23

### a worked example shows the path a reader will actually see _(archived)_

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `docs-describe-the-old-evidence-path`
- **Landed:** 2026-08-23

### the guard fails when a surface reintroduces the old claim _(archived)_

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-2`
- **Source issue:** `docs-describe-the-old-evidence-path`
- **Landed:** 2026-08-23

### every CLI module's banner describes what the verbs actually write _(archived)_

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-3`
- **Source issue:** `docs-describe-the-old-evidence-path`
- **Landed:** 2026-08-23

### the always-loaded instructions state the four-part reply shape _(archived)_

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `agent-speech-is-unchecked`
- **Landed:** 2026-08-23

### the shape carries its three rules _(archived)_

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `agent-speech-is-unchecked`
- **Landed:** 2026-08-23

### the length tension is resolved rather than left open _(archived)_

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `agent-speech-is-unchecked`
- **Landed:** 2026-08-23

### the portable instructions carry the shape too _(archived)_

- **Scenario id:** `TRC-A4`
- **Intent:** `INT-1`
- **Source issue:** `agent-speech-is-unchecked`
- **Landed:** 2026-08-23

### a worked list gives each leaky term its plain-English form _(archived)_

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-2`
- **Source issue:** `agent-speech-is-unchecked`
- **Landed:** 2026-08-23

### the list covers every term the cold reader named _(archived)_

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-2`
- **Source issue:** `agent-speech-is-unchecked`
- **Landed:** 2026-08-23

### the rule is attached to a moment, not stated as advice _(archived)_

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-3`
- **Source issue:** `agent-speech-is-unchecked`
- **Landed:** 2026-08-23

### the headings tell distinguishes a label from an answer _(archived)_

- **Scenario id:** `TRC-D1`
- **Intent:** `INT-4`
- **Source issue:** `agent-speech-is-unchecked`
- **Landed:** 2026-08-23

### no instruction tells a session both to use and to avoid reply headings _(archived)_

- **Scenario id:** `TRC-D2`
- **Intent:** `INT-4`
- **Source issue:** `agent-speech-is-unchecked`
- **Landed:** 2026-08-23

### a registered artifact declares its kind, path, status and reason _(archived)_

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `the-human-front-door`
- **Landed:** 2026-08-23

### an omitted artifact records why it was omitted _(archived)_

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `the-human-front-door`
- **Landed:** 2026-08-23

### the schema refuses an entry that explains nothing _(archived)_

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `the-human-front-door`
- **Landed:** 2026-08-23

### a registered path resolves ahead of the flat filename _(archived)_

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-2`
- **Source issue:** `the-human-front-door`
- **Landed:** 2026-08-23

### an issue with no registry still resolves its artifacts _(archived)_

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-2`
- **Source issue:** `the-human-front-door`
- **Landed:** 2026-08-23

### an artifact that resolves by neither route is reported, not silently absent _(archived)_

- **Scenario id:** `TRC-B3`
- **Intent:** `INT-2`
- **Source issue:** `the-human-front-door`
- **Landed:** 2026-08-23

### every landed issue still resolves after the change _(archived)_

- **Scenario id:** `TRC-B4`
- **Intent:** `INT-2`
- **Source issue:** `the-human-front-door`
- **Landed:** 2026-08-23

### the dashboard names the decision required and where to start _(archived)_

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-3`
- **Source issue:** `the-human-front-door`
- **Landed:** 2026-08-23

### it lists every registered artifact with its status and why it exists _(archived)_

- **Scenario id:** `TRC-C2`
- **Intent:** `INT-3`
- **Source issue:** `the-human-front-door`
- **Landed:** 2026-08-23

### it lists what was deliberately omitted, with reasons _(archived)_

- **Scenario id:** `TRC-C3`
- **Intent:** `INT-3`
- **Source issue:** `the-human-front-door`
- **Landed:** 2026-08-23

### it carries no raw evidence _(archived)_

- **Scenario id:** `TRC-C4`
- **Intent:** `INT-3`
- **Source issue:** `the-human-front-door`
- **Landed:** 2026-08-23

### the dashboard can be generated and checked from the CLI _(archived)_

- **Scenario id:** `TRC-C5`
- **Intent:** `INT-3`
- **Source issue:** `the-human-front-door`
- **Landed:** 2026-08-23

### the pack separates a document that exists from one still owed _(archived)_

- **Scenario id:** `TRC-C6`
- **Intent:** `INT-1`
- **Source issue:** `the-human-front-door`
- **Landed:** 2026-08-23

### a document's status can be moved, and an omission recorded _(archived)_

- **Scenario id:** `TRC-C7`
- **Intent:** `INT-1`
- **Source issue:** `the-human-front-door`
- **Landed:** 2026-08-23

### a dashboard that no longer matches the spine is reported as stale _(archived)_

- **Scenario id:** `TRC-D1`
- **Intent:** `INT-4`
- **Source issue:** `the-human-front-door`
- **Landed:** 2026-08-23

### a drifted dashboard fails the check rather than warning _(archived)_

- **Scenario id:** `TRC-D2`
- **Intent:** `INT-4`
- **Source issue:** `the-human-front-door`
- **Landed:** 2026-08-23

### the currency check is wired into a guardrail _(archived)_

- **Scenario id:** `TRC-D3`
- **Intent:** `INT-4`
- **Source issue:** `the-human-front-door`
- **Landed:** 2026-08-23

### the instructions tell a stage to link evidence rather than paste it _(archived)_

- **Scenario id:** `TRC-E1`
- **Intent:** `INT-5`
- **Source issue:** `the-human-front-door`
- **Landed:** 2026-08-23

### the evaluator computes the artifact set from the assessment _(archived)_

- **Scenario id:** `TRC-F1`
- **Intent:** `INT-6`
- **Source issue:** `the-human-front-door`
- **Landed:** 2026-08-23

### a trivial atomic change earns almost nothing _(archived)_

- **Scenario id:** `TRC-F2`
- **Intent:** `INT-6`
- **Source issue:** `the-human-front-door`
- **Landed:** 2026-08-23

### a policy rule can add an artifact the way it adds a gate _(archived)_

- **Scenario id:** `TRC-F3`
- **Intent:** `INT-6`
- **Source issue:** `the-human-front-door`
- **Landed:** 2026-08-23

### the same assessment computes the same artifact set every time _(archived)_

- **Scenario id:** `TRC-F4`
- **Intent:** `INT-6`
- **Source issue:** `the-human-front-door`
- **Landed:** 2026-08-23

### a stage hand-off fits on one screen _(archived)_

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `the-terminal-output-contract`
- **Landed:** 2026-08-24

### the hand-off says what was decided and what to read _(archived)_

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `the-terminal-output-contract`
- **Landed:** 2026-08-24

### a hand-off with nothing to decide is shorter, not padded _(archived)_

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `the-terminal-output-contract`
- **Landed:** 2026-08-24

### at most three key choices and three concerns _(archived)_

- **Scenario id:** `TRC-A4`
- **Intent:** `INT-1`
- **Source issue:** `the-terminal-output-contract`
- **Landed:** 2026-08-24

### the budget cannot be met by making the lines longer _(archived)_

- **Scenario id:** `TRC-A5`
- **Intent:** `INT-1`
- **Source issue:** `the-terminal-output-contract`
- **Landed:** 2026-08-24

### the gate verdict keeps its guidance one flag away _(archived)_

- **Scenario id:** `TRC-A6`
- **Intent:** `INT-1`
- **Source issue:** `the-terminal-output-contract`
- **Landed:** 2026-08-24

### a report opens with a summary a reader can stop at _(archived)_

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-5`
- **Source issue:** `the-terminal-output-contract`
- **Landed:** 2026-08-24

### a report's own detail is never truncated by the contract _(archived)_

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-5`
- **Source issue:** `the-terminal-output-contract`
- **Landed:** 2026-08-24

### every verb accepts every mode flag _(archived)_

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-3`
- **Source issue:** `the-terminal-output-contract`
- **Landed:** 2026-08-24

### quiet prints nothing on success _(archived)_

- **Scenario id:** `TRC-C2`
- **Intent:** `INT-3`
- **Source issue:** `the-terminal-output-contract`
- **Landed:** 2026-08-24

### json is the machine mode and carries no prose _(archived)_

- **Scenario id:** `TRC-C3`
- **Intent:** `INT-3`
- **Source issue:** `the-terminal-output-contract`
- **Landed:** 2026-08-24

### evidence-out writes the raw capture rather than printing it _(archived)_

- **Scenario id:** `TRC-C4`
- **Intent:** `INT-2`
- **Source issue:** `the-terminal-output-contract`
- **Landed:** 2026-08-24

### verbose is where detail goes, not where the contract is escaped _(archived)_

- **Scenario id:** `TRC-C5`
- **Intent:** `INT-3`
- **Source issue:** `the-terminal-output-contract`
- **Landed:** 2026-08-24

### every verb declares which contract it is under _(archived)_

- **Scenario id:** `TRC-C6`
- **Intent:** `INT-5`
- **Source issue:** `the-terminal-output-contract`
- **Landed:** 2026-08-24

### evidence-out on a verb with nothing to capture _(archived)_

- **Scenario id:** `TRC-C7`
- **Intent:** `INT-2`
- **Source issue:** `the-terminal-output-contract`
- **Landed:** 2026-08-24

### an identifier survives compression with its meaning attached _(archived)_

- **Scenario id:** `TRC-D1`
- **Intent:** `INT-4`
- **Source issue:** `the-terminal-output-contract`
- **Landed:** 2026-08-24

### the meaning still comes before the code _(archived)_

- **Scenario id:** `TRC-D2`
- **Intent:** `INT-4`
- **Source issue:** `the-terminal-output-contract`
- **Landed:** 2026-08-24

### retired vocabulary stays out of printed strings _(archived)_

- **Scenario id:** `TRC-D3`
- **Intent:** `INT-4`
- **Source issue:** `the-terminal-output-contract`
- **Landed:** 2026-08-24

### an expected string is updated only when the test's intent still holds _(archived)_

- **Scenario id:** `TRC-D4`
- **Intent:** `INT-1`
- **Source issue:** `the-terminal-output-contract`
- **Landed:** 2026-08-24

### a verb prints past its budget and the guard says which one _(archived)_

- **Scenario id:** `TRC-E1`
- **Intent:** `INT-1`
- **Source issue:** `the-terminal-output-contract`
- **Landed:** 2026-08-24

### the budget guard fails when the budget is breached _(archived)_

- **Scenario id:** `TRC-E2`
- **Intent:** `INT-1`
- **Source issue:** `the-terminal-output-contract`
- **Landed:** 2026-08-24

### the template asks the four questions and no others _(archived)_

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-2`
- **Source issue:** `adaptive-artifact-composition`
- **Landed:** 2026-08-24

### a threat with no scenario is visibly unfinished _(archived)_

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-2`
- **Source issue:** `adaptive-artifact-composition`
- **Landed:** 2026-08-24

### the fourth question is answered by evidence, not by assertion _(archived)_

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-2`
- **Source issue:** `adaptive-artifact-composition`
- **Landed:** 2026-08-24

### the template records when the rollback was last rehearsed _(archived)_

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-3`
- **Source issue:** `adaptive-artifact-composition`
- **Landed:** 2026-08-24

### the evidence type stops accepting a plan as a rollback _(archived)_

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-3`
- **Source issue:** `adaptive-artifact-composition`
- **Landed:** 2026-08-24

### a rollback plan with no rehearsal date is caught _(archived)_

- **Scenario id:** `TRC-B3`
- **Intent:** `INT-3`
- **Source issue:** `adaptive-artifact-composition`
- **Landed:** 2026-08-24

### the design template offers a cross-cutting concerns section _(archived)_

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-4`
- **Source issue:** `adaptive-artifact-composition`
- **Landed:** 2026-08-24

### the skill that governs the optional sections knows about it _(archived)_

- **Scenario id:** `TRC-C2`
- **Intent:** `INT-4`
- **Source issue:** `adaptive-artifact-composition`
- **Landed:** 2026-08-24

### every document kind the policy names has a template _(archived)_

- **Scenario id:** `TRC-D1`
- **Intent:** `INT-1`
- **Source issue:** `adaptive-artifact-composition`
- **Landed:** 2026-08-24

### no document was added that nothing asks for _(archived)_

- **Scenario id:** `TRC-D2`
- **Intent:** `INT-4`
- **Source issue:** `adaptive-artifact-composition`
- **Landed:** 2026-08-24

### both templates stay shorter than the framework's own PRD _(archived)_

- **Scenario id:** `TRC-D3`
- **Intent:** `INT-4`
- **Source issue:** `adaptive-artifact-composition`
- **Landed:** 2026-08-24

### a command, its key and its artifact name the same thing _(archived)_

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### the designer's command is design again _(archived)_

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### every overloaded word carries a glossary entry _(archived)_

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-4`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### the planning stage answers to plan in the CLI too _(archived)_

- **Scenario id:** `TRC-A4`
- **Intent:** `INT-1`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### no live surface sends the engineering stage to /compass:design _(archived)_

- **Scenario id:** `TRC-A5`
- **Intent:** `INT-1`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### a spine written before the rename still reads _(archived)_

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-2`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### a document written before the rename still resolves _(archived)_

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-2`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### both spellings are accepted before any caller switches _(archived)_

- **Scenario id:** `TRC-B3`
- **Intent:** `INT-2`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### the retired commands answer with a pointer _(archived)_

- **Scenario id:** `TRC-B4`
- **Intent:** `INT-2`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### a document written after the rename resolves under its new name _(archived)_

- **Scenario id:** `TRC-B5`
- **Intent:** `INT-2`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### the current filename wins when both are present _(archived)_

- **Scenario id:** `TRC-B6`
- **Intent:** `INT-2`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### the design lint still reads a landed issue's design _(archived)_

- **Scenario id:** `TRC-B7`
- **Intent:** `INT-2`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### a policy floor written with a retired stage key still applies _(archived)_

- **Scenario id:** `TRC-B8`
- **Intent:** `INT-2`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### the map carries the stage keys _(archived)_

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-3`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### migrate rewrites a stale reference _(archived)_

- **Scenario id:** `TRC-C2`
- **Intent:** `INT-3`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### a dry run writes nothing and says what it would do _(archived)_

- **Scenario id:** `TRC-C3`
- **Intent:** `INT-3`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### a stopped migration says what it did and what remains _(archived)_

- **Scenario id:** `TRC-C4`
- **Intent:** `INT-3`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### migrate refuses a many-to-one filename collision _(archived)_

- **Scenario id:** `TRC-C5`
- **Intent:** `INT-2`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### migrate repoints the spine at the files it renamed _(archived)_

- **Scenario id:** `TRC-C6`
- **Intent:** `INT-3`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### a ban never points at a banned replacement _(archived)_

- **Scenario id:** `TRC-D1`
- **Intent:** `INT-4`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### governance files are scanned for retired vocabulary _(archived)_

- **Scenario id:** `TRC-D2`
- **Intent:** `INT-5`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### the acceptance-criteria guardrail reads the current stage key _(archived)_

- **Scenario id:** `TRC-D3`
- **Intent:** `INT-3`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### no term is both defined and banned _(archived)_

- **Scenario id:** `TRC-D4`
- **Intent:** `INT-4`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### the code-position scan knows this rename _(archived)_

- **Scenario id:** `TRC-D5`
- **Intent:** `INT-3`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### the rename is not counted as done while a surface still says the old word _(archived)_

- **Scenario id:** `TRC-E1`
- **Intent:** `INT-1`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### the guard fails when handed nothing _(archived)_

- **Scenario id:** `TRC-E2`
- **Intent:** `INT-5`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### the coherence check reads the stage table the template writes _(archived)_

- **Scenario id:** `TRC-E3`
- **Intent:** `INT-3`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### every citation into the archive opens _(archived)_

- **Scenario id:** `TRC-E4`
- **Intent:** `INT-3`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### a local file becomes intent.md _(archived)_

- **Scenario id:** `ING-A1`
- **Intent:** `INT-1`
- **Source issue:** `ingest-an-existing-brief`
- **Landed:** 2026-08-25

### the source may be called anything _(archived)_

- **Scenario id:** `ING-A2`
- **Intent:** `INT-1`
- **Source issue:** `ingest-an-existing-brief`
- **Landed:** 2026-08-25

### a URL becomes intent.md _(archived)_

- **Scenario id:** `ING-A3`
- **Intent:** `INT-1`
- **Source issue:** `ingest-an-existing-brief`
- **Landed:** 2026-08-25

### a source that is not there fails before anything is written _(archived)_

- **Scenario id:** `ING-A4`
- **Intent:** `INT-1`
- **Source issue:** `ingest-an-existing-brief`
- **Landed:** 2026-08-25

### the document is reshaped, not copied _(archived)_

- **Scenario id:** `ING-B1`
- **Intent:** `INT-2`
- **Source issue:** `ingest-an-existing-brief`
- **Landed:** 2026-08-25

### a gap becomes a question, not a TBD _(archived)_

- **Scenario id:** `ING-B2`
- **Intent:** `INT-2`
- **Source issue:** `ingest-an-existing-brief`
- **Landed:** 2026-08-25

### nothing is invented _(archived)_

- **Scenario id:** `ING-B3`
- **Intent:** `INT-2`
- **Source issue:** `ingest-an-existing-brief`
- **Landed:** 2026-08-25

### a person can decline every question and still get an intent.md _(archived)_

- **Scenario id:** `ING-B4`
- **Intent:** `INT-2`
- **Source issue:** `ingest-an-existing-brief`
- **Landed:** 2026-08-25

### an ingested brief says where it came from _(archived)_

- **Scenario id:** `ING-C1`
- **Intent:** `INT-3`
- **Source issue:** `ingest-an-existing-brief`
- **Landed:** 2026-08-25

### the reshaping is auditable _(archived)_

- **Scenario id:** `ING-C2`
- **Intent:** `INT-3`
- **Source issue:** `ingest-an-existing-brief`
- **Landed:** 2026-08-25

### an authenticated source is refused with a way forward _(archived)_

- **Scenario id:** `ING-D1`
- **Intent:** `INT-4`
- **Source issue:** `ingest-an-existing-brief`
- **Landed:** 2026-08-25

### no network, no silent failure _(archived)_

- **Scenario id:** `ING-D2`
- **Intent:** `INT-4`
- **Source issue:** `ingest-an-existing-brief`
- **Landed:** 2026-08-25

### a redirect is followed, and provenance names where it landed _(archived)_

- **Scenario id:** `ING-D3`
- **Intent:** `INT-4`
- **Source issue:** `ingest-an-existing-brief`
- **Landed:** 2026-08-25

### a URL that is not https is refused _(archived)_

- **Scenario id:** `ING-D4`
- **Intent:** `INT-4`
- **Source issue:** `ingest-an-existing-brief`
- **Landed:** 2026-08-25

### the fidelity gate reports which human the material came from _(archived)_

- **Scenario id:** `ING-E1`
- **Intent:** `INT-2`
- **Source issue:** `ingest-an-existing-brief`
- **Landed:** 2026-08-25

### a queued issue is not asked for an assessment it cannot have _(archived)_

- **Scenario id:** `CIQ-A1`
- **Intent:** `INT-1`
- **Source issue:** `ci-fails-a-queued-issue-for-being-queued`
- **Landed:** 2026-08-26

### every verb says what it does _(archived)_

- **Scenario id:** `CLIV-A1`
- **Intent:** `INT-1`
- **Source issue:** `cli-verbs-do-not-describe-themselves`
- **Landed:** 2026-08-26

### a landed issue with a pointer passes without its own record _(archived)_

- **Scenario id:** `DEL-A1`
- **Intent:** `INT-1`
- **Source issue:** `no-status-for-work-done-elsewhere`
- **Landed:** 2026-08-26

### the same issue without the pointer still fails _(archived)_

- **Scenario id:** `DEL-A2`
- **Intent:** `INT-2`
- **Source issue:** `no-status-for-work-done-elsewhere`
- **Landed:** 2026-08-26

### several entries are all checked _(archived)_

- **Scenario id:** `DEL-A3`
- **Intent:** `INT-2`
- **Source issue:** `no-status-for-work-done-elsewhere`
- **Landed:** 2026-08-26

### an absorbed issue that was never assessed still lints _(archived)_

- **Scenario id:** `DEL-A4`
- **Intent:** `INT-1`
- **Source issue:** `no-status-for-work-done-elsewhere`
- **Landed:** 2026-08-26

### a pointer at an issue that does not exist fails _(archived)_

- **Scenario id:** `DEL-B1`
- **Intent:** `INT-2`
- **Source issue:** `no-status-for-work-done-elsewhere`
- **Landed:** 2026-08-26

### a pointer at an issue that has not landed fails _(archived)_

- **Scenario id:** `DEL-B2`
- **Intent:** `INT-2`
- **Source issue:** `no-status-for-work-done-elsewhere`
- **Landed:** 2026-08-26

### a pointer at an issue with no record of its own fails _(archived)_

- **Scenario id:** `DEL-B3`
- **Intent:** `INT-2`
- **Source issue:** `no-status-for-work-done-elsewhere`
- **Landed:** 2026-08-26

### a pointer is only meaningful on a landed issue _(archived)_

- **Scenario id:** `DEL-B4`
- **Intent:** `INT-2`
- **Source issue:** `no-status-for-work-done-elsewhere`
- **Landed:** 2026-08-26

### a pointer the named issue does not acknowledge fails _(archived)_

- **Scenario id:** `DEL-B5`
- **Intent:** `INT-2`
- **Source issue:** `no-status-for-work-done-elsewhere`
- **Landed:** 2026-08-26

### a delivered issue stops being recorded as abandoned _(archived)_

- **Scenario id:** `DEL-C1`
- **Intent:** `INT-3`
- **Source issue:** `no-status-for-work-done-elsewhere`
- **Landed:** 2026-08-26

### retro counts them as delivered _(archived)_

- **Scenario id:** `DEL-C2`
- **Intent:** `INT-3`
- **Source issue:** `no-status-for-work-done-elsewhere`
- **Landed:** 2026-08-26

### an issue that was decided against stays abandoned _(archived)_

- **Scenario id:** `DEL-C3`
- **Intent:** `INT-3`
- **Source issue:** `no-status-for-work-done-elsewhere`
- **Landed:** 2026-08-26

### a commit entry resolves and says what it did _(archived)_

- **Scenario id:** `DEL-D1`
- **Intent:** `INT-1`
- **Source issue:** `no-status-for-work-done-elsewhere`
- **Landed:** 2026-08-26

### a commit that does not resolve fails _(archived)_

- **Scenario id:** `DEL-D2`
- **Intent:** `INT-2`
- **Source issue:** `no-status-for-work-done-elsewhere`
- **Landed:** 2026-08-26

### a commit with no explanation fails _(archived)_

- **Scenario id:** `DEL-D3`
- **Intent:** `INT-2`
- **Source issue:** `no-status-for-work-done-elsewhere`
- **Landed:** 2026-08-26

### without git, the commit form declines rather than passes _(archived)_

- **Scenario id:** `DEL-D4`
- **Intent:** `INT-2`
- **Source issue:** `no-status-for-work-done-elsewhere`
- **Landed:** 2026-08-26

### every drift guard passes on the slimmed documents _(archived)_

- **Scenario id:** `DOC-A1`
- **Intent:** `INT-1`
- **Source issue:** `docs-slimming-pass`
- **Landed:** 2026-08-26

### no document claims more than governance does _(archived)_

- **Scenario id:** `DOC-A2`
- **Intent:** `INT-2`
- **Source issue:** `docs-slimming-pass`
- **Landed:** 2026-08-26

### a guard taught a new shape can still fail _(archived)_

- **Scenario id:** `DOC-A3`
- **Intent:** `INT-3`
- **Source issue:** `docs-slimming-pass`
- **Landed:** 2026-08-26

### a retired guard says what stopped being covered _(archived)_

- **Scenario id:** `DOC-A4`
- **Intent:** `INT-3`
- **Source issue:** `docs-slimming-pass`
- **Landed:** 2026-08-26

### set-status names the issue in both outcomes _(archived)_

- **Scenario id:** `SSN-A1`
- **Intent:** `INT-1`
- **Source issue:** `set-status-does-not-name-the-issue`
- **Landed:** 2026-08-26

### a landed_by entry still reads its own key _(archived)_

- **Scenario id:** `SSN-A2`
- **Intent:** `INT-1`
- **Source issue:** `set-status-does-not-name-the-issue`
- **Landed:** 2026-08-26

### the term is governed like every other _(archived)_

- **Scenario id:** `NIR-A1`
- **Intent:** `INT-1`
- **Source issue:** `name-the-issue-record`
- **Landed:** 2026-08-27

### the name needs no gloss _(archived)_

- **Scenario id:** `NIR-A2`
- **Intent:** `INT-1`
- **Source issue:** `name-the-issue-record`
- **Landed:** 2026-08-27

### no live surface carries the retired word _(archived)_

- **Scenario id:** `NIR-B1`
- **Intent:** `INT-2`
- **Source issue:** `name-the-issue-record`
- **Landed:** 2026-08-27

### the old name survives only where history needs it _(archived)_

- **Scenario id:** `NIR-B2`
- **Intent:** `INT-2`
- **Source issue:** `name-the-issue-record`
- **Landed:** 2026-08-27

### the file, the CLI and the module agree _(archived)_

- **Scenario id:** `NIR-C1`
- **Intent:** `INT-2`
- **Source issue:** `name-the-issue-record`
- **Landed:** 2026-08-27

### a file written under the old name still loads _(archived)_

- **Scenario id:** `NIR-D1`
- **Intent:** `INT-3`
- **Source issue:** `name-the-issue-record`
- **Landed:** 2026-08-27

### the migrator moves the archive _(archived)_

- **Scenario id:** `NIR-D2`
- **Intent:** `INT-3`
- **Source issue:** `name-the-issue-record`
- **Landed:** 2026-08-27

### the freeze ceremony is paid _(archived)_

- **Scenario id:** `NIR-E1`
- **Intent:** `INT-2`
- **Source issue:** `name-the-issue-record`
- **Landed:** 2026-08-27

### the resident cost is bounded _(archived)_

- **Scenario id:** `IV-A1`
- **Intent:** `INT-2`
- **Source issue:** `instruction-volume`
- **Landed:** 2026-08-27

### a quick fix reads what a quick fix needs _(archived)_

- **Scenario id:** `IV-A2`
- **Intent:** `INT-1`
- **Source issue:** `instruction-volume`
- **Landed:** 2026-08-27

### strategies is not in the per-issue read _(archived)_

- **Scenario id:** `IV-B1`
- **Intent:** `INT-1`
- **Source issue:** `instruction-volume`
- **Landed:** 2026-08-27

### no skill loads whole to answer one question _(archived)_

- **Scenario id:** `IV-C1`
- **Intent:** `INT-2`
- **Source issue:** `instruction-volume`
- **Landed:** 2026-08-27

### a split skill says where its parts are _(archived)_

- **Scenario id:** `IV-C2`
- **Intent:** `INT-3`
- **Source issue:** `instruction-volume`
- **Landed:** 2026-08-27

### every frontmatter parses _(archived)_

- **Scenario id:** `IV-D1`
- **Intent:** `INT-3`
- **Source issue:** `instruction-volume`
- **Landed:** 2026-08-27

### a session in a Compass project starts with the contract _(archived)_

- **Scenario id:** `SB-A1`
- **Intent:** `INT-1`
- **Source issue:** `session-bootstrap`
- **Landed:** 2026-08-27

### the contract is short enough to always carry _(archived)_

- **Scenario id:** `SB-A2`
- **Intent:** `INT-1`
- **Source issue:** `session-bootstrap`
- **Landed:** 2026-08-27

### the contract is silent outside a Compass project _(archived)_

- **Scenario id:** `SB-A3`
- **Intent:** `INT-1`
- **Source issue:** `session-bootstrap`
- **Landed:** 2026-08-27

### the contract exists once _(archived)_

- **Scenario id:** `SB-B1`
- **Intent:** `INT-2`
- **Source issue:** `session-bootstrap`
- **Landed:** 2026-08-27

### the two Claude Code documents share no sentence _(archived)_

- **Scenario id:** `SB-B2`
- **Intent:** `INT-2`
- **Source issue:** `session-bootstrap`
- **Landed:** 2026-08-27

### the runtime-neutral document is left alone _(archived)_

- **Scenario id:** `SB-B3`
- **Intent:** `INT-2`
- **Source issue:** `session-bootstrap`
- **Landed:** 2026-08-27

### the contract names every agent that exists _(archived)_

- **Scenario id:** `SB-B4`
- **Intent:** `INT-2`
- **Source issue:** `session-bootstrap`
- **Landed:** 2026-08-27

### plugin-shipped paths resolve from any directory _(archived)_

- **Scenario id:** `SB-C1`
- **Intent:** `INT-3`
- **Source issue:** `session-bootstrap`
- **Landed:** 2026-08-27

### project governance still wins where a project has its own _(archived)_

- **Scenario id:** `SB-C2`
- **Intent:** `INT-3`
- **Source issue:** `session-bootstrap`
- **Landed:** 2026-08-27

### a source install registers the same hook _(archived)_

- **Scenario id:** `SB-D1`
- **Intent:** `INT-1`
- **Source issue:** `session-bootstrap`
- **Landed:** 2026-08-27

### the portability mapping names the new adapter feature _(archived)_

- **Scenario id:** `SB-D2`
- **Intent:** `INT-1`
- **Source issue:** `session-bootstrap`
- **Landed:** 2026-08-27

### a source install enforces what the plugin enforces _(archived)_

- **Scenario id:** `SB-D3`
- **Intent:** `INT-1`
- **Source issue:** `session-bootstrap`
- **Landed:** 2026-08-27

### an exemption carries its reason _(archived)_

- **Scenario id:** `VGH-A1`
- **Intent:** `INT-1`
- **Source issue:** `version-guard-cannot-see-a-historical-version`
- **Landed:** 2026-08-27

### the exemption list cannot grow quietly _(archived)_

- **Scenario id:** `VGH-A2`
- **Intent:** `INT-1`
- **Source issue:** `version-guard-cannot-see-a-historical-version`
- **Landed:** 2026-08-27

### the historical reference is exempt and still says 3.3.0 _(archived)_

- **Scenario id:** `VGH-A3`
- **Intent:** `INT-1`
- **Source issue:** `version-guard-cannot-see-a-historical-version`
- **Landed:** 2026-08-27

### every file the approaches index names exists _(archived)_

- **Scenario id:** `VOC-A1`
- **Intent:** `INT-1`
- **Source issue:** `vocabulary-debt`
- **Landed:** 2026-08-27

### no document says a shipped rename is still pending _(archived)_

- **Scenario id:** `VOC-B1`
- **Intent:** `INT-1`
- **Source issue:** `vocabulary-debt`
- **Landed:** 2026-08-27

### the deep dive names the gates the policy staples _(archived)_

- **Scenario id:** `VOC-C1`
- **Intent:** `INT-2`
- **Source issue:** `vocabulary-debt`
- **Landed:** 2026-08-27

### the deep dive does not claim scoped gates are immovable _(archived)_

- **Scenario id:** `VOC-C2`
- **Intent:** `INT-2`
- **Source issue:** `vocabulary-debt`
- **Landed:** 2026-08-27

### A retired concept word is reported by the vocabulary scan _(archived)_

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `anthropic-aligned-vocabulary`
- **Landed:** 2026-08-28

### Every retired concept word has a ban entry naming its replacement _(archived)_

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `anthropic-aligned-vocabulary`
- **Landed:** 2026-08-28

### The scanned surfaces are free of the retired concept words _(archived)_

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `anthropic-aligned-vocabulary`
- **Landed:** 2026-08-28

### An ordinary use of a retired word is not reported _(archived)_

- **Scenario id:** `TRC-A4`
- **Intent:** `INT-1`
- **Source issue:** `anthropic-aligned-vocabulary`
- **Landed:** 2026-08-28

### A new manifest records orchestration rather than topology _(archived)_

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-1`
- **Source issue:** `anthropic-aligned-vocabulary`
- **Landed:** 2026-08-28

### An existing manifest written with topology still loads _(archived)_

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-3`
- **Source issue:** `anthropic-aligned-vocabulary`
- **Landed:** 2026-08-28

### A retired topology word is read as the ceiling it always implied _(archived)_

- **Scenario id:** `TRC-B3`
- **Intent:** `INT-3`
- **Source issue:** `anthropic-aligned-vocabulary`
- **Landed:** 2026-08-28

### The parallel-work ceiling is named for the unit it counts _(archived)_

- **Scenario id:** `TRC-B4`
- **Intent:** `INT-1`
- **Source issue:** `anthropic-aligned-vocabulary`
- **Landed:** 2026-08-28

### The architecture gate is named for what it checks _(archived)_

- **Scenario id:** `TRC-B5`
- **Intent:** `INT-1`
- **Source issue:** `anthropic-aligned-vocabulary`
- **Landed:** 2026-08-28

### A route shape declares a ceiling rather than an orchestration _(archived)_

- **Scenario id:** `TRC-B6`
- **Intent:** `INT-1`
- **Source issue:** `anthropic-aligned-vocabulary`
- **Landed:** 2026-08-28

### The project config names multiagent work by its new name _(archived)_

- **Scenario id:** `TRC-B7`
- **Intent:** `INT-1`
- **Source issue:** `anthropic-aligned-vocabulary`
- **Landed:** 2026-08-28

### Who integrates is decided by the number of subtasks _(archived)_

- **Scenario id:** `TRC-B8`
- **Intent:** `INT-1`
- **Source issue:** `anthropic-aligned-vocabulary`
- **Landed:** 2026-08-28

### A rename is not reported as new mechanism _(archived)_

- **Scenario id:** `TRC-B9`
- **Intent:** `INT-1`
- **Source issue:** `anthropic-aligned-vocabulary`
- **Landed:** 2026-08-28

### A renamed command is invocable under its new name _(archived)_

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-1`
- **Source issue:** `anthropic-aligned-vocabulary`
- **Landed:** 2026-08-28

### A retired command name still resolves _(archived)_

- **Scenario id:** `TRC-C2`
- **Intent:** `INT-3`
- **Source issue:** `anthropic-aligned-vocabulary`
- **Landed:** 2026-08-28

### The three role agents are named after their role _(archived)_

- **Scenario id:** `TRC-C3`
- **Intent:** `INT-1`
- **Source issue:** `anthropic-aligned-vocabulary`
- **Landed:** 2026-08-28

### The lens carve-out is removed once the identifiers are gone _(archived)_

- **Scenario id:** `TRC-C4`
- **Intent:** `INT-1`
- **Source issue:** `anthropic-aligned-vocabulary`
- **Landed:** 2026-08-28

### The assessment agent is named for what it does _(archived)_

- **Scenario id:** `TRC-C5`
- **Intent:** `INT-1`
- **Source issue:** `anthropic-aligned-vocabulary`
- **Landed:** 2026-08-28

### A renamed skill is discoverable under its new name _(archived)_

- **Scenario id:** `TRC-C6`
- **Intent:** `INT-1`
- **Source issue:** `anthropic-aligned-vocabulary`
- **Landed:** 2026-08-28

### The glossary defines each term this rename introduces _(archived)_

- **Scenario id:** `TRC-D1`
- **Intent:** `INT-2`
- **Source issue:** `anthropic-aligned-vocabulary`
- **Landed:** 2026-08-28

### The glossary is regenerated rather than hand-edited _(archived)_

- **Scenario id:** `TRC-D2`
- **Intent:** `INT-2`
- **Source issue:** `anthropic-aligned-vocabulary`
- **Landed:** 2026-08-28

### Retiring a frozen term is recorded as a decision _(archived)_

- **Scenario id:** `TRC-D3`
- **Intent:** `INT-2`
- **Source issue:** `anthropic-aligned-vocabulary`
- **Landed:** 2026-08-28

### A decision record keeps the words it was decided in _(archived)_

- **Scenario id:** `TRC-D4`
- **Intent:** `INT-3`
- **Source issue:** `anthropic-aligned-vocabulary`
- **Landed:** 2026-08-28

### A replacement that misreads the source meaning is rejected _(archived)_

- **Scenario id:** `TRC-F1`
- **Intent:** `INT-1`
- **Source issue:** `anthropic-aligned-vocabulary`
- **Landed:** 2026-08-28

### A key rename that silently drops data fails the build _(archived)_

- **Scenario id:** `TRC-F2`
- **Intent:** `INT-3`
- **Source issue:** `anthropic-aligned-vocabulary`
- **Landed:** 2026-08-28

### A ban with no working pattern is caught before it ships _(archived)_

- **Scenario id:** `TRC-F3`
- **Intent:** `INT-1`
- **Source issue:** `anthropic-aligned-vocabulary`
- **Landed:** 2026-08-28

### A loose pattern that reports neighbouring text fails the suite _(archived)_

- **Scenario id:** `TRC-F4`
- **Intent:** `INT-1`
- **Source issue:** `anthropic-aligned-vocabulary`
- **Landed:** 2026-08-28

### No printed string names a retired verb or value _(archived)_

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `printed-output-guard-coverage`
- **Landed:** 2026-08-28

### The walk reaches far more than the two commands it replaces _(archived)_

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `printed-output-guard-coverage`
- **Landed:** 2026-08-28

### A planted retired name is reported _(archived)_

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `printed-output-guard-coverage`
- **Landed:** 2026-08-28

### A red in the worktree allows an edit in the worktree _(archived)_

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `pre-tool-hook-misses-worktree-red`
- **Landed:** 2026-08-28

### A red in the session does not unlock a worktree _(archived)_

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `pre-tool-hook-misses-worktree-red`
- **Landed:** 2026-08-28

### A call naming no file still resolves from the session _(archived)_

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `pre-tool-hook-misses-worktree-red`
- **Landed:** 2026-08-28

### The decision names an observable quantity _(archived)_

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `what-compass-owes-an-unobserved-adopter`
- **Landed:** 2026-08-28

### Publication is refused as evidence of adoption _(archived)_

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `what-compass-owes-an-unobserved-adopter`
- **Landed:** 2026-08-28

### The revival condition is readable from the record alone _(archived)_

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-2`
- **Source issue:** `what-compass-owes-an-unobserved-adopter`
- **Landed:** 2026-08-28

### The record says what it adds beyond the release _(archived)_

- **Scenario id:** `TRC-A4`
- **Intent:** `INT-6`
- **Source issue:** `what-compass-owes-an-unobserved-adopter`
- **Landed:** 2026-08-28

### The supersession is navigable in both directions _(archived)_

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-4`
- **Source issue:** `what-compass-owes-an-unobserved-adopter`
- **Landed:** 2026-08-28

### Every link in the decisions index resolves _(archived)_

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-4`
- **Source issue:** `what-compass-owes-an-unobserved-adopter`
- **Landed:** 2026-08-28

### Inv-8 resolves to a record that is not superseded _(archived)_

- **Scenario id:** `TRC-B3`
- **Intent:** `INT-3`
- **Source issue:** `what-compass-owes-an-unobserved-adopter`
- **Landed:** 2026-08-28

### ADR-006 is not superseded _(archived)_

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-3`
- **Source issue:** `what-compass-owes-an-unobserved-adopter`
- **Landed:** 2026-08-28

### Inv-8's two promises are stated separately _(archived)_

- **Scenario id:** `TRC-C2`
- **Intent:** `INT-3`
- **Source issue:** `what-compass-owes-an-unobserved-adopter`
- **Landed:** 2026-08-28

### The archive rule is untouched _(archived)_

- **Scenario id:** `TRC-C3`
- **Intent:** `INT-3`
- **Source issue:** `what-compass-owes-an-unobserved-adopter`
- **Landed:** 2026-08-28

### The retired slash commands no longer exist _(archived)_

- **Scenario id:** `TRC-D1`
- **Intent:** `INT-5`
- **Source issue:** `what-compass-owes-an-unobserved-adopter`
- **Landed:** 2026-08-28

### The hidden CLI alias no longer resolves _(archived)_

- **Scenario id:** `TRC-D2`
- **Intent:** `INT-5`
- **Source issue:** `what-compass-owes-an-unobserved-adopter`
- **Landed:** 2026-08-28

### Read-side migration survives, for the archive's reason _(archived)_

- **Scenario id:** `TRC-D3`
- **Intent:** `INT-5`
- **Source issue:** `what-compass-owes-an-unobserved-adopter`
- **Landed:** 2026-08-28

### The vocabulary has one value per concept again _(archived)_

- **Scenario id:** `TRC-D4`
- **Intent:** `INT-5`
- **Source issue:** `what-compass-owes-an-unobserved-adopter`
- **Landed:** 2026-08-28

### A stale exemption fails the build _(archived)_

- **Scenario id:** `TRC-D5`
- **Intent:** `INT-5`
- **Source issue:** `what-compass-owes-an-unobserved-adopter`
- **Landed:** 2026-08-28

### The release that carries the removal says so _(archived)_

- **Scenario id:** `TRC-D6`
- **Intent:** `INT-5`
- **Source issue:** `what-compass-owes-an-unobserved-adopter`
- **Landed:** 2026-08-28

### Nothing is left over from the removal _(archived)_

- **Scenario id:** `TRC-D7`
- **Intent:** `INT-5`
- **Source issue:** `what-compass-owes-an-unobserved-adopter`
- **Landed:** 2026-08-28

### Every list of the governance files names all of them _(archived)_

- **Scenario id:** `TRC-D8`
- **Intent:** `INT-5`
- **Source issue:** `what-compass-owes-an-unobserved-adopter`
- **Landed:** 2026-08-28

### A record that only restates the existing schedule is refused _(archived)_

- **Scenario id:** `TRC-F1`
- **Intent:** `INT-6`
- **Source issue:** `what-compass-owes-an-unobserved-adopter`
- **Landed:** 2026-08-28

### A revival condition nobody can observe is refused _(archived)_

- **Scenario id:** `TRC-F2`
- **Intent:** `INT-1`
- **Source issue:** `what-compass-owes-an-unobserved-adopter`
- **Landed:** 2026-08-28

### Orphaning Inv-8 fails the change _(archived)_

- **Scenario id:** `TRC-F3`
- **Intent:** `INT-3`
- **Source issue:** `what-compass-owes-an-unobserved-adopter`
- **Landed:** 2026-08-28

### The examples check names the file that exists _(archived)_

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `release-gate-greps-the-old-manifest-filename`
- **Landed:** 2026-08-30

### A reason on any status leaves the manifest valid _(archived)_

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `set-status-reason-writes-an-invalid-manifest`
- **Landed:** 2026-08-30

### The recorded reason says which transition it belongs to _(archived)_

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `set-status-reason-writes-an-invalid-manifest`
- **Landed:** 2026-08-30

### A check that cannot pass is refused _(archived)_

- **Scenario id:** `TRC-F1`
- **Intent:** `INT-1`
- **Source issue:** `release-gate-greps-the-old-manifest-filename`
- **Landed:** 2026-08-30

### A key the schema forbids is refused _(archived)_

- **Scenario id:** `TRC-F1`
- **Intent:** `INT-1`
- **Source issue:** `set-status-reason-writes-an-invalid-manifest`
- **Landed:** 2026-08-30

### No shipped document teaches a flag the CLI rejects _(archived)_

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `reframe-is-documented-but-does-not-exist`
- **Landed:** 2026-08-30

### Nothing promises the retired spelling still works _(archived)_

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `reframe-is-documented-but-does-not-exist`
- **Landed:** 2026-08-30

### A guard that reads no flags is refused _(archived)_

- **Scenario id:** `TRC-F1`
- **Intent:** `INT-1`
- **Source issue:** `reframe-is-documented-but-does-not-exist`
- **Landed:** 2026-08-30

### No shipped document names a slash command that does not exist _(archived)_

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `stale-command-names-in-shipped-prose`
- **Landed:** 2026-08-30

### The safety contract names one start version _(archived)_

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-2`
- **Source issue:** `stale-command-names-in-shipped-prose`
- **Landed:** 2026-08-30

### A guard that reads no commands is refused _(archived)_

- **Scenario id:** `TRC-F1`
- **Intent:** `INT-1`
- **Source issue:** `stale-command-names-in-shipped-prose`
- **Landed:** 2026-08-30

### A marker with no reason is refused _(archived)_

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `allow-marker-supplies-its-own-reason`
- **Landed:** 2026-08-30

### A marker with a real reason still exempts _(archived)_

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `allow-marker-supplies-its-own-reason`
- **Landed:** 2026-08-30

### The guards that honour the marker share its definition _(archived)_

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-2`
- **Source issue:** `allow-marker-supplies-its-own-reason`
- **Landed:** 2026-08-30

### The action check reads the rule body, not its own anchor _(archived)_

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `decay-rule-imperative-check-cannot-fail`
- **Landed:** 2026-08-30

### The rule still passes when it does state an action _(archived)_

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `decay-rule-imperative-check-cannot-fail`
- **Landed:** 2026-08-30

### No exemption excludes nothing _(archived)_

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `exemptions-that-exclude-nothing`
- **Landed:** 2026-08-30

### The grandfather list is empty _(archived)_

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `exemptions-that-exclude-nothing`
- **Landed:** 2026-08-30

### A file that must not be scanned is checked directly _(archived)_

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-2`
- **Source issue:** `exemptions-that-exclude-nothing`
- **Landed:** 2026-08-30

### A corrected reading is logged when the approach does not move _(archived)_

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `reassessment-log-drops-reading-only-changes`
- **Landed:** 2026-08-30

### The reason is not discarded _(archived)_

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `reassessment-log-drops-reading-only-changes`
- **Landed:** 2026-08-30

### A first write records no re-assessment _(archived)_

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-2`
- **Source issue:** `reassessment-log-drops-reading-only-changes`
- **Landed:** 2026-08-30

### A registered document outside the issue directory resolves _(archived)_

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-3`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### A registered path is anchored to the project, not to the caller _(archived)_

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-3`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### An issue with no registry resolves exactly as it does today _(archived)_

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-4`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### The schema says where a registered path is measured from _(archived)_

- **Scenario id:** `TRC-A4`
- **Intent:** `INT-3`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### A written document lands under a dated issue directory _(archived)_

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-1`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### Machine state stays where the CLI keeps it _(archived)_

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-2`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### Creating the docs directory is reported, never silent _(archived)_

- **Scenario id:** `TRC-B3`
- **Intent:** `INT-1`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### A reading command still does not create anything _(archived)_

- **Scenario id:** `TRC-B4`
- **Intent:** `INT-2`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### A reader finds a relocated document _(archived)_

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-3`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### No reader builds its own path to a document _(archived)_

- **Scenario id:** `TRC-C2`
- **Intent:** `INT-3`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### A missed reader is caught by the test, not by a user _(archived)_

- **Scenario id:** `TRC-C3`
- **Intent:** `INT-3`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### The verification report is found where the registry says _(archived)_

- **Scenario id:** `TRC-C4`
- **Intent:** `INT-3`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### A missed reader turns a guardrail check red, never green _(archived)_

- **Scenario id:** `TRC-C5`
- **Intent:** `INT-3`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### The pre-tool hook accepts a relocated delivery-approach record _(archived)_

- **Scenario id:** `TRC-D1`
- **Intent:** `INT-3`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### The pre-tool hook still blocks when assessment really has not run _(archived)_

- **Scenario id:** `TRC-D2`
- **Intent:** `INT-3`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### The stop hook reads the three documents it warns about _(archived)_

- **Scenario id:** `TRC-D3`
- **Intent:** `INT-3`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### Migration moves the documents and writes the registry _(archived)_

- **Scenario id:** `TRC-E1`
- **Intent:** `INT-4`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### The dry run changes nothing _(archived)_

- **Scenario id:** `TRC-E2`
- **Intent:** `INT-4`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### An unmigrated issue keeps working untouched _(archived)_

- **Scenario id:** `TRC-E3`
- **Intent:** `INT-4`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### The shipped examples show the new layout _(archived)_

- **Scenario id:** `TRC-E4`
- **Intent:** `INT-1`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### An older install is not locked out by the move _(archived)_

- **Scenario id:** `TRC-E5`
- **Intent:** `INT-4`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### A quick fix reads one command and one skill _(archived)_

- **Scenario id:** `TRC-F1`
- **Intent:** `INT-5`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### A quick fix writes only the delivery-approach record _(archived)_

- **Scenario id:** `TRC-F2`
- **Intent:** `INT-5`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### Two skills merge into their neighbours _(archived)_

- **Scenario id:** `TRC-F3`
- **Intent:** `INT-6`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### The framework's own documents are off the adopter's path _(archived)_

- **Scenario id:** `TRC-F4`
- **Intent:** `INT-6`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### The resident cost is measured and pinned _(archived)_

- **Scenario id:** `TRC-F5`
- **Intent:** `INT-5`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### A document registered at a path that does not exist _(archived)_

- **Scenario id:** `TRC-G1`
- **Intent:** `INT-3`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### A half-finished migration is not mistaken for a finished one _(archived)_

- **Scenario id:** `TRC-G2`
- **Intent:** `INT-4`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### The same document in both places _(archived)_

- **Scenario id:** `TRC-G3`
- **Intent:** `INT-4`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### A registered path that climbs out of the project _(archived)_

- **Scenario id:** `TRC-G4`
- **Intent:** `INT-3`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### A bare pytest run passes on a clean checkout _(archived)_

- **Scenario id:** `BPF-1`
- **Intent:** `INT-1`
- **Source issue:** `bare-pytest-fails-on-two-tests`
- **Landed:** 2026-09-11

### An issue still in flight has its declared tests checked _(archived)_

- **Scenario id:** `QRL-1`
- **Intent:** `INT-1`
- **Source issue:** `queued-issues-read-as-landed`
- **Landed:** 2026-09-11

### A recorded rehearsal passes whatever words surround it _(archived)_

- **Scenario id:** `RGN-1`
- **Intent:** `INT-1`
- **Source issue:** `rehearsal-guard-fails-on-a-neighbour`
- **Landed:** 2026-09-11

### CLAUDE.md tells a session to write plain English with no idiom or metaphor _(archived)_

- **Scenario id:** `PE-1`
- **Intent:** `INT-1`
- **Source issue:** `claude-md-plain-english`
- **Landed:** 2026-09-11

### CLAUDE.md and AGENTS.md carry the full plain-English rules _(archived)_

- **Scenario id:** `PFR-1`
- **Intent:** `INT-1`
- **Source issue:** `plain-english-full-rules`
- **Landed:** 2026-09-11

### No retired v1 word survives in prose, a comment or a test docstring _(archived)_

- **Scenario id:** `PBW-A1`
- **Intent:** `INT-1`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### A stated count matches the thing it counts _(archived)_

- **Scenario id:** `PBW-A10`
- **Intent:** `INT-4`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### The shorter word stands where the word is not an identifier _(archived)_

- **Scenario id:** `PBW-A2`
- **Intent:** `INT-1`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### The spelling is British _(archived)_

- **Scenario id:** `PBW-A3`
- **Intent:** `INT-1`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### "artifact" is the only spelling _(archived)_

- **Scenario id:** `PBW-A4`
- **Intent:** `INT-1`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### No idiom from the table survives _(archived)_

- **Scenario id:** `PBW-A5`
- **Intent:** `INT-1`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### No citation points at a path git does not distribute _(archived)_

- **Scenario id:** `PBW-A6`
- **Intent:** `INT-4`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### A bare code carries its meaning or goes _(archived)_

- **Scenario id:** `PBW-A7`
- **Intent:** `INT-4`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### Every file and command a comment names exists _(archived)_

- **Scenario id:** `PBW-A8`
- **Intent:** `INT-4`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### No sentence is left broken by an earlier find-and-replace _(archived)_

- **Scenario id:** `PBW-A9`
- **Intent:** `INT-2`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### No sentence is left broken by an earlier find-and-replace _(archived)_

- **Scenario id:** `PBW-A9`
- **Intent:** `INT-1`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### A document leads with the point _(archived)_

- **Scenario id:** `PBW-B1`
- **Intent:** `INT-2`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### Each sentence makes one point _(archived)_

- **Scenario id:** `PBW-B2`
- **Intent:** `INT-2`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### A set of items is a vertical list _(archived)_

- **Scenario id:** `PBW-B3`
- **Intent:** `INT-2`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### "must", "can" and "do not" say which is which _(archived)_

- **Scenario id:** `PBW-B4`
- **Intent:** `INT-2`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### The actor is named before the action _(archived)_

- **Scenario id:** `PBW-B5`
- **Intent:** `INT-2`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### A document describes the state now _(archived)_

- **Scenario id:** `PBW-B6`
- **Intent:** `INT-3`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### No document holds a changelog, a version banner or a dated count _(archived)_

- **Scenario id:** `PBW-B7`
- **Intent:** `INT-3`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### No document states a fact its source contradicts _(archived)_

- **Scenario id:** `PBW-B8`
- **Intent:** `INT-3`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### No document states a fact its source contradicts _(archived)_

- **Scenario id:** `PBW-B8`
- **Intent:** `INT-4`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### A comment states what the code does _(archived)_

- **Scenario id:** `PBW-C1`
- **Intent:** `INT-5`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### A comment gives its reason before its detail _(archived)_

- **Scenario id:** `PBW-C2`
- **Intent:** `INT-5`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### A CLI module's header describes that module _(archived)_

- **Scenario id:** `PBW-C3`
- **Intent:** `INT-5`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### A copied block is fixed the same way in every file that holds it _(archived)_

- **Scenario id:** `PBW-C4`
- **Intent:** `INT-1`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### A copied block is fixed the same way in every file that holds it _(archived)_

- **Scenario id:** `PBW-C4`
- **Intent:** `INT-3`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### A test docstring says what the file tests and cites its issue by slug _(archived)_

- **Scenario id:** `PBW-C5`
- **Intent:** `INT-2`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### A test docstring says what the file tests and cites its issue by slug _(archived)_

- **Scenario id:** `PBW-C5`
- **Intent:** `INT-4`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### Every identifier keeps its spelling _(archived)_

- **Scenario id:** `PBW-D1`
- **Intent:** `INT-6`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### The frozen vocabulary still names the words it bans _(archived)_

- **Scenario id:** `PBW-D2`
- **Intent:** `INT-6`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### The archive quotes are unchanged _(archived)_

- **Scenario id:** `PBW-D3`
- **Intent:** `INT-6`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### The deliberately bad text survives _(archived)_

- **Scenario id:** `PBW-D4`
- **Intent:** `INT-6`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### Every CLI module keeps its DEPENDENCY: line _(archived)_

- **Scenario id:** `PBW-D5`
- **Intent:** `INT-6`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### A test that pinned the old wording changes in the same commit _(archived)_

- **Scenario id:** `PBW-D6`
- **Intent:** `INT-6`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### The help text in scripts/release.sh stays inside its printed range _(archived)_

- **Scenario id:** `PBW-D7`
- **Intent:** `INT-6`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### The excluded files are untouched _(archived)_

- **Scenario id:** `PBW-D8`
- **Intent:** `INT-6`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### The case study and the launch article keep their form _(archived)_

- **Scenario id:** `PBW-D9`
- **Intent:** `INT-6`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### Each sweep reports a planted breach _(archived)_

- **Scenario id:** `PBW-E1`
- **Intent:** `INT-7`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### A result of zero is believed only after the sweep has reported _(archived)_

- **Scenario id:** `PBW-E2`
- **Intent:** `INT-7`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### A sweep is never loosened to clear a report _(archived)_

- **Scenario id:** `PBW-E3`
- **Intent:** `INT-7`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### No changed file alters behaviour _(archived)_

- **Scenario id:** `PBW-E4`
- **Intent:** `INT-6`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### A prose edit that changes behaviour is refused _(archived)_

- **Scenario id:** `PBW-F1`
- **Intent:** `INT-6`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### An out-of-scope defect folded into a batch is refused _(archived)_

- **Scenario id:** `PBW-F2`
- **Intent:** `INT-6`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### An edit that adds an em dash or an attribution line is refused _(archived)_

- **Scenario id:** `PBW-F3`
- **Intent:** `INT-1`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### An edit that adds an em dash or an attribution line is refused _(archived)_

- **Scenario id:** `PBW-F3`
- **Intent:** `INT-6`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### A rewrite that swaps one idiom for another is refused _(archived)_

- **Scenario id:** `PBW-F4`
- **Intent:** `INT-1`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### An edit made from a stale line number is refused _(archived)_

- **Scenario id:** `PBW-F5`
- **Intent:** `INT-6`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### A batch that cannot show its sweeps ran is refused _(archived)_

- **Scenario id:** `PBW-F6`
- **Intent:** `INT-7`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### A rewritten instruction still instructs the same behaviour _(archived)_

- **Scenario id:** `PBW-F7`
- **Intent:** `INT-2`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### A rewritten instruction still instructs the same behaviour _(archived)_

- **Scenario id:** `PBW-F7`
- **Intent:** `INT-6`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### A clarity review that read less than the sampling rule is refused _(archived)_

- **Scenario id:** `PBW-F8`
- **Intent:** `INT-2`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### A clarity review that read less than the sampling rule is refused _(archived)_

- **Scenario id:** `PBW-F8`
- **Intent:** `INT-3`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### A batch that does not record its changed files is refused _(archived)_

- **Scenario id:** `PBW-F9`
- **Intent:** `INT-6`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### every published surface reports 5.0.0 _(archived)_

- **Scenario id:** `REL-1`
- **Intent:** `INT-1`
- **Source issue:** `release-5-0-0`
- **Landed:** 2026-09-24

### the removal guard accepts a later major _(archived)_

- **Scenario id:** `REL-2`
- **Intent:** `INT-1`
- **Source issue:** `release-5-0-0`
- **Landed:** 2026-09-24

### the upgrade notes name the removed skills _(archived)_

- **Scenario id:** `REL-3`
- **Intent:** `INT-2`
- **Source issue:** `release-5-0-0`
- **Landed:** 2026-09-24

### The injected contract names docs/compass as the home of an issue's documents _(archived)_

- **Scenario id:** `CF-1`
- **Intent:** `INT-1`
- **Source issue:** `contract-facts`
- **Landed:** 2026-09-24

### validate.sh skips an issue's own documents and still fails a broken reference in a living file _(archived)_

- **Scenario id:** `VSA-1`
- **Intent:** `INT-1`
- **Source issue:** `validate-scan-vs-archive`
- **Landed:** 2026-09-24

### An issue whose only evidence is an unbound green fails suite-passed _(archived)_

- **Scenario id:** `UGR-1`
- **Intent:** `INT-1`
- **Source issue:** `unbound-green-needs-no-red`
- **Landed:** 2026-09-24

### One red of either binding satisfies the rule _(archived)_

- **Scenario id:** `UGR-2`
- **Intent:** `INT-1`
- **Source issue:** `unbound-green-needs-no-red`
- **Landed:** 2026-09-24

### An acceptance record stands in for a red _(archived)_

- **Scenario id:** `UGR-3`
- **Intent:** `INT-2`
- **Source issue:** `unbound-green-needs-no-red`
- **Landed:** 2026-09-24

### An issue with no scenarios is not asked for a red _(archived)_

- **Scenario id:** `UGR-4`
- **Intent:** `INT-1`
- **Source issue:** `unbound-green-needs-no-red`
- **Landed:** 2026-09-24

### An issue created before the cutoff keeps its result _(archived)_

- **Scenario id:** `UGR-5`
- **Intent:** `INT-3`
- **Source issue:** `unbound-green-needs-no-red`
- **Landed:** 2026-09-24

### The bound-green refusal names acceptance, not the bypass _(archived)_

- **Scenario id:** `UGR-6`
- **Intent:** `INT-4`
- **Source issue:** `unbound-green-needs-no-red`
- **Landed:** 2026-09-24

### An unbound green with no red does not claim a red _(archived)_

- **Scenario id:** `UGR-7`
- **Intent:** `INT-4`
- **Source issue:** `unbound-green-needs-no-red`
- **Landed:** 2026-09-24

### The governance text states the rule _(archived)_

- **Scenario id:** `UGR-8`
- **Intent:** `INT-1`
- **Source issue:** `unbound-green-needs-no-red`
- **Landed:** 2026-09-24

### An unstamped red written since the cutoff does not unlock _(archived)_

- **Scenario id:** `RIC-1`
- **Intent:** `INT-1`
- **Source issue:** `red-record-identity-cutoff`
- **Landed:** 2026-09-24

### An unstamped red written before the cutoff still unlocks _(archived)_

- **Scenario id:** `RIC-2`
- **Intent:** `INT-2`
- **Source issue:** `red-record-identity-cutoff`
- **Landed:** 2026-09-24

### A project with no cutoff behaves as today _(archived)_

- **Scenario id:** `RIC-3`
- **Intent:** `INT-2`
- **Source issue:** `red-record-identity-cutoff`
- **Landed:** 2026-09-24

### A stamped red is judged by its digest in every project _(archived)_

- **Scenario id:** `RIC-4`
- **Intent:** `INT-2`
- **Source issue:** `red-record-identity-cutoff`
- **Landed:** 2026-09-24

### compass init declares the cutoff for a new project _(archived)_

- **Scenario id:** `RIC-5`
- **Intent:** `INT-1`
- **Source issue:** `red-record-identity-cutoff`
- **Landed:** 2026-09-24

### suite-passed applies the same identity rule _(archived)_

- **Scenario id:** `RIC-6`
- **Intent:** `INT-4`
- **Source issue:** `red-record-identity-cutoff`
- **Landed:** 2026-09-24

### The hook has no identity rule of its own _(archived)_

- **Scenario id:** `RIC-7`
- **Intent:** `INT-4`
- **Source issue:** `red-record-identity-cutoff`
- **Landed:** 2026-09-24

### The safety contract states the cutoff _(archived)_

- **Scenario id:** `RIC-8`
- **Intent:** `INT-3`
- **Source issue:** `red-record-identity-cutoff`
- **Landed:** 2026-09-24

### Every reader that cannot run refuses and names itself _(archived)_

- **Scenario id:** `HFM-1`
- **Intent:** `INT-1`
- **Source issue:** `hook-failure-matrix`
- **Landed:** 2026-09-24

### With no python3 the refusal says so _(archived)_

- **Scenario id:** `HFM-2`
- **Intent:** `INT-1`
- **Source issue:** `hook-failure-matrix`
- **Landed:** 2026-09-24

### A config that does not parse does not unguard code_globs _(archived)_

- **Scenario id:** `HFM-3`
- **Intent:** `INT-2`
- **Source issue:** `hook-failure-matrix`
- **Landed:** 2026-09-24

### A missing approach record is still reported as missing _(archived)_

- **Scenario id:** `HFM-4`
- **Intent:** `INT-1`
- **Source issue:** `hook-failure-matrix`
- **Landed:** 2026-09-24

### The safety contract scopes the worktree redirect gap _(archived)_

- **Scenario id:** `HFM-5`
- **Intent:** `INT-3`
- **Source issue:** `hook-failure-matrix`
- **Landed:** 2026-09-24

### The hooks use no retired word or tool name _(archived)_

- **Scenario id:** `HFM-6`
- **Intent:** `INT-4`
- **Source issue:** `hook-failure-matrix`
- **Landed:** 2026-09-24

### A new file with prose leaves the reach test green _(archived)_

- **Scenario id:** `RCM-1`
- **Intent:** `INT-1`
- **Source issue:** `reach-counts-move-with-every-test`
- **Landed:** 2026-09-25

### A new file with no prose fails the reach test, naming the rule _(archived)_

- **Scenario id:** `RCM-2`
- **Intent:** `INT-1`
- **Source issue:** `reach-counts-move-with-every-test`
- **Landed:** 2026-09-25

### A widened reach fails the reach test, naming the rule _(archived)_

- **Scenario id:** `RCM-3`
- **Intent:** `INT-1`
- **Source issue:** `reach-counts-move-with-every-test`
- **Landed:** 2026-09-25

### validate.sh --help prints both exit codes and every check _(archived)_

- **Scenario id:** `VHP-1`
- **Intent:** `INT-1`
- **Source issue:** `validate-help-prints-headings-only`
- **Landed:** 2026-09-25

### A backdated issue with evidence dated after the cutoff gets the rule _(archived)_

- **Scenario id:** `CDB-1`
- **Intent:** `INT-1`
- **Source issue:** `created-date-can-be-backdated`
- **Landed:** 2026-09-25

### An issue created and worked before the cutoff keeps its result _(archived)_

- **Scenario id:** `CDB-2`
- **Intent:** `INT-1`
- **Source issue:** `created-date-can-be-backdated`
- **Landed:** 2026-09-25

### An acceptance declared after the first green does not satisfy suite-passed _(archived)_

- **Scenario id:** `ADW-1`
- **Intent:** `INT-1`
- **Source issue:** `acceptance-declared-after-the-work`
- **Landed:** 2026-09-25

### An acceptance declared before any green counts _(archived)_

- **Scenario id:** `ADW-2`
- **Intent:** `INT-1`
- **Source issue:** `acceptance-declared-after-the-work`
- **Landed:** 2026-09-25

### An acceptance record with no declared_at counts as today _(archived)_

- **Scenario id:** `ADW-3`
- **Intent:** `INT-1`
- **Source issue:** `acceptance-declared-after-the-work`
- **Landed:** 2026-09-25

### compass acceptance record carries declared_at _(archived)_

- **Scenario id:** `ADW-4`
- **Intent:** `INT-1`
- **Source issue:** `acceptance-declared-after-the-work`
- **Landed:** 2026-09-25

### A command that turns the plugin off gets no coverage flag _(archived)_

- **Scenario id:** `CFA-1`
- **Intent:** `INT-1`
- **Source issue:** `coverage-flag-with-autoload-off`
- **Landed:** 2026-09-25

### The variable in the calling environment gets no flag _(archived)_

- **Scenario id:** `CFA-2`
- **Intent:** `INT-1`
- **Source issue:** `coverage-flag-with-autoload-off`
- **Landed:** 2026-09-25

### A command where the plugin loads keeps the flag _(archived)_

- **Scenario id:** `CFA-3`
- **Intent:** `INT-1`
- **Source issue:** `coverage-flag-with-autoload-off`
- **Landed:** 2026-09-25

### A pointer holding a path makes the hook refuse _(archived)_

- **Scenario id:** `CTP-1`
- **Intent:** `INT-1`
- **Source issue:** `pointer-path-traversal`
- **Landed:** 2026-09-25

### The CLI refuses a slug holding a path _(archived)_

- **Scenario id:** `CTP-2`
- **Intent:** `INT-1`
- **Source issue:** `pointer-path-traversal`
- **Landed:** 2026-09-25

### An ordinary slug behaves as today _(archived)_

- **Scenario id:** `CTP-3`
- **Intent:** `INT-1`
- **Source issue:** `pointer-path-traversal`
- **Landed:** 2026-09-25

### code_globs of the wrong shape refuses and names the config _(archived)_

- **Scenario id:** `CGS-1`
- **Intent:** `INT-1`
- **Source issue:** `code-globs-as-a-string`
- **Landed:** 2026-09-25

### A list of strings behaves as today _(archived)_

- **Scenario id:** `CGS-2`
- **Intent:** `INT-1`
- **Source issue:** `code-globs-as-a-string`
- **Landed:** 2026-09-25

### The deep dive's gate counts match the evaluator _(archived)_

- **Scenario id:** `FDG-1`
- **Intent:** `INT-1`
- **Source issue:** `facts-drift-guard`
- **Landed:** 2026-09-25

### The immovable list and never_skip match the policy, and verify.claims is not called immovable _(archived)_

- **Scenario id:** `FDG-2`
- **Intent:** `INT-1`
- **Source issue:** `facts-drift-guard`
- **Landed:** 2026-09-25

### The contract's document home matches the CLI's naming rule _(archived)_

- **Scenario id:** `FDG-3`
- **Intent:** `INT-1`
- **Source issue:** `facts-drift-guard`
- **Landed:** 2026-09-25

### The derived-spec header names the real command and input _(archived)_

- **Scenario id:** `FDG-4`
- **Intent:** `INT-1`
- **Source issue:** `facts-drift-guard`
- **Landed:** 2026-09-25

### Every registered claim is found exactly once _(archived)_

- **Scenario id:** `FDG-5`
- **Intent:** `INT-1`
- **Source issue:** `facts-drift-guard`
- **Landed:** 2026-09-25

### A test record names the tree it ran on _(archived)_

- **Scenario id:** `EVB-1`
- **Intent:** `INT-1`
- **Source issue:** `evidence-binding`
- **Landed:** 2026-09-25

### A green for a changed tree fails at ship _(archived)_

- **Scenario id:** `EVB-2`
- **Intent:** `INT-2`
- **Source issue:** `evidence-binding`
- **Landed:** 2026-09-25

### Before ship a stale green is a note, not a failure _(archived)_

- **Scenario id:** `EVB-3`
- **Intent:** `INT-2`
- **Source issue:** `evidence-binding`
- **Landed:** 2026-09-25

### An edit to an ignored path does not make a green stale _(archived)_

- **Scenario id:** `EVB-4`
- **Intent:** `INT-2`
- **Source issue:** `evidence-binding`
- **Landed:** 2026-09-25

### A landed issue is checked against the commit that landed it _(archived)_

- **Scenario id:** `EVB-5`
- **Intent:** `INT-3`
- **Source issue:** `evidence-binding`
- **Landed:** 2026-09-25

### Records without a tree are not judged _(archived)_

- **Scenario id:** `EVB-6`
- **Intent:** `INT-3`
- **Source issue:** `evidence-binding`
- **Landed:** 2026-09-25

### The safety contract states the boundary _(archived)_

- **Scenario id:** `EVB-7`
- **Intent:** `INT-4`
- **Source issue:** `evidence-binding`
- **Landed:** 2026-09-25

### A dispatch records its subtask _(archived)_

- **Scenario id:** `OLH-1`
- **Intent:** `INT-2`
- **Source issue:** `orchestrator-loop-hardening`
- **Landed:** 2026-09-25

### A subtask's progress is recorded _(archived)_

- **Scenario id:** `OLH-2`
- **Intent:** `INT-1`
- **Source issue:** `orchestrator-loop-hardening`
- **Landed:** 2026-09-25

### An interrupted run resumes losing nothing _(archived)_

- **Scenario id:** `OLH-3`
- **Intent:** `INT-5`
- **Source issue:** `orchestrator-loop-hardening`
- **Landed:** 2026-09-25

### A review package is a file cut from the base commit _(archived)_

- **Scenario id:** `OLH-5`
- **Intent:** `INT-1`
- **Source issue:** `orchestrator-loop-hardening`
- **Landed:** 2026-09-25

### A coaching reviewer brief is refused _(archived)_

- **Scenario id:** `OLH-6`
- **Intent:** `INT-3`
- **Source issue:** `orchestrator-loop-hardening`
- **Landed:** 2026-09-25

### A rehearsal interrupted mid-review and mid-integration resumes _(archived)_

- **Scenario id:** `OLH-8`
- **Intent:** `INT-5`
- **Source issue:** `orchestrator-loop-hardening`
- **Landed:** 2026-09-25

### Each half of the review catches its own seeded defect _(archived)_

- **Scenario id:** `OLH-9`
- **Intent:** `INT-6`
- **Source issue:** `orchestrator-loop-hardening`
- **Landed:** 2026-09-25

### No shipped Markdown file calls verify.claims immovable _(archived)_

- **Scenario id:** `CCI-1`
- **Intent:** `INT-1`
- **Source issue:** `claims-called-immovable-elsewhere`
- **Landed:** 2026-09-25

### A red for a project module not yet written is recorded as an import red _(archived)_

- **Scenario id:** `RSF-1`
- **Intent:** `INT-1`
- **Source issue:** `red-for-a-module-not-yet-written`
- **Landed:** 2026-09-25

### An ordinary failing assertion is still a red _(archived)_

- **Scenario id:** `RSF-2`
- **Intent:** `INT-1`
- **Source issue:** `red-for-a-module-not-yet-written`
- **Landed:** 2026-09-25

### Any other collection error is refused _(archived)_

- **Scenario id:** `RSF-3`
- **Intent:** `INT-1`
- **Source issue:** `red-for-a-module-not-yet-written`
- **Landed:** 2026-09-25

### A run that hides a collection error, or where no test failed, is refused; the skill names the import red _(archived)_

- **Scenario id:** `RSF-4`
- **Intent:** `INT-1`
- **Source issue:** `red-for-a-module-not-yet-written`
- **Landed:** 2026-09-25

### A declared test changed after the green fails the landed check _(archived)_

- **Scenario id:** `CUF-1`
- **Intent:** `INT-1`
- **Source issue:** `changes-id-misses-unlisted-files`
- **Landed:** 2026-09-25

### The tested files landing pass, whatever HEAD does next _(archived)_

- **Scenario id:** `CUF-2`
- **Intent:** `INT-1`
- **Source issue:** `changes-id-misses-unlisted-files`
- **Landed:** 2026-09-25

### A record built before the change is judged as built _(archived)_

- **Scenario id:** `CUF-3`
- **Intent:** `INT-1`
- **Source issue:** `changes-id-misses-unlisted-files`
- **Landed:** 2026-09-25

### Current route names count up and down, and weigh the same as retired ones _(archived)_

- **Scenario id:** `RWC-1`
- **Intent:** `INT-1`
- **Source issue:** `retro-weighs-only-retired-route-names`
- **Landed:** 2026-09-25

### A route with no weight is unweighed, not sideways _(archived)_

- **Scenario id:** `RWC-2`
- **Intent:** `INT-1`
- **Source issue:** `retro-weighs-only-retired-route-names`
- **Landed:** 2026-09-25

### Retro prints no retired name for assessment _(archived)_

- **Scenario id:** `RWC-3`
- **Intent:** `INT-1`
- **Source issue:** `retro-weighs-only-retired-route-names`
- **Landed:** 2026-09-25

### py.test is recognised and gets the pytest rule _(archived)_

- **Scenario id:** `DSW-1`
- **Intent:** `INT-1`
- **Source issue:** `red-through-a-shell-wrapper`
- **Landed:** 2026-09-25

### A bash -c pipeline around pytest is judged by pytest's report _(archived)_

- **Scenario id:** `DSW-2`
- **Intent:** `INT-1`
- **Source issue:** `red-through-a-shell-wrapper`
- **Landed:** 2026-09-25

### A runner that writes no report is marked exit-code _(archived)_

- **Scenario id:** `DSW-3`
- **Intent:** `INT-1`
- **Source issue:** `red-through-a-shell-wrapper`
- **Landed:** 2026-09-25

### An edit outside the project is not logged _(archived)_

- **Scenario id:** `DLO-1`
- **Intent:** `INT-1`
- **Source issue:** `devlog-logs-edits-outside-the-project`
- **Landed:** 2026-09-25

### An edit inside the project is logged relative to it _(archived)_

- **Scenario id:** `DLO-2`
- **Intent:** `INT-1`
- **Source issue:** `devlog-logs-edits-outside-the-project`
- **Landed:** 2026-09-25

### A relative path is judged by where it resolves; the no-project message names the devlog _(archived)_

- **Scenario id:** `DLO-3`
- **Intent:** `INT-1`
- **Source issue:** `devlog-logs-edits-outside-the-project`
- **Landed:** 2026-09-25

### A conflict in Compass's records does not stop integration _(archived)_

- **Scenario id:** `DPR-4`
- **Intent:** `INT-5`
- **Source issue:** `dispatch-protocol`
- **Landed:** 2026-09-25

### The protocol document answers every step _(archived)_

- **Scenario id:** `DPR-5`
- **Intent:** `INT-1`
- **Source issue:** `dispatch-protocol`
- **Landed:** 2026-09-25

### A repeated scenario flag records every value _(archived)_

- **Scenario id:** `CKS-1`
- **Intent:** `INT-1`
- **Source issue:** `changed-file-keeps-one-scenario`
- **Landed:** 2026-09-25

### A later add keeps the earlier scenarios _(archived)_

- **Scenario id:** `CKS-2`
- **Intent:** `INT-1`
- **Source issue:** `changed-file-keeps-one-scenario`
- **Landed:** 2026-09-25

### A green after a script edit is not a re-run _(archived)_

- **Scenario id:** `RSE-1`
- **Intent:** `INT-1`
- **Source issue:** `rerun-check-misses-script-changes`
- **Landed:** 2026-09-25

### A green with nothing changed is still a re-run _(archived)_

- **Scenario id:** `RSE-2`
- **Intent:** `INT-1`
- **Source issue:** `rerun-check-misses-script-changes`
- **Landed:** 2026-09-25

### A subtask id that could leave the worktree root is refused _(archived)_

- **Scenario id:** `MCC-1`
- **Intent:** `INT-1`
- **Source issue:** `map-cells-reach-git-unchecked`
- **Landed:** 2026-09-25

### A branch git would not accept is refused _(archived)_

- **Scenario id:** `MCC-2`
- **Intent:** `INT-1`
- **Source issue:** `map-cells-reach-git-unchecked`
- **Landed:** 2026-09-25

### A branch that committed an ignored record is refused _(archived)_

- **Scenario id:** `MIR-1`
- **Intent:** `INT-1`
- **Source issue:** `merge-overwrites-an-ignored-record`
- **Landed:** 2026-09-25

### A branch with no ignored record merges _(archived)_

- **Scenario id:** `MIR-2`
- **Intent:** `INT-1`
- **Source issue:** `merge-overwrites-an-ignored-record`
- **Landed:** 2026-09-25
