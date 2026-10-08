<!-- DERIVED FILE - do not hand-edit; `compass _derive-system-spec` rebuilds it from the scenarios in each landed issue's manifest.yml - edit the scenario there and in the issue's acceptance-criteria.md -->

# System Specification (derived)

> `compass _derive-system-spec` builds this file from the `scenarios:` block of each landed issue's `.compass/work/<slug>/manifest.yml`.
> **Do not hand-edit** - the next derivation overwrites it.
> Edit the source: the scenario in that manifest, and its prose in the issue's `acceptance-criteria.md` under `docs/compass/<created>-<slug>/`.

## Current Behaviour

### the follow-up surfaces match the schema

- **Scenario id:** `GL-E1`
- **Intent:** `DOC-DRIFT`
- **Source issue:** `id-prefix-vocabulary-and-glossary`
- **Landed:** 2026-08-13

### the parser still reads the retired tag

- **Scenario id:** `GL-E2`
- **Intent:** `DOC-DRIFT`
- **Source issue:** `id-prefix-vocabulary-and-glossary`
- **Landed:** 2026-08-13

### The two views equal the generator's output byte for byte; a stale view names the regenerate command

- **Scenario id:** `GV-1`
- **Intent:** `E1.S1.04b`
- **Source issue:** `generated-legacy-views`
- **Landed:** 2026-10-07

### A generated header says generated and names the command; preset, sidecar and template changes change the text

- **Scenario id:** `GV-2`
- **Intent:** `E1.S1.04b`
- **Source issue:** `generated-legacy-views`
- **Landed:** 2026-10-07

### The mutation-proof register and the plain-language derivation read the preset

- **Scenario id:** `GV-3`
- **Intent:** `E1.S1.04b`
- **Source issue:** `generated-legacy-views`
- **Landed:** 2026-10-07

### Preset digests are pinned and a changed preset file fails naming the digest file

- **Scenario id:** `GV-4`
- **Intent:** `E1.S1.04b`
- **Source issue:** `generated-legacy-views`
- **Landed:** 2026-10-07

### The generator script writes, is idempotent, and --check fails on a stale view

- **Scenario id:** `GV-5`
- **Intent:** `E1.S1.04b`
- **Source issue:** `generated-legacy-views`
- **Landed:** 2026-10-07

### The seven Definition of Ready items are human checks equal to the template text, listed as the plan stage's entry

- **Scenario id:** `RD-1`
- **Intent:** `E1.S1.04c`
- **Source issue:** `ready-and-done-as-data`
- **Landed:** 2026-10-07

### The seven Definition of Done items are human checks equal to the template text, listed as the verify stage's exit

- **Scenario id:** `RD-2`
- **Intent:** `E1.S1.04c`
- **Source issue:** `ready-and-done-as-data`
- **Landed:** 2026-10-07

### The 14 checks require the off capability, are blocking, and carry on_skipped; no other stage has a list

- **Scenario id:** `RD-3`
- **Intent:** `E1.S1.04c`
- **Source issue:** `ready-and-done-as-data`
- **Landed:** 2026-10-07

### The generated views do not name the human checks and stay unchanged

- **Scenario id:** `RD-4`
- **Intent:** `E1.S1.04c`
- **Source issue:** `ready-and-done-as-data`
- **Landed:** 2026-10-07

### A drifted template item, missing check, reordered list or wrong kind is named by the guard

- **Scenario id:** `RD-5`
- **Intent:** `E1.S1.04c`
- **Source issue:** `ready-and-done-as-data`
- **Landed:** 2026-10-07

### A spike owes none of the 14 checks while the capability is off

- **Scenario id:** `RD-6`
- **Intent:** `E1.S1.04c`
- **Source issue:** `ready-and-done-as-data`
- **Landed:** 2026-10-07

### A stray line in a template section is refused

- **Scenario id:** `RD-7`
- **Intent:** `E1.S1.04c`
- **Source issue:** `ready-and-done-as-data`
- **Landed:** 2026-10-07

### The preset file headers do not claim the adapter wrote the files once

- **Scenario id:** `RD-8`
- **Intent:** `E1.S1.04c`
- **Source issue:** `ready-and-done-as-data`
- **Landed:** 2026-10-07

### stable_ids.py imports nothing and its ids equal the default preset

- **Scenario id:** `SI-1`
- **Intent:** `E1.S1.19`
- **Source issue:** `stable-ids`
- **Landed:** 2026-10-07

### The scanner finds an id in five positions and skips text

- **Scenario id:** `SI-2`
- **Intent:** `E1.S1.19`
- **Source issue:** `stable-ids`
- **Landed:** 2026-10-07

### No module outside stable_ids.py holds an approach id or a gate id in a scanned position

- **Scenario id:** `SI-3`
- **Intent:** `E1.S1.19`
- **Source issue:** `stable-ids`
- **Landed:** 2026-10-07

### Legacy approach names and routing.py approach ids live only in stable_ids.py

- **Scenario id:** `SI-4`
- **Intent:** `E1.S1.19`
- **Source issue:** `stable-ids`
- **Landed:** 2026-10-07

### The allow list names a reason, matches a line, and a stale entry fails

- **Scenario id:** `SI-5`
- **Intent:** `E1.S1.19`
- **Source issue:** `stable-ids`
- **Landed:** 2026-10-07

### The stage-id literals left in each module equal the recorded count

- **Scenario id:** `SI-6`
- **Intent:** `E1.S1.19`
- **Source issue:** `stable-ids`
- **Landed:** 2026-10-07

### The rebuilt maps equal today's values and core.py stays within its cap

- **Scenario id:** `SI-7`
- **Intent:** `E1.S1.19`
- **Source issue:** `stable-ids`
- **Landed:** 2026-10-07

### the four surfaces are scanned

- **Scenario id:** `SS-1`
- **Intent:** `GAP-1`
- **Source issue:** `scan-the-remaining-surfaces`
- **Landed:** 2026-08-13

### a JSON schema's prose is read, its contract is not

- **Scenario id:** `SS-2`
- **Intent:** `GAP-1`
- **Source issue:** `scan-the-remaining-surfaces`
- **Landed:** 2026-08-13

### the machine contract is untouched

- **Scenario id:** `SS-3`
- **Intent:** `GAP-1`
- **Source issue:** `scan-the-remaining-surfaces`
- **Landed:** 2026-08-13

### the guard can fail on each new surface

- **Scenario id:** `SS-4`
- **Intent:** `GAP-1`
- **Source issue:** `scan-the-remaining-surfaces`
- **Landed:** 2026-08-13

### no issue claims to be in flight when it is not

- **Scenario id:** `SW-1`
- **Intent:** `HYGIENE`
- **Source issue:** `stale-active-issue-sweep`
- **Landed:** 2026-08-13

### a status change is justified by evidence

- **Scenario id:** `SW-2`
- **Intent:** `HYGIENE`
- **Source issue:** `stale-active-issue-sweep`
- **Landed:** 2026-08-13

### nothing is marked landed without its gates

- **Scenario id:** `SW-3`
- **Intent:** `HYGIENE`
- **Source issue:** `stale-active-issue-sweep`
- **Landed:** 2026-08-13

### the archive still lints and checks clean

- **Scenario id:** `SW-4`
- **Intent:** `HYGIENE`
- **Source issue:** `stale-active-issue-sweep`
- **Landed:** 2026-08-13

### Given the maintainer accepted ADR-030 on 2026-10-03, then its status, its index row and the owning doc say accepted, and the test pins accepted.

- **Scenario id:** `AA-1`
- **Intent:** `INT-1`
- **Source issue:** `accept-adr-030`
- **Landed:** 2026-10-03

### An acceptance declared after the first green does not satisfy suite-passed

- **Scenario id:** `ADW-1`
- **Intent:** `INT-1`
- **Source issue:** `acceptance-declared-after-the-work`
- **Landed:** 2026-09-25

### An acceptance declared before any green counts

- **Scenario id:** `ADW-2`
- **Intent:** `INT-1`
- **Source issue:** `acceptance-declared-after-the-work`
- **Landed:** 2026-09-25

### An acceptance record with no declared_at counts as today

- **Scenario id:** `ADW-3`
- **Intent:** `INT-1`
- **Source issue:** `acceptance-declared-after-the-work`
- **Landed:** 2026-09-25

### compass acceptance record carries declared_at

- **Scenario id:** `ADW-4`
- **Intent:** `INT-1`
- **Source issue:** `acceptance-declared-after-the-work`
- **Landed:** 2026-09-25

### Given a refactor acceptance recorded with no edit in a repository with no pytest cache, When compass acceptance record runs, Then it refuses because the source tree has not changed

- **Scenario id:** `AT-1`
- **Intent:** `INT-1`
- **Source issue:** `acceptance-timing-gaps`
- **Landed:** 2026-10-05

### Given schemas/adapter-contract.yml, then every capability in docs/portability.md has a row, every adapter has a full, partial or none cell with a path, an adapter directory without a column fails, and a new negative-identity check in cli/ or hooks/ fails the scan

- **Scenario id:** `AC-A`
- **Intent:** `INT-1`
- **Source issue:** `adapter-contract-gate`
- **Landed:** 2026-10-02

### every document kind the policy names has a template

- **Scenario id:** `TRC-D1`
- **Intent:** `INT-1`
- **Source issue:** `adaptive-artifact-composition`
- **Landed:** 2026-08-24

### no public file claims an outside user

- **Scenario id:** `TRC-1`
- **Intent:** `INT-1`
- **Source issue:** `adr-013-context-tense`
- **Landed:** 2026-08-11

### no public file attaches a duration to a user

- **Scenario id:** `TRC-2`
- **Intent:** `INT-1`
- **Source issue:** `adr-013-context-tense`
- **Landed:** 2026-08-11

### the guard catches the defect it was written for

- **Scenario id:** `TRC-3`
- **Intent:** `INT-1`
- **Source issue:** `adr-013-context-tense`
- **Landed:** 2026-08-11

### Given an ADR index with sections after its table, then compass adr new puts the new row, as a link, right after the last ADR row

- **Scenario id:** `AN-A`
- **Intent:** `INT-1`
- **Source issue:** `adr-new-row-in-the-table`
- **Landed:** 2026-10-02

### Given the maintainer approved the configurable-framework recommendation on 2026-10-05 When a reader opens architecture/decisions/README.md Then ADR-002 shows superseded by ADR-033, ADR-010 shows accepted, Inv-2 and Inv-3 carry the new wording, and the ledger holds both decisions

- **Scenario id:** `TRC-001`
- **Intent:** `INT-1`
- **Source issue:** `adr-projects-add-checks-as-data`
- **Landed:** 2026-10-05

### Given a project after compass init, when a person reads the mode comment in .compass/config.yml, then it says advisory mode stops checks and CI from failing and that the pre-tool hook still blocks code edits without a failing test, instead of saying nothing blocks

- **Scenario id:** `TRC-001`
- **Intent:** `INT-1`
- **Source issue:** `advisory-mode-wording`
- **Landed:** 2026-10-06

### Given an issue, when the agent runs compass issue friction with a category, phase, an existing evidence path and a fix, then a source: agent entry is added; a fourth note, a repeated category and phase, a missing fix or an unknown evidence path is refused

- **Scenario id:** `TRC-001`
- **Intent:** `INT-1`
- **Source issue:** `agent-recorded-friction`
- **Landed:** 2026-10-06

### Given agent and person friction, when compass retro --friction runs, then agent entries are counted in their own column and never merged with person or derived entries

- **Scenario id:** `TRC-002`
- **Intent:** `INT-1`
- **Source issue:** `agent-recorded-friction`
- **Landed:** 2026-10-06

### Given the same friction in three issues from agent notes only, when lessons are proposed, then none is proposed; with one person entry for it, one is

- **Scenario id:** `TRC-003`
- **Intent:** `INT-1`
- **Source issue:** `agent-recorded-friction`
- **Landed:** 2026-10-06

### Given a note about a guardrail-backed step, when it is recorded, then it is accepted, reported as guardrail, not changeable by friction, and never counts toward a lesson or a recurring cluster

- **Scenario id:** `TRC-004`
- **Intent:** `INT-1`
- **Source issue:** `agent-recorded-friction`
- **Landed:** 2026-10-06

### Given the instruction to record agent friction, then it adds at most 40 words to resident context and resident context stays under its ceiling

- **Scenario id:** `TRC-005`
- **Intent:** `INT-1`
- **Source issue:** `agent-recorded-friction`
- **Landed:** 2026-10-06

### the always-loaded instructions state the four-part reply shape

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `agent-speech-is-unchecked`
- **Landed:** 2026-08-23

### the shape carries its three rules

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `agent-speech-is-unchecked`
- **Landed:** 2026-08-23

### the length tension is resolved rather than left open

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `agent-speech-is-unchecked`
- **Landed:** 2026-08-23

### the portable instructions carry the shape too

- **Scenario id:** `TRC-A4`
- **Intent:** `INT-1`
- **Source issue:** `agent-speech-is-unchecked`
- **Landed:** 2026-08-23

### A marker with no reason is refused

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `allow-marker-supplies-its-own-reason`
- **Landed:** 2026-08-30

### A marker with a real reason still exempts

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `allow-marker-supplies-its-own-reason`
- **Landed:** 2026-08-30

### A retired concept word is reported by the vocabulary scan

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `anthropic-aligned-vocabulary`
- **Landed:** 2026-08-28

### Every retired concept word has a ban entry naming its replacement

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `anthropic-aligned-vocabulary`
- **Landed:** 2026-08-28

### The scanned surfaces are free of the retired concept words

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `anthropic-aligned-vocabulary`
- **Landed:** 2026-08-28

### An ordinary use of a retired word is not reported

- **Scenario id:** `TRC-A4`
- **Intent:** `INT-1`
- **Source issue:** `anthropic-aligned-vocabulary`
- **Landed:** 2026-08-28

### A new manifest records orchestration rather than topology

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-1`
- **Source issue:** `anthropic-aligned-vocabulary`
- **Landed:** 2026-08-28

### The parallel-work ceiling is named for the unit it counts

- **Scenario id:** `TRC-B4`
- **Intent:** `INT-1`
- **Source issue:** `anthropic-aligned-vocabulary`
- **Landed:** 2026-08-28

### The architecture gate is named for what it checks

- **Scenario id:** `TRC-B5`
- **Intent:** `INT-1`
- **Source issue:** `anthropic-aligned-vocabulary`
- **Landed:** 2026-08-28

### A route shape declares a ceiling rather than an orchestration

- **Scenario id:** `TRC-B6`
- **Intent:** `INT-1`
- **Source issue:** `anthropic-aligned-vocabulary`
- **Landed:** 2026-08-28

### The project config names multiagent work by its new name

- **Scenario id:** `TRC-B7`
- **Intent:** `INT-1`
- **Source issue:** `anthropic-aligned-vocabulary`
- **Landed:** 2026-08-28

### Who integrates is decided by the number of subtasks

- **Scenario id:** `TRC-B8`
- **Intent:** `INT-1`
- **Source issue:** `anthropic-aligned-vocabulary`
- **Landed:** 2026-08-28

### A rename is not reported as new mechanism

- **Scenario id:** `TRC-B9`
- **Intent:** `INT-1`
- **Source issue:** `anthropic-aligned-vocabulary`
- **Landed:** 2026-08-28

### A renamed command is invocable under its new name

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-1`
- **Source issue:** `anthropic-aligned-vocabulary`
- **Landed:** 2026-08-28

### The three role agents are named after their role

- **Scenario id:** `TRC-C3`
- **Intent:** `INT-1`
- **Source issue:** `anthropic-aligned-vocabulary`
- **Landed:** 2026-08-28

### The lens carve-out is removed once the identifiers are gone

- **Scenario id:** `TRC-C4`
- **Intent:** `INT-1`
- **Source issue:** `anthropic-aligned-vocabulary`
- **Landed:** 2026-08-28

### The assessment agent is named for what it does

- **Scenario id:** `TRC-C5`
- **Intent:** `INT-1`
- **Source issue:** `anthropic-aligned-vocabulary`
- **Landed:** 2026-08-28

### A renamed skill is discoverable under its new name

- **Scenario id:** `TRC-C6`
- **Intent:** `INT-1`
- **Source issue:** `anthropic-aligned-vocabulary`
- **Landed:** 2026-08-28

### A replacement that misreads the source meaning is rejected

- **Scenario id:** `TRC-F1`
- **Intent:** `INT-1`
- **Source issue:** `anthropic-aligned-vocabulary`
- **Landed:** 2026-08-28

### A ban with no working pattern is caught before it ships

- **Scenario id:** `TRC-F3`
- **Intent:** `INT-1`
- **Source issue:** `anthropic-aligned-vocabulary`
- **Landed:** 2026-08-28

### A loose pattern that reports neighbouring text fails the suite

- **Scenario id:** `TRC-F4`
- **Intent:** `INT-1`
- **Source issue:** `anthropic-aligned-vocabulary`
- **Landed:** 2026-08-28

### Given the shipped policy and `--autonomy balanced`, when `compass approach diagram` runs, then the regular row marks define and plan as stops for a person, the quick-fix row marks none, and every cell names its weight as a word.

- **Scenario id:** `RD-1`
- **Intent:** `INT-1`
- **Source issue:** `approach-diagram`
- **Landed:** 2026-10-06

### Given no `--autonomy`, when it runs, then it uses the project's `autonomy:` setting; an unknown value is refused, naming the values.

- **Scenario id:** `RD-2`
- **Intent:** `INT-1`
- **Source issue:** `approach-diagram`
- **Landed:** 2026-10-06

### Given a project with its own `governance/routing-policy.yml`, when it runs, then the diagram shows that policy, read through the same route names as the evaluator.

- **Scenario id:** `RD-3`
- **Intent:** `INT-1`
- **Source issue:** `approach-diagram`
- **Landed:** 2026-10-06

### Given any render, then it names the three ways work comes back: a reassessment, a refusal from the pre-tool hook and a failed `compass check`.

- **Scenario id:** `RD-5`
- **Intent:** `INT-1`
- **Source issue:** `approach-diagram`
- **Landed:** 2026-10-06

### Given `docs/approach-diagram.html`, when the suite runs, then a test fails when it differs from a fresh render of the shipped policy under `balanced`, and two renders are byte-identical.

- **Scenario id:** `RD-6`
- **Intent:** `INT-1`
- **Source issue:** `approach-diagram`
- **Landed:** 2026-10-06

### Given a checkout with the full archive but without the adapter's generated feature file, When the archive citation guard runs with COMPASS_FULL_ARCHIVE=1, Then the README's mention of the file bdd extract writes is treated as illustrative and the guard passes

- **Scenario id:** `AC-1`
- **Intent:** `INT-1`
- **Source issue:** `archive-citation-in-adapter-readme`
- **Landed:** 2026-10-04

### a fabricated quote fails even without the archive

- **Scenario id:** `TRC-1`
- **Intent:** `INT-1`
- **Source issue:** `archive-quote-verification`
- **Landed:** 2026-08-12

### an unaltered quote is accepted, and the report names what went unverified

- **Scenario id:** `TRC-2`
- **Intent:** `INT-1`
- **Source issue:** `archive-quote-verification`
- **Landed:** 2026-08-12

### a genuine quote passes by direct verification

- **Scenario id:** `TRC-3`
- **Intent:** `INT-1`
- **Source issue:** `archive-quote-verification`
- **Landed:** 2026-08-12

### a mismatched quote fails, not skips, when the archive is present

- **Scenario id:** `TRC-4`
- **Intent:** `INT-1`
- **Source issue:** `archive-quote-verification`
- **Landed:** 2026-08-12

### the regeneration path refuses an unverified hash

- **Scenario id:** `TRC-5`
- **Intent:** `INT-1`
- **Source issue:** `archive-quote-verification`
- **Landed:** 2026-08-12

### Given the local archive, then the sample builder copies a fixed list of landed and abandoned issues with their layout, replaces local and private paths, recomputes the digest of each record it changed, and gives the same files when run twice.

- **Scenario id:** `AS-A`
- **Intent:** `INT-1`
- **Source issue:** `archive-sample`
- **Landed:** 2026-10-03

### Given the sample, then compass check passes for every issue in it, run from the sample's root.

- **Scenario id:** `AS-B`
- **Intent:** `INT-1`
- **Source issue:** `archive-sample`
- **Landed:** 2026-10-03

### Given the sample, then a test fails if any file in it holds a local absolute path, a private planning path, an email address or a credential shape.

- **Scenario id:** `AS-C`
- **Intent:** `INT-1`
- **Source issue:** `archive-sample`
- **Landed:** 2026-10-03

### Given a clean checkout with no local archive, then the tests that read the archive's shape read the sample and run, and with the full-archive switch set they read the real archive.

- **Scenario id:** `AS-D`
- **Intent:** `INT-1`
- **Source issue:** `archive-sample`
- **Landed:** 2026-10-03

### Given a clean checkout, then the living-spec currency and archive citation tests skip naming the full-archive switch, run when it is set, and the release guide says to set it.

- **Scenario id:** `AS-E`
- **Intent:** `INT-1`
- **Source issue:** `archive-sample`
- **Landed:** 2026-10-03

### Given the sample, then the self-architecture tests read the issue's real name, and the readable-specs test reads older acceptance criteria without a Summary, so neither returns early on a stale name.

- **Scenario id:** `AS-F`
- **Intent:** `INT-1`
- **Source issue:** `archive-sample`
- **Landed:** 2026-10-03

### Given atomic_io, when a file is written and the process fails before the rename, then the old file is intact and no temporary file is left; a YAML file with a duplicate key is refused with its line; equal data gives equal canonical JSON and digests

- **Scenario id:** `TRC-001`
- **Intent:** `INT-1`
- **Source issue:** `atomic-io`
- **Landed:** 2026-10-06

### Given no autonomy setting, when an assessment is evaluated, then the manifest's checkpoints follow the balanced column of the policy's checkpoint table.

- **Scenario id:** `AU-1`
- **Intent:** `INT-1`
- **Source issue:** `autonomy-setting`
- **Landed:** 2026-10-03

### Given one assessment under each of the three autonomy values, when it is evaluated, then only the checkpoints differ; the route, stages, gates and rules fired stay the same.

- **Scenario id:** `AU-2`
- **Intent:** `INT-1`
- **Source issue:** `autonomy-setting`
- **Landed:** 2026-10-03

### Given an autonomy value that is not one of the three, when an assessment is evaluated, then it is refused with the setting and the allowed values named.

- **Scenario id:** `AU-3`
- **Intent:** `INT-1`
- **Source issue:** `autonomy-setting`
- **Landed:** 2026-10-03

### Given an issue, when approach summary runs, then it still prints three lines and the first names the checkpoints that wait or says none do.

- **Scenario id:** `AU-4`
- **Intent:** `INT-1`
- **Source issue:** `autonomy-setting`
- **Landed:** 2026-10-03

### Given the assess, define, refine and plan commands, then each hand-off waits only when its stage is a listed checkpoint, and otherwise shows the hand-off and logs the skip.

- **Scenario id:** `AU-5`
- **Intent:** `INT-1`
- **Source issue:** `autonomy-setting`
- **Landed:** 2026-10-03

### Given a checkpoint table that names something other than the four checkpoint stages, when the policy is linted, then it is refused.

- **Scenario id:** `AU-6`
- **Intent:** `INT-1`
- **Source issue:** `autonomy-setting`
- **Landed:** 2026-10-03

### A bare pytest run passes on a clean checkout

- **Scenario id:** `BPF-1`
- **Intent:** `INT-1`
- **Source issue:** `bare-pytest-fails-on-two-tests`
- **Landed:** 2026-09-11

### each runner should have a worked project

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `bdd-adapters-and-skill-length`
- **Landed:** 

### each adapter should run the extracted feature and pass

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `bdd-adapters-and-skill-length`
- **Landed:** 

### every adapter should share the same four documented steps

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `bdd-adapters-and-skill-length`
- **Landed:** 

### the tag selector should know every shipped runner

- **Scenario id:** `TRC-A4`
- **Intent:** `INT-1`
- **Source issue:** `bdd-adapters-and-skill-length`
- **Landed:** 

### Given both files and a recognised compass.yml, an old file that holds a settings key makes the hook refuse with settings-conflict and the CLI raise the same text

- **Scenario id:** `BS-1`
- **Intent:** `INT-1`
- **Source issue:** `both-settings-files-present`
- **Landed:** 2026-10-07

### Given both files and a compass.yml with no schema, the old file is read, a warning goes to stderr once, and the hook decides as for the old file alone

- **Scenario id:** `BS-2`
- **Intent:** `INT-1`
- **Source issue:** `both-settings-files-present`
- **Landed:** 2026-10-07

### Given both files, a recognised compass.yml and an old file with only state keys, compass.yml is read with no refusal and no warning

- **Scenario id:** `BS-3`
- **Intent:** `INT-1`
- **Source issue:** `both-settings-files-present`
- **Landed:** 2026-10-07

### Given only compass.yml, with or without schema, it is read and nothing warns

- **Scenario id:** `BS-4`
- **Intent:** `INT-1`
- **Source issue:** `both-settings-files-present`
- **Landed:** 2026-10-07

### Given a broken file beside the other, the reader refuses naming the broken file

- **Scenario id:** `BS-5`
- **Intent:** `INT-1`
- **Source issue:** `both-settings-files-present`
- **Landed:** 2026-10-07

### Given more than five conflicting keys, the text lists five in file order and says and N more

- **Scenario id:** `BS-6`
- **Intent:** `INT-1`
- **Source issue:** `both-settings-files-present`
- **Landed:** 2026-10-07

### Given a conflict, compass check and every reader that used to ignore an unreadable file fail with the conflict text

- **Scenario id:** `BS-7`
- **Intent:** `INT-1`
- **Source issue:** `both-settings-files-present`
- **Landed:** 2026-10-07

### Given the registry, settings-conflict follows the three-line shape and is listed in the generated refusal codes

- **Scenario id:** `BS-8`
- **Intent:** `INT-1`
- **Source issue:** `both-settings-files-present`
- **Landed:** 2026-10-07

### Given the recorded hook corpus with settings moved to compass.yml with schema, every decision matches

- **Scenario id:** `BS-9`
- **Intent:** `INT-1`
- **Source issue:** `both-settings-files-present`
- **Landed:** 2026-10-07

### Given the field table, then it names the eight catalogues, each catalogue's fields with their type, merge kind and compare kind, the obligation fields the clas

- **Scenario id:** `CS-1`
- **Intent:** `INT-1`
- **Source issue:** `catalogue-spec`
- **Landed:** 2026-10-06

### Given a layer document, when it is checked, then an unknown top-level key, an unknown catalogue field, an id that breaks the id pattern, a settings key in a pa

- **Scenario id:** `CS-2`
- **Intent:** `INT-1`
- **Source issue:** `catalogue-spec`
- **Landed:** 2026-10-06

### Given a dimension entry, when it is checked, then a type outside `ordered-enum`, `enum` and `set`, an ordered dimension without `tighter:`, and `at_least:` on 

- **Scenario id:** `CS-3`
- **Intent:** `INT-1`
- **Source issue:** `catalogue-spec`
- **Landed:** 2026-10-06

### Given `when: { risk: { at_least: cross-cutting } }`, when an assessment is matched, then cross-cutting and critical match and trivial and contained do not; eve

- **Scenario id:** `CS-4`
- **Intent:** `INT-1`
- **Source issue:** `catalogue-spec`
- **Landed:** 2026-10-06

### Given the committed JSON Schema for compass.yml in the schemas folder, then it equals the schema generated from the field table

- **Scenario id:** `CS-5`
- **Intent:** `INT-1`
- **Source issue:** `catalogue-spec`
- **Landed:** 2026-10-06

### A repeated scenario flag records every value

- **Scenario id:** `CKS-1`
- **Intent:** `INT-1`
- **Source issue:** `changed-file-keeps-one-scenario`
- **Landed:** 2026-09-25

### A later add keeps the earlier scenarios

- **Scenario id:** `CKS-2`
- **Intent:** `INT-1`
- **Source issue:** `changed-file-keeps-one-scenario`
- **Landed:** 2026-09-25

### A declared test changed after the green fails the landed check

- **Scenario id:** `CUF-1`
- **Intent:** `INT-1`
- **Source issue:** `changes-id-misses-unlisted-files`
- **Landed:** 2026-09-25

### The tested files landing pass, whatever HEAD does next

- **Scenario id:** `CUF-2`
- **Intent:** `INT-1`
- **Source issue:** `changes-id-misses-unlisted-files`
- **Landed:** 2026-09-25

### A record built before the change is judged as built

- **Scenario id:** `CUF-3`
- **Intent:** `INT-1`
- **Source issue:** `changes-id-misses-unlisted-files`
- **Landed:** 2026-09-25

### Given a traced file whose deletion is staged but not yet committed, then the traceability check counts its absence as the change; a traced file missing from disk with no deletion staged or committed is still reported.

- **Scenario id:** `SD-1`
- **Intent:** `INT-1`
- **Source issue:** `check-accepts-a-staged-deletion`
- **Landed:** 2026-10-04

### A mapped subtask the record lacks fails the check

- **Scenario id:** `CRM-1`
- **Intent:** `INT-1`
- **Source issue:** `check-does-not-compare-record-with-map`
- **Landed:** 2026-09-25

### subtask next lists a mapped subtask not yet dispatched

- **Scenario id:** `CRM-2`
- **Intent:** `INT-1`
- **Source issue:** `check-does-not-compare-record-with-map`
- **Landed:** 2026-09-25

### With no map the check judges the record as before

- **Scenario id:** `CRM-3`
- **Intent:** `INT-1`
- **Source issue:** `check-does-not-compare-record-with-map`
- **Landed:** 2026-09-25

### Given the mutation-proof register, When the runner breaks each check to always pass and then always fail in a copy of the checkout, Then each fails test and each restores test goes red, a weakened, skipped or uncollected test is reported by name with a non-zero exit, and the checkout is unchanged

- **Scenario id:** `CM-1`
- **Intent:** `INT-1`
- **Source issue:** `check-mutation-runner`
- **Landed:** 2026-10-06

### The registry holds one versioned entry per built-in check and CHECK_FNS is derived from it

- **Scenario id:** `CR-1`
- **Intent:** `INT-1`
- **Source issue:** `check-registry`
- **Landed:** 2026-10-07

### The registry answers the installed version and major of an implementation

- **Scenario id:** `CR-2`
- **Intent:** `INT-1`
- **Source issue:** `check-registry`
- **Landed:** 2026-10-07

### Each implementation has a verdict-only corpus seeded from its mutation proof, and a test runs each seed

- **Scenario id:** `CR-3`
- **Intent:** `INT-1`
- **Source issue:** `check-registry`
- **Landed:** 2026-10-07

### The lock file build rule fails on a changed verdict digest without a major bump

- **Scenario id:** `CR-4`
- **Intent:** `INT-1`
- **Source issue:** `check-registry`
- **Landed:** 2026-10-07

### Policy lint refuses a check naming an impl the registry does not hold

- **Scenario id:** `CR-5`
- **Intent:** `INT-1`
- **Source issue:** `check-registry`
- **Landed:** 2026-10-07

### Given a generation with an advisory check, when it fails, then the run passes and shows the failure as advisory

- **Scenario id:** `CS-1`
- **Intent:** `INT-1`
- **Source issue:** `check-severity-from-generation`
- **Landed:** 2026-10-08

### Given a landed_by relaxation on a shipped check with on_skipped fail, the verdict is unchanged

- **Scenario id:** `CS-10`
- **Intent:** `INT-1`
- **Source issue:** `check-severity-from-generation`
- **Landed:** 2026-10-08

### Given a spike with an advisory guardrail check that fails, then the run passes and shows the failure as advisory

- **Scenario id:** `CS-11`
- **Intent:** `INT-1`
- **Source issue:** `check-severity-from-generation`
- **Landed:** 2026-10-08

### Given a blocking check, when it fails, then the run fails

- **Scenario id:** `CS-2`
- **Intent:** `INT-1`
- **Source issue:** `check-severity-from-generation`
- **Landed:** 2026-10-08

### Given on_skipped fail and nothing to check, then the run fails and says why

- **Scenario id:** `CS-3`
- **Intent:** `INT-1`
- **Source issue:** `check-severity-from-generation`
- **Landed:** 2026-10-08

### Given on_skipped pass and nothing to check, then the check counts as a pass

- **Scenario id:** `CS-4`
- **Intent:** `INT-1`
- **Source issue:** `check-severity-from-generation`
- **Landed:** 2026-10-08

### Given on_skipped not-applicable and nothing to check, then it is counted apart as before

- **Scenario id:** `CS-5`
- **Intent:** `INT-1`
- **Source issue:** `check-severity-from-generation`
- **Landed:** 2026-10-08

### Given a blocking_when that does not match, an advisory severity is shown as advisory with the condition

- **Scenario id:** `CS-6`
- **Intent:** `INT-1`
- **Source issue:** `check-severity-from-generation`
- **Landed:** 2026-10-08

### Given the shipped preset and an existing issue, then the verdicts are unchanged

- **Scenario id:** `CS-7`
- **Intent:** `INT-1`
- **Source issue:** `check-severity-from-generation`
- **Landed:** 2026-10-08

### The JSON shape of an advisory failure is documented and pinned

- **Scenario id:** `CS-8`
- **Intent:** `INT-1`
- **Source issue:** `check-severity-from-generation`
- **Landed:** 2026-10-08

### Given an issue with no generation, then check behaves as before

- **Scenario id:** `CS-9`
- **Intent:** `INT-1`
- **Source issue:** `check-severity-from-generation`
- **Landed:** 2026-10-08

### Given a checkpoint table that leaves out a value or a route, then that case waits at every hand-off the route runs, and a misspelt or repeated route key is refused.

- **Scenario id:** `CT-1`
- **Intent:** `INT-1`
- **Source issue:** `checkpoint-table-gaps`
- **Landed:** 2026-10-03

### a queued issue is not asked for an assessment it cannot have

- **Scenario id:** `CIQ-A1`
- **Intent:** `INT-1`
- **Source issue:** `ci-fails-a-queued-issue-for-being-queued`
- **Landed:** 2026-08-26

### a malformed spine fails the sweep whatever its status

- **Scenario id:** `TRC-1`
- **Intent:** `INT-1`
- **Source issue:** `ci-lints-every-issue`
- **Landed:** 2026-08-12

### a well-formed not-yet-started issue still does not fail

- **Scenario id:** `TRC-2`
- **Intent:** `INT-1`
- **Source issue:** `ci-lints-every-issue`
- **Landed:** 2026-08-12

### Given the Claude review workflow, then it starts only by hand and never on a pull request event.

- **Scenario id:** `CR-1`
- **Intent:** `INT-1`
- **Source issue:** `ci-review-manual-only`
- **Landed:** 2026-10-03

### Given a pull request, then the CI review's prompt holds the review rules that match its changed files, taken with the CLI from the base branch

- **Scenario id:** `RB-A`
- **Intent:** `INT-1`
- **Source issue:** `ci-review-reads-review-rules`
- **Landed:** 2026-10-02

### the CI workflow runs the test suite

- **Scenario id:** `SCN-001`
- **Intent:** `INT-1`
- **Source issue:** `ci-runs-test-suite`
- **Landed:** 2026-07-29

### No shipped Markdown file calls verify.claims immovable

- **Scenario id:** `CCI-1`
- **Intent:** `INT-1`
- **Source issue:** `claims-called-immovable-elsewhere`
- **Landed:** 2026-09-25

### the promise should not say a test ran when only a command exited zero

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-1`
- **Source issue:** `claims-match-what-is-proved`
- **Landed:** 2026-08-22

### the promise should read the same in every place it is made

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-1`
- **Source issue:** `claims-match-what-is-proved`
- **Landed:** 2026-08-22

### the safety contract should state what a green record does not establish

- **Scenario id:** `TRC-B3`
- **Intent:** `INT-1`
- **Source issue:** `claims-match-what-is-proved`
- **Landed:** 2026-08-22

### every guarantee should name the mechanism that backs it

- **Scenario id:** `TRC-B4`
- **Intent:** `INT-1`
- **Source issue:** `claims-match-what-is-proved`
- **Landed:** 2026-08-22

### narrowing the promise should not weaken what the check actually enforces

- **Scenario id:** `TRC-F2`
- **Intent:** `INT-1`
- **Source issue:** `claims-match-what-is-proved`
- **Landed:** 2026-08-22

### The grid: union domains, grouped classes, named labels and subsets, the cap of eight

- **Scenario id:** `CL-1`
- **Intent:** `INT-1`
- **Source issue:** `classifier`
- **Landed:** 2026-10-07

### Points combine into equivalent, tightening, loosening or incomparable; refusals are outcomes

- **Scenario id:** `CL-2`
- **Intent:** `INT-1`
- **Source issue:** `classifier`
- **Landed:** 2026-10-07

### Each field compares by the kind the field table gives it

- **Scenario id:** `CL-3`
- **Intent:** `INT-1`
- **Source issue:** `classifier`
- **Landed:** 2026-10-07

### The first looser, tighter or mixed point is named with field, parent and child; early exit

- **Scenario id:** `CL-4`
- **Intent:** `INT-1`
- **Source issue:** `classifier`
- **Landed:** 2026-10-07

### The grouped grid equals the full grid, and the atoms cover every read

- **Scenario id:** `CL-5`
- **Intent:** `INT-1`
- **Source issue:** `classifier`
- **Landed:** 2026-10-07

### The verdict has complete, stable, pinned JSON

- **Scenario id:** `CL-6`
- **Intent:** `INT-1`
- **Source issue:** `classifier`
- **Landed:** 2026-10-07

### The benchmark, the module's declarations, the owning doc and the unchanged core

- **Scenario id:** `CL-7`
- **Intent:** `INT-1`
- **Source issue:** `classifier`
- **Landed:** 2026-10-07

### The evaluator routes without copying the policy

- **Scenario id:** `CS-1`
- **Intent:** `INT-1`
- **Source issue:** `classifier-speed`
- **Landed:** 2026-10-07

### A stored classification is reused when both configurations and the classifier version are unchanged

- **Scenario id:** `CS-2`
- **Intent:** `INT-1`
- **Source issue:** `classifier-speed`
- **Landed:** 2026-10-07

### The benchmark pair keeps its verdict and counts and the benchmark prints CPU seconds

- **Scenario id:** `CS-3`
- **Intent:** `INT-1`
- **Source issue:** `classifier-speed`
- **Landed:** 2026-10-07

### The lock scan classifies only the label sites a footprint can read

- **Scenario id:** `CS-4`
- **Intent:** `INT-1`
- **Source issue:** `classifier-speed`
- **Landed:** 2026-10-07

### The footprint scan gives the full scan's refusals on every lock case and route

- **Scenario id:** `CS-5`
- **Intent:** `INT-1`
- **Source issue:** `classifier-speed`
- **Landed:** 2026-10-07

### A ninth label no locked entry reads is not refused

- **Scenario id:** `CS-6`
- **Intent:** `INT-1`
- **Source issue:** `classifier-speed`
- **Landed:** 2026-10-07

### The classifier has a public scan with a point callback and locks read no private name

- **Scenario id:** `CS-7`
- **Intent:** `INT-1`
- **Source issue:** `classifier-speed`
- **Landed:** 2026-10-07

### CLAUDE.md tells a session to write plain English with no idiom or metaphor

- **Scenario id:** `PE-1`
- **Intent:** `INT-1`
- **Source issue:** `claude-md-plain-english`
- **Landed:** 2026-09-11

### Given the review workflow, when it is read, then it authenticates with the federation rule, organisation and service account variables, and no step uses an API key or OAuth token

- **Scenario id:** `TRC-001`
- **Intent:** `INT-1`
- **Source issue:** `claude-review-federation`
- **Landed:** 2026-10-01

### Given the review workflow, when it is read, then every action is pinned to a commit, contents are read-only, and no allowed tool can commit or push

- **Scenario id:** `TRC-001`
- **Intent:** `INT-1`
- **Source issue:** `claude-review-workflow`
- **Landed:** 2026-10-01

### Given the review workflow, when it is read, then it passes anthropic_workspace_id from the ANTHROPIC_WORKSPACE_ID repository variable

- **Scenario id:** `TRC-001`
- **Intent:** `INT-1`
- **Source issue:** `claude-review-workspace`
- **Landed:** 2026-10-01

### the entry point should be thin

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `cli-module-split`
- **Landed:** 

### the modules should follow the groupings the code already had

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `cli-module-split`
- **Landed:** 

### the package should import cleanly on its own

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `cli-module-split`
- **Landed:** 

### Given each of the inconsistent refusals the command corpus found, when it runs, then it exits 2, names the real problem and the flag it has, writes to stderr, and the corpus entry records the new exit on purpose

- **Scenario id:** `TRC-001`
- **Intent:** `INT-1`
- **Source issue:** `cli-refusal-consistency`
- **Landed:** 2026-10-06

### every verb says what it does

- **Scenario id:** `CLIV-A1`
- **Intent:** `INT-1`
- **Source issue:** `cli-verbs-do-not-describe-themselves`
- **Landed:** 2026-08-26

### Given a project, when tdd-red, tdd-green, flow --digest, adr new, issue lint and ci run, then none of them prints the project's absolute path; each path is relative to the project root.

- **Scenario id:** `CP-A`
- **Intent:** `INT-1`
- **Source issue:** `clickable-paths`
- **Landed:** 2026-10-03

### Given a scenario defined on a line of the acceptance criteria, when tdd-red or tdd-green runs for it, then the output names that file as path:line.

- **Scenario id:** `CP-B`
- **Intent:** `INT-1`
- **Source issue:** `clickable-paths`
- **Landed:** 2026-10-03

### Given the verbs CP-A runs, with their output piped, then it carries no escape code of any kind.

- **Scenario id:** `CP-D`
- **Intent:** `INT-1`
- **Source issue:** `clickable-paths`
- **Landed:** 2026-10-03

### code_globs of the wrong shape refuses and names the config

- **Scenario id:** `CGS-1`
- **Intent:** `INT-1`
- **Source issue:** `code-globs-as-a-string`
- **Landed:** 2026-09-25

### A list of strings behaves as today

- **Scenario id:** `CGS-2`
- **Intent:** `INT-1`
- **Source issue:** `code-globs-as-a-string`
- **Landed:** 2026-09-25

### Given FORCE_COLOR is set in the environment, When compass tdd-red runs a test that imports a project module not yet written, Then it records an import red, and the eval harness reads each test's outcome from coloured pytest output

- **Scenario id:** `CL-1`
- **Intent:** `INT-1`
- **Source issue:** `colour-hides-an-import-red`
- **Landed:** 2026-10-04

### Given the commit-msg hook is installed, then a commit whose message names a rival product is refused before it is made, a clean message commits, and the refusal names no product.

- **Scenario id:** `CM-1`
- **Intent:** `INT-1`
- **Source issue:** `commit-msg-name-check`
- **Landed:** 2026-10-04

### Given a compass run record with compass_commit and no framework block, when the comparison report is built, then it shows that commit

- **Scenario id:** `TRC-001`
- **Intent:** `INT-1`
- **Source issue:** `compare-names-the-compass-commit`
- **Landed:** 2026-09-30

### coherent artifacts pass cleanly

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### an artifact a route legitimately omits is not flagged

- **Scenario id:** `TRC-A10`
- **Intent:** `INT-1`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### analyze reports only coherence findings, not evidence findings

- **Scenario id:** `TRC-A11`
- **Intent:** `INT-1`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### a scenario with no upstream intent is flagged as orphaned

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### route disagreement between route.md and task.yml is flagged

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### claim with no backing scenario is flagged

- **Scenario id:** `TRC-A4`
- **Intent:** `INT-1`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### incoherence on a route below the analyze-gate threshold warns but does not block Land

- **Scenario id:** `TRC-A7`
- **Intent:** `INT-1`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### incoherence on a route that earns the analyze gate blocks Land

- **Scenario id:** `TRC-A8`
- **Intent:** `INT-1`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### analyze is never promoted to a gate globally

- **Scenario id:** `TRC-A9`
- **Intent:** `INT-1`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### analyze on a malformed task.yml exits non-zero with a structured error

- **Scenario id:** `TRC-F1`
- **Intent:** `INT-1`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### analyze on a task that has not yet been framed reports clearly

- **Scenario id:** `TRC-F4`
- **Intent:** `INT-1`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### a hand-edit to task.yml made by a tool is caught by analyze

- **Scenario id:** `TRC-F5`
- **Intent:** `INT-1`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### Each new scenario has every field, its seed's tests pass, and its hidden tests fail on the seed

- **Scenario id:** `CSD-1`
- **Intent:** `INT-1`
- **Source issue:** `comparison-scenarios-that-discriminate`
- **Landed:** 2026-09-30

### A correct change passes each new scenario's hidden tests

- **Scenario id:** `CSD-2`
- **Intent:** `INT-1`
- **Source issue:** `comparison-scenarios-that-discriminate`
- **Landed:** 2026-09-30

### A careless change passes the seed's tests and fails the hidden tests

- **Scenario id:** `CSD-3`
- **Intent:** `INT-1`
- **Source issue:** `comparison-scenarios-that-discriminate`
- **Landed:** 2026-09-30

### Each prompt reads as a real request, and two do not state the rule their hidden tests check

- **Scenario id:** `CSD-4`
- **Intent:** `INT-1`
- **Source issue:** `comparison-scenarios-that-discriminate`
- **Landed:** 2026-09-30

### A published report gives each condition's hidden-test result per new scenario and says whether they differed

- **Scenario id:** `CSD-5`
- **Intent:** `INT-1`
- **Source issue:** `comparison-scenarios-that-discriminate`
- **Landed:** 2026-09-30

### CMP-1

- **Scenario id:** `CMP-1`
- **Intent:** `INT-1`
- **Source issue:** `comparison-suite`
- **Landed:** 2026-09-28

### CMP-2

- **Scenario id:** `CMP-2`
- **Intent:** `INT-1`
- **Source issue:** `comparison-suite`
- **Landed:** 2026-09-28

### CMP-3

- **Scenario id:** `CMP-3`
- **Intent:** `INT-1`
- **Source issue:** `comparison-suite`
- **Landed:** 2026-09-28

### CMP-4

- **Scenario id:** `CMP-4`
- **Intent:** `INT-1`
- **Source issue:** `comparison-suite`
- **Landed:** 2026-09-28

### CMP-5

- **Scenario id:** `CMP-5`
- **Intent:** `INT-1`
- **Source issue:** `comparison-suite`
- **Landed:** 2026-09-28

### CMP-6

- **Scenario id:** `CMP-6`
- **Intent:** `INT-1`
- **Source issue:** `comparison-suite`
- **Landed:** 2026-09-28

### system-context.md exists with the canonical sections

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `compass-self-architecture`
- **Landed:** 

### relations.md documents the call graph between framework components

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `compass-self-architecture`
- **Landed:** 

### ownership.md documents what each component must and must not do

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `compass-self-architecture`
- **Landed:** 

### Given the archive sample at 5.6.0, when the archive baseline is captured, then every check's verdict on every sampled issue is recorded, issue lint and issue receipt exit 0 on each, the test passes on today's code, and it fails when one verdict changes

- **Scenario id:** `TRC-001`
- **Intent:** `INT-1`
- **Source issue:** `compat-archive-baseline`
- **Landed:** 2026-10-06

### Given the 5.6.0 CLI, when the command corpus is captured, then each recorded invocation exits as recorded, and the test fails when one exit code changes

- **Scenario id:** `TRC-001`
- **Intent:** `INT-1`
- **Source issue:** `compat-command-corpus`
- **Landed:** 2026-10-06

### Given the 5.6.0 pre-tool hook, when the hook corpus is captured, then each recorded tool call gets the recorded decision and refusal code, including both reads of .compass/config.yml, and the test fails when one decision changes

- **Scenario id:** `TRC-001`
- **Intent:** `INT-1`
- **Source issue:** `compat-hook-corpus`
- **Landed:** 2026-10-06

### Given the 5.6.0 evaluator, when the routing baseline is captured, then every one of the 1,200 assessments and every label subset over the four named labels has a recorded result, the test passes on today's code, and it fails when one shipped default changes

- **Scenario id:** `TRC-001`
- **Intent:** `INT-1`
- **Source issue:** `compat-routing-baseline`
- **Landed:** 2026-10-06

### the block names the rule that matched

- **Scenario id:** `SCN-B1`
- **Intent:** `INT-1`
- **Source issue:** `configurable-enforced-set`
- **Landed:** 2026-08-13

### a built-in match says so

- **Scenario id:** `SCN-B2`
- **Intent:** `INT-1`
- **Source issue:** `configurable-enforced-set`
- **Landed:** 2026-08-13

### Each structural decision of the configuration foundation is a proposed ADR with a rejected alternative, listed in the index

- **Scenario id:** `DR-1`
- **Intent:** `INT-1`
- **Source issue:** `configuration-decision-records`
- **Landed:** 2026-10-06

### Each product decision of 5 and 6 October 2026 for the configurable framework has a ledger entry

- **Scenario id:** `DR-2`
- **Intent:** `INT-1`
- **Source issue:** `configuration-decision-records`
- **Landed:** 2026-10-06

### No record cites a private planning path or names a rival product

- **Scenario id:** `DR-3`
- **Intent:** `INT-1`
- **Source issue:** `configuration-decision-records`
- **Landed:** 2026-10-06

### The vocabulary amendment names the approaches catalogue, the adoption setting and every new term

- **Scenario id:** `DR-4`
- **Intent:** `INT-1`
- **Source issue:** `configuration-decision-records`
- **Landed:** 2026-10-06

### The injected contract names docs/compass as the home of an issue's documents

- **Scenario id:** `CF-1`
- **Intent:** `INT-1`
- **Source issue:** `contract-facts`
- **Landed:** 2026-09-24

### Given the contribution guide, then it names the required CI check, how review works with the automatic review off, the review rules file, the code owners and the house rules, and every path it names exists.

- **Scenario id:** `CG-1`
- **Intent:** `INT-1`
- **Source issue:** `contribution-guide`
- **Landed:** 2026-10-03

### Given the published breakdown, then it carries a dated correction saying shell calls that ran compass also read files in the same call, so the Compass CLI share is an upper bound, and what those calls read.

- **Scenario id:** `CB-1`
- **Intent:** `INT-1`
- **Source issue:** `correct-token-breakdown-categories`
- **Landed:** 2026-10-04

### A command that turns the plugin off gets no coverage flag

- **Scenario id:** `CFA-1`
- **Intent:** `INT-1`
- **Source issue:** `coverage-flag-with-autoload-off`
- **Landed:** 2026-09-25

### The variable in the calling environment gets no flag

- **Scenario id:** `CFA-2`
- **Intent:** `INT-1`
- **Source issue:** `coverage-flag-with-autoload-off`
- **Landed:** 2026-09-25

### A command where the plugin loads keeps the flag

- **Scenario id:** `CFA-3`
- **Intent:** `INT-1`
- **Source issue:** `coverage-flag-with-autoload-off`
- **Landed:** 2026-09-25

### A backdated issue with evidence dated after the cutoff gets the rule

- **Scenario id:** `CDB-1`
- **Intent:** `INT-1`
- **Source issue:** `created-date-can-be-backdated`
- **Landed:** 2026-09-25

### An issue created and worked before the cutoff keeps its result

- **Scenario id:** `CDB-2`
- **Intent:** `INT-1`
- **Source issue:** `created-date-can-be-backdated`
- **Landed:** 2026-09-25

### Frame loads architecture/ into the task's working context

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### Frame degrades gracefully when architecture/ is absent

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### compass adr new <slug> creates a numbered ADR file

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### Compass ships templates for the architecture artifacts

- **Scenario id:** `TRC-A4`
- **Intent:** `INT-1`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### invariants.yml is loaded by mechanism when present

- **Scenario id:** `TRC-A5`
- **Intent:** `INT-1`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### Frame proceeds normally when invariants.yml is absent

- **Scenario id:** `TRC-A5b`
- **Intent:** `INT-1`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### Compass ships governance/signals.yml with default patterns

- **Scenario id:** `TRC-G1`
- **Intent:** `INT-1`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### Malformed invariants.yml fails Frame loudly

- **Scenario id:** `TRC-X1`
- **Intent:** `INT-1`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### The action check reads the rule body, not its own anchor

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `decay-rule-imperative-check-cannot-fail`
- **Landed:** 2026-08-30

### The rule still passes when it does state an action

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `decay-rule-imperative-check-cannot-fail`
- **Landed:** 2026-08-30

### Given the decisions of 5 and 6 October 2026, When governance/decisions/ is read, Then entries record that old route names stay readable until 7.0.0, B39 folds into PRD 22, A16 waits for PRD 19 and this repository may hold a settings-only compass.yml, each superseding what it replaces

- **Scenario id:** `DE-1`
- **Intent:** `INT-1`
- **Source issue:** `decisions-2026-10-06`
- **Landed:** 2026-10-06

### Given compass decision record <slug>, then it writes a new entry from the template, dated today, with Decided by taken from git config compass.decidedBy, else git config user.name. It refuses an existing slug, and refuses when git has neither name set. There is no option to set Decided by.

- **Scenario id:** `DL-A`
- **Intent:** `INT-1`
- **Source issue:** `decisions-ledger`
- **Landed:** 2026-10-02

### Given compass decision list, then it prints each entry's date, slug and the first line of its decision, newest first. Given compass decision show <slug>, then it prints that entry.

- **Scenario id:** `DL-B`
- **Intent:** `INT-1`
- **Source issue:** `decisions-ledger`
- **Landed:** 2026-10-02

### Given compass decision check --base <ref>, then it fails, naming the entry, when an entry that exists at the ref is changed or removed. A new entry passes. A ref git cannot resolve fails loudly.

- **Scenario id:** `DL-C`
- **Intent:** `INT-1`
- **Source issue:** `decisions-ledger`
- **Landed:** 2026-10-02

### Given compass ci --since <ref> in a project with governance/decisions/, then it runs the history check against that ref. Without --since, it says the history check was skipped and why.

- **Scenario id:** `DL-D`
- **Intent:** `INT-1`
- **Source issue:** `decisions-ledger`
- **Landed:** 2026-10-02

### Given the reviewer agent and the governance-check skill, then each says to read governance/decisions/ before recommending a rename, a wording change or a reversal, and to report a collision as "settled by <path>".

- **Scenario id:** `DL-E`
- **Intent:** `INT-1`
- **Source issue:** `decisions-ledger`
- **Landed:** 2026-10-02

### Given the verb surface, then decision is in the CLI's baseline and in the README's CLI surface block.

- **Scenario id:** `DL-F`
- **Intent:** `INT-1`
- **Source issue:** `decisions-ledger`
- **Landed:** 2026-10-02

### Given governance/decisions/, then it holds at least ten entries, each a decision the maintainer made on record and confirmed in their own words.

- **Scenario id:** `DL-G`
- **Intent:** `INT-1`
- **Source issue:** `decisions-ledger`
- **Landed:** 2026-10-02

### Today's two policy files convert to the committed preset, and a planted policy change breaks the match

- **Scenario id:** `DP-1`
- **Intent:** `INT-1`
- **Source issue:** `default-preset-data`
- **Landed:** 2026-10-07

### The preset is named default at version 6.0.0 with capabilities off and checks as a parent layer

- **Scenario id:** `DP-2`
- **Intent:** `INT-1`
- **Source issue:** `default-preset-data`
- **Landed:** 2026-10-07

### Stage modes carry the ruled ranks on the depth ladder and no rank elsewhere

- **Scenario id:** `DP-3`
- **Intent:** `INT-1`
- **Source issue:** `default-preset-data`
- **Landed:** 2026-10-07

### Exactly the entries of the shipped lock set are locked, with the human sign-off hard-locked

- **Scenario id:** `DP-4`
- **Intent:** `INT-1`
- **Source issue:** `default-preset-data`
- **Landed:** 2026-10-07

### The adapter reads old key names, leaves its input unchanged and is read by nothing yet

- **Scenario id:** `DP-5`
- **Intent:** `INT-1`
- **Source issue:** `default-preset-data`
- **Landed:** 2026-10-07

### Every reference in the preset resolves and the evidence types match the guardrails file

- **Scenario id:** `DP-6`
- **Intent:** `INT-1`
- **Source issue:** `default-preset-data`
- **Landed:** 2026-10-07

### Given an issue in progress, then its board row shows its route, current stage, gates passed out of total, and whether its newest test record still matches its files.

- **Scenario id:** `DB-1`
- **Intent:** `INT-1`
- **Source issue:** `delivery-board`
- **Landed:** 2026-10-03

### Given in-progress issues whose evidence is stale and parked issues, then each appears in its own section, apart from the issues moving normally.

- **Scenario id:** `DB-2`
- **Intent:** `INT-1`
- **Source issue:** `delivery-board`
- **Landed:** 2026-10-03

### Given queued and landed issues, then the board shows the queue with age and signal, what landed in the last seven days, and the most common friction among them.

- **Scenario id:** `DB-3`
- **Intent:** `INT-1`
- **Source issue:** `delivery-board`
- **Landed:** 2026-10-03

### Given the flow command with an html file named, then it writes one self-contained page with the same sections and rows, every value escaped.

- **Scenario id:** `DB-4`
- **Intent:** `INT-1`
- **Source issue:** `delivery-board`
- **Landed:** 2026-10-03

### Given this repository's manifests, then the flow board stays within the speed bound its test sets.

- **Scenario id:** `DB-5`
- **Intent:** `INT-1`
- **Source issue:** `delivery-board`
- **Landed:** 2026-10-03

### Given a manifest whose fields have the wrong types, then the board lists it as unreadable and still renders every other issue.

- **Scenario id:** `DB-6`
- **Intent:** `INT-1`
- **Source issue:** `delivery-board`
- **Landed:** 2026-10-03

### Given the clock moves one day on between the test module loading and board() running, When the queue age test runs, Then it still reports the age it set up

- **Scenario id:** `DM-1`
- **Intent:** `INT-1`
- **Source issue:** `delivery-board-midnight-flake`
- **Landed:** 2026-10-06

### Given a configured record, then record sync adds and updates its paths in the record repository, redacting credentials, commits naming the project's HEAD and pushes; it deletes only with prune, refuses a full sync from a linked worktree and any path outside the project or into git's folder.

- **Scenario id:** `DR-A`
- **Intent:** `INT-1`
- **Source issue:** `delivery-record`
- **Landed:** 2026-10-03

### Given no record in the config, then record sync says none is configured and exits 0, and ship is unchanged.

- **Scenario id:** `DR-B`
- **Intent:** `INT-1`
- **Source issue:** `delivery-record`
- **Landed:** 2026-10-03

### Given a configured record, then ship-commit syncs it after a landing, and a failed sync makes ship exit non-zero naming the fix.

- **Scenario id:** `DR-C`
- **Intent:** `INT-1`
- **Source issue:** `delivery-record`
- **Landed:** 2026-10-03

### Given a fresh clone and the record repository, then record restore copies the record's paths back, refuses to overwrite a differing file without force, and reports what it restored.

- **Scenario id:** `DR-D`
- **Intent:** `INT-1`
- **Source issue:** `delivery-record`
- **Landed:** 2026-10-03

### Given the change, then a decision record states the choice of a second private repository, and the restore drill has been run once from a fresh clone.

- **Scenario id:** `DR-E`
- **Intent:** `INT-1`
- **Source issue:** `delivery-record`
- **Landed:** 2026-10-03

### a scenario that serves two intents answers for both

- **Scenario id:** `TRC-1`
- **Intent:** `INT-1`
- **Source issue:** `derive-spec-multi-intent`
- **Landed:** 2026-08-10

### the single-intent form is unchanged

- **Scenario id:** `TRC-2`
- **Intent:** `INT-1`
- **Source issue:** `derive-spec-multi-intent`
- **Landed:** 2026-08-10

### An edit outside the project is not logged

- **Scenario id:** `DLO-1`
- **Intent:** `INT-1`
- **Source issue:** `devlog-logs-edits-outside-the-project`
- **Landed:** 2026-09-25

### An edit inside the project is logged relative to it

- **Scenario id:** `DLO-2`
- **Intent:** `INT-1`
- **Source issue:** `devlog-logs-edits-outside-the-project`
- **Landed:** 2026-09-25

### A relative path is judged by where it resolves; the no-project message names the devlog

- **Scenario id:** `DLO-3`
- **Intent:** `INT-1`
- **Source issue:** `devlog-logs-edits-outside-the-project`
- **Landed:** 2026-09-25

### Given a landed_by mapping, an unbound green, an early omission or an issue landed through another, then compass issue diagnose prints the value, (unbound), no false deviation, and that the records are in the other issue

- **Scenario id:** `DE-A`
- **Intent:** `INT-1`
- **Source issue:** `diagnose-output-edges`
- **Landed:** 2026-10-02

### Given the plugin as the directory receives it, then the icon is under the 5 MiB per-file limit and still square, and the README lists everything Compass runs on the machine, sends and fetches.

- **Scenario id:** `DL-1`
- **Intent:** `INT-1`
- **Source issue:** `directory-listing-prep`
- **Landed:** 2026-10-04

### The protocol document answers every step

- **Scenario id:** `DPR-5`
- **Intent:** `INT-1`
- **Source issue:** `dispatch-protocol`
- **Landed:** 2026-09-25

### Given a repository with one tracked and one untracked document, When the document scans list their files, Then only the tracked document is listed

- **Scenario id:** `DS-1`
- **Intent:** `INT-1`
- **Source issue:** `doc-scans-read-tracked-files`
- **Landed:** 2026-10-06

### A written document lands under a dated issue directory

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-1`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### Creating the docs directory is reported, never silent

- **Scenario id:** `TRC-B3`
- **Intent:** `INT-1`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### The shipped examples show the new layout

- **Scenario id:** `TRC-E4`
- **Intent:** `INT-1`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### no published surface claims a green is always written to the shared path

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `docs-describe-the-old-evidence-path`
- **Landed:** 2026-08-23

### the documentation names both forms and says which is written when

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `docs-describe-the-old-evidence-path`
- **Landed:** 2026-08-23

### a worked example shows the path a reader will actually see

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `docs-describe-the-old-evidence-path`
- **Landed:** 2026-08-23

### Given mkdocs.yml and the docs workflow, then the site lists the five core pages and the pages they link to, every listed page exists, every relative link on them stays inside the site, the build tool is pinned and used only in CI, and the site is published from main only.

- **Scenario id:** `DS-1`
- **Intent:** `INT-1`
- **Source issue:** `docs-site`
- **Landed:** 2026-10-04

### Given the docs site, then its root serves a home page, index.md, that is first in the navigation and links only to pages in the site.

- **Scenario id:** `DH-1`
- **Intent:** `INT-1`
- **Source issue:** `docs-site-home-page`
- **Landed:** 2026-10-04

### every drift guard passes on the slimmed documents

- **Scenario id:** `DOC-A1`
- **Intent:** `INT-1`
- **Source issue:** `docs-slimming-pass`
- **Landed:** 2026-08-26

### Given a docs page with a table cell holding inline code such as /compass:intent, When the site renders it at desktop width, Then the code stays on one line rather than breaking mid-word

- **Scenario id:** `DT-1`
- **Intent:** `INT-1`
- **Source issue:** `docs-table-code-wraps`
- **Landed:** 2026-10-04

### The reader helper returns the stored view, a live view for a project with a compass.yml, nothing for a legacy project and refuses generation 0

- **Scenario id:** `EF-1`
- **Intent:** `INT-1`
- **Source issue:** `effective-readers`
- **Landed:** 2026-10-08

### An issue with no generation reads the governance files and prints what it printed before

- **Scenario id:** `EF-10`
- **Intent:** `INT-1`
- **Source issue:** `effective-readers`
- **Landed:** 2026-10-08

### Every read of a governance policy file is in a function that asks the effective view first

- **Scenario id:** `EF-11`
- **Intent:** `INT-1`
- **Source issue:** `effective-readers`
- **Landed:** 2026-10-08

### The approach diagram of a project with a compass.yml renders the effective configuration

- **Scenario id:** `EF-12`
- **Intent:** `INT-1`
- **Source issue:** `effective-readers`
- **Landed:** 2026-10-08

### The accessors of the shipped default's generation equal what the governance files hold

- **Scenario id:** `EF-2`
- **Intent:** `INT-1`
- **Source issue:** `effective-readers`
- **Landed:** 2026-10-08

### compass check judges an issue by its generation after the governance files change or compass.yml is deleted

- **Scenario id:** `EF-3`
- **Intent:** `INT-1`
- **Source issue:** `effective-readers`
- **Landed:** 2026-10-08

### A check with a custom id and the command-passes implementation runs its command from the generation

- **Scenario id:** `EF-4`
- **Intent:** `INT-1`
- **Source issue:** `effective-readers`
- **Landed:** 2026-10-08

### Gate evidence requirements come from the generation in gate pass, the evidence check and the receipt

- **Scenario id:** `EF-5`
- **Intent:** `INT-1`
- **Source issue:** `effective-readers`
- **Landed:** 2026-10-08

### approach evaluate on an issue with a generation computes from the generation

- **Scenario id:** `EF-6`
- **Intent:** `INT-1`
- **Source issue:** `effective-readers`
- **Landed:** 2026-10-08

### Loop ceilings come from the generation

- **Scenario id:** `EF-7`
- **Intent:** `INT-1`
- **Source issue:** `effective-readers`
- **Landed:** 2026-10-08

### Readers with no issue read the live effective configuration of a project with a compass.yml

- **Scenario id:** `EF-8`
- **Intent:** `INT-1`
- **Source issue:** `effective-readers`
- **Landed:** 2026-10-08

### compass check prints the generation, the parent version and a pending config change

- **Scenario id:** `EF-9`
- **Intent:** `INT-1`
- **Source issue:** `effective-readers`
- **Landed:** 2026-10-08

### Given cli/compass holds the shebang, build_parser and main, When a verb is registered in build_parser, Then the entry-point guard still passes; and when logic is added outside build_parser, or a loop or a new function is added, Then it fails

- **Scenario id:** `EC-1`
- **Intent:** `INT-1`
- **Source issue:** `entry-point-cap-measures-code`
- **Landed:** 2026-10-04

### Given an error naming a project file, or compass approach evaluate's Read line, then the path is printed relative to the project root

- **Scenario id:** `EP-A`
- **Intent:** `INT-1`
- **Source issue:** `errors-print-relative-paths`
- **Landed:** 2026-10-03

### EGA-1

- **Scenario id:** `EGA-1`
- **Intent:** `INT-1`
- **Source issue:** `eval-gaps-after-d30`
- **Landed:** 2026-09-27

### EGA-2

- **Scenario id:** `EGA-2`
- **Intent:** `INT-1`
- **Source issue:** `eval-gaps-after-d30`
- **Landed:** 2026-09-27

### EGA-3

- **Scenario id:** `EGA-3`
- **Intent:** `INT-1`
- **Source issue:** `eval-gaps-after-d30`
- **Landed:** 2026-09-27

### EGA-4

- **Scenario id:** `EGA-4`
- **Intent:** `INT-1`
- **Source issue:** `eval-gaps-after-d30`
- **Landed:** 2026-09-27

### EGA-5

- **Scenario id:** `EGA-5`
- **Intent:** `INT-1`
- **Source issue:** `eval-gaps-after-d30`
- **Landed:** 2026-09-27

### EGA-6

- **Scenario id:** `EGA-6`
- **Intent:** `INT-1`
- **Source issue:** `eval-gaps-after-d30`
- **Landed:** 2026-09-27

### EGA-7

- **Scenario id:** `EGA-7`
- **Intent:** `INT-1`
- **Source issue:** `eval-gaps-after-d30`
- **Landed:** 2026-09-27

### EGB-1

- **Scenario id:** `EGB-1`
- **Intent:** `INT-1`
- **Source issue:** `eval-gaps-after-d33`
- **Landed:** 2026-09-28

### EGB-2

- **Scenario id:** `EGB-2`
- **Intent:** `INT-1`
- **Source issue:** `eval-gaps-after-d33`
- **Landed:** 2026-09-28

### EGB-3

- **Scenario id:** `EGB-3`
- **Intent:** `INT-1`
- **Source issue:** `eval-gaps-after-d33`
- **Landed:** 2026-09-28

### EGB-4

- **Scenario id:** `EGB-4`
- **Intent:** `INT-1`
- **Source issue:** `eval-gaps-after-d33`
- **Landed:** 2026-09-28

### EGB-5

- **Scenario id:** `EGB-5`
- **Intent:** `INT-1`
- **Source issue:** `eval-gaps-after-d33`
- **Landed:** 2026-09-28

### EGB-6

- **Scenario id:** `EGB-6`
- **Intent:** `INT-1`
- **Source issue:** `eval-gaps-after-d33`
- **Landed:** 2026-09-28

### EGB-7

- **Scenario id:** `EGB-7`
- **Intent:** `INT-1`
- **Source issue:** `eval-gaps-after-d33`
- **Landed:** 2026-09-28

### EGB-8

- **Scenario id:** `EGB-8`
- **Intent:** `INT-1`
- **Source issue:** `eval-gaps-after-d33`
- **Landed:** 2026-09-28

### Given a hidden test run that skipped a test and exited 1, when the harness corrects its counts, then it leaves them alone, and corrects only a collection error that exited 2

- **Scenario id:** `TRC-001`
- **Intent:** `INT-1`
- **Source issue:** `eval-gaps-after-d34`
- **Landed:** 2026-10-01

### A comparison corrects a record against the hidden-test count its own run recorded

- **Scenario id:** `TRC-002`
- **Intent:** `INT-1`
- **Source issue:** `eval-gaps-after-d34`
- **Landed:** 2026-10-01

### EJG-1

- **Scenario id:** `EJG-1`
- **Intent:** `INT-1`
- **Source issue:** `eval-judge-gaps`
- **Landed:** 2026-09-27

### EJG-2

- **Scenario id:** `EJG-2`
- **Intent:** `INT-1`
- **Source issue:** `eval-judge-gaps`
- **Landed:** 2026-09-27

### EJG-3

- **Scenario id:** `EJG-3`
- **Intent:** `INT-1`
- **Source issue:** `eval-judge-gaps`
- **Landed:** 2026-09-27

### EJG-4

- **Scenario id:** `EJG-4`
- **Intent:** `INT-1`
- **Source issue:** `eval-judge-gaps`
- **Landed:** 2026-09-27

### EJG-5

- **Scenario id:** `EJG-5`
- **Intent:** `INT-1`
- **Source issue:** `eval-judge-gaps`
- **Landed:** 2026-09-27

### EJG-6

- **Scenario id:** `EJG-6`
- **Intent:** `INT-1`
- **Source issue:** `eval-judge-gaps`
- **Landed:** 2026-09-27

### EJG-7

- **Scenario id:** `EJG-7`
- **Intent:** `INT-1`
- **Source issue:** `eval-judge-gaps`
- **Landed:** 2026-09-27

### EJG-8

- **Scenario id:** `EJG-8`
- **Intent:** `INT-1`
- **Source issue:** `eval-judge-gaps`
- **Landed:** 2026-09-27

### Given an eval session transcript that edits compass.yml, When the judge checks protected files, Then it reports the edit as touching a protected file, as it does for .compass/config.yml

- **Scenario id:** `TRC-001`
- **Intent:** `INT-1`
- **Source issue:** `eval-judge-guards-compass-yml`
- **Landed:** 2026-10-07

### Given the eval scenario records for other frameworks, then none holds a sentence copied from that framework's own templates, and their file layout and heading form are unchanged.

- **Scenario id:** `QT-1`
- **Intent:** `INT-1`
- **Source issue:** `eval-record-quotes-a-template`
- **Landed:** 2026-10-03

### Given an issue manifest whose assessment holds a key the manifest schema does not allow, such as risk_reason, When compass approach evaluate --write or compass check runs on it, Then each refuses and names the unknown key and the allowed keys, as issue lint does, with or without jsonschema installed

- **Scenario id:** `SK-1`
- **Intent:** `INT-1`
- **Source issue:** `evaluate-and-check-apply-the-schema`
- **Landed:** 2026-10-04

### A test record names the tree it ran on

- **Scenario id:** `EVB-1`
- **Intent:** `INT-1`
- **Source issue:** `evidence-binding`
- **Landed:** 2026-09-25

### extraction should produce a feature file a BDD runner can read

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### extraction should be byte-for-byte deterministic

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### each extracted scenario should carry its traceability id as a tag

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### the extracted Feature should name the task it came from

- **Scenario id:** `TRC-A4`
- **Intent:** `INT-1`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### extraction should resolve the current task when none is named

- **Scenario id:** `TRC-A5`
- **Intent:** `INT-1`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### the new verb should appear in the documented CLI surface

- **Scenario id:** `TRC-A6`
- **Intent:** `INT-1`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### a configured features directory should override the default location

- **Scenario id:** `TRC-A7`
- **Intent:** `INT-1`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### a spec with no gherkin fences should fail loudly

- **Scenario id:** `TRC-F1`
- **Intent:** `INT-1`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### a malformed gherkin fence should fail loudly

- **Scenario id:** `TRC-F2`
- **Intent:** `INT-1`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### a title that drifts between the heading and the fence should be caught

- **Scenario id:** `TRC-F3`
- **Intent:** `INT-1`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### extraction should not modify anything it did not create

- **Scenario id:** `TRC-F4`
- **Intent:** `INT-1`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### No exemption excludes nothing

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `exemptions-that-exclude-nothing`
- **Landed:** 2026-08-30

### The grandfather list is empty

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `exemptions-that-exclude-nothing`
- **Landed:** 2026-08-30

### The deep dive's gate counts match the evaluator

- **Scenario id:** `FDG-1`
- **Intent:** `INT-1`
- **Source issue:** `facts-drift-guard`
- **Landed:** 2026-09-25

### The immovable list and never_skip match the policy, and verify.claims is not called immovable

- **Scenario id:** `FDG-2`
- **Intent:** `INT-1`
- **Source issue:** `facts-drift-guard`
- **Landed:** 2026-09-25

### The contract's document home matches the CLI's naming rule

- **Scenario id:** `FDG-3`
- **Intent:** `INT-1`
- **Source issue:** `facts-drift-guard`
- **Landed:** 2026-09-25

### The derived-spec header names the real command and input

- **Scenario id:** `FDG-4`
- **Intent:** `INT-1`
- **Source issue:** `facts-drift-guard`
- **Landed:** 2026-09-25

### Every registered claim is found exactly once

- **Scenario id:** `FDG-5`
- **Intent:** `INT-1`
- **Source issue:** `facts-drift-guard`
- **Landed:** 2026-09-25

### Given commands/define.md and skills/bdd-specification/SKILL.md, then each asks the author which input classes and failure modes the brief implies that no scenario covers, says each answer becomes a scenario or a recorded de-scope, and gives two worked examples.

- **Scenario id:** `FM-A`
- **Intent:** `INT-1`
- **Source issue:** `failure-modes-in-define`
- **Landed:** 2026-10-02

### Given compass scenario descope "<mode>" --reason "<why>", then it appends the mode, the reason and the date to the manifest's failure_modes_descoped, and the manifest still passes compass issue lint. It refuses an empty mode or reason, and a mode already recorded.

- **Scenario id:** `FM-B`
- **Intent:** `INT-1`
- **Source issue:** `failure-modes-in-define`
- **Landed:** 2026-10-02

### Given an issue with de-scoped failure modes, then agents/verifier.md tells the verifier to list each in the verification report, and templates/verification-report.md has a section for them.

- **Scenario id:** `FM-C`
- **Intent:** `INT-1`
- **Source issue:** `failure-modes-in-define`
- **Landed:** 2026-10-02

### Given the verb surface, then scenario descope is in verb_help.py, the README's CLI block and compass scenario --help. The top-level verb set does not change.

- **Scenario id:** `FM-D`
- **Intent:** `INT-1`
- **Source issue:** `failure-modes-in-define`
- **Landed:** 2026-10-02

### Given pytest-xdist is installed, when make test runs, then the suite runs on parallel workers. Given it is not installed, then make test runs the suite in series, as before.

- **Scenario id:** `FS-A`
- **Intent:** `INT-1`
- **Source issue:** `faster-suite-and-release`
- **Landed:** 2026-10-02

### Given the local issue archive, when the suite is collected, then the two archive sweeps in test_phase2_invariants.py and test_record_keeping_integrity.py are one test per issue, each named after its issue. Given no archive, then they skip as before.

- **Scenario id:** `FS-B`
- **Intent:** `INT-1`
- **Source issue:** `faster-suite-and-release`
- **Landed:** 2026-10-02

### Given compass ci --since <ref>, then it lints every manifest, fully checks every issue in flight and every issue landed after <ref>, and reports the rest as lint-only. Given no --since, then compass ci checks exactly what it checked before.

- **Scenario id:** `FS-C`
- **Intent:** `INT-1`
- **Source issue:** `faster-suite-and-release`
- **Landed:** 2026-10-02

### Given make ci in this repository, then it runs compass ci --since the latest release tag. Given COMPASS_FULL_ARCHIVE=1, then make ci checks every issue.

- **Scenario id:** `FS-D`
- **Intent:** `INT-1`
- **Source issue:** `faster-suite-and-release`
- **Landed:** 2026-10-02

### Given pytest-xdist is installed, when scripts/release.sh runs its test step, then it runs the suite on parallel workers. Given it is not installed, then it runs in series, as before.

- **Scenario id:** `FS-E`
- **Intent:** `INT-1`
- **Source issue:** `faster-suite-and-release`
- **Landed:** 2026-10-02

### Given the CI self-check job, then it installs pytest-xdist and runs the suite on parallel workers.

- **Scenario id:** `FS-F`
- **Intent:** `INT-1`
- **Source issue:** `faster-suite-and-release`
- **Landed:** 2026-10-02

### Given docs/releasing.md, then it says how to install pytest-xdist, and names COMPASS_FULL_ARCHIVE=1 as the full-archive check to run before a release.

- **Scenario id:** `FS-G`
- **Intent:** `INT-1`
- **Source issue:** `faster-suite-and-release`
- **Landed:** 2026-10-02

### A feature assessment earns and registers the map

- **Scenario id:** `FRM-1`
- **Intent:** `INT-1`
- **Source issue:** `feature-route-omits-the-map`
- **Landed:** 2026-09-27

### Every multiagent route earns the map

- **Scenario id:** `FRM-2`
- **Intent:** `INT-1`
- **Source issue:** `feature-route-omits-the-map`
- **Landed:** 2026-09-27

### TRC-A1

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `field-feedback-2026-07`
- **Landed:** 2026-07-27

### TRC-A2

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `field-feedback-2026-07`
- **Landed:** 2026-07-27

### TRC-A3

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `field-feedback-2026-07`
- **Landed:** 2026-07-27

### TRC-F2

- **Scenario id:** `TRC-F2`
- **Intent:** `INT-1`
- **Source issue:** `field-feedback-2026-07`
- **Landed:** 2026-07-27

### Given a fix that creates a file whose name has a space, a quote or a n

- **Scenario id:** `FSE-1`
- **Intent:** `INT-1`
- **Source issue:** `finish-and-ship-commit-edges`
- **Landed:** 2026-09-29

### Given a quick fix started with a local file present, when it lands, th

- **Scenario id:** `FSE-2`
- **Intent:** `INT-1`
- **Source issue:** `finish-and-ship-commit-edges`
- **Landed:** 2026-09-29

### Given a successful `finish`, when it prints its hand-off, then the fil

- **Scenario id:** `FSE-3`
- **Intent:** `INT-1`
- **Source issue:** `finish-and-ship-commit-edges`
- **Landed:** 2026-09-29

### the safety contract states the three limits

- **Scenario id:** `FSE-4`
- **Intent:** `INT-1`
- **Source issue:** `finish-and-ship-commit-edges`
- **Landed:** 2026-09-29

### Given an untracked file present before `quick-fix start` that nobody t

- **Scenario id:** `FUU-1`
- **Intent:** `INT-1`
- **Source issue:** `finish-commits-unrelated-untracked-files`
- **Landed:** 2026-09-29

### Given a tracked file already modified before `quick-fix start` that no

- **Scenario id:** `FUU-2`
- **Intent:** `INT-1`
- **Source issue:** `finish-commits-unrelated-untracked-files`
- **Landed:** 2026-09-29

### Given a file present before `start` that the agent then traced with `c

- **Scenario id:** `FUU-3`
- **Intent:** `INT-1`
- **Source issue:** `finish-commits-unrelated-untracked-files`
- **Landed:** 2026-09-29

### Given an issue with no record of its start state, when `finish` runs w

- **Scenario id:** `FUU-5`
- **Intent:** `INT-1`
- **Source issue:** `finish-commits-unrelated-untracked-files`
- **Landed:** 2026-09-29

### Given a quick fix that recorded an acceptance of kind refactor and no red, When quick-fix finish runs, Then it records the green, passes the three gates and finishes

- **Scenario id:** `FA-1`
- **Intent:** `INT-1`
- **Source issue:** `finish-honours-acceptance`
- **Landed:** 2026-10-05

### Given a quick fix with two scenarios, each with a red on record, when quick-fix finish runs, then the test command runs once and each scenario gets its own green record

- **Scenario id:** `TRC-001`
- **Intent:** `INT-1`
- **Source issue:** `finish-runs-the-suite-once`
- **Landed:** 2026-10-06

### Given a committed living spec that names an issue whose records are missing, when quick-fix finish lands a fix, then its output says the living spec was not re-derived and names compass issue refresh-spec

- **Scenario id:** `TRC-001`
- **Intent:** `INT-1`
- **Source issue:** `finish-shows-a-failed-derive`
- **Landed:** 2026-10-06

### Given a quick fix that changes a tracked file under .compass, such as the project config, then finish traces and commits it with one run, while untracked issue state under .compass stays out.

- **Scenario id:** `FT-1`
- **Intent:** `INT-1`
- **Source issue:** `finish-traces-compass-files`
- **Landed:** 2026-10-03

### scenarios-have-tests flags a narrative scenario as FAIL on the current code (baseline)

- **Scenario id:** `TRC-R1-1`
- **Intent:** `INT-1`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### A documented narrative scenario with no test clears the check

- **Scenario id:** `TRC-R1-2`
- **Intent:** `INT-1`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### A non-narrative scenario with no test still fails scenarios-have-tests

- **Scenario id:** `TRC-R1-3`
- **Intent:** `INT-1`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### A narrative scenario with an empty When/Then body still fails (documented, not anything-goes)

- **Scenario id:** `TRC-R1-4`
- **Intent:** `INT-1`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### A narrative scenario carrying an incidental command is assessed on documentation, not the command

- **Scenario id:** `TRC-R1-5`
- **Intent:** `INT-1`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### the strategy states the trigger, the staffing rule, and the method

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `fresh-eyes-verify-sweeps`
- **Landed:** 2026-08-11

### the strategy states the prohibition, the evidence, and carries the file's own conventions

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `fresh-eyes-verify-sweeps`
- **Landed:** 2026-08-11

### the verify stage guidance points at the strategy without repeating it

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-1`
- **Source issue:** `fresh-eyes-verify-sweeps`
- **Landed:** 2026-08-11

### no new mechanism is introduced

- **Scenario id:** `TRC-F1`
- **Intent:** `INT-1`
- **Source issue:** `fresh-eyes-verify-sweeps`
- **Landed:** 2026-08-11

### an optional friction block validates against the task schema

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `friction-loop`
- **Landed:** 2026-06-04

### Land derives a friction entry from a recorded reframe

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `friction-loop`
- **Landed:** 2026-06-04

### Land derives a friction entry from absorbed reframe-debt

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `friction-loop`
- **Landed:** 2026-06-04

### the author's optional answer is recorded as a human-sourced entry

- **Scenario id:** `TRC-A4`
- **Intent:** `INT-1`
- **Source issue:** `friction-loop`
- **Landed:** 2026-06-04

### Given an issue whose friction entry names a current stage such as implement, When compass issue lint runs with jsonschema installed, Then it passes; and Compass writes and loads friction phases in the current stage names, mapping a retired name such as frame to assess

- **Scenario id:** `FP-1`
- **Intent:** `INT-1`
- **Source issue:** `friction-phase-takes-v2-stages`
- **Landed:** 2026-10-04

### a critical-blast-radius task requires a human approval

- **Scenario id:** `SCN-A1`
- **Intent:** `INT-1`
- **Source issue:** `g5-trigger-matches-statement`
- **Landed:** 2026-08-13

### a critical task with a recorded approval clears G5

- **Scenario id:** `SCN-A2`
- **Intent:** `INT-1`
- **Source issue:** `g5-trigger-matches-statement`
- **Landed:** 2026-08-13

### any_of matches when one clause matches

- **Scenario id:** `SCN-B1`
- **Intent:** `INT-1`
- **Source issue:** `g5-trigger-matches-statement`
- **Landed:** 2026-08-13

### any_of fails when no clause matches

- **Scenario id:** `SCN-B2`
- **Intent:** `INT-1`
- **Source issue:** `g5-trigger-matches-statement`
- **Landed:** 2026-08-13

### effective_for reads live with no generation, refuses generation 0, resolves live with no issue

- **Scenario id:** `GS-1`
- **Intent:** `INT-1`
- **Source issue:** `generation-store`
- **Landed:** 2026-10-07

### The manifest schema and template accept generation and config

- **Scenario id:** `GS-10`
- **Intent:** `INT-1`
- **Source issue:** `generation-store`
- **Landed:** 2026-10-07

### approach evaluate --write commits generation 1, says no change on a repeat, commits 2 on a change

- **Scenario id:** `GS-11`
- **Intent:** `INT-1`
- **Source issue:** `generation-store`
- **Landed:** 2026-10-07

### compass check writes results.yml for an issue with a generation and refuses a broken one

- **Scenario id:** `GS-12`
- **Intent:** `INT-1`
- **Source issue:** `generation-store`
- **Landed:** 2026-10-07

### compass ci reports generation states and fails on a broken one

- **Scenario id:** `GS-13`
- **Intent:** `INT-1`
- **Source issue:** `generation-store`
- **Landed:** 2026-10-07

### Only effective imports generation and the reader modules import no resolver module

- **Scenario id:** `GS-14`
- **Intent:** `INT-1`
- **Source issue:** `generation-store`
- **Landed:** 2026-10-07

### An issue with no generation gets no generation files and the compatibility contracts pass

- **Scenario id:** `GS-15`
- **Intent:** `INT-1`
- **Source issue:** `generation-store`
- **Landed:** 2026-10-07

### The bench script, DEPENDENCY headers, owning-doc row and core.py line cap hold

- **Scenario id:** `GS-16`
- **Intent:** `INT-1`
- **Source issue:** `generation-store`
- **Landed:** 2026-10-07

### A commit refuses a symbolic link, a landed issue and a rejected compass.yml, and its messages name only commands that exist

- **Scenario id:** `GS-17`
- **Intent:** `INT-1`
- **Source issue:** `generation-store`
- **Landed:** 2026-10-07

### The command writes the manifest atomically and every file keeps the previous mode or the umask

- **Scenario id:** `GS-18`
- **Intent:** `INT-1`
- **Source issue:** `generation-store`
- **Landed:** 2026-10-07

### A rejected compass.yml during quick-fix start leaves no issue folder behind

- **Scenario id:** `GS-19`
- **Intent:** `INT-1`
- **Source issue:** `generation-store`
- **Landed:** 2026-10-07

### A generation holds the four files and the complete marker with the contents ADR-036 names

- **Scenario id:** `GS-2`
- **Intent:** `INT-1`
- **Source issue:** `generation-store`
- **Landed:** 2026-10-07

### Folder states, verdict merging and overwrite rules hold on the edge cases

- **Scenario id:** `GS-20`
- **Intent:** `INT-1`
- **Source issue:** `generation-store`
- **Landed:** 2026-10-07

### Only classify and effective import obligations, on any import form

- **Scenario id:** `GS-21`
- **Intent:** `INT-1`
- **Source issue:** `generation-store`
- **Landed:** 2026-10-07

### EffectiveView.evaluator_policy returns the evaluator's policy from the resolved configuration

- **Scenario id:** `GS-22`
- **Intent:** `INT-1`
- **Source issue:** `generation-store`
- **Landed:** 2026-10-07

### A commit writes the files, then the marker, then the manifest, under an exclusive lock

- **Scenario id:** `GS-3`
- **Intent:** `INT-1`
- **Source issue:** `generation-store`
- **Landed:** 2026-10-07

### An interrupted commit leaves the manifest on generation n and a named leftover state

- **Scenario id:** `GS-4`
- **Intent:** `INT-1`
- **Source issue:** `generation-store`
- **Landed:** 2026-10-07

### A commit equal to generation n commits nothing and says no change

- **Scenario id:** `GS-5`
- **Intent:** `INT-1`
- **Source issue:** `generation-store`
- **Landed:** 2026-10-07

### A commit refuses a complete-unreferenced target, overwrites an incomplete one, keeps proposed.yml

- **Scenario id:** `GS-6`
- **Intent:** `INT-1`
- **Source issue:** `generation-store`
- **Landed:** 2026-10-07

### Every file the store writes is written atomically and leaves no temporary file

- **Scenario id:** `GS-7`
- **Intent:** `INT-1`
- **Source issue:** `generation-store`
- **Landed:** 2026-10-07

### effective_for returns the stored generation after the project file changes, and refuses a broken one

- **Scenario id:** `GS-8`
- **Intent:** `INT-1`
- **Source issue:** `generation-store`
- **Landed:** 2026-10-07

### Generation directories are classified as current, superseded, proposal, incomplete, complete-unreferenced or broken

- **Scenario id:** `GS-9`
- **Intent:** `INT-1`
- **Source issue:** `generation-store`
- **Landed:** 2026-10-07

### Given a heavier route started by /compass:go, then go and assess agree that the approach summary already shown is the confirmation, and go does not stop at assess step 7 to wait for one.

- **Scenario id:** `GC-1`
- **Intent:** `INT-1`
- **Source issue:** `go-confirms-on-the-heavier-route`
- **Landed:** 2026-10-03

### the shipped governance should declare a version that has moved

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `governance-drift-detection`
- **Landed:** 

### changing governance content without bumping its version should fail

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `governance-drift-detection`
- **Landed:** 

### a project behind the framework's governance version should be told

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `governance-drift-detection`
- **Landed:** 

### missing floors and strategies should be named individually

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-1`
- **Source issue:** `governance-drift-detection`
- **Landed:** 

### missing guardrail checks should be named individually

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-1`
- **Source issue:** `governance-drift-detection`
- **Landed:** 

### Given a compass.yml with schema: 1 and governance_drift: strict, When the project layer is checked and loaded, Then it is accepted and governance_drift is read as a setting, not a layer key

- **Scenario id:** `TRC-001`
- **Intent:** `INT-1`
- **Source issue:** `governance-drift-is-a-settings-key`
- **Landed:** 2026-10-07

### Given a green record edited after it was written, its stored digest le

- **Scenario id:** `GDH-1`
- **Intent:** `INT-1`
- **Source issue:** `green-digest-and-hook-scope`
- **Landed:** 2026-09-29

### Given a git pre-commit hook that stages a file outside the issue's sco

- **Scenario id:** `GDH-2`
- **Intent:** `INT-1`
- **Source issue:** `green-digest-and-hook-scope`
- **Landed:** 2026-09-29

### Given a tracked file that matches `.gitignore`, traced by an issue and

- **Scenario id:** `GDH-3`
- **Intent:** `INT-1`
- **Source issue:** `green-digest-and-hook-scope`
- **Landed:** 2026-09-29

### Given the safety contract and the post-commit refusal, then the contra

- **Scenario id:** `GDH-4`
- **Intent:** `INT-1`
- **Source issue:** `green-digest-and-hook-scope`
- **Landed:** 2026-09-29

### Given a script that sets pipefail, then it never pipes into grep -q, because a grep that exits at its first match can fail the pipe and turn a found line into a missing one.

- **Scenario id:** `GQ-1`
- **Intent:** `INT-1`
- **Source issue:** `grep-q-under-pipefail`
- **Landed:** 2026-10-03

### Given an eval run, then every session runs without writing bytecode, a compass run as root is refused unless its plugin copy is on a read-only mount or --allow-root is given, each record names the uid, Python version and whether it ran as root, and the comparison report states those and how many runs were not contained.

- **Scenario id:** `HC-1`
- **Intent:** `INT-1`
- **Source issue:** `harness-containment-under-root`
- **Landed:** 2026-10-04

### Given a session that planted a folder where a hidden test is copied, When the run finishes, Then the record says not contained and names the path, instead of the run ending with an error

- **Scenario id:** `PSW-1`
- **Intent:** `INT-1`
- **Source issue:** `harness-post-session-walks`
- **Landed:** 2026-10-05

### Given a session that replaced .compass with a link, when the run lists its compass files, then it lists nothing and never walks the link

- **Scenario id:** `PSW-2`
- **Intent:** `INT-1`
- **Source issue:** `harness-post-session-walks`
- **Landed:** 2026-10-05

### Given the harness running as root on Linux, When it prepares its plugin copy, Then it bind-mounts the copy read-only before any session, records that it did, removes the mount at the end, and falls back to the refusal when the mount fails

- **Scenario id:** `RM-1`
- **Intent:** `INT-1`
- **Source issue:** `harness-read-only-bind-mount`
- **Landed:** 2026-10-06

### Given the harness runs as root with --session-user naming an unprivileged user, then each session runs as that user, owns its working folder, cannot write the plugin copy or the checkout, and the record states its uid.

- **Scenario id:** `HR-A`
- **Intent:** `INT-1`
- **Source issue:** `harness-root-sanctioned-path`
- **Landed:** 2026-10-05

### Given a root run with Compass installed and no sanctioned path, then it is refused before any session, naming --session-user and a read-only mount first and --allow-root last.

- **Scenario id:** `HR-B`
- **Intent:** `INT-1`
- **Source issue:** `harness-root-sanctioned-path`
- **Landed:** 2026-10-05

### Given --allow-root where CI or COMPASS_UNATTENDED is set, then the run is refused before any session.

- **Scenario id:** `HR-C`
- **Intent:** `INT-1`
- **Source issue:** `harness-root-sanctioned-path`
- **Landed:** 2026-10-05

### Given --session-user naming root or an unknown user, then the run is refused before any session and names the problem.

- **Scenario id:** `HR-D`
- **Intent:** `INT-1`
- **Source issue:** `harness-root-sanctioned-path`
- **Landed:** 2026-10-05

### Given --session-user while the harness is not root, then the run is refused.

- **Scenario id:** `HR-E`
- **Intent:** `INT-1`
- **Source issue:** `harness-root-sanctioned-path`
- **Landed:** 2026-10-05

### Given a run that is not as root and has no --session-user, then sessions start as before and session_uid equals the harness's uid.

- **Scenario id:** `HR-F`
- **Intent:** `INT-1`
- **Source issue:** `harness-root-sanctioned-path`
- **Landed:** 2026-10-05

### Given a root run with a session user, then git and the test command in the session's folder run as that user, so code the session wrote never runs as root.

- **Scenario id:** `HR-G`
- **Intent:** `INT-1`
- **Source issue:** `harness-root-sanctioned-path`
- **Landed:** 2026-10-05

### Given a session that replaced a file in its folder with a link outside it, then the harness's own reads and writes there do not follow the link.

- **Scenario id:** `HR-H`
- **Intent:** `INT-1`
- **Source issue:** `harness-root-sanctioned-path`
- **Landed:** 2026-10-05

### Given a session that left a process running, then the harness ends the session user's processes before it touches the folder again.

- **Scenario id:** `HR-I`
- **Intent:** `INT-1`
- **Source issue:** `harness-root-sanctioned-path`
- **Landed:** 2026-10-05

### Given a real root run with a real unprivileged session user, then the run is contained and the session's edit is in the diff.

- **Scenario id:** `HR-J`
- **Intent:** `INT-1`
- **Source issue:** `harness-root-sanctioned-path`
- **Landed:** 2026-10-05

### Given a session that leaves a process holding its output open, when the call ends, then the harness ends it and records the run as not contained

- **Scenario id:** `SUH-1`
- **Intent:** `INT-1`
- **Source issue:** `harness-session-user-hardening`
- **Landed:** 2026-10-05

### Given a session user with running processes or a link in its watched Claude configuration, when a run starts, then it is refused naming what was found

- **Scenario id:** `SUH-2`
- **Intent:** `INT-1`
- **Source issue:** `harness-session-user-hardening`
- **Landed:** 2026-10-05

### Given a session user with a crontab or a queued at job, when the harness checks it, then the run is refused naming which

- **Scenario id:** `SUH-3`
- **Intent:** `INT-1`
- **Source issue:** `harness-session-user-hardening`
- **Landed:** 2026-10-05

### Given a run that changed the contents, permissions or type of the session user's watched Claude configuration, when the record is written, then it lists the changed paths

- **Scenario id:** `SUH-4`
- **Intent:** `INT-1`
- **Source issue:** `harness-session-user-hardening`
- **Landed:** 2026-10-05

### Given any run with a session user, when it ends, then the harness has modified nothing in the session user's home

- **Scenario id:** `SUH-5`
- **Intent:** `INT-1`
- **Source issue:** `harness-session-user-hardening`
- **Landed:** 2026-10-05

### Given the three places that start a process as the session user, when their arguments are built, then they come from one helper

- **Scenario id:** `SUH-6`
- **Intent:** `INT-1`
- **Source issue:** `harness-session-user-hardening`
- **Landed:** 2026-10-05

### Given the CI demo workflow exists and has run, then the headless-runner doc does not say the live acceptance is unmet, and says what the demo covers and that each run costs money.

- **Scenario id:** `HD-1`
- **Intent:** `INT-1`
- **Source issue:** `headless-doc-after-the-demo`
- **Landed:** 2026-10-03

### Given a project, then compass run exits 2 and starts no session when the project has no .compass, the issue does not exist, the stage is not build or verify, no stop file is given, claude cannot be found, or a ceiling flag is out of range or above its policy ceiling.

- **Scenario id:** `HR-A`
- **Intent:** `INT-1`
- **Source issue:** `headless-runner`
- **Landed:** 2026-10-03

### Given sessions that change the records but never finish the stage, when the run reaches its cycle ceiling, then it exits 4, records a stopped run with a stop reason naming the ceiling and the run record, and the issue is not landed.

- **Scenario id:** `HR-B`
- **Intent:** `INT-1`
- **Source issue:** `headless-runner`
- **Landed:** 2026-10-03

### Given a stop file, present at the start or appearing during the run, then the runner starts no further session and exits 4 with the stop file as the reason.

- **Scenario id:** `HR-C`
- **Intent:** `INT-1`
- **Source issue:** `headless-runner`
- **Landed:** 2026-10-03

### Given a run whose stage is done, every gate passing for verify or every scenario green for build, then it exits 0 with the outcome done, and a session that lands the issue stops the run.

- **Scenario id:** `HR-D`
- **Intent:** `INT-1`
- **Source issue:** `headless-runner`
- **Landed:** 2026-10-03

### Given a session whose error output carries a credential, then the run record, the manifest and the printed output hold the text with the credential redacted.

- **Scenario id:** `HR-E`
- **Intent:** `INT-1`
- **Source issue:** `headless-runner`
- **Landed:** 2026-10-03

### Given any run, then each cycle starts a new claude -p session that resumes nothing, loads the Compass plugin, names the stage's command, says it is unattended, and forbids landing, pushing and merging.

- **Scenario id:** `HR-F`
- **Intent:** `INT-1`
- **Source issue:** `headless-runner`
- **Landed:** 2026-10-03

### Given sessions that change nothing on disk, then the run stops after the repeated-error ceiling's number of cycles without progress, and a manifest it cannot read stops it too.

- **Scenario id:** `HR-G`
- **Intent:** `INT-1`
- **Source issue:** `headless-runner`
- **Landed:** 2026-10-03

### Given a run that passes its minute ceiling during a session, then the session is ended and the run stops with the minute ceiling as the reason.

- **Scenario id:** `HR-H`
- **Intent:** `INT-1`
- **Source issue:** `headless-runner`
- **Landed:** 2026-10-03

### Given the eval harness, then it starts claude through the same launcher function compass run uses.

- **Scenario id:** `HR-I`
- **Intent:** `INT-1`
- **Source issue:** `headless-runner`
- **Landed:** 2026-10-03

### Given the change, then a decision record states the exception to the rule that Compass launches nothing, as proposed; a reference workflow runs only when started by hand; and the owning doc says the live CI acceptance is not met.

- **Scenario id:** `HR-J`
- **Intent:** `INT-1`
- **Source issue:** `headless-runner`
- **Landed:** 2026-10-03

### a validation acceptance permits the edit

- **Scenario id:** `SCN-A1`
- **Intent:** `INT-1`
- **Source issue:** `honest-acceptance-for-config-and-refactor`
- **Landed:** 2026-08-13

### a validation acceptance records the validator's output

- **Scenario id:** `SCN-B1`
- **Intent:** `INT-1`
- **Source issue:** `honest-acceptance-for-config-and-refactor`
- **Landed:** 2026-08-13

### a refactor that preserved behaviour is recorded

- **Scenario id:** `SCN-B5`
- **Intent:** `INT-1`
- **Source issue:** `honest-acceptance-for-config-and-refactor`
- **Landed:** 2026-08-13

### the recorded evidence satisfies the existing checks

- **Scenario id:** `SCN-F1`
- **Intent:** `INT-1`
- **Source issue:** `honest-acceptance-for-config-and-refactor`
- **Landed:** 2026-08-13

### the anti-pattern is named where authors will meet it

- **Scenario id:** `SCN-F2`
- **Intent:** `INT-1`
- **Source issue:** `honest-acceptance-for-config-and-refactor`
- **Landed:** 2026-08-13

### a redirect into a source file is blocked with no red on record

- **Scenario id:** `SCN-A1`
- **Intent:** `INT-1`
- **Source issue:** `hook-bash-write-bypass`
- **Landed:** 2026-08-13

### an in-place edit of a source file is blocked

- **Scenario id:** `SCN-A2`
- **Intent:** `INT-1`
- **Source issue:** `hook-bash-write-bypass`
- **Landed:** 2026-08-13

### an inline interpreter script that writes a source file is blocked

- **Scenario id:** `SCN-A3`
- **Intent:** `INT-1`
- **Source issue:** `hook-bash-write-bypass`
- **Landed:** 2026-08-13

### the same command is allowed once a red is on record

- **Scenario id:** `SCN-A4`
- **Intent:** `INT-1`
- **Source issue:** `hook-bash-write-bypass`
- **Landed:** 2026-08-13

### a path exempt for Edit is exempt for Bash

- **Scenario id:** `SCN-C1`
- **Intent:** `INT-1`
- **Source issue:** `hook-bash-write-bypass`
- **Landed:** 2026-08-13

### the Spike route suspends the check for Bash too

- **Scenario id:** `SCN-C2`
- **Intent:** `INT-1`
- **Source issue:** `hook-bash-write-bypass`
- **Landed:** 2026-08-13

### a full Specify with no scenarios blocks a code edit

- **Scenario id:** `SCN-A1`
- **Intent:** `INT-1`
- **Source issue:** `hook-enforces-g2`
- **Landed:** 2026-08-13

### scenarios present allow the edit

- **Scenario id:** `SCN-A2`
- **Intent:** `INT-1`
- **Source issue:** `hook-enforces-g2`
- **Landed:** 2026-08-13

### the message names the guardrail and the remedy

- **Scenario id:** `SCN-B1`
- **Intent:** `INT-1`
- **Source issue:** `hook-enforces-g2`
- **Landed:** 2026-08-13

### the hook blocks an edit it cannot check

- **Scenario id:** `TRC-1`
- **Intent:** `INT-1`
- **Source issue:** `hook-fails-open-on-broken-vendor`
- **Landed:** 

### control: the hook still blocks when it can read the spine

- **Scenario id:** `TRC-3`
- **Intent:** `INT-1`
- **Source issue:** `hook-fails-open-on-broken-vendor`
- **Landed:** 

### the guarded-surface decision fails closed too

- **Scenario id:** `TRC-4`
- **Intent:** `INT-1`
- **Source issue:** `hook-fails-open-on-broken-vendor`
- **Landed:** 

### Every reader that cannot run refuses and names itself

- **Scenario id:** `HFM-1`
- **Intent:** `INT-1`
- **Source issue:** `hook-failure-matrix`
- **Landed:** 2026-09-24

### With no python3 the refusal says so

- **Scenario id:** `HFM-2`
- **Intent:** `INT-1`
- **Source issue:** `hook-failure-matrix`
- **Landed:** 2026-09-24

### A missing approach record is still reported as missing

- **Scenario id:** `HFM-4`
- **Intent:** `INT-1`
- **Source issue:** `hook-failure-matrix`
- **Landed:** 2026-09-24

### a read-only open is allowed

- **Scenario id:** `SCN-A1`
- **Intent:** `INT-1`
- **Source issue:** `hotfix-1-8-1-false-blocks-and-land-scope`
- **Landed:** 2026-08-13

### a path named inside written prose is not the write target

- **Scenario id:** `SCN-A2`
- **Intent:** `INT-1`
- **Source issue:** `hotfix-1-8-1-false-blocks-and-land-scope`
- **Landed:** 2026-08-13

### every before/after pair should be a real passage from the work archive

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `human-voice`
- **Landed:** 2026-08-09

### the tells list should name all nine tells and say which a string can find

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `human-voice`
- **Landed:** 2026-08-09

### no rewritten passage should still carry a tell

- **Scenario id:** `TRC-A4`
- **Intent:** `INT-1`
- **Source issue:** `human-voice`
- **Landed:** 2026-08-09

### the root instruction files should carry a short voice paragraph

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-1`
- **Source issue:** `human-voice`
- **Landed:** 2026-08-09

### the three talkiest stages should each point at the reference

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-1`
- **Source issue:** `human-voice`
- **Landed:** 2026-08-09

### a real requirements review from the archive should become the canonical worked example

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-1`
- **Source issue:** `human-voice`
- **Landed:** 2026-08-09

### the original should stay readable beside the rewrite

- **Scenario id:** `TRC-C2`
- **Intent:** `INT-1`
- **Source issue:** `human-voice`
- **Landed:** 2026-08-09

### the requirements-review template should show a decision recorded in a human voice

- **Scenario id:** `TRC-C3`
- **Intent:** `INT-1`
- **Source issue:** `human-voice`
- **Landed:** 2026-08-09

### the clarity dimension should name the tells as judgement, not as a rule

- **Scenario id:** `TRC-D1`
- **Intent:** `INT-1`
- **Source issue:** `human-voice`
- **Landed:** 2026-08-09

### the tell check should name the file and line of each hit

- **Scenario id:** `TRC-D2`
- **Intent:** `INT-1`
- **Source issue:** `human-voice`
- **Landed:** 2026-08-09

### a clean set of artifacts should get a stated result, not silence

- **Scenario id:** `TRC-D3`
- **Intent:** `INT-1`
- **Source issue:** `human-voice`
- **Landed:** 2026-08-09

### the exhibits should not be read as defects

- **Scenario id:** `TRC-F2`
- **Intent:** `INT-1`
- **Source issue:** `human-voice`
- **Landed:** 2026-08-09

### every file this issue writes should clear house style and the frozen vocabulary

- **Scenario id:** `TRC-F4`
- **Intent:** `INT-1`
- **Source issue:** `human-voice`
- **Landed:** 2026-08-09

### A major difference refuses only that check

- **Scenario id:** `IR-1`
- **Intent:** `INT-1`
- **Source issue:** `impl-refusal`
- **Landed:** 2026-10-08

### migrate-config commits nothing when already pinned

- **Scenario id:** `IR-10`
- **Intent:** `INT-1`
- **Source issue:** `impl-refusal`
- **Landed:** 2026-10-08

### migrate-config adopts an issue with no generation

- **Scenario id:** `IR-11`
- **Intent:** `INT-1`
- **Source issue:** `impl-refusal`
- **Landed:** 2026-10-08

### The coverage page is derived and kept current

- **Scenario id:** `IR-12`
- **Intent:** `INT-1`
- **Source issue:** `impl-refusal`
- **Landed:** 2026-10-08

### The refusal names what to do

- **Scenario id:** `IR-2`
- **Intent:** `INT-1`
- **Source issue:** `impl-refusal`
- **Landed:** 2026-10-08

### A minor or patch difference is not refused

- **Scenario id:** `IR-3`
- **Intent:** `INT-1`
- **Source issue:** `impl-refusal`
- **Landed:** 2026-10-08

### A resolver or schema major difference refuses the run

- **Scenario id:** `IR-4`
- **Intent:** `INT-1`
- **Source issue:** `impl-refusal`
- **Landed:** 2026-10-08

### A refused check is reported as refused and records no result

- **Scenario id:** `IR-5`
- **Intent:** `INT-1`
- **Source issue:** `impl-refusal`
- **Landed:** 2026-10-08

### A verdict change without a major bump fails the build

- **Scenario id:** `IR-6`
- **Intent:** `INT-1`
- **Source issue:** `impl-refusal`
- **Landed:** 2026-10-08

### The lock file holds a version and a verdict digest per implementation

- **Scenario id:** `IR-7`
- **Intent:** `INT-1`
- **Source issue:** `impl-refusal`
- **Landed:** 2026-10-08

### migrate-config pins the installed versions and invalidates old results

- **Scenario id:** `IR-8`
- **Intent:** `INT-1`
- **Source issue:** `impl-refusal`
- **Landed:** 2026-10-08

### migrate-config refuses a landed issue

- **Scenario id:** `IR-9`
- **Intent:** `INT-1`
- **Source issue:** `impl-refusal`
- **Landed:** 2026-10-08

### a local file becomes intent.md

- **Scenario id:** `ING-A1`
- **Intent:** `INT-1`
- **Source issue:** `ingest-an-existing-brief`
- **Landed:** 2026-08-25

### the source may be called anything

- **Scenario id:** `ING-A2`
- **Intent:** `INT-1`
- **Source issue:** `ingest-an-existing-brief`
- **Landed:** 2026-08-25

### a URL becomes intent.md

- **Scenario id:** `ING-A3`
- **Intent:** `INT-1`
- **Source issue:** `ingest-an-existing-brief`
- **Landed:** 2026-08-25

### a source that is not there fails before anything is written

- **Scenario id:** `ING-A4`
- **Intent:** `INT-1`
- **Source issue:** `ingest-an-existing-brief`
- **Landed:** 2026-08-25

### a quick fix reads what a quick fix needs

- **Scenario id:** `IV-A2`
- **Intent:** `INT-1`
- **Source issue:** `instruction-volume`
- **Landed:** 2026-08-27

### strategies is not in the per-issue read

- **Scenario id:** `IV-B1`
- **Intent:** `INT-1`
- **Source issue:** `instruction-volume`
- **Landed:** 2026-08-27

### Given an issue's scenarios and its red and green records, then the page has one table row per scenario with its title, a red mark, a green mark and its evidence path, using ✓ and ○.

- **Scenario id:** `IO-A`
- **Intent:** `INT-1`
- **Source issue:** `issue-overview`
- **Landed:** 2026-10-03

### Given the same issue, then the page has a Mermaid flowchart from each intent to its scenarios, tests and evidence, and a scenario with a red but no green is styled as open.

- **Scenario id:** `IO-B`
- **Intent:** `INT-1`
- **Source issue:** `issue-overview`
- **Landed:** 2026-10-03

### Given more than 25 scenarios, then the flowchart shows a summary node instead of every scenario, and the table still lists them all.

- **Scenario id:** `IO-C`
- **Intent:** `INT-1`
- **Source issue:** `issue-overview`
- **Landed:** 2026-10-03

### Given a green recorded after the page was written, then compass check fails the page as stale and names compass issue dashboard as the fix.

- **Scenario id:** `IO-D`
- **Intent:** `INT-1`
- **Source issue:** `issue-overview`
- **Landed:** 2026-10-03

### Given the status line, then it names the gates passed out of the gates required.

- **Scenario id:** `IO-E`
- **Intent:** `INT-1`
- **Source issue:** `issue-overview`
- **Landed:** 2026-10-03

### Given a session that ran compass quick-fix start before its first code edit, when the rule judge scores it, then it passes

- **Scenario id:** `JSQ-1`
- **Intent:** `INT-1`
- **Source issue:** `judge-sees-quick-fix-start`
- **Landed:** 2026-09-29

### Given a technical spec written to docs/specs/ When git status runs Then the file is ignored and git ls-files lists nothing under docs/specs/

- **Scenario id:** `TRC-001`
- **Intent:** `INT-1`
- **Source issue:** `keep-docs-specs-untracked`
- **Landed:** 2026-10-05

### Given the comparison run found Compass stopped to warn of a change that would break a hidden consumer, then the decisions ledger records the maintainer's decision to keep that stop at its measured cost, with its evidence.

- **Scenario id:** `KS-1`
- **Intent:** `INT-1`
- **Source issue:** `keep-the-stop-before-a-breaking-change`
- **Landed:** 2026-10-04

### Given a refusal from ship-commit or finish, when its advice is followed, then the refusal clears

- **Scenario id:** `LRA-1`
- **Intent:** `INT-1`
- **Source issue:** `land-refusal-advice`
- **Landed:** 2026-09-29

### Given a quick fix whose files changed after quick-fix start, staged or not, When acceptance start --kind validation runs, Then it refuses and names the files; declared before the change, the same work records and finishes

- **Scenario id:** `LV-1`
- **Intent:** `INT-1`
- **Source issue:** `late-validation-acceptance`
- **Landed:** 2026-10-06

### A non-text key anywhere in a layer is refused with L-KEY-NOT-TEXT naming its path and telling the person to quote it

- **Scenario id:** `TRC-001`
- **Intent:** `INT-1`
- **Source issue:** `layer-non-text-key`
- **Landed:** 2026-10-07

### A project file loads with its layer keys and settings keys split

- **Scenario id:** `LM-1`
- **Intent:** `INT-1`
- **Source issue:** `layers-and-merge`
- **Landed:** 2026-10-06

### Removing an entry something refers to names each referrer

- **Scenario id:** `LM-10`
- **Intent:** `INT-1`
- **Source issue:** `layers-and-merge`
- **Landed:** 2026-10-06

### One error reports every fault in a layer and inputs stay unchanged

- **Scenario id:** `LM-11`
- **Intent:** `INT-1`
- **Source issue:** `layers-and-merge`
- **Landed:** 2026-10-06

### A layer digest covers the layer keys only

- **Scenario id:** `LM-2`
- **Intent:** `INT-1`
- **Source issue:** `layers-and-merge`
- **Landed:** 2026-10-06

### The chain runs parent, project, issue and refuses a settings key in a parent

- **Scenario id:** `LM-3`
- **Intent:** `INT-1`
- **Source issue:** `layers-and-merge`
- **Landed:** 2026-10-06

### Entry operations add, set, replace and remove

- **Scenario id:** `LM-4`
- **Intent:** `INT-1`
- **Source issue:** `layers-and-merge`
- **Landed:** 2026-10-06

### Field operations inside set on scalars, lists and maps

- **Scenario id:** `LM-5`
- **Intent:** `INT-1`
- **Source issue:** `layers-and-merge`
- **Landed:** 2026-10-06

### Provenance names the layer and operation of every field

- **Scenario id:** `LM-6`
- **Intent:** `INT-1`
- **Source issue:** `layers-and-merge`
- **Landed:** 2026-10-06

### Bad targets and bad entries are refused by code

- **Scenario id:** `LM-7`
- **Intent:** `INT-1`
- **Source issue:** `layers-and-merge`
- **Landed:** 2026-10-06

### Misused list and map operations are refused by code

- **Scenario id:** `LM-8`
- **Intent:** `INT-1`
- **Source issue:** `layers-and-merge`
- **Landed:** 2026-10-06

### An operation or field a layer may not use is refused

- **Scenario id:** `LM-9`
- **Intent:** `INT-1`
- **Source issue:** `layers-and-merge`
- **Landed:** 2026-10-06

### Given commands/assess.md, When its size and the procedure file are checked, Then assess is at most 2,500 characters, names the procedure file for heavier routes and --reassess, and the procedure keeps every step

- **Scenario id:** `LA-1`
- **Intent:** `INT-1`
- **Source issue:** `lean-assess`
- **Landed:** 2026-10-05

### Given a ledger whose entries have very long first sentences, When quick-fix start lists the settled decisions, Then each line and the whole listing stay within their character budgets and every line still names its entry

- **Scenario id:** `TC-3`
- **Intent:** `INT-1`
- **Source issue:** `ledger-listing-cap`
- **Landed:** 2026-10-05

### Given a pending lesson proposal, then compass lesson decline removes it and records its text, so compass retro --lessons does not propose it again

- **Scenario id:** `LD-A`
- **Intent:** `INT-1`
- **Source issue:** `lesson-proposal-decline`
- **Landed:** 2026-10-02

### Given a landed issue, when an issue is created with `quick-fix start --raised-by <it> --found-at review`, or `compass issue raised-by <it> --found-at review` runs on an existing issue, then the manifest carries `raised_by` with that issue and `found_at: review`, and `compass issue lint` accepts it.

- **Scenario id:** `LN-1`
- **Intent:** `INT-1`
- **Source issue:** `lineage`
- **Landed:** 2026-10-06

### Given `--raised-by` names no issue in the project, or `--found-at` is not one of define, plan, implement, verify, review, ci, after-landing, or only one of the two flags is given, when either verb runs, then it exits non-zero and writes nothing. A manifest whose `raised_by` has an unknown `found_at` fails `compass issue lint`.

- **Scenario id:** `LN-2`
- **Intent:** `INT-1`
- **Source issue:** `lineage`
- **Landed:** 2026-10-06

### Given three issues raised at review and one raised after-landing, when `compass retro --lineage` runs, then it reports three found before landing and one after, counts by `found_at`, names chains of three or more and the parents with the most children, and exits 0. With no raised issues it says so and exits 0.

- **Scenario id:** `LN-3`
- **Intent:** `INT-1`
- **Source issue:** `lineage`
- **Landed:** 2026-10-06

### Given issue C raised from B, which was raised from A, when C's `raised_by` is recorded, then one line names A as the root and points at `S14` in `governance/strategies.md`. A second-level issue prints no such line.

- **Scenario id:** `LN-5`
- **Intent:** `INT-1`
- **Source issue:** `lineage`
- **Landed:** 2026-10-06

### Given an issue with status abandoned and no assessment block, When compass issue lint runs, Then it does not demand an assessment; and an active issue with no assessment is still refused

- **Scenario id:** `LA-1`
- **Intent:** `INT-1`
- **Source issue:** `lint-excuses-unassessed-abandoned`
- **Landed:** 2026-10-05

### a stale derived spec should fail a check

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `living-spec-and-process-impact`
- **Landed:** 

### a current derived spec should pass

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `living-spec-and-process-impact`
- **Landed:** 

### the committed spec should cover every landed task

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `living-spec-and-process-impact`
- **Landed:** 

### a project with no landed tasks should not be broken by the check

- **Scenario id:** `TRC-F2`
- **Intent:** `INT-1`
- **Source issue:** `living-spec-and-process-impact`
- **Landed:** 

### Given a git project where an issue is landed in local records, is not named in the spec committed at HEAD and its `land_commit` is not reachable from HEAD, when the spec is derived, then its scenarios are left out; an issue named in HEAD's spec, or whose `land_commit` is reachable, is kept.

- **Scenario id:** `LS-1`
- **Intent:** `INT-1`
- **Source issue:** `living-spec-conflicts`
- **Landed:** 2026-10-06

### Given a branch that conflicts with its base only in the two derived spec files, when `compass issue refresh-spec --base <ref>` runs, then the base is merged, the base's spec is taken, the spec is re-derived with the branch's own issue and committed, and no conflict is left.

- **Scenario id:** `LS-2`
- **Intent:** `INT-1`
- **Source issue:** `living-spec-conflicts`
- **Landed:** 2026-10-06

### Given a merge that also conflicts in another file, when `compass issue refresh-spec` runs, then it aborts the merge, leaves the branch as it was and names the other files.

- **Scenario id:** `LS-3`
- **Intent:** `INT-1`
- **Source issue:** `living-spec-conflicts`
- **Landed:** 2026-10-06

### Given the decision, then an architecture decision record states the new selection rule and how it narrows ADR-008's "reconstructible from landed issues alone".

- **Scenario id:** `LS-4`
- **Intent:** `INT-1`
- **Source issue:** `living-spec-conflicts`
- **Landed:** 2026-10-06

### Given the count of compared lock cases is partial because pytest-xdist split the file When test_cs_5 runs inside a worker Then it skips instead of failing, and outside a worker it still requires at least 70

- **Scenario id:** `TRC-001`
- **Intent:** `INT-1`
- **Source issue:** `lock-proof-under-xdist`
- **Landed:** 2026-10-07

### Locks are read from layer documents and the shipped preset gives the ADR lock set

- **Scenario id:** `LK-1`
- **Intent:** `INT-1`
- **Source issue:** `locks`
- **Landed:** 2026-10-07

### The footprint of a locked check, gate, stage, rule set or approach

- **Scenario id:** `LK-2`
- **Intent:** `INT-1`
- **Source issue:** `locks`
- **Landed:** 2026-10-07

### A lock allows tightening and refuses loosening and each indirect route on a check

- **Scenario id:** `LK-3`
- **Intent:** `INT-1`
- **Source issue:** `locks`
- **Landed:** 2026-10-07

### A lock on a gate, stage, rule set or approach refuses removal and moves

- **Scenario id:** `LK-4`
- **Intent:** `INT-1`
- **Source issue:** `locks`
- **Landed:** 2026-10-07

### A waiver, a hard lock and the label cap: what a lock refuses regardless

- **Scenario id:** `LK-5`
- **Intent:** `INT-1`
- **Source issue:** `locks`
- **Landed:** 2026-10-07

### An unlock needs the project layer, the owner's waiver and a lock that is not hard

- **Scenario id:** `LK-6`
- **Intent:** `INT-1`
- **Source issue:** `locks`
- **Landed:** 2026-10-07

### Conformance is conformant, or non-conformant naming each unlocked entry

- **Scenario id:** `LK-7`
- **Intent:** `INT-1`
- **Source issue:** `locks`
- **Landed:** 2026-10-07

### Check, the receipt and the summary print the conformance line and nothing else changes

- **Scenario id:** `LK-8`
- **Intent:** `INT-1`
- **Source issue:** `locks`
- **Landed:** 2026-10-07

### The module declares its dependencies and owning doc, and core stays in bounds

- **Scenario id:** `LK-9`
- **Intent:** `INT-1`
- **Source issue:** `locks`
- **Landed:** 2026-10-07

### Given the shipped routing policy, then an issue's ceilings resolve from loop_ceilings rules with RP- ids, the lowest matching limit wins, and a policy without the rules gives no ceiling and a drift report naming the missing ids.

- **Scenario id:** `LC-A`
- **Intent:** `INT-1`
- **Source issue:** `loop-ceilings`
- **Landed:** 2026-10-03

### Given a subtask whose builder reported the same error three times, when another attempt is asked for, then the update refuses it and names the repeated error, and subtask next lists the subtask as refused.

- **Scenario id:** `LC-B`
- **Intent:** `INT-1`
- **Source issue:** `loop-ceilings`
- **Landed:** 2026-10-03

### Given a subtask at its attempt ceiling, when another attempt is asked for, then the update refuses it and names the ceiling and its rule id.

- **Scenario id:** `LC-C`
- **Intent:** `INT-1`
- **Source issue:** `loop-ceilings`
- **Landed:** 2026-10-03

### Given a multiagent issue whose subtask has more review rounds than its ceiling, then compass check fails it until a stop reason is recorded with an evidence file, and a subtask stopped that way passes without being done.

- **Scenario id:** `LC-D`
- **Intent:** `INT-1`
- **Source issue:** `loop-ceilings`
- **Landed:** 2026-10-03

### Given an issue created before the ceilings existed, then compass check judges it as before, whatever its counts.

- **Scenario id:** `LC-E`
- **Intent:** `INT-1`
- **Source issue:** `loop-ceilings`
- **Landed:** 2026-10-03

### Given a run at its replan ceiling, when another replan is recorded, then subtask replan refuses it and names the ceiling.

- **Scenario id:** `LC-F`
- **Intent:** `INT-1`
- **Source issue:** `loop-ceilings`
- **Landed:** 2026-10-03

### a landed Standard task with typed evidence renders the canonical receipt

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `make-receipt-render`
- **Landed:** 2026-05-26

### the rendered receipt fits within a single terminal screen

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `make-receipt-render`
- **Landed:** 2026-05-26

### the receipt labels each evidence type with its name and type-specific minimal fields

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-1`
- **Source issue:** `make-receipt-render`
- **Landed:** 2026-05-26

### a missing task slug fails cleanly

- **Scenario id:** `TRC-D3`
- **Intent:** `INT-1`
- **Source issue:** `make-receipt-render`
- **Landed:** 2026-05-26

### A subtask id that could leave the worktree root is refused

- **Scenario id:** `MCC-1`
- **Intent:** `INT-1`
- **Source issue:** `map-cells-reach-git-unchecked`
- **Landed:** 2026-09-25

### A branch git would not accept is refused

- **Scenario id:** `MCC-2`
- **Intent:** `INT-1`
- **Source issue:** `map-cells-reach-git-unchecked`
- **Landed:** 2026-09-25

### Given a distribution map whose subtask table lists a different number of rows from the Final subtask count after caps it states, When multiagent.sh provisions it, Then it refuses, names both numbers and creates nothing; and a map whose counts agree, or that states no number, is provisioned as before

- **Scenario id:** `MC-1`
- **Intent:** `INT-1`
- **Source issue:** `map-counts-agree`
- **Landed:** 2026-10-04

### A branch that committed an ignored record is refused

- **Scenario id:** `MIR-1`
- **Intent:** `INT-1`
- **Source issue:** `merge-overwrites-an-ignored-record`
- **Landed:** 2026-09-25

### A branch with no ignored record merges

- **Scenario id:** `MIR-2`
- **Intent:** `INT-1`
- **Source issue:** `merge-overwrites-an-ignored-record`
- **Landed:** 2026-09-25

### Given many manifests read in one process, then the migrate map is parsed once, and parsed again only when its path or contents change.

- **Scenario id:** `MM-1`
- **Intent:** `INT-1`
- **Source issue:** `migrate-map-parsed-once`
- **Landed:** 2026-10-03

### No script says integration lands or happens at ship

- **Scenario id:** `DSS-1`
- **Intent:** `INT-1`
- **Source issue:** `multiagent-scripts-still-say-ship`
- **Landed:** 2026-09-25

### multiagent.sh names the order of waves and --no-clean

- **Scenario id:** `DSS-2`
- **Intent:** `INT-1`
- **Source issue:** `multiagent-scripts-still-say-ship`
- **Landed:** 2026-09-25

### integrate.sh says no regression ran when none did

- **Scenario id:** `DSS-3`
- **Intent:** `INT-1`
- **Source issue:** `multiagent-scripts-still-say-ship`
- **Landed:** 2026-09-25

### The protocol's landing command runs as written

- **Scenario id:** `DSS-4`
- **Intent:** `INT-1`
- **Source issue:** `multiagent-scripts-still-say-ship`
- **Landed:** 2026-09-25

### Given a shipped check with no register entry, when the register test runs, then it fails naming the check

- **Scenario id:** `MPR-1`
- **Intent:** `INT-1`
- **Source issue:** `mutation-proof-register`
- **Landed:** 2026-10-05

### Given a register entry missing a required field, when the register test runs, then it fails naming the check and the field

- **Scenario id:** `MPR-2`
- **Intent:** `INT-1`
- **Source issue:** `mutation-proof-register`
- **Landed:** 2026-10-05

### Given a register entry for a check that no longer exists, when the register test runs, then it fails naming the entry

- **Scenario id:** `MPR-3`
- **Intent:** `INT-1`
- **Source issue:** `mutation-proof-register`
- **Landed:** 2026-10-05

### Given the shipped checks cannot be read or are empty, when the register test runs, then it fails rather than passing

- **Scenario id:** `MPR-4`
- **Intent:** `INT-1`
- **Source issue:** `mutation-proof-register`
- **Landed:** 2026-10-05

### Given each shipped check, when the register is read, then its entry names a failing-input test and a passing control that exist

- **Scenario id:** `MPR-5`
- **Intent:** `INT-1`
- **Source issue:** `mutation-proof-register`
- **Landed:** 2026-10-05

### Given the change lands, then nothing under governance changes and the project guardrail list stays empty

- **Scenario id:** `MPR-6`
- **Intent:** `INT-1`
- **Source issue:** `mutation-proof-register`
- **Landed:** 2026-10-05

### the strategy states the method and the reason

- **Scenario id:** `TRC-1`
- **Intent:** `INT-1`
- **Source issue:** `mutation-proof-standing`
- **Landed:** 2026-08-12

### the verify guidance points at the strategy

- **Scenario id:** `TRC-2`
- **Intent:** `INT-1`
- **Source issue:** `mutation-proof-standing`
- **Landed:** 2026-08-12

### the id set admits the new strategy deliberately

- **Scenario id:** `TRC-3`
- **Intent:** `INT-1`
- **Source issue:** `mutation-proof-standing`
- **Landed:** 2026-08-12

### Given the mutation runner, When --check names no register entry, Then it exits non-zero naming the id; and when a test stays green its output is shown

- **Scenario id:** `MT-1`
- **Intent:** `INT-1`
- **Source issue:** `mutation-runner-tidy`
- **Landed:** 2026-10-06

### the term is governed like every other

- **Scenario id:** `NIR-A1`
- **Intent:** `INT-1`
- **Source issue:** `name-the-issue-record`
- **Landed:** 2026-08-27

### the name needs no gloss

- **Scenario id:** `NIR-A2`
- **Intent:** `INT-1`
- **Source issue:** `name-the-issue-record`
- **Landed:** 2026-08-27

### Given the named-patterns strategy, then it asks a design to name its patterns and any it rejected, the reviewer checks both a novel structure where a pattern fits and a pattern where none is needed, and it stays advice.

- **Scenario id:** `NP-1`
- **Intent:** `INT-1`
- **Source issue:** `named-patterns-strategy`
- **Landed:** 2026-10-03

### Given a manifest whose gates is not a list, whose stages is not a mapping, or whose stage weight is not a string, When compass next runs, Then it prints a stage and exits 0 with nothing on stderr, and the status line prints its line

- **Scenario id:** `TRC-001`
- **Intent:** `INT-1`
- **Source issue:** `next-crashes-on-mistyped-manifest`
- **Landed:** 2026-10-02

### Given an issue with its approach record and no other record, when compass next runs, then it reports Define.

- **Scenario id:** `NS-A`
- **Intent:** `INT-1`
- **Source issue:** `next-never-leaves-assess`
- **Landed:** 2026-10-02

### Given the acceptance criteria registered as draft, and no later record, then it reports Refine on a route that runs refine. Given the requirements review registered as well, then it reports Plan on a route that runs plan. Given scenarios and no later record on a route that collapses refine and plan and skips breakdown, then it reports Implement.

- **Scenario id:** `NS-B`
- **Intent:** `INT-1`
- **Source issue:** `next-never-leaves-assess`
- **Landed:** 2026-10-02

### Given the technical design registered, and no subtask, distribution map or test record, then it reports Breakdown on a route that runs breakdown. Given a subtask or the distribution map recorded, then it reports Implement.

- **Scenario id:** `NS-C`
- **Intent:** `INT-1`
- **Source issue:** `next-never-leaves-assess`
- **Landed:** 2026-10-02

### Given a red on record and no green, or test evidence for some scenarios but not all, then it reports Implement.

- **Scenario id:** `NS-D`
- **Intent:** `INT-1`
- **Source issue:** `next-never-leaves-assess`
- **Landed:** 2026-10-02

### Given test evidence for every scenario that needs one and a gate not passed, then it reports Verify, even when no design or breakdown record exists.

- **Scenario id:** `NS-E`
- **Intent:** `INT-1`
- **Source issue:** `next-never-leaves-assess`
- **Landed:** 2026-10-02

### Given every gate passed and the issue not landed, then it reports Ship. Given status: landed, then it reports all phases complete.

- **Scenario id:** `NS-F`
- **Intent:** `INT-1`
- **Source issue:** `next-never-leaves-assess`
- **Landed:** 2026-10-02

### Given a current_phase key in the manifest, then it reports that stage, whatever the records show.

- **Scenario id:** `NS-G`
- **Intent:** `INT-1`
- **Source issue:** `next-never-leaves-assess`
- **Landed:** 2026-10-02

### Given any issue in NS-A to NS-F, then the status line's stage and the rail's current marker name the same stage as compass next.

- **Scenario id:** `NS-H`
- **Intent:** `INT-1`
- **Source issue:** `next-never-leaves-assess`
- **Landed:** 2026-10-02

### Given a manifest whose artifacts, evidence, scenarios or subtasks is not a list, or whose ids are not strings, then compass next still prints a stage and exits 0, and the status line still prints its line.

- **Scenario id:** `NS-I`
- **Intent:** `INT-1`
- **Source issue:** `next-never-leaves-assess`
- **Landed:** 2026-10-02

### TRC-A1

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `no-compass-refs-in-product-code`
- **Landed:** 2026-07-27

### TRC-A2

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `no-compass-refs-in-product-code`
- **Landed:** 2026-07-27

### TRC-A3

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `no-compass-refs-in-product-code`
- **Landed:** 2026-07-27

### TRC-A4

- **Scenario id:** `TRC-A4`
- **Intent:** `INT-1`
- **Source issue:** `no-compass-refs-in-product-code`
- **Landed:** 2026-07-27

### a landed issue with a pointer passes without its own record

- **Scenario id:** `DEL-A1`
- **Intent:** `INT-1`
- **Source issue:** `no-status-for-work-done-elsewhere`
- **Landed:** 2026-08-26

### an absorbed issue that was never assessed still lints

- **Scenario id:** `DEL-A4`
- **Intent:** `INT-1`
- **Source issue:** `no-status-for-work-done-elsewhere`
- **Landed:** 2026-08-26

### a commit entry resolves and says what it did

- **Scenario id:** `DEL-D1`
- **Intent:** `INT-1`
- **Source issue:** `no-status-for-work-done-elsewhere`
- **Landed:** 2026-08-26

### Given an issue where some checks have nothing to inspect and one fails, When compass check runs in the verbose and default views, Then those checks are labelled NOTHING TO CHECK rather than PASS, and the failing verdict counts only checks that inspected something and names how many had nothing to check

- **Scenario id:** `NI-1`
- **Intent:** `INT-1`
- **Source issue:** `nothing-inspected-is-not-pass`
- **Landed:** 2026-10-04

### The preset, through the adapter, routes the whole compatibility grid as today's policy does, and a planted preset change breaks the replay

- **Scenario id:** `OB-1`
- **Intent:** `INT-1`
- **Source issue:** `obligations`
- **Landed:** 2026-10-07

### The evaluator lifts by rank when given ranks, and by today's fixed set when not

- **Scenario id:** `OB-2`
- **Intent:** `INT-1`
- **Source issue:** `obligations`
- **Landed:** 2026-10-07

### Obligations name every fact the design lists and equal the evaluator's answers, and every compared field is a fact or a lock footprint

- **Scenario id:** `OB-3`
- **Intent:** `INT-1`
- **Source issue:** `obligations`
- **Landed:** 2026-10-07

### A refused assessment is a Refused outcome with the evaluator's reason, counted as the baseline counts it, and a configuration fault still raises

- **Scenario id:** `OB-4`
- **Intent:** `INT-1`
- **Source issue:** `obligations`
- **Landed:** 2026-10-07

### An issue layer picks the candidate, overrides base modes, then floors, caps and role rules apply and floors win

- **Scenario id:** `OB-5`
- **Intent:** `INT-1`
- **Source issue:** `obligations`
- **Landed:** 2026-10-07

### Checks are active by when and capabilities, severity follows blocking_when, guardrail gates apply by ships and when

- **Scenario id:** `OB-6`
- **Intent:** `INT-1`
- **Source issue:** `obligations`
- **Landed:** 2026-10-07

### The preset's on_skipped values give today's verdicts on the archive sample, apart from the landed_by relaxations

- **Scenario id:** `OB-7`
- **Intent:** `INT-1`
- **Source issue:** `obligations`
- **Landed:** 2026-10-07

### The evaluator called as today answers as before, nothing else reads the new module, and it declares its dependencies

- **Scenario id:** `OB-8`
- **Intent:** `INT-1`
- **Source issue:** `obligations`
- **Landed:** 2026-10-07

### Given `commands/go.md`, then it runs `compass init`, assesses with `compass quick-fix start`, shows `compass approach summary`, and continues into the

- **Scenario id:** `ONE-1`
- **Intent:** `INT-1`
- **Source issue:** `one-entry-point`
- **Landed:** 2026-10-01

### Given an assessed issue, when `compass approach summary` runs, then it prints exactly three lines: the approach, its gates, and where the issue's file

- **Scenario id:** `ONE-2`
- **Intent:** `INT-1`
- **Source issue:** `one-entry-point`
- **Landed:** 2026-10-01

### Given a pre-tool hook block on an assessed issue, then one line for that issue and `hook_blocks` is appended to `.compass/interruptions.log`, and the 

- **Scenario id:** `ONE-3`
- **Intent:** `INT-1`
- **Source issue:** `one-entry-point`
- **Landed:** 2026-10-01

### Given a failing `compass check`, then one `check_failures` line is appended to the log and the issue folder is untouched; a `compass ci` sweep does no

- **Scenario id:** `ONE-4`
- **Intent:** `INT-1`
- **Source issue:** `one-entry-point`
- **Landed:** 2026-10-01

### Given issues with interruptions, then `compass retro` reports their totals.

- **Scenario id:** `ONE-5`
- **Intent:** `INT-1`
- **Source issue:** `one-entry-point`
- **Landed:** 2026-10-01

### Given a fresh repository, when a session types `/compass:go` with a small change, then it lands a quick fix; measured in an eval run (spend asked for 

- **Scenario id:** `ONE-6`
- **Intent:** `INT-1`
- **Source issue:** `one-entry-point`
- **Landed:** 2026-10-01

### Given a fired policy rule with a rationale, an id and a kind, When approach evaluate prints its summary or verbose view and issue receipt prints the receipt, Then each line is exactly what it is today, and all three come from one shared formatter

- **Scenario id:** `FR-1`
- **Intent:** `INT-1`
- **Source issue:** `one-fired-rule-formatter-shared`
- **Landed:** 2026-10-04

### Given a policy or manifest with an old route name, when it is read, then it maps to the new name with one warning and the same approach

- **Scenario id:** `RN-1`
- **Intent:** `INT-1`
- **Source issue:** `one-name-per-route`
- **Landed:** 2026-10-05

### Given the shipped routing policy, when it is read, then route_shapes and every route reference use the five route names

- **Scenario id:** `RN-2`
- **Intent:** `INT-1`
- **Source issue:** `one-name-per-route`
- **Landed:** 2026-10-05

### Given the checkpoint routes, the lint route check and the schema, when compared with route_shapes, then they match

- **Scenario id:** `RN-3`
- **Intent:** `INT-1`
- **Source issue:** `one-name-per-route`
- **Landed:** 2026-10-05

### Given a manifest with an unknown delivery approach, when the issue is linted, then the value is reported

- **Scenario id:** `RN-4`
- **Intent:** `INT-1`
- **Source issue:** `one-name-per-route`
- **Landed:** 2026-10-05

### Given the retro over the archive, when it runs before and after the rename, then the counts are the same with no translation left

- **Scenario id:** `RN-5`
- **Intent:** `INT-1`
- **Source issue:** `one-name-per-route`
- **Landed:** 2026-10-05

### Given the approach documents, when the rename lands, then regular and full replace the old files and no link is broken

- **Scenario id:** `RN-6`
- **Intent:** `INT-1`
- **Source issue:** `one-name-per-route`
- **Landed:** 2026-10-05

### Given the decisions of 5 October on routing, when this lands, then each is a decision entry

- **Scenario id:** `RN-7`
- **Intent:** `INT-1`
- **Source issue:** `one-name-per-route`
- **Landed:** 2026-10-05

### A subtask's progress is recorded

- **Scenario id:** `OLH-2`
- **Intent:** `INT-1`
- **Source issue:** `orchestrator-loop-hardening`
- **Landed:** 2026-09-25

### A review package is a file cut from the base commit

- **Scenario id:** `OLH-5`
- **Intent:** `INT-1`
- **Source issue:** `orchestrator-loop-hardening`
- **Landed:** 2026-09-25

### Given a doc under docs/ that the docs/README.md index does not list, or a path in its owning-docs table that does not exist, When the suite runs, Then a test fails naming it

- **Scenario id:** `TRC-001`
- **Intent:** `INT-1`
- **Source issue:** `owning-doc-router`
- **Landed:** 2026-10-02

### Given the suite runs on parallel workers, When make test or CI runs it, Then tests marked serial, including the two timing tests, run in a second pass on their own

- **Scenario id:** `TRC-001`
- **Intent:** `INT-1`
- **Source issue:** `parallel-ci-flakes`
- **Landed:** 2026-10-02

### the skill should state a method, in order

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `phase-2-skills-check-and-cli-split`
- **Landed:** 

### three failed fixes should send the engineer back to Frame

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `phase-2-skills-check-and-cli-split`
- **Landed:** 

### the skill should be reachable from where the failure happens

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `phase-2-skills-check-and-cli-split`
- **Landed:** 

### CLAUDE.md and AGENTS.md carry the full plain-English rules

- **Scenario id:** `PFR-1`
- **Intent:** `INT-1`
- **Source issue:** `plain-english-full-rules`
- **Landed:** 2026-09-11

### "seam" used for code structure should be flagged

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-1`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### "seam" used for anything else should not be flagged

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-1`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### the ban should name what to write instead

- **Scenario id:** `TRC-B3`
- **Intent:** `INT-1`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### a rare word quoted from a tool should survive the ban

- **Scenario id:** `TRC-B4`
- **Intent:** `INT-1`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### the shipped list should say what is true today, not what is intended

- **Scenario id:** `TRC-B7`
- **Intent:** `INT-1`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### governance prose should be scanned for bare codes, not exempt by path

- **Scenario id:** `TRC-C11`
- **Intent:** `INT-1`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### the claims gate should say it checks traceability, not truth

- **Scenario id:** `TRC-C12`
- **Intent:** `INT-1`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### a derivation failure should name what changed and what was expected

- **Scenario id:** `TRC-C9`
- **Intent:** `INT-1`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### the title rule should name the shapes it refuses

- **Scenario id:** `TRC-D1`
- **Intent:** `INT-1`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### the body template should say what a reviewer needs

- **Scenario id:** `TRC-D2`
- **Intent:** `INT-1`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### a commit title should be held to the same rule

- **Scenario id:** `TRC-D3`
- **Intent:** `INT-1`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### a correction should not leave the record contradicting itself

- **Scenario id:** `TRC-D4`
- **Intent:** `INT-1`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### a search reporting zero should have been proved able to find something

- **Scenario id:** `TRC-D5`
- **Intent:** `INT-1`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### the correction rule should say which places take a correction and which take a note

- **Scenario id:** `TRC-D6`
- **Intent:** `INT-1`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### repairing a banned word should not paraphrase a quoted tool string

- **Scenario id:** `TRC-X4`
- **Intent:** `INT-1`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### Given the plugin manifests, then the plugin keeps the name compass, its display name is Compass Adaptive Spec-Driven Development, and its author is ayeo.io in both manifests.

- **Scenario id:** `PN-1`
- **Intent:** `INT-1`
- **Source issue:** `plugin-display-name`
- **Landed:** 2026-10-04

### Given a session that edited under one issue, when another session moves the pointer, then that session's next code edit is refused naming both issues and the command to confirm.

- **Scenario id:** `CL-A`
- **Intent:** `INT-1`
- **Source issue:** `pointer-lease`
- **Landed:** 2026-10-03

### Given that refusal, then compass issue use run in the session sets the pointer and lets its edits through on the issue it names.

- **Scenario id:** `CL-B`
- **Intent:** `INT-1`
- **Source issue:** `pointer-lease`
- **Landed:** 2026-10-03

### Given the session that moved the pointer, then its own edits are not refused, because issue use and quick-fix start record the new issue for the calling session.

- **Scenario id:** `CL-C`
- **Intent:** `INT-1`
- **Source issue:** `pointer-lease`
- **Landed:** 2026-10-03

### Given the session-issue variable, no session id, or a session record older than 12 hours, then the hook refuses nothing for a moved pointer.

- **Scenario id:** `CL-D`
- **Intent:** `INT-1`
- **Source issue:** `pointer-lease`
- **Landed:** 2026-10-03

### A pointer holding a path makes the hook refuse

- **Scenario id:** `CTP-1`
- **Intent:** `INT-1`
- **Source issue:** `pointer-path-traversal`
- **Landed:** 2026-09-25

### The CLI refuses a slug holding a path

- **Scenario id:** `CTP-2`
- **Intent:** `INT-1`
- **Source issue:** `pointer-path-traversal`
- **Landed:** 2026-09-25

### An ordinary slug behaves as today

- **Scenario id:** `CTP-3`
- **Intent:** `INT-1`
- **Source issue:** `pointer-path-traversal`
- **Landed:** 2026-09-25

### The references resolve to configurations or exit 2

- **Scenario id:** `PD-1`
- **Intent:** `INT-1`
- **Source issue:** `policy-diff`
- **Landed:** 2026-10-07

### The verb is documented, registered, in the command corpus and within the caps

- **Scenario id:** `PD-10`
- **Intent:** `INT-1`
- **Source issue:** `policy-diff`
- **Landed:** 2026-10-07

### The classification is the classifier's own JSON

- **Scenario id:** `PD-2`
- **Intent:** `INT-1`
- **Source issue:** `policy-diff`
- **Landed:** 2026-10-07

### The grid is replayed and each changed point is listed

- **Scenario id:** `PD-3`
- **Intent:** `INT-1`
- **Source issue:** `policy-diff`
- **Landed:** 2026-10-07

### The label combinations are replayed and the cap skips them

- **Scenario id:** `PD-4`
- **Intent:** `INT-1`
- **Source issue:** `policy-diff`
- **Landed:** 2026-10-07

### The archive's assessments are replayed

- **Scenario id:** `PD-5`
- **Intent:** `INT-1`
- **Source issue:** `policy-diff`
- **Landed:** 2026-10-07

### --open lists the open issues and the waivers a change affects

- **Scenario id:** `PD-6`
- **Intent:** `INT-1`
- **Source issue:** `policy-diff`
- **Landed:** 2026-10-07

### The exit codes and --exit-code

- **Scenario id:** `PD-7`
- **Intent:** `INT-1`
- **Source issue:** `policy-diff`
- **Landed:** 2026-10-07

### --json has a pinned, deterministic shape

- **Scenario id:** `PD-8`
- **Intent:** `INT-1`
- **Source issue:** `policy-diff`
- **Landed:** 2026-10-07

### The text output

- **Scenario id:** `PD-9`
- **Intent:** `INT-1`
- **Source issue:** `policy-diff`
- **Landed:** 2026-10-07

### A project with no compass.yml and the framework repository keep the legacy lint

- **Scenario id:** `PL-1`
- **Intent:** `INT-1`
- **Source issue:** `policy-lint`
- **Landed:** 2026-10-07

### Effective prints every resolved field with source and waiver

- **Scenario id:** `PL-10`
- **Intent:** `INT-1`
- **Source issue:** `policy-lint`
- **Landed:** 2026-10-07

### Effective --json has a pinned, deterministic shape

- **Scenario id:** `PL-11`
- **Intent:** `INT-1`
- **Source issue:** `policy-lint`
- **Landed:** 2026-10-07

### Both verbs are documented, in the command corpus and within the line caps

- **Scenario id:** `PL-12`
- **Intent:** `INT-1`
- **Source issue:** `policy-lint`
- **Landed:** 2026-10-07

### Per-layer faults are reported and stop the lint before the merge

- **Scenario id:** `PL-2`
- **Intent:** `INT-1`
- **Source issue:** `policy-lint`
- **Landed:** 2026-10-07

### Every merge code of the first refused layer is reported

- **Scenario id:** `PL-3`
- **Intent:** `INT-1`
- **Source issue:** `policy-lint`
- **Landed:** 2026-10-07

### The merged configuration is checked as a whole

- **Scenario id:** `PL-4`
- **Intent:** `INT-1`
- **Source issue:** `policy-lint`
- **Landed:** 2026-10-07

### Lock refusals are reported and an evaluator fault is reported once

- **Scenario id:** `PL-5`
- **Intent:** `INT-1`
- **Source issue:** `policy-lint`
- **Landed:** 2026-10-07

### An unexcused loosening is an error and waivers are checked

- **Scenario id:** `PL-6`
- **Intent:** `INT-1`
- **Source issue:** `policy-lint`
- **Landed:** 2026-10-07

### A vocabulary change is its own warning

- **Scenario id:** `PL-7`
- **Intent:** `INT-1`
- **Source issue:** `policy-lint`
- **Landed:** 2026-10-07

### The text output, the options and the exit codes

- **Scenario id:** `PL-8`
- **Intent:** `INT-1`
- **Source issue:** `policy-lint`
- **Landed:** 2026-10-07

### Lint --json has a pinned, deterministic shape

- **Scenario id:** `PL-9`
- **Intent:** `INT-1`
- **Source issue:** `policy-lint`
- **Landed:** 2026-10-07

### A dry run prints the compass.yml it would write and changes no file

- **Scenario id:** `PM-1`
- **Intent:** `INT-1`
- **Source issue:** `policy-migrate`
- **Landed:** 2026-10-08

### The json output has fixed keys, is deterministic and is pinned by an example

- **Scenario id:** `PM-10`
- **Intent:** `INT-1`
- **Source issue:** `policy-migrate`
- **Landed:** 2026-10-08

### The owning doc, README row, help text and command corpus exist

- **Scenario id:** `PM-11`
- **Intent:** `INT-1`
- **Source issue:** `policy-migrate`
- **Landed:** 2026-10-08

### A table of shipped releases is data, and holds every tagged release

- **Scenario id:** `PM-12`
- **Intent:** `INT-1`
- **Source issue:** `policy-migrate`
- **Landed:** 2026-10-08

### policy-migrate review round, group 13

- **Scenario id:** `PM-13`
- **Intent:** `INT-1`
- **Source issue:** `policy-migrate`
- **Landed:** 2026-10-08

### policy-migrate review round, group 14

- **Scenario id:** `PM-14`
- **Intent:** `INT-1`
- **Source issue:** `policy-migrate`
- **Landed:** 2026-10-08

### policy-migrate review round, group 15

- **Scenario id:** `PM-15`
- **Intent:** `INT-1`
- **Source issue:** `policy-migrate`
- **Landed:** 2026-10-08

### policy-migrate review round, group 16

- **Scenario id:** `PM-16`
- **Intent:** `INT-1`
- **Source issue:** `policy-migrate`
- **Landed:** 2026-10-08

### policy-migrate review round, group 17

- **Scenario id:** `PM-17`
- **Intent:** `INT-1`
- **Source issue:** `policy-migrate`
- **Landed:** 2026-10-08

### policy-migrate review round, group 18

- **Scenario id:** `PM-18`
- **Intent:** `INT-1`
- **Source issue:** `policy-migrate`
- **Landed:** 2026-10-08

### No member of the compressed archive of shipped releases holds a rival name

- **Scenario id:** `PM-19`
- **Intent:** `INT-1`
- **Source issue:** `policy-migrate`
- **Landed:** 2026-10-08

### An unchanged copy migrates to an empty overlay and classifies equivalent

- **Scenario id:** `PM-2`
- **Intent:** `INT-1`
- **Source issue:** `policy-migrate`
- **Landed:** 2026-10-08

### A changed copy migrates to exactly its differing entries and classifies equivalent

- **Scenario id:** `PM-3`
- **Intent:** `INT-1`
- **Source issue:** `policy-migrate`
- **Landed:** 2026-10-08

### A loosening gets unapproved waiver stubs and blocks apply with exit 1

- **Scenario id:** `PM-4`
- **Intent:** `INT-1`
- **Source issue:** `policy-migrate`
- **Landed:** 2026-10-08

### Settings fold into compass.yml, state goes to state.yml, and nothing is dropped silently

- **Scenario id:** `PM-5`
- **Intent:** `INT-1`
- **Source issue:** `policy-migrate`
- **Landed:** 2026-10-08

### Apply copies the sources, writes compass.yml last and keeps the governance files

- **Scenario id:** `PM-6`
- **Intent:** `INT-1`
- **Source issue:** `policy-migrate`
- **Landed:** 2026-10-08

### A compass.yml, the framework repository or a lone governance file is refused with exit 2

- **Scenario id:** `PM-7`
- **Intent:** `INT-1`
- **Source issue:** `policy-migrate`
- **Landed:** 2026-10-08

### An interrupted apply finishes on the next run

- **Scenario id:** `PM-8`
- **Intent:** `INT-1`
- **Source issue:** `policy-migrate`
- **Landed:** 2026-10-08

### A project with nothing to migrate exits 0 and writes nothing

- **Scenario id:** `PM-9`
- **Intent:** `INT-1`
- **Source issue:** `policy-migrate`
- **Landed:** 2026-10-08

### already on the target major: nothing to do, nothing written

- **Scenario id:** `UP-1`
- **Intent:** `INT-1`
- **Source issue:** `policy-update-default`
- **Landed:** 2026-10-08

### a dropped entry or an unresolvable file is refused

- **Scenario id:** `UP-10`
- **Intent:** `INT-1`
- **Source issue:** `policy-update-default`
- **Landed:** 2026-10-08

### a failed write leaves the file as it was

- **Scenario id:** `UP-11`
- **Intent:** `INT-1`
- **Source issue:** `policy-update-default`
- **Landed:** 2026-10-08

### the update shows the classification and the replay counts

- **Scenario id:** `UP-12`
- **Intent:** `INT-1`
- **Source issue:** `policy-update-default`
- **Landed:** 2026-10-08

### no terminal and no yes shows the plan and exits 1

- **Scenario id:** `UP-13`
- **Intent:** `INT-1`
- **Source issue:** `policy-update-default`
- **Landed:** 2026-10-08

### json equals the pinned example and never prompts

- **Scenario id:** `UP-14`
- **Intent:** `INT-1`
- **Source issue:** `policy-update-default`
- **Landed:** 2026-10-08

### an edit the command cannot make exactly exits 2 before writing

- **Scenario id:** `UP-15`
- **Intent:** `INT-1`
- **Source issue:** `policy-update-default`
- **Landed:** 2026-10-08

### help, doc, verb description and corpus state the behaviour

- **Scenario id:** `UP-16`
- **Intent:** `INT-1`
- **Source issue:** `policy-update-default`
- **Landed:** 2026-10-08

### a bump with no waiver changes only the integer after @

- **Scenario id:** `UP-2`
- **Intent:** `INT-1`
- **Source issue:** `policy-update-default`
- **Landed:** 2026-10-08

### a target not shipped, older, a foreign extends or no file exits 2

- **Scenario id:** `UP-3`
- **Intent:** `INT-1`
- **Source issue:** `policy-update-default`
- **Landed:** 2026-10-08

### an affected waiver is listed and the move refused without a terminal

- **Scenario id:** `UP-4`
- **Intent:** `INT-1`
- **Source issue:** `policy-update-default`
- **Landed:** 2026-10-08

### yes never re-approves a waiver

- **Scenario id:** `UP-5`
- **Intent:** `INT-1`
- **Source issue:** `policy-update-default`
- **Landed:** 2026-10-08

### terminal re-approval writes the integer and the approval in one write

- **Scenario id:** `UP-6`
- **Intent:** `INT-1`
- **Source issue:** `policy-update-default`
- **Landed:** 2026-10-08

### an approver outside the allowed list is refused

- **Scenario id:** `UP-7`
- **Intent:** `INT-1`
- **Source issue:** `policy-update-default`
- **Landed:** 2026-10-08

### declining refuses and writes nothing

- **Scenario id:** `UP-8`
- **Intent:** `INT-1`
- **Source issue:** `policy-update-default`
- **Landed:** 2026-10-08

### a waiver whose field is unchanged stays valid

- **Scenario id:** `UP-9`
- **Intent:** `INT-1`
- **Source issue:** `policy-update-default`
- **Landed:** 2026-10-08

### A red in the worktree allows an edit in the worktree

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `pre-tool-hook-misses-worktree-red`
- **Landed:** 2026-08-28

### A red in the session does not unlock a worktree

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `pre-tool-hook-misses-worktree-red`
- **Landed:** 2026-08-28

### A call naming no file still resolves from the session

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `pre-tool-hook-misses-worktree-red`
- **Landed:** 2026-08-28

### Given the 4 October comparison run, then its document is on record with every condition and scenario, the decision rule's verdict for each of the four careful-process scenarios, the cost per condition, the tokens per stage, and what it does not show.

- **Scenario id:** `PR-1`
- **Intent:** `INT-1`
- **Source issue:** `premium-run`
- **Landed:** 2026-10-04

### Given each of the four new scenarios, then it has a seed, a hidden test, a real-request prompt, the standard reply, and a reference that passes both test sets.

- **Scenario id:** `PS-1`
- **Intent:** `INT-1`
- **Source issue:** `premium-scenario-classes`
- **Landed:** 2026-10-03

### Given each of the four new scenarios, when its careless change is applied, then the seed's own tests pass and the hidden tests fail.

- **Scenario id:** `PS-2`
- **Intent:** `INT-1`
- **Source issue:** `premium-scenario-classes`
- **Landed:** 2026-10-03

### Given the two scenarios that start from earlier work, then each condition finds it in its usual place and every record states the rule the hidden test checks.

- **Scenario id:** `PS-3`
- **Intent:** `INT-1`
- **Source issue:** `premium-scenario-classes`
- **Landed:** 2026-10-03

### Given the eval readme, then it states the decision rule for the run that uses these scenarios before any run.

- **Scenario id:** `PS-4`
- **Intent:** `INT-1`
- **Source issue:** `premium-scenario-classes`
- **Landed:** 2026-10-03

### No printed string names a retired verb or value

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `printed-output-guard-coverage`
- **Landed:** 2026-08-28

### The walk reaches far more than the two commands it replaces

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `printed-output-guard-coverage`
- **Landed:** 2026-08-28

### A planted retired name is reported

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `printed-output-guard-coverage`
- **Landed:** 2026-08-28

### Given an issue, When approach evaluate --verbose --write, gate pass on an unknown gate, check with no gates and retro print their output, Then none of it says route, candidate shape or phases where it means the delivery approach or its stages

- **Scenario id:** `RW-1`
- **Intent:** `INT-1`
- **Source issue:** `printed-route-wording`
- **Landed:** 2026-10-04

### Given the CLI, hooks and scripts, when their string literals are scanned, then none uses an idiom from the writing-style table or "accretion", the scan fails on a planted breach, the no-reason re-assessment warning names `reassessments`, and the README and five-minutes guide name Python 3.10 or later

- **Scenario id:** `TRC-001`
- **Intent:** `INT-1`
- **Source issue:** `printed-wording-sweep`
- **Landed:** 2026-09-30

### Given stdout is a terminal and neither CLAUDECODE nor NO_COLOR is set, when compass next runs on an issue in progress, then the line after the header is a rail of the route's stages with exactly one current marker.

- **Scenario id:** `RL-A`
- **Intent:** `INT-1`
- **Source issue:** `progress-rail`
- **Landed:** 2026-10-02

### Given stdout is a pipe, when compass next runs, then its output matches the golden file captured before the rail, byte for byte, for every route in the fixtures.

- **Scenario id:** `RL-B`
- **Intent:** `INT-1`
- **Source issue:** `progress-rail`
- **Landed:** 2026-10-02

### Given a route that skips or collapses a stage, when the rail is shown, then that stage is shown with the skipped marker, not left out.

- **Scenario id:** `RL-C`
- **Intent:** `INT-1`
- **Source issue:** `progress-rail`
- **Landed:** 2026-10-02

### Given CLAUDECODE is set, when compass next runs with stdout a terminal, then its output is today's output, byte for byte.

- **Scenario id:** `RL-D`
- **Intent:** `INT-1`
- **Source issue:** `progress-rail`
- **Landed:** 2026-10-02

### Given NO_COLOR, then the rail has no colour codes; given COMPASS_COLOR=never, then it uses ASCII markers; given COMPASS_COLOR=always, then the rail shows when piped, unless CLAUDECODE is set.

- **Scenario id:** `RL-E`
- **Intent:** `INT-1`
- **Source issue:** `progress-rail`
- **Landed:** 2026-10-02

### Given a terminal narrower than the rail, then the rail wraps between stages and no line is wider than the terminal.

- **Scenario id:** `RL-F`
- **Intent:** `INT-1`
- **Source issue:** `progress-rail`
- **Landed:** 2026-10-02

### Given an issue in progress, then the rail is followed by a Next line naming the command for the current stage.

- **Scenario id:** `RL-G`
- **Intent:** `INT-1`
- **Source issue:** `progress-rail`
- **Landed:** 2026-10-02

### Given the status line, then it fits its line with the shared renderer, so width fitting lives in one module.

- **Scenario id:** `RL-H`
- **Intent:** `INT-1`
- **Source issue:** `progress-rail`
- **Landed:** 2026-10-02

### a project command should not run unless the project has opted in

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `project-commands-are-a-trust-boundary`
- **Landed:** 2026-08-22

### a project that has opted in should have its command run

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `project-commands-are-a-trust-boundary`
- **Landed:** 2026-08-22

### the report should distinguish disabled from nothing declared

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `project-commands-are-a-trust-boundary`
- **Landed:** 2026-08-22

### Given compass lesson add "<rule>", then it writes a lesson to the lessons file with added_by from git config compass.decidedBy, else user.name; there is no option to set it. An exact repeat is refused; a rule that contains an existing one replaces it and records superseded.

- **Scenario id:** `PL-A`
- **Intent:** `INT-1`
- **Source issue:** `project-lessons`
- **Landed:** 2026-10-02

### Given a rule that names a guardrail id from governance/guardrails.yml, a model id or a tool version, or --source verify, then add and propose refuse it with the reason; a near-miss sentence is accepted.

- **Scenario id:** `PL-B`
- **Intent:** `INT-1`
- **Source issue:** `project-lessons`
- **Landed:** 2026-10-02

### Given compass lesson propose "<rule>", then it writes to the pending lessons file only, and compass lesson accept <id> moves it to lessons.yml.

- **Scenario id:** `PL-C`
- **Intent:** `INT-1`
- **Source issue:** `project-lessons`
- **Landed:** 2026-10-02

### Given compass lesson list and compass lesson remove <id>, then list prints each lesson and each pending proposal, marking on_topic lessons "stored, not yet surfaced", and remove deletes one lesson.

- **Scenario id:** `PL-D`
- **Intent:** `INT-1`
- **Source issue:** `project-lessons`
- **Landed:** 2026-10-02

### Given five always lessons and one on_topic lesson, when a session starts, then the injected context holds the five after the operating contract under [Project lessons], with a line saying they cannot override a guardrail, and not the on_topic one.

- **Scenario id:** `PL-E`
- **Intent:** `INT-1`
- **Source issue:** `project-lessons`
- **Landed:** 2026-10-02

### Given always lessons over 150 words, then the injected block holds at most 150 words, oldest first, cut between lessons, and a frame line names how many were shown and how many omitted.

- **Scenario id:** `PL-F`
- **Intent:** `INT-1`
- **Source issue:** `project-lessons`
- **Landed:** 2026-10-02

### Given the same friction observation in three distinct issues, then compass retro --lessons writes one pending proposal with source: friction, and does not write lessons.yml.

- **Scenario id:** `PL-G`
- **Intent:** `INT-1`
- **Source issue:** `project-lessons`
- **Landed:** 2026-10-02

### Given a lesson that says a gate passes, then compass check gives the same result as without it.

- **Scenario id:** `PL-H`
- **Intent:** `INT-1`
- **Source issue:** `project-lessons`
- **Landed:** 2026-10-02

### Given the verb surface, then lesson is in the CLI baseline, the README's CLI block, verb_help.py and each frozen verb list, and ADR-029 records the decision. The 900-word resident test passes unchanged.

- **Scenario id:** `PL-I`
- **Intent:** `INT-1`
- **Source issue:** `project-lessons`
- **Landed:** 2026-10-02

### No retired v1 word survives in prose, a comment or a test docstring

- **Scenario id:** `PBW-A1`
- **Intent:** `INT-1`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### The shorter word stands where the word is not an identifier

- **Scenario id:** `PBW-A2`
- **Intent:** `INT-1`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### The spelling is British

- **Scenario id:** `PBW-A3`
- **Intent:** `INT-1`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### "artifact" is the only spelling

- **Scenario id:** `PBW-A4`
- **Intent:** `INT-1`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### No idiom from the table survives

- **Scenario id:** `PBW-A5`
- **Intent:** `INT-1`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### No sentence is left broken by an earlier find-and-replace

- **Scenario id:** `PBW-A9`
- **Intent:** `INT-1`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### A copied block is fixed the same way in every file that holds it

- **Scenario id:** `PBW-C4`
- **Intent:** `INT-1`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### An edit that adds an em dash or an attribution line is refused

- **Scenario id:** `PBW-F3`
- **Intent:** `INT-1`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### A rewrite that swaps one idiom for another is refused

- **Scenario id:** `PBW-F4`
- **Intent:** `INT-1`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### no published file should misspell the word the framework renamed to

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `public-docs-tell-the-truth`
- **Landed:** 2026-08-22

### the safety contract should be titled for the release it describes

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `public-docs-tell-the-truth`
- **Landed:** 2026-08-22

### the security guide should not deny a distribution channel the project publishes on

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `public-docs-tell-the-truth`
- **Landed:** 2026-08-22

### a document should not point at files that do not exist

- **Scenario id:** `TRC-A4`
- **Intent:** `INT-1`
- **Source issue:** `public-docs-tell-the-truth`
- **Landed:** 2026-08-22

### a live architecture artifact should not describe a retired stage as current

- **Scenario id:** `TRC-A5`
- **Intent:** `INT-1`
- **Source issue:** `public-docs-tell-the-truth`
- **Landed:** 2026-08-22

### a message the CLI prints should not tell a user to run a stage that no longer exists

- **Scenario id:** `TRC-A6`
- **Intent:** `INT-1`
- **Source issue:** `public-docs-tell-the-truth`
- **Landed:** 2026-08-22

### no live surface should carry a retired stage name

- **Scenario id:** `TRC-D1`
- **Intent:** `INT-1`
- **Source issue:** `public-docs-tell-the-truth`
- **Landed:** 2026-08-22

### a repair should not change what an agent is instructed to do

- **Scenario id:** `TRC-D2`
- **Intent:** `INT-1`
- **Source issue:** `public-docs-tell-the-truth`
- **Landed:** 2026-08-22

### Given pytest-bdd is installed, When the reference-adapter end-to-end test and the pytest-bdd case of the all-adapters test run, including under make test with plugin autoload off, Then both pass, and the bdd-adapter CI job runs them and fails if either skips

- **Scenario id:** `PB-1`
- **Intent:** `INT-1`
- **Source issue:** `pytest-bdd-adapter-tests-run`
- **Landed:** 2026-10-04

### Given an opted-in project and no python3 on the PATH, when a session starts, then the hook prints valid JSON with a systemMessage for the person and additionalContext for the model, each saying Compass needs Python 3.10 or later, that edits will be refused until it is installed, and how to fix it.

- **Scenario id:** `PY-A`
- **Intent:** `INT-1`
- **Source issue:** `python-dependency-said-early`
- **Landed:** 2026-10-02

### Given an opted-in project and a python3 older than 3.10, when a session starts, then the hook says the same and names the version it found.

- **Scenario id:** `PY-B`
- **Intent:** `INT-1`
- **Source issue:** `python-dependency-said-early`
- **Landed:** 2026-10-02

### Given a repository that never opted in, when a session starts without python3, then the hook prints nothing and exits 0, as now.

- **Scenario id:** `PY-C`
- **Intent:** `INT-1`
- **Source issue:** `python-dependency-said-early`
- **Landed:** 2026-10-02

### Given scripts/install.sh on a machine without python3 3.10+, then it says so before it finishes, names what will not work, and still installs. With it, it names the version found.

- **Scenario id:** `PY-D`
- **Intent:** `INT-1`
- **Source issue:** `python-dependency-said-early`
- **Landed:** 2026-10-02

### Given docs/safety-contract.md, then it has a table of what each hook and the CLI do without python3 3.10+, and the table's pre-tool row matches the hook's python-missing refusal.

- **Scenario id:** `PY-E`
- **Intent:** `INT-1`
- **Source issue:** `python-dependency-said-early`
- **Landed:** 2026-10-02

### Given ADR-028, then it records the single-file CLI decision with the measured size and startup cost.

- **Scenario id:** `PY-F`
- **Intent:** `INT-1`
- **Source issue:** `python-dependency-said-early`
- **Landed:** 2026-10-02

### Given a run record and its scenario, when the final code is rebuilt from the seed and the diff, then the measures cover changed Python files outside tests, and a diff that does not apply gives no measure.

- **Scenario id:** `QS-1`
- **Intent:** `INT-1`
- **Source issue:** `quality-static-signals`
- **Landed:** 2026-10-03

### Given a before and after version of a file, then complexity added, duplicated lines and lint findings are counted as the design states.

- **Scenario id:** `QS-2`
- **Intent:** `INT-1`
- **Source issue:** `quality-static-signals`
- **Landed:** 2026-10-03

### Given records for several conditions, then the comparison report shows the three measures per cell and per condition, and not recorded where none exists.

- **Scenario id:** `QS-3`
- **Intent:** `INT-1`
- **Source issue:** `quality-static-signals`
- **Landed:** 2026-10-03

### Given a diff with unusual paths, deleted or unparsable files, or a git environment pointing elsewhere, then the rebuild measures exactly the right files and touches nothing outside its directory.

- **Scenario id:** `QS-4`
- **Intent:** `INT-1`
- **Source issue:** `quality-static-signals`
- **Landed:** 2026-10-03

### Given queued issues, then compass flow --digest lists each with its age and flags those older than the threshold that carry a recommendation heading or a label a routing rule names, and the release guide asks which queued issues touch the release

- **Scenario id:** `QA-A`
- **Intent:** `INT-1`
- **Source issue:** `queue-ageing-signal`
- **Landed:** 2026-10-02

### An issue still in flight has its declared tests checked

- **Scenario id:** `QRL-1`
- **Intent:** `INT-1`
- **Source issue:** `queued-issues-read-as-landed`
- **Landed:** 2026-09-11

### Given a quick fix whose manifest records a re-assessment, When quick-fix finish runs, Then the manifest's friction list holds the derived entry; with no signal, no friction key is written and no extra line is printed

- **Scenario id:** `QF-1`
- **Intent:** `INT-1`
- **Source issue:** `quick-fix-finish-captures-friction`
- **Landed:** 2026-10-06

### a second finish reuses the covering green and commits

- **Scenario id:** `QFG-1`
- **Intent:** `INT-1`
- **Source issue:** `quick-fix-finish-gaps`
- **Landed:** 2026-09-28

### finish works from a subdirectory

- **Scenario id:** `QFG-2`
- **Intent:** `INT-1`
- **Source issue:** `quick-fix-finish-gaps`
- **Landed:** 2026-09-28

### ship-commit refuses a stale green for the issue's files

- **Scenario id:** `QFG-3`
- **Intent:** `INT-1`
- **Source issue:** `quick-fix-finish-gaps`
- **Landed:** 2026-09-28

### the safety contract states both limits

- **Scenario id:** `QFG-4`
- **Intent:** `INT-1`
- **Source issue:** `quick-fix-finish-gaps`
- **Landed:** 2026-09-28

### Given a 45-character slug and a cross-cutting change, when quick-fix start computes a heavier process, then no line passes 100 characters, nothing is cut, and each rule's id and kind share a line

- **Scenario id:** `TRC-001`
- **Intent:** `INT-1`
- **Source issue:** `quick-fix-message-edges`
- **Landed:** 2026-10-01

### start records the whole assessment in one call

- **Scenario id:** `QFO-1`
- **Intent:** `INT-1`
- **Source issue:** `quick-fix-overhead`
- **Landed:** 2026-09-28

### start stops when the approach is not a quick fix

- **Scenario id:** `QFO-2`
- **Intent:** `INT-1`
- **Source issue:** `quick-fix-overhead`
- **Landed:** 2026-09-28

### start refuses an unreasoned or unknown dimension

- **Scenario id:** `QFO-3`
- **Intent:** `INT-1`
- **Source issue:** `quick-fix-overhead`
- **Landed:** 2026-09-28

### finish traces, checks, passes the three gates and lands

- **Scenario id:** `QFO-4`
- **Intent:** `INT-1`
- **Source issue:** `quick-fix-overhead`
- **Landed:** 2026-09-28

### finish refuses and passes nothing on any unmet condition

- **Scenario id:** `QFO-5`
- **Intent:** `INT-1`
- **Source issue:** `quick-fix-overhead`
- **Landed:** 2026-09-28

### the command and skill teach the two verbs

- **Scenario id:** `QFO-6`
- **Intent:** `INT-1`
- **Source issue:** `quick-fix-overhead`
- **Landed:** 2026-09-28

### a re-run costs at most twice R1

- **Scenario id:** `QFO-7`
- **Intent:** `INT-1`
- **Source issue:** `quick-fix-overhead`
- **Landed:** 2026-09-28

### the breakdown gives calls and tokens by step

- **Scenario id:** `QFO-8`
- **Intent:** `INT-1`
- **Source issue:** `quick-fix-overhead`
- **Landed:** 2026-09-28

### Given a project whose decisions ledger holds entries, then quick-fix start lists each live entry's slug and first decision sentence, newest first and capped with a count of the rest, leaves out superseded entries, and adds nothing when the ledger is empty.

- **Scenario id:** `SD-1`
- **Intent:** `INT-1`
- **Source issue:** `quick-fix-shows-settled-decisions`
- **Landed:** 2026-10-04

### Given `quick-fix start --labels auth` on a small, contained change, then the manifest records `labels: [auth]` and the approach is not a quick fix.

- **Scenario id:** `QFL-1`
- **Intent:** `INT-1`
- **Source issue:** `quick-fix-start-drops-labels`
- **Landed:** 2026-10-01

### Given that change, then `compass check` treats the human sign-off guardrail as applicable.

- **Scenario id:** `QFL-2`
- **Intent:** `INT-1`
- **Source issue:** `quick-fix-start-drops-labels`
- **Landed:** 2026-10-01

### Given no `--labels`, then the labels are empty and the result is unchanged; a malformed label is refused before anything is written.

- **Scenario id:** `QFL-3`
- **Intent:** `INT-1`
- **Source issue:** `quick-fix-start-drops-labels`
- **Landed:** 2026-10-01

### Given HOME points at an empty directory, when the quick-fix verb tests run, then every finish test commits and passes

- **Scenario id:** `QGI-1`
- **Intent:** `INT-1`
- **Source issue:** `quick-fix-tests-need-a-git-identity`
- **Landed:** 2026-09-28

### Given two Compass quick-fix sessions and their no-framework pairs from the 4 October run, then the breakdown is on record: resident load per request, each source's share of the tokens read, and the request counts, with how they were measured and what they do not show.

- **Scenario id:** `TB-1`
- **Intent:** `INT-1`
- **Source issue:** `quick-fix-token-breakdown`
- **Landed:** 2026-10-04

### Given the plugin installed under a path that contains a space, then each of the four hook commands in hooks.json runs its own script, because each quotes the plugin root.

- **Scenario id:** `HQ-1`
- **Intent:** `INT-1`
- **Source issue:** `quote-the-plugin-root-in-hooks`
- **Landed:** 2026-10-04

### an unparsed span is a failure

- **Scenario id:** `TRC-1`
- **Intent:** `INT-1`
- **Source issue:** `quote-verifier-rejects-unparsed`
- **Landed:** 2026-08-12

### update refuses to record an unparsed span

- **Scenario id:** `TRC-2`
- **Intent:** `INT-1`
- **Source issue:** `quote-verifier-rejects-unparsed`
- **Landed:** 2026-08-12

### a well-formed span still verifies

- **Scenario id:** `TRC-3`
- **Intent:** `INT-1`
- **Source issue:** `quote-verifier-rejects-unparsed`
- **Landed:** 2026-08-12

### A new file with prose leaves the reach test green

- **Scenario id:** `RCM-1`
- **Intent:** `INT-1`
- **Source issue:** `reach-counts-move-with-every-test`
- **Landed:** 2026-09-25

### A new file with no prose fails the reach test, naming the rule

- **Scenario id:** `RCM-2`
- **Intent:** `INT-1`
- **Source issue:** `reach-counts-move-with-every-test`
- **Landed:** 2026-09-25

### A widened reach fails the reach test, naming the rule

- **Scenario id:** `RCM-3`
- **Intent:** `INT-1`
- **Source issue:** `reach-counts-move-with-every-test`
- **Landed:** 2026-09-25

### the Summary should be the first thing a cold reader meets

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### the Summary should carry exactly the three named fields

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### Summary length should scale with the route

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### a filled Summary should be a condition of leaving Clarify

- **Scenario id:** `TRC-A6`
- **Intent:** `INT-1`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### the self-review should treat the Summary fields as placeholders to scan

- **Scenario id:** `TRC-F2`
- **Intent:** `INT-1`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### A corrected reading is logged when the approach does not move

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `reassessment-log-drops-reading-only-changes`
- **Landed:** 2026-08-30

### The reason is not discarded

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `reassessment-log-drops-reading-only-changes`
- **Landed:** 2026-08-30

### a test id whose file does not exist should be reported

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `record-keeping-integrity`
- **Landed:** 2026-08-03

### a test id naming a function the file does not contain should be reported

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `record-keeping-integrity`
- **Landed:** 2026-08-03

### a test id that resolves should pass

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `record-keeping-integrity`
- **Landed:** 2026-08-03

### Given a record holding a .gitignore or a submodule entry, then sync still records every file or refuses the submodule, a restore that copies nothing says why, and the clone runs with LFS filters off.

- **Scenario id:** `RG-1`
- **Intent:** `INT-1`
- **Source issue:** `record-sync-gaps`
- **Landed:** 2026-10-03

### Given the maintainer's choices of 5 October on issues #100, #105, #116 and #121, When the decisions ledger is read, Then each has an entry by jed72 with its decision, its reason and the issue it answers

- **Scenario id:** `TD-1`
- **Intent:** `INT-1`
- **Source issue:** `record-triage-decisions`
- **Landed:** 2026-10-05

### A red for a project module not yet written is recorded as an import red

- **Scenario id:** `RSF-1`
- **Intent:** `INT-1`
- **Source issue:** `red-for-a-module-not-yet-written`
- **Landed:** 2026-09-25

### An ordinary failing assertion is still a red

- **Scenario id:** `RSF-2`
- **Intent:** `INT-1`
- **Source issue:** `red-for-a-module-not-yet-written`
- **Landed:** 2026-09-25

### Any other collection error is refused

- **Scenario id:** `RSF-3`
- **Intent:** `INT-1`
- **Source issue:** `red-for-a-module-not-yet-written`
- **Landed:** 2026-09-25

### A run that hides a collection error, or where no test failed, is refused; the skill names the import red

- **Scenario id:** `RSF-4`
- **Intent:** `INT-1`
- **Source issue:** `red-for-a-module-not-yet-written`
- **Landed:** 2026-09-25

### Given an issue whose manifest has no scenario X, when tdd-red or tdd-green runs with scenario X, then it is refused, writes no record, and names compass scenario add.

- **Scenario id:** `US-1`
- **Intent:** `INT-1`
- **Source issue:** `red-for-an-unknown-scenario`
- **Landed:** 2026-10-03

### An unstamped red written since the cutoff does not unlock

- **Scenario id:** `RIC-1`
- **Intent:** `INT-1`
- **Source issue:** `red-record-identity-cutoff`
- **Landed:** 2026-09-24

### compass init declares the cutoff for a new project

- **Scenario id:** `RIC-5`
- **Intent:** `INT-1`
- **Source issue:** `red-record-identity-cutoff`
- **Landed:** 2026-09-24

### py.test is recognised and gets the pytest rule

- **Scenario id:** `DSW-1`
- **Intent:** `INT-1`
- **Source issue:** `red-through-a-shell-wrapper`
- **Landed:** 2026-09-25

### A bash -c pipeline around pytest is judged by pytest's report

- **Scenario id:** `DSW-2`
- **Intent:** `INT-1`
- **Source issue:** `red-through-a-shell-wrapper`
- **Landed:** 2026-09-25

### A runner that writes no report is marked exit-code

- **Scenario id:** `DSW-3`
- **Intent:** `INT-1`
- **Source issue:** `red-through-a-shell-wrapper`
- **Landed:** 2026-09-25

### A silent red naming no test is refused

- **Scenario id:** `RWT-1`
- **Intent:** `INT-1`
- **Source issue:** `red-without-a-test-unlocks-edits`
- **Landed:** 2026-09-27

### Reds that print or name a declared test still record

- **Scenario id:** `RWT-2`
- **Intent:** `INT-1`
- **Source issue:** `red-without-a-test-unlocks-edits`
- **Landed:** 2026-09-27

### Given a feature issue with its acceptance criteria registered and no technical design, When compass next runs, Then it reports Plan; and given an initiative issue with its criteria registered and no requirements review, Then it reports Refine

- **Scenario id:** `TRC-001`
- **Intent:** `INT-1`
- **Source issue:** `refine-never-clears-on-a-feature`
- **Landed:** 2026-10-02

### No shipped document teaches a flag the CLI rejects

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `reframe-is-documented-but-does-not-exist`
- **Landed:** 2026-08-30

### Nothing promises the retired spelling still works

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `reframe-is-documented-but-does-not-exist`
- **Landed:** 2026-08-30

### A guard that reads no flags is refused

- **Scenario id:** `TRC-F1`
- **Intent:** `INT-1`
- **Source issue:** `reframe-is-documented-but-does-not-exist`
- **Landed:** 2026-08-30

### reframe is a banned term, bound to a pattern that flags a planted use

- **Scenario id:** `RRA-1`
- **Intent:** `INT-1`
- **Source issue:** `reframe-to-reassessment`
- **Landed:** 2026-09-30

### No scanned surface uses reframe except a marked compatibility line

- **Scenario id:** `RRA-2`
- **Intent:** `INT-1`
- **Source issue:** `reframe-to-reassessment`
- **Landed:** 2026-09-30

### retro, flow, approach evaluate and the stop hook say re-assessment

- **Scenario id:** `RRA-3`
- **Intent:** `INT-1`
- **Source issue:** `reframe-to-reassessment`
- **Landed:** 2026-09-30

### Given a branch already up to date with its base whose derived spec is stale, when compass issue refresh-spec runs, then it commits the re-derived spec with a message that names no merge

- **Scenario id:** `TRC-001`
- **Intent:** `INT-1`
- **Source issue:** `refresh-spec-message-when-up-to-date`
- **Landed:** 2026-10-06

### Given the refusal registry, when each reason code is rendered with fix

- **Scenario id:** `RTP-1`
- **Intent:** `INT-1`
- **Source issue:** `refusal-template`
- **Landed:** 2026-09-29

### Given every rendered `Fix:` line, then none suggests dropping `--scena

- **Scenario id:** `RTP-2`
- **Intent:** `INT-1`
- **Source issue:** `refusal-template`
- **Landed:** 2026-09-29

### Given each cell of the hook failure matrix, when the hook refuses, the

- **Scenario id:** `RTP-3`
- **Intent:** `INT-1`
- **Source issue:** `refusal-template`
- **Landed:** 2026-09-29

### Given the registry, then `docs/refusal-codes.md` lists every code with

- **Scenario id:** `RTP-4`
- **Intent:** `INT-1`
- **Source issue:** `refusal-template`
- **Landed:** 2026-09-29

### no printed string names a retired word

- **Scenario id:** `RTP-5`
- **Intent:** `INT-1`
- **Source issue:** `refusal-template`
- **Landed:** 2026-09-29

### the measured eval run is compared with the baseline

- **Scenario id:** `RTP-6`
- **Intent:** `INT-1`
- **Source issue:** `refusal-template`
- **Landed:** 2026-09-29

### Given a python3 that fails and prints something, when the hook refuses

- **Scenario id:** `RTF-1`
- **Intent:** `INT-1`
- **Source issue:** `refusal-template-follow-ups`
- **Landed:** 2026-09-29

### Given the registry's Fix lines, then `python-missing` says 3.10+, each

- **Scenario id:** `RTF-2`
- **Intent:** `INT-1`
- **Source issue:** `refusal-template-follow-ups`
- **Landed:** 2026-09-29

### Given a template parameter longer than 20 words at run time, when a re

- **Scenario id:** `RTF-3`
- **Intent:** `INT-1`
- **Source issue:** `refusal-template-follow-ups`
- **Landed:** 2026-09-29

### Given the guards, then the call-site test finds a code only as an argu

- **Scenario id:** `RTF-4`
- **Intent:** `INT-1`
- **Source issue:** `refusal-template-follow-ups`
- **Landed:** 2026-09-29

### no script prints triage, and the scan covers scripts

- **Scenario id:** `RTF-5`
- **Intent:** `INT-1`
- **Source issue:** `refusal-template-follow-ups`
- **Landed:** 2026-09-29

### Given the texts, then `docs/refusal-codes.md` does not claim the CLI r

- **Scenario id:** `RTF-6`
- **Intent:** `INT-1`
- **Source issue:** `refusal-template-follow-ups`
- **Landed:** 2026-09-29

### A recorded rehearsal passes whatever words surround it

- **Scenario id:** `RGN-1`
- **Intent:** `INT-1`
- **Source issue:** `rehearsal-guard-fails-on-a-neighbour`
- **Landed:** 2026-09-11

### every version location carries 3.3.0 and the suite is green

- **Scenario id:** `TRC-001`
- **Intent:** `INT-1`
- **Source issue:** `release-3-3-0`
- **Landed:** 

### every published surface reports 5.0.0

- **Scenario id:** `REL-1`
- **Intent:** `INT-1`
- **Source issue:** `release-5-0-0`
- **Landed:** 2026-09-24

### the removal guard accepts a later major

- **Scenario id:** `REL-2`
- **Intent:** `INT-1`
- **Source issue:** `release-5-0-0`
- **Landed:** 2026-09-24

### Given the release intends 5.1.0, When the version tests run, Then every version location reads 5.1.0

- **Scenario id:** `TRC-001`
- **Intent:** `INT-1`
- **Source issue:** `release-5-1-0`
- **Landed:** 2026-10-02

### Given the release intends 5.2.0, When the version tests run, Then every version location reads 5.2.0

- **Scenario id:** `TRC-001`
- **Intent:** `INT-1`
- **Source issue:** `release-5-2-0`
- **Landed:** 2026-10-02

### Given Compass 5.3.0, then every location that carries the version says 5.3.0

- **Scenario id:** `RL-A`
- **Intent:** `INT-1`
- **Source issue:** `release-5-3-0`
- **Landed:** 2026-10-03

### Given the expected version is 5.4.0, then every published location carries 5.4.0.

- **Scenario id:** `RL-A`
- **Intent:** `INT-1`
- **Source issue:** `release-5-4-0`
- **Landed:** 2026-10-03

### Given the release is 5.5.0, then VERSION, the CLI, both plugin manifests and the install smoke test all say 5.5.0 and the version guard agrees.

- **Scenario id:** `RV-1`
- **Intent:** `INT-1`
- **Source issue:** `release-5-5-0`
- **Landed:** 2026-10-04

### Given the release procedure's seven version locations and the version test's expected version, When each is bumped to 5.6.0, Then the version consistency and coverage tests pass and compass --version prints 5.6.0

- **Scenario id:** `RL-1`
- **Intent:** `INT-1`
- **Source issue:** `release-5-6-0`
- **Landed:** 2026-10-05

### the repo check must ignore files git does not track

- **Scenario id:** `SCN-01`
- **Intent:** `INT-1`
- **Source issue:** `release-blockers-2026-08`
- **Landed:** 2026-08-13

### enforcement must not switch itself off based on the checkout path

- **Scenario id:** `SCN-02`
- **Intent:** `INT-1`
- **Source issue:** `release-blockers-2026-08`
- **Landed:** 2026-08-13

### a seeded worktree must not inherit another builder's red

- **Scenario id:** `SCN-03`
- **Intent:** `INT-1`
- **Source issue:** `release-blockers-2026-08`
- **Landed:** 2026-08-13

### a BDD run must record which scenarios it actually bound

- **Scenario id:** `SCN-04`
- **Intent:** `INT-1`
- **Source issue:** `release-blockers-2026-08`
- **Landed:** 2026-08-13

### a Spike route must still report an owed backfill

- **Scenario id:** `SCN-10`
- **Intent:** `INT-1`
- **Source issue:** `release-blockers-2026-08`
- **Landed:** 2026-08-13

### The examples check names the file that exists

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `release-gate-greps-the-old-manifest-filename`
- **Landed:** 2026-08-30

### A check that cannot pass is refused

- **Scenario id:** `TRC-F1`
- **Intent:** `INT-1`
- **Source issue:** `release-gate-greps-the-old-manifest-filename`
- **Landed:** 2026-08-30

### the release script packages a tarball on this platform

- **Scenario id:** `SCN-001`
- **Intent:** `INT-1`
- **Source issue:** `release-script-portable-tar`
- **Landed:** 2026-08-03

### dev-only state is excluded without stripping the worked examples

- **Scenario id:** `SCN-002`
- **Intent:** `INT-1`
- **Source issue:** `release-script-portable-tar`
- **Landed:** 2026-08-03

### untracked local files never ship

- **Scenario id:** `SCN-003`
- **Intent:** `INT-1`
- **Source issue:** `release-script-portable-tar`
- **Landed:** 2026-08-03

### Given the repository now lives at ayeo-io/compass, then no tracked file names the old address as the repository, the plugin manifests name the new one, and the marketplace owner is the organisation.

- **Scenario id:** `RA-1`
- **Intent:** `INT-1`
- **Source issue:** `repoint-to-ayeo-io`
- **Landed:** 2026-10-04

### Given this repository's .compass/config.yml, When an issue on the regular or full approach is evaluated, Then no checkpoint waits for a person

- **Scenario id:** `RA-1`
- **Intent:** `INT-1`
- **Source issue:** `repository-autonomy`
- **Landed:** 2026-10-05

### A green after a script edit is not a re-run

- **Scenario id:** `RSE-1`
- **Intent:** `INT-1`
- **Source issue:** `rerun-check-misses-script-changes`
- **Landed:** 2026-09-25

### A green with nothing changed is still a re-run

- **Scenario id:** `RSE-2`
- **Intent:** `INT-1`
- **Source issue:** `rerun-check-misses-script-changes`
- **Landed:** 2026-09-25

### Resident text at or under 900 words

- **Scenario id:** `RFD-1`
- **Intent:** `INT-1`
- **Source issue:** `resident-footprint-diet`
- **Landed:** 2026-09-28

### Triggering tests pass unchanged

- **Scenario id:** `RFD-2`
- **Intent:** `INT-1`
- **Source issue:** `resident-footprint-diet`
- **Landed:** 2026-09-28

### Given a quick fix resumed by a session that did not start it, then the resume command names the red and quick-fix finish as the way to land it, and quick-fix finish lands it in one call with no start record.

- **Scenario id:** `RQ-1`
- **Intent:** `INT-1`
- **Source issue:** `resumed-quick-fix-lands-in-one-command`
- **Landed:** 2026-10-04

### the archive sweep has no in-flight exemption

- **Scenario id:** `TRC-1`
- **Intent:** `INT-1`
- **Source issue:** `retire-route-md-alias`
- **Landed:** 2026-08-07

### an issue with only delivery-approach.md passes the pre-tool hook

- **Scenario id:** `TRC-2`
- **Intent:** `INT-1`
- **Source issue:** `retire-route-md-alias`
- **Landed:** 2026-08-07

### Given a retired_in_output block in governance/terminology.yml, When the printed-output guard builds its patterns, Then it scans for every name in the block and holds no hand-written list

- **Scenario id:** `TRC-001`
- **Intent:** `INT-1`
- **Source issue:** `retired-terms-from-terminology`
- **Landed:** 2026-10-05

### Given one judgement re-assessment and one policy correction, each moving standard to expedition, when compass retro runs, then it reports 1 up and 0 down

- **Scenario id:** `TRC-001`
- **Intent:** `INT-1`
- **Source issue:** `retro-counts-policy-corrections`
- **Landed:** 2026-09-30

### Given one manifest under .compass/work written as a YAML list, When compass retro runs, Then it exits 0, reports the other issues and names the skipped manifest

- **Scenario id:** `RL-1`
- **Intent:** `INT-1`
- **Source issue:** `retro-skips-list-manifest`
- **Landed:** 2026-10-06

### Given re-assessments recorded under retired and current route names, when compass retro runs, then each transition appears once under its current names with the counts summed.

- **Scenario id:** `RT-1`
- **Intent:** `INT-1`
- **Source issue:** `retro-transitions-split-by-old-names`
- **Landed:** 2026-10-03

### Current route names count up and down, and weigh the same as retired ones

- **Scenario id:** `RWC-1`
- **Intent:** `INT-1`
- **Source issue:** `retro-weighs-only-retired-route-names`
- **Landed:** 2026-09-25

### A route with no weight is unweighed, not sideways

- **Scenario id:** `RWC-2`
- **Intent:** `INT-1`
- **Source issue:** `retro-weighs-only-retired-route-names`
- **Landed:** 2026-09-25

### Retro prints no retired name for assessment

- **Scenario id:** `RWC-3`
- **Intent:** `INT-1`
- **Source issue:** `retro-weighs-only-retired-route-names`
- **Landed:** 2026-09-25

### Given a landed issue whose files a review fix changes, when its green is re-recorded and ship-commit runs for it with nothing staged, then land_commit names the fix commit and compass check passes; without the new green it is refused.

- **Scenario id:** `RB-1`
- **Intent:** `INT-1`
- **Source issue:** `review-fix-rebinds-land-commit`
- **Landed:** 2026-10-03

### Given an issue whose review page matched its manifest, When a verb that writes the manifest leaves the page stale, Then the verb prints one line naming compass issue dashboard, and prints none when the page is still current or there is no page

- **Scenario id:** `TRC-001`
- **Intent:** `INT-1`
- **Source issue:** `review-page-stale-reminder`
- **Landed:** 2026-10-05

### Given compass policy review-rules --changed-files hooks/pre-tool.sh, then it prints each rule whose patterns match that file, including the hook rules, and no rule scoped only to templates or the adopter's reading path.

- **Scenario id:** `RV-A`
- **Intent:** `INT-1`
- **Source issue:** `review-rules-as-data`
- **Landed:** 2026-10-02

### Given --rules PATH, then it reads that file instead of the project's, so CI can pass the base branch's copy. Given a project with no rules file, then it says so and exits 0. It reads the project's own governance/, never the shipped copy.

- **Scenario id:** `RV-B`
- **Intent:** `INT-1`
- **Source issue:** `review-rules-as-data`
- **Landed:** 2026-10-02

### Given compass policy lint and a rules file with a malformed or repeated id, an unknown enforces id, no patterns, a rule over 150 words or no incident, then it fails and names the rule and the field.

- **Scenario id:** `RV-C`
- **Intent:** `INT-1`
- **Source issue:** `review-rules-as-data`
- **Landed:** 2026-10-02

### Given agents/reviewer.md, then it says to run compass policy review-rules --changed-files, to report a finding under the RR- id it breaks, and not to flag what a rule's allowed list permits.

- **Scenario id:** `RV-D`
- **Intent:** `INT-1`
- **Source issue:** `review-rules-as-data`
- **Landed:** 2026-10-02

### Given governance/review-rules.yml, then it holds at least ten rules, each with an incident naming a pull request, issue or commit a reader can open.

- **Scenario id:** `RV-E`
- **Intent:** `INT-1`
- **Source issue:** `review-rules-as-data`
- **Landed:** 2026-10-02

### Given the verb surface, then policy review-rules is in verb_help.py, the README's CLI block and compass policy --help. The top-level verb set does not change.

- **Scenario id:** `RV-F`
- **Intent:** `INT-1`
- **Source issue:** `review-rules-as-data`
- **Landed:** 2026-10-02

### Given the review workflow, when it is read, then the review returns its verdict as structured output and a later step fails the job unless the verdict is PASS

- **Scenario id:** `TRC-001`
- **Intent:** `INT-1`
- **Source issue:** `review-verdict`
- **Landed:** 2026-10-01

### Given a non-UTF-8 file pinned by blob hash and path, when the gate scans the tree, then it passes the file's content; given any change to the file, a UTF-8 file, a path, or a stale pin, then the gate still fails or reports

- **Scenario id:** `TRC-001`
- **Intent:** `INT-1`
- **Source issue:** `rival-gate-new-key`
- **Landed:** 2026-10-07

### Given the tracked tree, when the gate scans every tracked file's text and every tracked path against the committed hashes, then it finds no rival name.

- **Scenario id:** `RN-1`
- **Intent:** `INT-1`
- **Source issue:** `rival-names-never-committed`
- **Landed:** 2026-10-04

### Given a name planted in a tracked file, a tracked path, a commit message and a pull request body, then the gate fails on each, and its output gives the place but never the name.

- **Scenario id:** `RN-2`
- **Intent:** `INT-1`
- **Source issue:** `rival-names-never-committed`
- **Landed:** 2026-10-04

### Given the order file's own name, which ends with one rival's alias, then the gate passes it; the same scan without the allowed compound fails, so the exemption is what passes it.

- **Scenario id:** `RN-3`
- **Intent:** `INT-1`
- **Source issue:** `rival-names-never-committed`
- **Landed:** 2026-10-04

### Given no names key, when the harness is asked for a rival condition, then it stops with a message naming the missing key, and bare and compass runs still work; given a key, a rival condition builds its copy from the key's pinned source.

- **Scenario id:** `RN-4`
- **Intent:** `INT-1`
- **Source issue:** `rival-names-never-committed`
- **Landed:** 2026-10-04

### Given a record path holding names and a project that configures a names key, when the record syncs, then the record holds codes only and the gate passes over the synced copy; when the configured key is missing, sync refuses with exit 2 and sends nothing.

- **Scenario id:** `RN-5`
- **Intent:** `INT-1`
- **Source issue:** `rival-names-never-committed`
- **Landed:** 2026-10-04

### Given a pull request, then CI runs the gate over the text of its commit messages, title and body.

- **Scenario id:** `RN-6`
- **Intent:** `INT-1`
- **Source issue:** `rival-names-never-committed`
- **Landed:** 2026-10-04

### Given CLAUDE.md, the house rules and the plugin's writing guidance, then each states the rule and the code convention.

- **Scenario id:** `RN-7`
- **Intent:** `INT-1`
- **Source issue:** `rival-names-never-committed`
- **Landed:** 2026-10-04

### Given the key, then the committed hash file is exactly what the generator writes from it, so the gate covers every entry in the key.

- **Scenario id:** `RN-8`
- **Intent:** `INT-1`
- **Source issue:** `rival-names-never-committed`
- **Landed:** 2026-10-04

### Given the published comparison runs after the sweep, then every number in them is unchanged and each carries one line saying rival products appear as codes and the maintainer holds the key.

- **Scenario id:** `RN-9`
- **Intent:** `INT-1`
- **Source issue:** `rival-names-never-committed`
- **Landed:** 2026-10-04

### Given the rules step's file count does not match, then its message names the cause it can tell apart: a missing count, the 3,000-file limit, or a count from before a newer push

- **Scenario id:** `RD-A`
- **Intent:** `INT-1`
- **Source issue:** `rules-step-count-message`
- **Landed:** 2026-10-02

### Given a pull request with more changed files than the files API lists, then the review's rules step fails rather than reviewing with a partial rule set

- **Scenario id:** `RC-A`
- **Intent:** `INT-1`
- **Source issue:** `rules-step-file-cap`
- **Landed:** 2026-10-02

### Given a run whose sessions report their cost, then each session gets the money left as its budget, and the run stops with exit 4 once the total reaches the cost ceiling the policy sets.

- **Scenario id:** `RC-1`
- **Intent:** `INT-1`
- **Source issue:** `run-cost-ceiling`
- **Landed:** 2026-10-03

### Given the demo quick fix, then a manually started workflow runs compass run on it in CI, authenticated by federation with no stored key, and keeps the run record.

- **Scenario id:** `RD-1`
- **Intent:** `INT-1`
- **Source issue:** `run-demo-in-ci`
- **Landed:** 2026-10-03

### Given an interrupted run, a run whose last session finishes the stage but breaks the runs key, or a manifest with an empty runs key, then the run record's outcome and reason match the exit code, and a run starts on the empty key.

- **Scenario id:** `RRE-1`
- **Intent:** `INT-1`
- **Source issue:** `run-record-edges`
- **Landed:** 2026-10-03

### Given an environment variable that names one issue and a pointer that names another, then the pre-tool hook judges an edit by the issue the variable names.

- **Scenario id:** `SI-A`
- **Intent:** `INT-1`
- **Source issue:** `run-session-issue`
- **Landed:** 2026-10-03

### Given the variable, then a CLI command run without an explicit issue works on that issue, and an explicit issue still wins.

- **Scenario id:** `SI-B`
- **Intent:** `INT-1`
- **Source issue:** `run-session-issue`
- **Landed:** 2026-10-03

### Given the variable names no issue or a path, then the hook and the CLI refuse it as they refuse a bad pointer, without falling back to the pointer.

- **Scenario id:** `SI-C`
- **Intent:** `INT-1`
- **Source issue:** `run-session-issue`
- **Landed:** 2026-10-03

### Given compass run, then every session it starts has the variable set to the run's issue, and the pointer file is unchanged by the run.

- **Scenario id:** `SI-D`
- **Intent:** `INT-1`
- **Source issue:** `run-session-issue`
- **Landed:** 2026-10-03

### Given the variable, then the post-tool and stop hooks, the receipt and the status line read the same issue the pre-tool hook does.

- **Scenario id:** `SI-E`
- **Intent:** `INT-1`
- **Source issue:** `run-session-issue`
- **Landed:** 2026-10-03

### Given compass run, then each session is allowed the file tools, Skill and the compass CLI, is denied landing, pushing, merging and starting another run, and the run record keeps each session's last message.

- **Scenario id:** `ST-1`
- **Intent:** `INT-1`
- **Source issue:** `run-session-tools`
- **Landed:** 2026-10-03

### the entry states the primary-record rule and defines what a primary record is

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-1`
- **Source issue:** `s9-primary-record`
- **Landed:** 2026-08-12

### the entry carries the ADR-013 worked example and warns the nearest document is often a summary

- **Scenario id:** `TRC-C2`
- **Intent:** `INT-1`
- **Source issue:** `s9-primary-record`
- **Landed:** 2026-08-12

### Given the compass schema, when a test walks every node, then each node has a non-empty description

- **Scenario id:** `TRC-001`
- **Intent:** `INT-1`
- **Source issue:** `schema-descriptions`
- **Landed:** 2026-10-08

### Given the repository root and .github, When a contributor looks for a security policy, a code of conduct and issue templates, Then SECURITY.md points to GitHub private vulnerability reporting and names the supported version, CODE_OF_CONDUCT.md adopts the Contributor Covenant 2.1 with conduct@ayeo.io as the contact, and bug and feature templates ask for the Compass version

- **Scenario id:** `CF-1`
- **Intent:** `INT-1`
- **Source issue:** `security-policy-and-templates`
- **Landed:** 2026-10-05

### Given another test's pytest run has made a pytest-cache-files folder inside a scenario seed, When the scenario-file walks in tests/test_eval_scenarios.py list the files to scan, Then they skip that folder and .pytest_cache, so a folder deleted mid-walk cannot fail them

- **Scenario id:** `SW-1`
- **Intent:** `INT-1`
- **Source issue:** `seed-walk-skips-pytest-cache`
- **Landed:** 2026-10-04

### a session in a Compass project starts with the contract

- **Scenario id:** `SB-A1`
- **Intent:** `INT-1`
- **Source issue:** `session-bootstrap`
- **Landed:** 2026-08-27

### the contract is short enough to always carry

- **Scenario id:** `SB-A2`
- **Intent:** `INT-1`
- **Source issue:** `session-bootstrap`
- **Landed:** 2026-08-27

### the contract is silent outside a Compass project

- **Scenario id:** `SB-A3`
- **Intent:** `INT-1`
- **Source issue:** `session-bootstrap`
- **Landed:** 2026-08-27

### a source install registers the same hook

- **Scenario id:** `SB-D1`
- **Intent:** `INT-1`
- **Source issue:** `session-bootstrap`
- **Landed:** 2026-08-27

### the portability mapping names the new adapter feature

- **Scenario id:** `SB-D2`
- **Intent:** `INT-1`
- **Source issue:** `session-bootstrap`
- **Landed:** 2026-08-27

### a source install enforces what the plugin enforces

- **Scenario id:** `SB-D3`
- **Intent:** `INT-1`
- **Source issue:** `session-bootstrap`
- **Landed:** 2026-08-27

### Given issues whose records carry a session id and that session's transcript, when `compass retro --compliance` runs, then each judge behaviour gets sessions, pass, fail, undecided, a pass rate over decided sessions and a 95% Wilson interval, and each failing session is named by issue id and tool-call index; `--json` prints the same; `--days N` and `--issue` narrow it.

- **Scenario id:** `CS-1`
- **Intent:** `INT-1`
- **Source issue:** `session-compliance`
- **Landed:** 2026-10-06

### Given a behaviour failing in three or more distinct issues in the window, when the report runs, then it writes a pending lesson with `source: compliance` naming the behaviour and the issues, and nothing takes effect until `compass lesson accept`.

- **Scenario id:** `CS-10`
- **Intent:** `INT-1`
- **Source issue:** `session-compliance`
- **Landed:** 2026-10-06

### Given a transcript that no issue's records name, when the report runs, then it is counted as unmatched and never assigned to an issue by time or path.

- **Scenario id:** `CS-2`
- **Intent:** `INT-1`
- **Source issue:** `session-compliance`
- **Landed:** 2026-10-06

### Given a transcript with tool calls, results and a hook refusal, when the adapter reads it, then it yields the run-record shape the judge reads (tool calls with name, input, output, error flag), and no other module reads the transcript format; a session that is not Claude Code is reported as `not-claude-code`.

- **Scenario id:** `CS-3`
- **Intent:** `INT-1`
- **Source issue:** `session-compliance`
- **Landed:** 2026-10-06

### Given a session in which the pre-tool hook refused a write to a path and a later call writes that path through a shape the hook does not classify (for example `python3 script.py`), when it is scored, then the behaviour for writing around a hook refusal fails at that call's index; with no later write, it passes.

- **Scenario id:** `CS-5`
- **Intent:** `INT-1`
- **Source issue:** `session-compliance`
- **Landed:** 2026-10-06

### Given a transcript seeded with a unique secret string, when the report runs in text and JSON, then the string appears in no output and no file the command writes.

- **Scenario id:** `CS-6`
- **Intent:** `INT-1`
- **Source issue:** `session-compliance`
- **Landed:** 2026-10-06

### Given the report, then `compass check` does not read it and no gate depends on it.

- **Scenario id:** `CS-9`
- **Intent:** `INT-1`
- **Source issue:** `session-compliance`
- **Landed:** 2026-10-06

### Given a landed issue, when compass issue diagnose runs, then it lists each stage the route ran, with the record that shows it ran and its path, and each gate with its status and evidence.

- **Scenario id:** `SD-A`
- **Intent:** `INT-1`
- **Source issue:** `session-diagnosis`
- **Landed:** 2026-10-02

### Given an issue's records, then the report gives a timeline of every dated record: reds, greens, subtask dispatches, review rounds, reassessments, hook refusals and failed checks from .compass/interruptions.log, and the landing, oldest first, each with its path.

- **Scenario id:** `SD-B`
- **Intent:** `INT-1`
- **Source issue:** `session-diagnosis`
- **Landed:** 2026-10-02

### Given a stage the route ran that has no record, a red dated after its scenario's green, a green in an issue with no red at all, a review round that failed, or a landed issue's gate not passed, then the report lists each as a deviation, naming the scenario, stage or gate. A solo breakdown, a spike's missing red and an unfinished issue's later stages are not deviations.

- **Scenario id:** `SD-C`
- **Intent:** `INT-1`
- **Source issue:** `session-diagnosis`
- **Landed:** 2026-10-02

### Given any issue, then the report ends with the questions its records cannot answer, including edits the hook refused, time between records, and what was said in the session.

- **Scenario id:** `SD-D`
- **Intent:** `INT-1`
- **Source issue:** `session-diagnosis`
- **Landed:** 2026-10-02

### Given the verb surface, then issue diagnose is in verb_help.py, the README's CLI block and compass issue --help. The top-level verb set does not change.

- **Scenario id:** `SD-E`
- **Intent:** `INT-1`
- **Source issue:** `session-diagnosis`
- **Landed:** 2026-10-02

### Given the session table, then concurrent writes keep every record, stale records are dropped when it is written, the table is ignored by git in any project, and a pointer-moved refusal is counted against the session's own issue.

- **Scenario id:** `ST2-1`
- **Intent:** `INT-1`
- **Source issue:** `session-table-tidy`
- **Landed:** 2026-10-03

### Given a root eval run with --session-user, When a run changes a folder's mode, installs a job, or leaves an oversized file, or a call is held and the kill-all fails, Then the record or the next run's check shows it, and the call's readers and pipes are closed

- **Scenario id:** `SF-1`
- **Intent:** `INT-1`
- **Source issue:** `session-user-follow-ups`
- **Landed:** 2026-10-06

### set-status names the issue in both outcomes

- **Scenario id:** `SSN-A1`
- **Intent:** `INT-1`
- **Source issue:** `set-status-does-not-name-the-issue`
- **Landed:** 2026-08-26

### a landed_by entry still reads its own key

- **Scenario id:** `SSN-A2`
- **Intent:** `INT-1`
- **Source issue:** `set-status-does-not-name-the-issue`
- **Landed:** 2026-08-26

### A reason on any status leaves the manifest valid

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `set-status-reason-writes-an-invalid-manifest`
- **Landed:** 2026-08-30

### The recorded reason says which transition it belongs to

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `set-status-reason-writes-an-invalid-manifest`
- **Landed:** 2026-08-30

### A key the schema forbids is refused

- **Scenario id:** `TRC-F1`
- **Intent:** `INT-1`
- **Source issue:** `set-status-reason-writes-an-invalid-manifest`
- **Landed:** 2026-08-30

### Given code_globs in compass.yml, the hook blocks a matching path as for the old file; compass.yml wins; an unreadable file blocks naming the file; no file allows an unlisted path

- **Scenario id:** `SH-1`
- **Intent:** `INT-1`
- **Source issue:** `settings-reader-hook`
- **Landed:** 2026-10-06

### Given a project with neither settings file, the hook starts no Python for the code_globs read; the names of the two files live in one allow-listed helper pinned equal to project_settings

- **Scenario id:** `SH-10`
- **Intent:** `INT-1`
- **Source issue:** `settings-reader-hook`
- **Landed:** 2026-10-06

### Given initialised in state.yml or only the old file, the first refusal says who initialised the project; a broken record adds nothing

- **Scenario id:** `SH-2`
- **Intent:** `INT-1`
- **Source issue:** `settings-reader-hook`
- **Landed:** 2026-10-06

### Given worktree root, cap or test command in compass.yml, multiagent.sh and integrate.sh read them there; old file keeps its values; compass.yml wins

- **Scenario id:** `SH-3`
- **Intent:** `INT-1`
- **Source issue:** `settings-reader-hook`
- **Landed:** 2026-10-06

### Given a new project, init writes state.yml and no .compass/config.yml; an old-file project is untouched

- **Scenario id:** `SH-4`
- **Intent:** `INT-1`
- **Source issue:** `settings-reader-hook`
- **Landed:** 2026-10-06

### Given an unreadable settings file, the refusal and its doc name the file the hook read

- **Scenario id:** `SH-5`
- **Intent:** `INT-1`
- **Source issue:** `settings-reader-hook`
- **Landed:** 2026-10-06

### Given the fold-in test, a hook or script naming the old file in any spelling, or reading it with compass.yml present, fails it

- **Scenario id:** `SH-6`
- **Intent:** `INT-1`
- **Source issue:** `settings-reader-hook`
- **Landed:** 2026-10-06

### Given the recorded hook corpus, every decision matches unchanged, and again with settings moved to compass.yml and state.yml

- **Scenario id:** `SH-7`
- **Intent:** `INT-1`
- **Source issue:** `settings-reader-hook`
- **Landed:** 2026-10-06

### Given prose that says where a setting is read or what init writes, then it matches the CLI: init writes no settings file, and a setting is read from compass.yml or the old file without one

- **Scenario id:** `SH-8`
- **Intent:** `INT-1`
- **Source issue:** `settings-reader-hook`
- **Landed:** 2026-10-06

### Given compass.yml, the scripts read only the documented paths (multiagent.worktree_root, multiagent.max_worktrees, project.test_command); the old file keeps the any-depth lookup; an unreadable settings file stops both scripts with exit 1 naming the file

- **Scenario id:** `SH-9`
- **Intent:** `INT-1`
- **Source issue:** `settings-reader-hook`
- **Landed:** 2026-10-06

### Given the same settings in `.compass/config.yml` or in `compass.yml`, when each Python reader runs (adoption mode, autonomy, drift strictness, record

- **Scenario id:** `SR-1`
- **Intent:** `INT-1`
- **Source issue:** `settings-reader-python`
- **Landed:** 2026-10-06

### Given a missing or broken settings file, when each reader runs, then it behaves as it did at 5.6.0 (the design's table: enforced, balanced or a refus

- **Scenario id:** `SR-2`
- **Intent:** `INT-1`
- **Source issue:** `settings-reader-python`
- **Landed:** 2026-10-06

### Given a project after compass init, then a state file in the .compass folder holds initialised and records_signed_since, no settings file is written, and the cutoff and the hook's explanation still read from it

- **Scenario id:** `SR-3`
- **Intent:** `INT-1`
- **Source issue:** `settings-reader-python`
- **Landed:** 2026-10-06

### Given the fold-in test, when one reader is left reading `.compass/config.yml` directly, then the test fails; and no module but `project_settings.py` 

- **Scenario id:** `SR-4`
- **Intent:** `INT-1`
- **Source issue:** `settings-reader-python`
- **Landed:** 2026-10-06

### The compatibility contracts 1 to 6 still pass, apart from any entry this change alters on purpose with its reason. 

- **Scenario id:** `SR-5`
- **Intent:** `INT-1`
- **Source issue:** `settings-reader-python`
- **Landed:** 2026-10-06

### Third-party actions in the self-check workflow are SHA-pinned

- **Scenario id:** `SCN-001`
- **Intent:** `INT-1`
- **Source issue:** `sha-pin-workflow-actions`
- **Landed:** 2026-08-13

### Given a git pre-commit hook that stages an untested copy of an issue f

- **Scenario id:** `SCF-1`
- **Intent:** `INT-1`
- **Source issue:** `ship-commit-follow-ups`
- **Landed:** 2026-09-29

### Given pre-commit set up, a tested copy staged and an untested edit on 

- **Scenario id:** `SCF-2`
- **Intent:** `INT-1`
- **Source issue:** `ship-commit-follow-ups`
- **Landed:** 2026-09-29

### Given a hook that rewrites an issue file with untested content and fai

- **Scenario id:** `SCF-3`
- **Intent:** `INT-1`
- **Source issue:** `ship-commit-follow-ups`
- **Landed:** 2026-09-29

### a green without argv is reused on its joined command

- **Scenario id:** `SCF-4`
- **Intent:** `INT-1`
- **Source issue:** `ship-commit-follow-ups`
- **Landed:** 2026-09-29

### Given names starting with `-` or holding `*` or `?`, when `ship-commit

- **Scenario id:** `SCF-5`
- **Intent:** `INT-1`
- **Source issue:** `ship-commit-follow-ups`
- **Landed:** 2026-09-29

### Given `docs/safety-contract.md`, then it states that a traced symlink 

- **Scenario id:** `SCF-6`
- **Intent:** `INT-1`
- **Source issue:** `ship-commit-follow-ups`
- **Landed:** 2026-09-29

### Given an issue whose gates have passed, when the staged copy of an iss

- **Scenario id:** `SJS-1`
- **Intent:** `INT-1`
- **Source issue:** `ship-commit-judges-the-staged-files`
- **Landed:** 2026-09-29

### Given a green recorded with one argument list, when `finish` runs with

- **Scenario id:** `SJS-2`
- **Intent:** `INT-1`
- **Source issue:** `ship-commit-judges-the-staged-files`
- **Landed:** 2026-09-29

### Given a multiagent issue whose files are already committed, when a lat

- **Scenario id:** `SJS-3`
- **Intent:** `INT-1`
- **Source issue:** `ship-commit-judges-the-staged-files`
- **Landed:** 2026-09-29

### Given a staged name holding `[`, `*` or `?`, or starting with `-`, whe

- **Scenario id:** `SJS-4`
- **Intent:** `INT-1`
- **Source issue:** `ship-commit-judges-the-staged-files`
- **Landed:** 2026-09-29

### Given a quick fix whose files the agent committed before `finish`, whe

- **Scenario id:** `SJS-5`
- **Intent:** `INT-1`
- **Source issue:** `ship-commit-judges-the-staged-files`
- **Landed:** 2026-09-29

### Given a landed quick fix, when it lands, then its start record is gone

- **Scenario id:** `SJS-6`
- **Intent:** `INT-1`
- **Source issue:** `ship-commit-judges-the-staged-files`
- **Landed:** 2026-09-29

### Given a commit message in a file, When compass ship-commit -F <file> runs with staged changes, Then it commits with that message and verifies HEAD advanced; and giving both -m and -F, or neither, is refused

- **Scenario id:** `SF-1`
- **Intent:** `INT-1`
- **Source issue:** `ship-commit-takes-a-message-file`
- **Landed:** 2026-10-04

### Given a quick fix whose working tree also changes docs/system-spec.md and docs/system-spec-archive.md, When quick-fix finish runs, Then it traces neither file and the issue's changed files are only its own

- **Scenario id:** `TRC-001`
- **Intent:** `INT-1`
- **Source issue:** `ship-restales-a-traced-living-spec`
- **Landed:** 2026-10-02

### Given a loaded machine, when a run is interrupted, then the tests wait for the session to start before signalling

- **Scenario id:** `TRC-001`
- **Intent:** `INT-1`
- **Source issue:** `sigint-tests-under-load`
- **Landed:** 2026-10-08

### Given other threads exist, when an interrupt arrives while the session is created, then the session is ended

- **Scenario id:** `TRC-001`
- **Intent:** `INT-1`
- **Source issue:** `signal-hold-all-threads`
- **Landed:** 2026-10-08

### A run is recorded under either condition

- **Scenario id:** `SPT-1`
- **Intent:** `INT-1`
- **Source issue:** `skill-prose-pressure-tests`
- **Landed:** 2026-09-27

### Given an issue slug that contains an eval scenario or behaviour id, then quick-fix start and approach evaluate refuse it before writing anything, and a slug that names none is accepted.

- **Scenario id:** `SN-1`
- **Intent:** `INT-1`
- **Source issue:** `slug-names-an-eval-scenario`
- **Landed:** 2026-10-04

### A small, contained greenfield change is a quick fix; unmapped still gets the heavier process

- **Scenario id:** `SCU-1`
- **Intent:** `INT-1`
- **Source issue:** `small-change-read-as-unmapped`
- **Landed:** 2026-09-30

### A heavier quick-fix start names the dimension that blocked it

- **Scenario id:** `SCU-2`
- **Intent:** `INT-1`
- **Source issue:** `small-change-read-as-unmapped`
- **Landed:** 2026-09-30

### Re-run of the edge-case and refactor comparison runs under Compass: no session ends without code

- **Scenario id:** `SCU-3`
- **Intent:** `INT-1`
- **Source issue:** `small-change-read-as-unmapped`
- **Landed:** 2026-09-30

### the document describes v2 behaviour

- **Scenario id:** `TRC-1`
- **Intent:** `INT-1`
- **Source issue:** `smoke-test-speaks-v2`
- **Landed:** 2026-08-12

### the document is scanned for the frozen vocabulary

- **Scenario id:** `TRC-2`
- **Intent:** `INT-1`
- **Source issue:** `smoke-test-speaks-v2`
- **Landed:** 2026-08-12

### every documented banner matches what the CLI prints

- **Scenario id:** `TRC-1`
- **Intent:** `INT-1`
- **Source issue:** `smoke-test-version-drift`
- **Landed:** 2026-08-12

### the banner uses current vocabulary

- **Scenario id:** `TRC-2`
- **Intent:** `INT-1`
- **Source issue:** `smoke-test-version-drift`
- **Landed:** 2026-08-12

### An edit under a nested .compass/ changes the source hash

- **Scenario id:** `SHN-1`
- **Intent:** `INT-1`
- **Source issue:** `source-hash-skips-nested-records`
- **Landed:** 2026-09-27

### An edit under the project root's .compass/ does not

- **Scenario id:** `SHN-2`
- **Intent:** `INT-1`
- **Source issue:** `source-hash-skips-nested-records`
- **Landed:** 2026-09-27

### Given a committed living spec that names an issue missing from the local archive, then deriving it refuses and names the issue instead of dropping its scenarios

- **Scenario id:** `SK-A`
- **Intent:** `INT-1`
- **Source issue:** `spec-derive-keeps-missing-issues`
- **Landed:** 2026-10-02

### a re-frame that changes gates but not the route name is logged

- **Scenario id:** `SCN-A1`
- **Intent:** `INT-1`
- **Source issue:** `spine-records-the-truth`
- **Landed:** 2026-08-13

### a re-frame with no material change is not logged

- **Scenario id:** `SCN-A2`
- **Intent:** `INT-1`
- **Source issue:** `spine-records-the-truth`
- **Landed:** 2026-08-13

### each entry records what changed

- **Scenario id:** `SCN-A3`
- **Intent:** `INT-1`
- **Source issue:** `spine-records-the-truth`
- **Landed:** 2026-08-13

### a recorded re-assessment lints clean

- **Scenario id:** `TRC-1`
- **Intent:** `INT-1`
- **Source issue:** `spine-schema-reassessment-keys`
- **Landed:** 2026-08-12

### the keys are declared, not merely tolerated

- **Scenario id:** `TRC-2`
- **Intent:** `INT-1`
- **Source issue:** `spine-schema-reassessment-keys`
- **Landed:** 2026-08-12

### Given eval records whose manifests measured assess and implement and whose session total is known, When the comparison report is built, Then each cell shows assess, implement, and verify and ship as the remainder, and a cell whose mean assess exceeds its mean implement is flagged

- **Scenario id:** `ST-1`
- **Intent:** `INT-1`
- **Source issue:** `stage-tokens-in-report`
- **Landed:** 2026-10-05

### No shipped document names a slash command that does not exist

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `stale-command-names-in-shipped-prose`
- **Landed:** 2026-08-30

### A guard that reads no commands is refused

- **Scenario id:** `TRC-F1`
- **Intent:** `INT-1`
- **Source issue:** `stale-command-names-in-shipped-prose`
- **Landed:** 2026-08-30

### Given no Compass project, or garbage on stdin, then `bin/compass-statusline` prints nothing, writes nothing to stderr and exits 0.

- **Scenario id:** `SL-A`
- **Intent:** `INT-1`
- **Source issue:** `status-line`
- **Landed:** 2026-10-01

### Given an issue with a red on record for its scenario, then the line shows `compass`, the slug, the approach, the stage, the gates cleared out of those

- **Scenario id:** `SL-B`
- **Intent:** `INT-1`
- **Source issue:** `status-line`
- **Landed:** 2026-10-01

### Given an unparseable manifest, then the line is empty, stderr is empty and the exit code is 0.

- **Scenario id:** `SL-C`
- **Intent:** `INT-1`
- **Source issue:** `status-line`
- **Landed:** 2026-10-01

### Given any issue, then the stage on the line is the one `compass next` reports, and the line shows no stage when `compass next` reports none.

- **Scenario id:** `SL-D`
- **Intent:** `INT-1`
- **Source issue:** `status-line`
- **Landed:** 2026-10-01

### Given a narrow terminal (COLUMNS), then fields drop right to left and the slug is cut last.

- **Scenario id:** `SL-E`
- **Intent:** `INT-1`
- **Source issue:** `status-line`
- **Landed:** 2026-10-01

### Given `bin/compass-statusline`, then it does not load the full CLI, and a run takes under 0.25 s (median of 7).

- **Scenario id:** `SL-F`
- **Intent:** `INT-1`
- **Source issue:** `status-line`
- **Landed:** 2026-10-01

### Given a manifest with one cleared gate and one malformed gate entry, When the status line runs, Then it shows gates 1/2

- **Scenario id:** `TRC-001`
- **Intent:** `INT-1`
- **Source issue:** `status-line-gate-count-and-width`
- **Landed:** 2026-10-02

### Given a session start with CLAUDE_PLUGIN_DATA set, then a launcher named compass-statusline exists there and runs the current plugin root's status line script, passing stdin through.

- **Scenario id:** `SL-A`
- **Intent:** `INT-1`
- **Source issue:** `status-line-launcher`
- **Landed:** 2026-10-02

### Given a second session start from a different plugin root, then the launcher is rewritten to the new root; from the same root, the file is left unchanged, with the same modification time.

- **Scenario id:** `SL-B`
- **Intent:** `INT-1`
- **Source issue:** `status-line-launcher`
- **Landed:** 2026-10-02

### Given CLAUDE_PLUGIN_DATA unset or not writable, then session start exits as before and its output is byte-identical; with it set, the output to the model is unchanged too.

- **Scenario id:** `SL-C`
- **Intent:** `INT-1`
- **Source issue:** `status-line-launcher`
- **Landed:** 2026-10-02

### Given the launcher's target is missing, then the launcher prints nothing and exits 0.

- **Scenario id:** `SL-D`
- **Intent:** `INT-1`
- **Source issue:** `status-line-launcher`
- **Landed:** 2026-10-02

### Given the setup helper and a settings file with no statusLine, then it shows the diff and writes nothing without --apply, and writes the entry with it.

- **Scenario id:** `SL-E`
- **Intent:** `INT-1`
- **Source issue:** `status-line-launcher`
- **Landed:** 2026-10-02

### Given a settings file whose statusLine does not name Compass, then the file is left byte-identical, with or without --apply, and the helper says how to combine the two.

- **Scenario id:** `SL-F`
- **Intent:** `INT-1`
- **Source issue:** `status-line-launcher`
- **Landed:** 2026-10-02

### Given a settings file whose statusLine names a versioned Compass path, then the helper offers the launcher path as the replacement and writes it only with --apply.

- **Scenario id:** `SL-G`
- **Intent:** `INT-1`
- **Source issue:** `status-line-launcher`
- **Landed:** 2026-10-02

### Given the init command and the quickstart, then init has a status line step that runs even when its first step stops for existing governance, and asks before applying; the quickstart gives the launcher path and no longer says to edit the path after each upgrade.

- **Scenario id:** `SL-H`
- **Intent:** `INT-1`
- **Source issue:** `status-line-launcher`
- **Landed:** 2026-10-02

### a parked task can record why and when

- **Scenario id:** `SCN-A3`
- **Intent:** `INT-1`
- **Source issue:** `status-vocabulary`
- **Landed:** 2026-08-13

### flow separates parked work from active work

- **Scenario id:** `SCN-C1`
- **Intent:** `INT-1`
- **Source issue:** `status-vocabulary`
- **Landed:** 2026-08-13

### calibration excludes parked and abandoned

- **Scenario id:** `SCN-C2`
- **Intent:** `INT-1`
- **Source issue:** `status-vocabulary`
- **Landed:** 2026-08-13

### Given eval session records, when the comparison report is built, then each cell and the summary show the hook blocks and check failures each condition met, and a record without them shows not recorded.

- **Scenario id:** `SC-1`
- **Intent:** `INT-1`
- **Source issue:** `stops-and-cost-per-condition`
- **Landed:** 2026-10-03

### Two tries keep both costs and their total

- **Scenario id:** `SCT-1`
- **Intent:** `INT-1`
- **Source issue:** `subtask-cost-keeps-last-try-only`
- **Landed:** 2026-09-27

### A second cost for the same try replaces it

- **Scenario id:** `SCT-2`
- **Intent:** `INT-1`
- **Source issue:** `subtask-cost-keeps-last-try-only`
- **Landed:** 2026-09-27

### Given a checkout with gitignored local state such as .compass/work, When make test-clean runs, Then it clones the committed HEAD into a temporary folder, runs the suite there without that state, and removes the folder afterwards

- **Scenario id:** `CC-1`
- **Intent:** `INT-1`
- **Source issue:** `suite-from-a-clean-clone`
- **Landed:** 2026-10-04

### Given the workflows in .github/workflows and the copyable files in ci/, When a test reads every uses: line and every package install, Then each action is pinned by a full commit SHA, each pip install reads a requirements file of exact versions or pins inline with ==, and the cucumber-js job installs with npm ci from its lockfile

- **Scenario id:** `SP-1`
- **Intent:** `INT-1`
- **Source issue:** `supply-chain-pins`
- **Landed:** 2026-10-04

### swarm.sh strips markdown punctuation from the branch-name cell

- **Scenario id:** `TRC-1`
- **Intent:** `INT-1`
- **Source issue:** `swarm-script-strips-markdown`
- **Landed:** 2026-08-13

### a not-yet-started issue does not fail the sweep

- **Scenario id:** `TRC-1`
- **Intent:** `INT-1`
- **Source issue:** `sweep-respects-queued`
- **Landed:** 2026-08-12

### the sweep still names what it did not check

- **Scenario id:** `TRC-2`
- **Intent:** `INT-1`
- **Source issue:** `sweep-respects-queued`
- **Landed:** 2026-08-12

### an in-flight issue is still checked

- **Scenario id:** `TRC-3`
- **Intent:** `INT-1`
- **Source issue:** `sweep-respects-queued`
- **Landed:** 2026-08-12

### Given the landed issues, when the spec is derived, then docs/system-spec.md holds only current behaviour under 4,000 words with a pointer, and docs/system-spec-archive.md holds every archived section unchanged

- **Scenario id:** `TRC-001`
- **Intent:** `INT-1`
- **Source issue:** `system-spec-split`
- **Landed:** 2026-10-01

### recording a scenario-bound green leaves the unbound green intact

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `tdd-green-unbound-record`
- **Landed:** 2026-08-23

### recording a scenario-bound acceptance leaves the unbound acceptance intact

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `tdd-green-unbound-record`
- **Landed:** 2026-08-23

### no evidence-writing verb overwrites a path the registry names

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `tdd-green-unbound-record`
- **Landed:** 2026-08-23

### the unbound record can still be re-recorded deliberately

- **Scenario id:** `TRC-A4`
- **Intent:** `INT-1`
- **Source issue:** `tdd-green-unbound-record`
- **Landed:** 2026-08-23

### Given the terminology tests running in parallel workers, then each worker scans its samples in a folder of its own, so no worker removes another's folder.

- **Scenario id:** `TV-1`
- **Intent:** `INT-1`
- **Source issue:** `terminology-test-shares-a-folder`
- **Landed:** 2026-10-04

### the pinned assertions run where the history is absent

- **Scenario id:** `TRC-1`
- **Intent:** `INT-1`
- **Source issue:** `tests-survive-shallow-clone`
- **Landed:** 2026-08-10

### the version guard compares every location it names

- **Scenario id:** `TRC-1`
- **Intent:** `INT-1`
- **Source issue:** `tests-that-can-fail`
- **Landed:** 2026-08-12

### the validate guard fails when the lint is skipped

- **Scenario id:** `TRC-2`
- **Intent:** `INT-1`
- **Source issue:** `tests-that-can-fail`
- **Landed:** 2026-08-12

### the tell-scope guard fails when nothing was found

- **Scenario id:** `TRC-3`
- **Intent:** `INT-1`
- **Source issue:** `tests-that-can-fail`
- **Landed:** 2026-08-12

### the reference-location guard fails on a new skill directory

- **Scenario id:** `TRC-4`
- **Intent:** `INT-1`
- **Source issue:** `tests-that-can-fail`
- **Landed:** 2026-08-12

### the header scan proves how many modules it read

- **Scenario id:** `TRC-5`
- **Intent:** `INT-1`
- **Source issue:** `tests-that-can-fail`
- **Landed:** 2026-08-12

### a registered artifact declares its kind, path, status and reason

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `the-human-front-door`
- **Landed:** 2026-08-23

### an omitted artifact records why it was omitted

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `the-human-front-door`
- **Landed:** 2026-08-23

### the schema refuses an entry that explains nothing

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `the-human-front-door`
- **Landed:** 2026-08-23

### the pack separates a document that exists from one still owed

- **Scenario id:** `TRC-C6`
- **Intent:** `INT-1`
- **Source issue:** `the-human-front-door`
- **Landed:** 2026-08-23

### a document's status can be moved, and an omission recorded

- **Scenario id:** `TRC-C7`
- **Intent:** `INT-1`
- **Source issue:** `the-human-front-door`
- **Landed:** 2026-08-23

### a stage hand-off fits on one screen

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `the-terminal-output-contract`
- **Landed:** 2026-08-24

### the hand-off says what was decided and what to read

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `the-terminal-output-contract`
- **Landed:** 2026-08-24

### a hand-off with nothing to decide is shorter, not padded

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `the-terminal-output-contract`
- **Landed:** 2026-08-24

### at most three key choices and three concerns

- **Scenario id:** `TRC-A4`
- **Intent:** `INT-1`
- **Source issue:** `the-terminal-output-contract`
- **Landed:** 2026-08-24

### the budget cannot be met by making the lines longer

- **Scenario id:** `TRC-A5`
- **Intent:** `INT-1`
- **Source issue:** `the-terminal-output-contract`
- **Landed:** 2026-08-24

### the gate verdict keeps its guidance one flag away

- **Scenario id:** `TRC-A6`
- **Intent:** `INT-1`
- **Source issue:** `the-terminal-output-contract`
- **Landed:** 2026-08-24

### an expected string is updated only when the test's intent still holds

- **Scenario id:** `TRC-D4`
- **Intent:** `INT-1`
- **Source issue:** `the-terminal-output-contract`
- **Landed:** 2026-08-24

### a verb prints past its budget and the guard says which one

- **Scenario id:** `TRC-E1`
- **Intent:** `INT-1`
- **Source issue:** `the-terminal-output-contract`
- **Landed:** 2026-08-24

### the budget guard fails when the budget is breached

- **Scenario id:** `TRC-E2`
- **Intent:** `INT-1`
- **Source issue:** `the-terminal-output-contract`
- **Landed:** 2026-08-24

### a command, its key and its artifact name the same thing

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### the designer's command is design again

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### the planning stage answers to plan in the CLI too

- **Scenario id:** `TRC-A4`
- **Intent:** `INT-1`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### no live surface sends the engineering stage to /compass:design

- **Scenario id:** `TRC-A5`
- **Intent:** `INT-1`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### the rename is not counted as done while a surface still says the old word

- **Scenario id:** `TRC-E1`
- **Intent:** `INT-1`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### Given a scenario title that attaches a duration to a user or claims an outside user, then scenario add refuses it when it is recorded, using the same patterns the public-copy check applies.

- **Scenario id:** `TT-1`
- **Intent:** `INT-1`
- **Source issue:** `title-times-a-user`
- **Landed:** 2026-10-03

### Given a scenario title naming a missing file path or an eval scenario or behaviour id, then compass scenario add and quick-fix start refuse it before it can reach the living spec

- **Scenario id:** `TC-A`
- **Intent:** `INT-1`
- **Source issue:** `titles-checked-before-ship`
- **Landed:** 2026-10-02

### Given a Claude Code transcript, then the reader gives each request's time, model and token counts once, though the transcript can repeat a request over several lines (taking the first line's time and the highest count per field), and it includes the session's subagent transcripts by their own times.

- **Scenario id:** `TS-1`
- **Intent:** `INT-1`
- **Source issue:** `tokens-per-stage-interactive`
- **Landed:** 2026-10-04

### Given a quick fix finished in a Claude Code session, with or without `--no-commit`, then its manifest records the input, output and cache tokens spent in its assess and implement stages, taken from that session''s transcript between the times the manifest records for the stage boundaries, and records verify and ship as not measured.

- **Scenario id:** `TS-2`
- **Intent:** `INT-1`
- **Source issue:** `tokens-per-stage-interactive`
- **Landed:** 2026-10-04

### Given a quick fix finished outside Claude Code, or with a transcript that cannot be read, then the finish succeeds as before and the manifest says why no tokens were recorded.

- **Scenario id:** `TS-3`
- **Intent:** `INT-1`
- **Source issue:** `tokens-per-stage-interactive`
- **Landed:** 2026-10-04

### Given a model whose price the project configures, then each stage also records its cost; given none, cost is "not recorded", never a guessed price.

- **Scenario id:** `TS-4`
- **Intent:** `INT-1`
- **Source issue:** `tokens-per-stage-interactive`
- **Landed:** 2026-10-04

### Given eval records whose manifests carry tokens per stage, then the comparison report shows each condition's tokens per stage.

- **Scenario id:** `TS-5`
- **Intent:** `INT-1`
- **Source issue:** `tokens-per-stage-interactive`
- **Landed:** 2026-10-04

### Given one session that works on two issues, then each issue's assess window starts after the other issue's last boundary in that session, and a stage whose window overlaps the other issue's is marked shared.

- **Scenario id:** `TS-6`
- **Intent:** `INT-1`
- **Source issue:** `tokens-per-stage-interactive`
- **Landed:** 2026-10-04

### Given a transcript whose messages hold a sentence of text, then nothing the reader returns or the manifest records contains that sentence, a path or an error message; a reason for not recording comes from a fixed list.

- **Scenario id:** `TS-7`
- **Intent:** `INT-1`
- **Source issue:** `tokens-per-stage-interactive`
- **Landed:** 2026-10-04

### No tr set in the scripts reads differently on Linux

- **Scenario id:** `DTR-1`
- **Intent:** `INT-1`
- **Source issue:** `tr-range-fails-on-linux`
- **Landed:** 2026-09-25

### Given an issue with scenarios TRC-1 and TRC-2, When compass changed-file add or compass evidence add is given a scenario id the issue does not define, or several ids in one quoted string, Then it refuses, names the issue's scenarios and writes nothing

- **Scenario id:** `TS-1`
- **Intent:** `INT-1`
- **Source issue:** `trace-checks-scenario-ids`
- **Landed:** 2026-10-04

### a missing changed_files path fails a task claiming correctness

- **Scenario id:** `SCN-A1`
- **Intent:** `INT-1`
- **Source issue:** `trace-rot-detection`
- **Landed:** 2026-08-13

### a task that has not yet claimed correctness is not failed

- **Scenario id:** `SCN-A3`
- **Intent:** `INT-1`
- **Source issue:** `trace-rot-detection`
- **Landed:** 2026-08-13

### a clean task says what it verified

- **Scenario id:** `SCN-B2`
- **Intent:** `INT-1`
- **Source issue:** `trace-rot-detection`
- **Landed:** 2026-08-13

### a project outside git still gets the check

- **Scenario id:** `SCN-F2`
- **Intent:** `INT-1`
- **Source issue:** `trace-rot-detection`
- **Landed:** 2026-08-13

### A same-size edit in the same second changes the tree id

- **Scenario id:** `TSE-1`
- **Intent:** `INT-1`
- **Source issue:** `tree-id-misses-a-same-second-edit`
- **Landed:** 2026-09-25

### Given the session-start contract, then it is at most 2,250 characters, from 2,517, and still holds a pinned phrase for each of its rules - assess first, never skip assessment, trigger on intent, the five guardrails, guardrails hard and strategies soft, evidence not assertion, state on disk, the numbered stages, the instruction to use the CLI, the statement that there are five guardrails, where to look and writing for no context - and deleting any one of them fails the test.

- **Scenario id:** `TC-1`
- **Intent:** `INT-1`
- **Source issue:** `trim-quick-fix-context`
- **Landed:** 2026-10-04

### Given `--help` for `quick-fix start`, `quick-fix finish`, `tdd-red` and `tdd-green`, then each, printed at 80 columns, is within a budget set from the rewrite (2,600 characters for `quick-fix start`, 1,500 for `quick-fix finish`, 1,450 for `tdd-red`, 1,250 for `tdd-green`) and still lists every option it accepted before.

- **Scenario id:** `TC-2`
- **Intent:** `INT-1`
- **Source issue:** `trim-quick-fix-context`
- **Landed:** 2026-10-04

### An issue whose only evidence is an unbound green fails suite-passed

- **Scenario id:** `UGR-1`
- **Intent:** `INT-1`
- **Source issue:** `unbound-green-needs-no-red`
- **Landed:** 2026-09-24

### One red of either binding satisfies the rule

- **Scenario id:** `UGR-2`
- **Intent:** `INT-1`
- **Source issue:** `unbound-green-needs-no-red`
- **Landed:** 2026-09-24

### An issue with no scenarios is not asked for a red

- **Scenario id:** `UGR-4`
- **Intent:** `INT-1`
- **Source issue:** `unbound-green-needs-no-red`
- **Landed:** 2026-09-24

### The governance text states the rule

- **Scenario id:** `UGR-8`
- **Intent:** `INT-1`
- **Source issue:** `unbound-green-needs-no-red`
- **Landed:** 2026-09-24

### Given a project unlock whose waiver has an approved_on date in the future, When the lock chain is enforced, Then the unlock is refused and the entry stays locked

- **Scenario id:** `TRC-001`
- **Intent:** `INT-1`
- **Source issue:** `unlock-uses-the-waiver-check`
- **Landed:** 2026-10-07

### Given an atomic or small change with trivial or contained risk on unmapped ground, when it is assessed, then it gets the mapped route, the unmapped floor does not fire, and behaviour-mapping is advice.

- **Scenario id:** `UA-1`
- **Intent:** `INT-1`
- **Source issue:** `unmapped-small-change-advisory`
- **Landed:** 2026-10-03

### Given quick-fix start on a small, contained, unmapped change, then the quick fix starts and its approach record names behaviour-mapping as advice.

- **Scenario id:** `UA-2`
- **Intent:** `INT-1`
- **Source issue:** `unmapped-small-change-advisory`
- **Landed:** 2026-10-03

### Given a project and an issue made with the 5.0.0 CLI, when the working tree's CLI reads them, then every manifest loads and compass check gives the same gate-by-gate verdict.

- **Scenario id:** `UP-1`
- **Intent:** `INT-1`
- **Source issue:** `upgrade-from-5-0-0`
- **Landed:** 2026-10-03

### the template set carries the v2 names plus the two new intake templates

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `v2-artifact-renames`
- **Landed:** 

### the resolver prefers v2 names and accepts v1

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `v2-artifact-renames`
- **Landed:** 

### readers resolve both naming generations of issue directories

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `v2-artifact-renames`
- **Landed:** 

### extracted runnable Gherkin is named acceptance-criteria.feature

- **Scenario id:** `TRC-A4`
- **Intent:** `INT-1`
- **Source issue:** `v2-artifact-renames`
- **Landed:** 

### repository validation knows the v2 template inventory

- **Scenario id:** `TRC-A5`
- **Intent:** `INT-1`
- **Source issue:** `v2-artifact-renames`
- **Landed:** 

### the v2 verbs exist and work

- **Scenario id:** `TRC-1`
- **Intent:** `INT-1`
- **Source issue:** `v2-cli-voice`
- **Landed:** 2026-08-07

### a retired verb fails loudly and legibly

- **Scenario id:** `TRC-2`
- **Intent:** `INT-1`
- **Source issue:** `v2-cli-voice`
- **Landed:** 2026-08-07

### the --issue flag with --task tolerated

- **Scenario id:** `TRC-3`
- **Intent:** `INT-1`
- **Source issue:** `v2-cli-voice`
- **Landed:** 2026-08-07

### follow-up states are outstanding and resolved with 1.x readable

- **Scenario id:** `TRC-4`
- **Intent:** `INT-1`
- **Source issue:** `v2-cli-voice`
- **Landed:** 2026-08-07

### CLI output speaks v2 change-type names and the receipt shows overrides

- **Scenario id:** `TRC-5`
- **Intent:** `INT-1`
- **Source issue:** `v2-cli-voice`
- **Landed:** 2026-08-07

### the vocabulary carries receipt, the amended follow-up, and a bump

- **Scenario id:** `TRC-6`
- **Intent:** `INT-1`
- **Source issue:** `v2-cli-voice`
- **Landed:** 2026-08-07

### the cli surface is enforced and widened

- **Scenario id:** `TRC-7`
- **Intent:** `INT-1`
- **Source issue:** `v2-cli-voice`
- **Landed:** 2026-08-07

### the compass-backfill tolerance is re-tightened

- **Scenario id:** `TRC-8`
- **Intent:** `INT-1`
- **Source issue:** `v2-cli-voice`
- **Landed:** 2026-08-07

### the command set carries the v2 names

- **Scenario id:** `TRC-1`
- **Intent:** `INT-1`
- **Source issue:** `v2-command-renames`
- **Landed:** 2026-08-07

### each renamed v1 command is a redirect stub

- **Scenario id:** `TRC-2`
- **Intent:** `INT-1`
- **Source issue:** `v2-command-renames`
- **Landed:** 2026-08-07

### the vocabulary carries the command names and a version bump

- **Scenario id:** `TRC-3`
- **Intent:** `INT-1`
- **Source issue:** `v2-command-renames`
- **Landed:** 2026-08-07

### commands and the plugin manifests are enforced surfaces

- **Scenario id:** `TRC-4`
- **Intent:** `INT-1`
- **Source issue:** `v2-command-renames`
- **Landed:** 2026-08-07

### no live instruction surface points at a dead command name

- **Scenario id:** `TRC-5`
- **Intent:** `INT-1`
- **Source issue:** `v2-command-renames`
- **Landed:** 2026-08-07

### the ruling conditions hold

- **Scenario id:** `TRC-6`
- **Intent:** `INT-1`
- **Source issue:** `v2-command-renames`
- **Landed:** 2026-08-07

### the ratchet reaches zero

- **Scenario id:** `TRC-1`
- **Intent:** `INT-1`
- **Source issue:** `v2-docs-prose`
- **Landed:** 2026-08-08

### the delivery-approach reference docs carry v2 names

- **Scenario id:** `TRC-2`
- **Intent:** `INT-1`
- **Source issue:** `v2-docs-prose`
- **Landed:** 2026-08-08

### the worked examples carry v2 change-type names

- **Scenario id:** `TRC-3`
- **Intent:** `INT-1`
- **Source issue:** `v2-docs-prose`
- **Landed:** 2026-08-08

### the remaining docs are enforced surfaces

- **Scenario id:** `TRC-4`
- **Intent:** `INT-1`
- **Source issue:** `v2-docs-prose`
- **Landed:** 2026-08-08

### the install refusal points at the plugin-dir path

- **Scenario id:** `TRC-5`
- **Intent:** `INT-1`
- **Source issue:** `v2-docs-prose`
- **Landed:** 2026-08-08

### the ratchet reaches zero

- **Scenario id:** `TRC-1`
- **Intent:** `INT-1`
- **Source issue:** `v2-docs-prose-2`
- **Landed:** 2026-08-08

### the four deferred docs are enforced and clean

- **Scenario id:** `TRC-2`
- **Intent:** `INT-1`
- **Source issue:** `v2-docs-prose-2`
- **Landed:** 2026-08-08

### the implementation plan document is reviewable and complete

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `v2-implementation-plan`
- **Landed:** 2026-08-06

### the evaluator writes a v2 spine

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `v2-machine-spine`
- **Landed:** 2026-08-07

### a 1.x spine is still readable by normalisation

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `v2-machine-spine`
- **Landed:** 2026-08-07

### the policy keys speak v2

- **Scenario id:** `TRC-A7`
- **Intent:** `INT-1`
- **Source issue:** `v2-machine-spine`
- **Landed:** 2026-08-07

### dry run reports and writes nothing

- **Scenario id:** `TRC-1`
- **Intent:** `INT-1`
- **Source issue:** `v2-migrate`
- **Landed:** 2026-08-08

### apply migrates a v1 tree to v2

- **Scenario id:** `TRC-2`
- **Intent:** `INT-1`
- **Source issue:** `v2-migrate`
- **Landed:** 2026-08-08

### a second apply is a no-op

- **Scenario id:** `TRC-3`
- **Intent:** `INT-1`
- **Source issue:** `v2-migrate`
- **Landed:** 2026-08-08

### the mapping lives in the exempt data file

- **Scenario id:** `TRC-4`
- **Intent:** `INT-1`
- **Source issue:** `v2-migrate`
- **Landed:** 2026-08-08

### the v2 PRD exists in the v2 register with all required sections

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `v2-prd-and-freeze-adr`
- **Landed:** 2026-08-07

### the version is 2.0.0 in every guarded location

- **Scenario id:** `TRC-1`
- **Intent:** `INT-1`
- **Source issue:** `v2-release`
- **Landed:** 2026-08-08

### desired-state graduates and is enforced

- **Scenario id:** `TRC-2`
- **Intent:** `INT-1`
- **Source issue:** `v2-release`
- **Landed:** 2026-08-08

### CLAUDE.md is clean v2 register and operationally exact

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `v2-session-instructions`
- **Landed:** 2026-08-07

### AGENTS.md is clean v2 register with the adapter contract intact

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `v2-session-instructions`
- **Landed:** 2026-08-07

### the compass-runtime skill carries the stage-to-command mapping in the v2 register

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `v2-session-instructions`
- **Landed:** 2026-08-07

### skills is an enforced surface

- **Scenario id:** `TRC-1`
- **Intent:** `INT-1`
- **Source issue:** `v2-skills-prose`
- **Landed:** 2026-08-07

### agents is a scanned enforced never-pending surface

- **Scenario id:** `TRC-2`
- **Intent:** `INT-1`
- **Source issue:** `v2-skills-prose`
- **Landed:** 2026-08-07

### the worktree-swarm skill carries the stash rule

- **Scenario id:** `TRC-3`
- **Intent:** `INT-1`
- **Source issue:** `v2-skills-prose`
- **Landed:** 2026-08-07

### the lens ban catches the concept not the agent identifiers

- **Scenario id:** `TRC-4`
- **Intent:** `INT-1`
- **Source issue:** `v2-skills-prose`
- **Landed:** 2026-08-07

### the templates speak the v2 register and templates/ is enforced, never pending again

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `v2-template-prose`
- **Landed:** 2026-08-07

### the follow-up ban tolerates its live machine forms (tag, CLI verb, spine key)

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `v2-template-prose`
- **Landed:** 2026-08-07

### the archive sweeps exclude issues the spine says have not started

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `v2-template-prose`
- **Landed:** 2026-08-07

### every related term is defined

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `v2-terminology-dangling-refs`
- **Landed:** 2026-08-07

### the vocabulary file parses and carries its three sections

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `v2-terminology-freeze`
- **Landed:** 2026-08-06

### every term states its meaning

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `v2-terminology-freeze`
- **Landed:** 2026-08-06

### every ban carries a replacement and a context

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `v2-terminology-freeze`
- **Landed:** 2026-08-06

### validate.sh --help prints both exit codes and every check

- **Scenario id:** `VHP-1`
- **Intent:** `INT-1`
- **Source issue:** `validate-help-prints-headings-only`
- **Landed:** 2026-09-25

### validate.sh skips an issue's own documents and still fails a broken reference in a living file

- **Scenario id:** `VSA-1`
- **Intent:** `INT-1`
- **Source issue:** `validate-scan-vs-archive`
- **Landed:** 2026-09-24

### Every published version surface reports 1.0.0

- **Scenario id:** `TRC-1`
- **Intent:** `INT-1`
- **Source issue:** `version-bump-1-0-0`
- **Landed:** 

### every published surface should report 1.7.0

- **Scenario id:** `TRC-1`
- **Intent:** `INT-1`
- **Source issue:** `version-bump-1-7-0`
- **Landed:** 2026-08-03

### an exemption carries its reason

- **Scenario id:** `VGH-A1`
- **Intent:** `INT-1`
- **Source issue:** `version-guard-cannot-see-a-historical-version`
- **Landed:** 2026-08-27

### the exemption list cannot grow quietly

- **Scenario id:** `VGH-A2`
- **Intent:** `INT-1`
- **Source issue:** `version-guard-cannot-see-a-historical-version`
- **Landed:** 2026-08-27

### the historical reference is exempt and still says 3.3.0

- **Scenario id:** `VGH-A3`
- **Intent:** `INT-1`
- **Source issue:** `version-guard-cannot-see-a-historical-version`
- **Landed:** 2026-08-27

### every published location reports the declared version

- **Scenario id:** `TRC-1`
- **Intent:** `INT-1`
- **Source issue:** `version-guard-covers-all`
- **Landed:** 2026-08-12

### the guard has a case for every published location

- **Scenario id:** `TRC-2`
- **Intent:** `INT-1`
- **Source issue:** `version-guard-covers-all`
- **Landed:** 2026-08-12

### no constant nothing reads

- **Scenario id:** `TRC-3`
- **Intent:** `INT-1`
- **Source issue:** `version-guard-covers-all`
- **Landed:** 2026-08-12

### A display name comes from the vocabulary and a project layer changes it

- **Scenario id:** `VC-1`
- **Intent:** `INT-1`
- **Source issue:** `vocabulary-catalogue`
- **Landed:** 2026-10-06

### An alias resolves to its id

- **Scenario id:** `VC-2`
- **Intent:** `INT-1`
- **Source issue:** `vocabulary-catalogue`
- **Landed:** 2026-10-06

### A name or alias that collides with another entry fails

- **Scenario id:** `VC-3`
- **Intent:** `INT-1`
- **Source issue:** `vocabulary-catalogue`
- **Landed:** 2026-10-06

### A vocabulary key that names nothing fails

- **Scenario id:** `VC-4`
- **Intent:** `INT-1`
- **Source issue:** `vocabulary-catalogue`
- **Landed:** 2026-10-06

### The ban scan covers display names

- **Scenario id:** `VC-5`
- **Intent:** `INT-1`
- **Source issue:** `vocabulary-catalogue`
- **Landed:** 2026-10-06

### The terminology file says how a project adds names

- **Scenario id:** `VC-6`
- **Intent:** `INT-1`
- **Source issue:** `vocabulary-catalogue`
- **Landed:** 2026-10-06

### The terms the accepted vocabulary decision defines are in the glossary

- **Scenario id:** `VC-7`
- **Intent:** `INT-1`
- **Source issue:** `vocabulary-catalogue`
- **Landed:** 2026-10-06

### every file the approaches index names exists

- **Scenario id:** `VOC-A1`
- **Intent:** `INT-1`
- **Source issue:** `vocabulary-debt`
- **Landed:** 2026-08-27

### no document says a shipped rename is still pending

- **Scenario id:** `VOC-B1`
- **Intent:** `INT-1`
- **Source issue:** `vocabulary-debt`
- **Landed:** 2026-08-27

### the strategy records permanence and the calibration sample

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `voice-audition-standing`
- **Landed:** 

### the strategy states its own test and its own failure mode

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `voice-audition-standing`
- **Landed:** 

### the reviewer's clarity dimension finds the audition without knowing it exists

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-1`
- **Source issue:** `voice-audition-standing`
- **Landed:** 

### no new mechanism is introduced

- **Scenario id:** `TRC-F1`
- **Intent:** `INT-1`
- **Source issue:** `voice-audition-standing`
- **Landed:** 

### A waiver is found with its id, scope, operation and fields, and its shape is checked

- **Scenario id:** `WV-1`
- **Intent:** `INT-1`
- **Source issue:** `waivers`
- **Landed:** 2026-10-07

### The approvers come from the layer above, and no owner fails

- **Scenario id:** `WV-2`
- **Intent:** `INT-1`
- **Source issue:** `waivers`
- **Landed:** 2026-10-07

### An issue waiver's approval is a matching human-approval record

- **Scenario id:** `WV-3`
- **Intent:** `INT-1`
- **Source issue:** `waivers`
- **Landed:** 2026-10-07

### The covered revision is derived and each waived field's parent value is recorded

- **Scenario id:** `WV-4`
- **Intent:** `INT-1`
- **Source issue:** `waivers`
- **Landed:** 2026-10-07

### A moved revision invalidates a waiver only when a waived field's parent value changed

- **Scenario id:** `WV-5`
- **Intent:** `INT-1`
- **Source issue:** `waivers`
- **Landed:** 2026-10-07

### Attribution classifies the residual layer and excuses only waived entries

- **Scenario id:** `WV-6`
- **Intent:** `INT-1`
- **Source issue:** `waivers`
- **Landed:** 2026-10-07

### A waiver that excuses nothing is reported as unneeded

- **Scenario id:** `WV-7`
- **Intent:** `INT-1`
- **Source issue:** `waivers`
- **Landed:** 2026-10-07

### The module declares its dependencies, is pure, is unused and has an owning doc

- **Scenario id:** `WV-8`
- **Intent:** `INT-1`
- **Source issue:** `waivers`
- **Landed:** 2026-10-07

### Given the well-architected register and strategy, then the register lists the three frameworks with sources, pillars and a review date that lint checks, and the strategy, its rationale and the planning texts name it as advice.

- **Scenario id:** `WA-1`
- **Intent:** `INT-1`
- **Source issue:** `well-architected-strategy`
- **Landed:** 2026-10-03

### The decision names an observable quantity

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `what-compass-owes-an-unobserved-adopter`
- **Landed:** 2026-08-28

### Publication is refused as evidence of adoption

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `what-compass-owes-an-unobserved-adopter`
- **Landed:** 2026-08-28

### A revival condition nobody can observe is refused

- **Scenario id:** `TRC-F2`
- **Intent:** `INT-1`
- **Source issue:** `what-compass-owes-an-unobserved-adopter`
- **Landed:** 2026-08-28

### a first triage completes with no Python package installed

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-1`
- **Source issue:** `zero-friction-install`
- **Landed:** 2026-08-10

### no CLI verb exits on a missing dependency

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-1`
- **Source issue:** `zero-friction-install`
- **Landed:** 2026-08-10

### the acceptance-before-code hook check runs instead of failing open

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-1`
- **Source issue:** `zero-friction-install`
- **Landed:** 2026-08-10

### integration records the landing rather than warning it could not

- **Scenario id:** `TRC-A4`
- **Intent:** `INT-1`
- **Source issue:** `zero-friction-install`
- **Landed:** 2026-08-10

### the session-end signal scan runs rather than returning empty

- **Scenario id:** `TRC-A5`
- **Intent:** `INT-1`
- **Source issue:** `zero-friction-install`
- **Landed:** 2026-08-10

### the repository check runs the policy lint rather than skipping it

- **Scenario id:** `TRC-A6`
- **Intent:** `INT-1`
- **Source issue:** `zero-friction-install`
- **Landed:** 2026-08-10

### preparing a swarm reads the cap rather than refusing

- **Scenario id:** `TRC-A7`
- **Intent:** `INT-1`
- **Source issue:** `zero-friction-install`
- **Landed:** 2026-08-10

### the copyable CI workflow runs with no dependency step

- **Scenario id:** `TRC-D3`
- **Intent:** `INT-1`
- **Source issue:** `zero-friction-install`
- **Landed:** 2026-08-10

### the install smoke test asserts the zero-install path

- **Scenario id:** `TRC-D4`
- **Intent:** `INT-1`
- **Source issue:** `zero-friction-install`
- **Landed:** 2026-08-10

### the distributed plugin actually contains the bundled copy

- **Scenario id:** `TRC-F6`
- **Intent:** `INT-1`
- **Source issue:** `zero-friction-install`
- **Landed:** 2026-08-10

### the bundled copy is the one used, whatever the machine has

- **Scenario id:** `TRC-G1`
- **Intent:** `INT-1`
- **Source issue:** `zero-friction-install`
- **Landed:** 2026-08-10

### regression-baseline is a named, registered soft strategy (S6)

- **Scenario id:** `TRC-R10-1`
- **Intent:** `INT-10`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### routing-policy surfaces regression-baseline when touches is shared/critical

- **Scenario id:** `TRC-R10-2`
- **Intent:** `INT-10`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### Verify expects baseline + post-change test-run evidence on a shared-surface task

- **Scenario id:** `TRC-R10-3`
- **Intent:** `INT-10`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### The Build phase prompts for the baseline capture up front

- **Scenario id:** `TRC-R10-4`
- **Intent:** `INT-10`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### Backward-compat - an absent baseline never blocks Land

- **Scenario id:** `TRC-R10-5`
- **Intent:** `INT-10`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### Backward-compat - guardrail count and gate set unchanged by S6

- **Scenario id:** `TRC-R10-6`
- **Intent:** `INT-10`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### the template asks the four questions and no others

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-2`
- **Source issue:** `adaptive-artifact-composition`
- **Landed:** 2026-08-24

### a threat with no scenario is visibly unfinished

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-2`
- **Source issue:** `adaptive-artifact-composition`
- **Landed:** 2026-08-24

### the fourth question is answered by evidence, not by assertion

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-2`
- **Source issue:** `adaptive-artifact-composition`
- **Landed:** 2026-08-24

### a worked list gives each leaky term its plain-English form

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-2`
- **Source issue:** `agent-speech-is-unchecked`
- **Landed:** 2026-08-23

### the list covers every term the cold reader named

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-2`
- **Source issue:** `agent-speech-is-unchecked`
- **Landed:** 2026-08-23

### The guards that honour the marker share its definition

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-2`
- **Source issue:** `allow-marker-supplies-its-own-reason`
- **Landed:** 2026-08-30

### The glossary defines each term this rename introduces

- **Scenario id:** `TRC-D1`
- **Intent:** `INT-2`
- **Source issue:** `anthropic-aligned-vocabulary`
- **Landed:** 2026-08-28

### The glossary is regenerated rather than hand-edited

- **Scenario id:** `TRC-D2`
- **Intent:** `INT-2`
- **Source issue:** `anthropic-aligned-vocabulary`
- **Landed:** 2026-08-28

### Retiring a frozen term is recorded as a decision

- **Scenario id:** `TRC-D3`
- **Intent:** `INT-2`
- **Source issue:** `anthropic-aligned-vocabulary`
- **Landed:** 2026-08-28

### every adapter should be exercised by a CI job

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-2`
- **Source issue:** `bdd-adapters-and-skill-length`
- **Landed:** 

### an adapter whose runner is absent should skip loudly, never silently pass

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-2`
- **Source issue:** `bdd-adapters-and-skill-length`
- **Landed:** 

### the summary reports what was and was not checked

- **Scenario id:** `TRC-3`
- **Intent:** `INT-2`
- **Source issue:** `ci-lints-every-issue`
- **Landed:** 2026-08-12

### an incomplete project governance directory should be refused rather than quietly replaced

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-2`
- **Source issue:** `claims-match-what-is-proved`
- **Landed:** 2026-08-22

### the refusal should name the file it found and the file it expected

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-2`
- **Source issue:** `claims-match-what-is-proved`
- **Landed:** 2026-08-22

### a project that has said nothing about governance should still use the shipped defaults silently

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-2`
- **Source issue:** `claims-match-what-is-proved`
- **Landed:** 2026-08-22

### a complete project governance directory should still be used

- **Scenario id:** `TRC-A4`
- **Intent:** `INT-2`
- **Source issue:** `claims-match-what-is-proved`
- **Landed:** 2026-08-22

### the documentation should state that project governance replaces the shipped defaults

- **Scenario id:** `TRC-A5`
- **Intent:** `INT-2`
- **Source issue:** `claims-match-what-is-proved`
- **Landed:** 2026-08-22

### an incomplete governance directory outside the project should not stop work inside it

- **Scenario id:** `TRC-A6`
- **Intent:** `INT-2`
- **Source issue:** `claims-match-what-is-proved`
- **Landed:** 2026-08-22

### a project governance directory missing its guardrails should be refused the same way

- **Scenario id:** `TRC-F1`
- **Intent:** `INT-2`
- **Source issue:** `claims-match-what-is-proved`
- **Landed:** 2026-08-22

### the public verb surface should be identical

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-2`
- **Source issue:** `cli-module-split`
- **Landed:** 

### the whole test suite should pass unchanged

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-2`
- **Source issue:** `cli-module-split`
- **Landed:** 

### loading the CLI by file path should still work

- **Scenario id:** `TRC-B3`
- **Intent:** `INT-2`
- **Source issue:** `cli-module-split`
- **Landed:** 

### every command should still run end to end

- **Scenario id:** `TRC-B4`
- **Intent:** `INT-2`
- **Source issue:** `cli-module-split`
- **Landed:** 

### no function should be renamed, merged or split by this task

- **Scenario id:** `TRC-F2`
- **Intent:** `INT-2`
- **Source issue:** `cli-module-split`
- **Landed:** 

### a landed behaviour change accretes into the system spec

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-2`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### the derived spec carries a "DERIVED FILE" header

- **Scenario id:** `TRC-B10`
- **Intent:** `INT-2`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### a landed task is the source-of-truth for the living spec via task.yml.status

- **Scenario id:** `TRC-B11`
- **Intent:** `INT-2`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### a pure Spike contributes nothing to the system spec

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-2`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### a superseding change updates the prior behaviour and archives the prior

- **Scenario id:** `TRC-B4`
- **Intent:** `INT-2`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### archived-behaviour appendix preserves the trace back to the prior task

- **Scenario id:** `TRC-B4a`
- **Intent:** `INT-2`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### a hand-edit to the spec is silently overwritten by the next Land

- **Scenario id:** `TRC-B9`
- **Intent:** `INT-2`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### derivation handles two landed tasks with conflicting scenarios deterministically

- **Scenario id:** `TRC-F2`
- **Intent:** `INT-2`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### architecture/decisions/ contains an ADR per principle (clustered or 1:1)

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-2`
- **Source issue:** `compass-self-architecture`
- **Landed:** 

### ADRs follow the template structure (frontmatter + 5 sections)

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-2`
- **Source issue:** `compass-self-architecture`
- **Landed:** 

### architecture/decisions/README.md is a usable index

- **Scenario id:** `TRC-B3`
- **Intent:** `INT-2`
- **Source issue:** `compass-self-architecture`
- **Landed:** 

### a project can add a file type

- **Scenario id:** `SCN-A1`
- **Intent:** `INT-2`
- **Source issue:** `configurable-enforced-set`
- **Landed:** 2026-08-13

### a path-shaped glob works too

- **Scenario id:** `SCN-A2`
- **Intent:** `INT-2`
- **Source issue:** `configurable-enforced-set`
- **Landed:** 2026-08-13

### /compass:roundtable can convene the architect-lens

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-2`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### Spec-author consults the architect-lens for boundary-touching tasks

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-2`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### Plan flags new service interactions for architect review

- **Scenario id:** `TRC-B3`
- **Intent:** `INT-2`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### Architect-lens flags missing architecture/ without blocking

- **Scenario id:** `TRC-B4`
- **Intent:** `INT-2`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### Architect-lens findings persist on disk

- **Scenario id:** `TRC-B5`
- **Intent:** `INT-2`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### Bootstrap - spec-author does not invoke architect-lens that doesn't exist yet

- **Scenario id:** `TRC-X5`
- **Intent:** `INT-2`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### A multiagent issue must record its run

- **Scenario id:** `DPR-1`
- **Intent:** `INT-2`
- **Source issue:** `dispatch-protocol`
- **Landed:** 2026-09-25

### Machine state stays where the CLI keeps it

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-2`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### A reading command still does not create anything

- **Scenario id:** `TRC-B4`
- **Intent:** `INT-2`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### the guard fails when a surface reintroduces the old claim

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-2`
- **Source issue:** `docs-describe-the-old-evidence-path`
- **Landed:** 2026-08-23

### no document claims more than governance does

- **Scenario id:** `DOC-A2`
- **Intent:** `INT-2`
- **Source issue:** `docs-slimming-pass`
- **Landed:** 2026-08-26

### A green for a changed tree fails at ship

- **Scenario id:** `EVB-2`
- **Intent:** `INT-2`
- **Source issue:** `evidence-binding`
- **Landed:** 2026-09-25

### Before ship a stale green is a note, not a failure

- **Scenario id:** `EVB-3`
- **Intent:** `INT-2`
- **Source issue:** `evidence-binding`
- **Landed:** 2026-09-25

### An edit to an ignored path does not make a green stale

- **Scenario id:** `EVB-4`
- **Intent:** `INT-2`
- **Source issue:** `evidence-binding`
- **Landed:** 2026-09-25

### the shipped config template should document the new keys

- **Scenario id:** `TRC-A8`
- **Intent:** `INT-2`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### the reference adapter should run an extracted feature end to end

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-2`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### the adapter README should show every step of the wire-up

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-2`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### a scenario with no step definition should fail loudly

- **Scenario id:** `TRC-B3`
- **Intent:** `INT-2`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### the adapter should be proved by a run, never by a skip

- **Scenario id:** `TRC-B4`
- **Intent:** `INT-2`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### A file that must not be scanned is checked directly

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-2`
- **Source issue:** `exemptions-that-exclude-nothing`
- **Landed:** 2026-08-30

### TRC-B1

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-2`
- **Source issue:** `field-feedback-2026-07`
- **Landed:** 2026-07-27

### TRC-B2

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-2`
- **Source issue:** `field-feedback-2026-07`
- **Landed:** 2026-07-27

### TRC-B3

- **Scenario id:** `TRC-B3`
- **Intent:** `INT-2`
- **Source issue:** `field-feedback-2026-07`
- **Landed:** 2026-07-27

### TRC-B4

- **Scenario id:** `TRC-B4`
- **Intent:** `INT-2`
- **Source issue:** `field-feedback-2026-07`
- **Landed:** 2026-07-27

### Given a new source file created after `start` and a new test file the 

- **Scenario id:** `FUU-4`
- **Intent:** `INT-2`
- **Source issue:** `finish-commits-unrelated-untracked-files`
- **Landed:** 2026-09-29

### A failing test piped to tail records a false green today (baseline)

- **Scenario id:** `TRC-R2-1`
- **Intent:** `INT-2`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### pipefail/argv hardening turns the masked failure into a real red

- **Scenario id:** `TRC-R2-2`
- **Intent:** `INT-2`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### A legitimate non-piped command still records green unchanged

- **Scenario id:** `TRC-R2-3`
- **Intent:** `INT-2`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### The detect-and-warn heuristic fires on a pager/filter final stage

- **Scenario id:** `TRC-R2-4`
- **Intent:** `INT-2`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### Output-token cross-check catches a green that lacks a pass token

- **Scenario id:** `TRC-R2-5`
- **Intent:** `INT-2`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### recurring friction is grouped by category and proposed change

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-2`
- **Source issue:** `friction-loop`
- **Landed:** 2026-06-04

### the friction view emits machine-readable JSON

- **Scenario id:** `TRC-B3`
- **Intent:** `INT-2`
- **Source issue:** `friction-loop`
- **Landed:** 2026-06-04

### a landed task without an approval is reported, not failed

- **Scenario id:** `SCN-C1`
- **Intent:** `INT-2`
- **Source issue:** `g5-trigger-matches-statement`
- **Landed:** 2026-08-13

### a waived rule should read as deliberate, not as drift

- **Scenario id:** `TRC-B3`
- **Intent:** `INT-2`
- **Source issue:** `governance-drift-detection`
- **Landed:** 

### a waiver without a reason should be refused

- **Scenario id:** `TRC-B4`
- **Intent:** `INT-2`
- **Source issue:** `governance-drift-detection`
- **Landed:** 

### waiving a rule the framework does not ship should be refused

- **Scenario id:** `TRC-B5`
- **Intent:** `INT-2`
- **Source issue:** `governance-drift-detection`
- **Landed:** 

### the waived block should be declared in the schema

- **Scenario id:** `TRC-B8`
- **Intent:** `INT-2`
- **Source issue:** `governance-drift-detection`
- **Landed:** 

### an unrecognised kind is refused

- **Scenario id:** `SCN-A3`
- **Intent:** `INT-2`
- **Source issue:** `honest-acceptance-for-config-and-refactor`
- **Landed:** 2026-08-13

### a failing validator does not close the acceptance

- **Scenario id:** `SCN-B2`
- **Intent:** `INT-2`
- **Source issue:** `honest-acceptance-for-config-and-refactor`
- **Landed:** 2026-08-13

### an acceptance does not survive into the next task

- **Scenario id:** `SCN-C2`
- **Intent:** `INT-2`
- **Source issue:** `honest-acceptance-for-config-and-refactor`
- **Landed:** 2026-08-13

### an undetectable write is a documented limit, not a silent one

- **Scenario id:** `SCN-F1`
- **Intent:** `INT-2`
- **Source issue:** `hook-bash-write-bypass`
- **Landed:** 2026-08-13

### G2 is checked before the red

- **Scenario id:** `SCN-F2`
- **Intent:** `INT-2`
- **Source issue:** `hook-enforces-g2`
- **Landed:** 2026-08-13

### the hook says why it could not check

- **Scenario id:** `TRC-2`
- **Intent:** `INT-2`
- **Source issue:** `hook-fails-open-on-broken-vendor`
- **Landed:** 

### A config that does not parse does not unguard code_globs

- **Scenario id:** `HFM-3`
- **Intent:** `INT-2`
- **Source issue:** `hook-failure-matrix`
- **Landed:** 2026-09-24

### the post-hook retry re-stages only the task's files

- **Scenario id:** `SCN-B1`
- **Intent:** `INT-2`
- **Source issue:** `hotfix-1-8-1-false-blocks-and-land-scope`
- **Landed:** 2026-08-13

### an out-of-scope staged path aborts the commit

- **Scenario id:** `SCN-B2`
- **Intent:** `INT-2`
- **Source issue:** `hotfix-1-8-1-false-blocks-and-land-scope`
- **Landed:** 2026-08-13

### a task that declares nothing is not silently widened

- **Scenario id:** `SCN-B3`
- **Intent:** `INT-2`
- **Source issue:** `hotfix-1-8-1-false-blocks-and-land-scope`
- **Landed:** 2026-08-13

### the reference should live under an existing skill and open with the principle

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-2`
- **Source issue:** `human-voice`
- **Landed:** 2026-08-09

### the tells should live in one place, so a later edit cannot leave a stale copy

- **Scenario id:** `TRC-B3`
- **Intent:** `INT-2`
- **Source issue:** `human-voice`
- **Landed:** 2026-08-09

### a tell that is found should block nothing

- **Scenario id:** `TRC-F1`
- **Intent:** `INT-2`
- **Source issue:** `human-voice`
- **Landed:** 2026-08-09

### nothing about how Compass behaves should change

- **Scenario id:** `TRC-F3`
- **Intent:** `INT-2`
- **Source issue:** `human-voice`
- **Landed:** 2026-08-09

### the document is reshaped, not copied

- **Scenario id:** `ING-B1`
- **Intent:** `INT-2`
- **Source issue:** `ingest-an-existing-brief`
- **Landed:** 2026-08-25

### a gap becomes a question, not a TBD

- **Scenario id:** `ING-B2`
- **Intent:** `INT-2`
- **Source issue:** `ingest-an-existing-brief`
- **Landed:** 2026-08-25

### nothing is invented

- **Scenario id:** `ING-B3`
- **Intent:** `INT-2`
- **Source issue:** `ingest-an-existing-brief`
- **Landed:** 2026-08-25

### a person can decline every question and still get an intent.md

- **Scenario id:** `ING-B4`
- **Intent:** `INT-2`
- **Source issue:** `ingest-an-existing-brief`
- **Landed:** 2026-08-25

### the fidelity gate reports which human the material came from

- **Scenario id:** `ING-E1`
- **Intent:** `INT-2`
- **Source issue:** `ingest-an-existing-brief`
- **Landed:** 2026-08-25

### the resident cost is bounded

- **Scenario id:** `IV-A1`
- **Intent:** `INT-2`
- **Source issue:** `instruction-volume`
- **Landed:** 2026-08-27

### no skill loads whole to answer one question

- **Scenario id:** `IV-C1`
- **Intent:** `INT-2`
- **Source issue:** `instruction-volume`
- **Landed:** 2026-08-27

### the generator should normalise house style on write

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-2`
- **Source issue:** `living-spec-and-process-impact`
- **Landed:** 

### the derived file should pass the repository's own style test

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-2`
- **Source issue:** `living-spec-and-process-impact`
- **Landed:** 

### a not-yet-landed task is labeled in-progress, not rendered as a final receipt

- **Scenario id:** `TRC-D1`
- **Intent:** `INT-2`
- **Source issue:** `make-receipt-render`
- **Landed:** 2026-05-26

### no live surface carries the retired word

- **Scenario id:** `NIR-B1`
- **Intent:** `INT-2`
- **Source issue:** `name-the-issue-record`
- **Landed:** 2026-08-27

### the old name survives only where history needs it

- **Scenario id:** `NIR-B2`
- **Intent:** `INT-2`
- **Source issue:** `name-the-issue-record`
- **Landed:** 2026-08-27

### the file, the CLI and the module agree

- **Scenario id:** `NIR-C1`
- **Intent:** `INT-2`
- **Source issue:** `name-the-issue-record`
- **Landed:** 2026-08-27

### the freeze ceremony is paid

- **Scenario id:** `NIR-E1`
- **Intent:** `INT-2`
- **Source issue:** `name-the-issue-record`
- **Landed:** 2026-08-27

### the same issue without the pointer still fails

- **Scenario id:** `DEL-A2`
- **Intent:** `INT-2`
- **Source issue:** `no-status-for-work-done-elsewhere`
- **Landed:** 2026-08-26

### several entries are all checked

- **Scenario id:** `DEL-A3`
- **Intent:** `INT-2`
- **Source issue:** `no-status-for-work-done-elsewhere`
- **Landed:** 2026-08-26

### a pointer at an issue that does not exist fails

- **Scenario id:** `DEL-B1`
- **Intent:** `INT-2`
- **Source issue:** `no-status-for-work-done-elsewhere`
- **Landed:** 2026-08-26

### a pointer at an issue that has not landed fails

- **Scenario id:** `DEL-B2`
- **Intent:** `INT-2`
- **Source issue:** `no-status-for-work-done-elsewhere`
- **Landed:** 2026-08-26

### a pointer at an issue with no record of its own fails

- **Scenario id:** `DEL-B3`
- **Intent:** `INT-2`
- **Source issue:** `no-status-for-work-done-elsewhere`
- **Landed:** 2026-08-26

### a pointer is only meaningful on a landed issue

- **Scenario id:** `DEL-B4`
- **Intent:** `INT-2`
- **Source issue:** `no-status-for-work-done-elsewhere`
- **Landed:** 2026-08-26

### a pointer the named issue does not acknowledge fails

- **Scenario id:** `DEL-B5`
- **Intent:** `INT-2`
- **Source issue:** `no-status-for-work-done-elsewhere`
- **Landed:** 2026-08-26

### a commit that does not resolve fails

- **Scenario id:** `DEL-D2`
- **Intent:** `INT-2`
- **Source issue:** `no-status-for-work-done-elsewhere`
- **Landed:** 2026-08-26

### a commit with no explanation fails

- **Scenario id:** `DEL-D3`
- **Intent:** `INT-2`
- **Source issue:** `no-status-for-work-done-elsewhere`
- **Landed:** 2026-08-26

### without git, the commit form declines rather than passes

- **Scenario id:** `DEL-D4`
- **Intent:** `INT-2`
- **Source issue:** `no-status-for-work-done-elsewhere`
- **Landed:** 2026-08-26

### A dispatch records its subtask

- **Scenario id:** `OLH-1`
- **Intent:** `INT-2`
- **Source issue:** `orchestrator-loop-hardening`
- **Landed:** 2026-09-25

### a suggestion should be checked against the code before it is acted on

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-2`
- **Source issue:** `phase-2-skills-check-and-cli-split`
- **Landed:** 

### the skill should shape disagreement rather than forbid it

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-2`
- **Source issue:** `phase-2-skills-check-and-cli-split`
- **Landed:** 

### the skill should be short enough to be read at the moment of use

- **Scenario id:** `TRC-B3`
- **Intent:** `INT-2`
- **Source issue:** `phase-2-skills-check-and-cli-split`
- **Landed:** 

### the strategy should state the order, with real pairs

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-2`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### an empty gloss registry should fail loudly, never report zero

- **Scenario id:** `TRC-C10`
- **Intent:** `INT-2`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### every screen printing a fired rule should put the meaning first

- **Scenario id:** `TRC-C15`
- **Intent:** `INT-2`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### a bare code in human-facing output should be counted

- **Scenario id:** `TRC-C2`
- **Intent:** `INT-2`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### a code with its meaning in front of it should not be counted

- **Scenario id:** `TRC-C3`
- **Intent:** `INT-2`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### a non-zero count should report rather than block

- **Scenario id:** `TRC-C4`
- **Intent:** `INT-2`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### the reviewer should be told to look for this

- **Scenario id:** `TRC-C5`
- **Intent:** `INT-2`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### the first run should record a starting count

- **Scenario id:** `TRC-C6`
- **Intent:** `INT-2`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### the meaning arriving after the code should still be counted

- **Scenario id:** `TRC-C7`
- **Intent:** `INT-2`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### an entry that is only an identifier should not have to gloss itself

- **Scenario id:** `TRC-C8`
- **Intent:** `INT-2`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### a banned word should never be fixed by deleting the identifier

- **Scenario id:** `TRC-X3`
- **Intent:** `INT-2`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### a command should be refused when the CI environment says the contribution is untrusted

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-2`
- **Source issue:** `project-commands-are-a-trust-boundary`
- **Landed:** 2026-08-22

### the repository must not be able to switch the refusal off

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-2`
- **Source issue:** `project-commands-are-a-trust-boundary`
- **Landed:** 2026-08-22

### detection should not depend on one CI provider

- **Scenario id:** `TRC-B3`
- **Intent:** `INT-2`
- **Source issue:** `project-commands-are-a-trust-boundary`
- **Landed:** 2026-08-22

### an ordinary local run should not be treated as untrusted

- **Scenario id:** `TRC-B4`
- **Intent:** `INT-2`
- **Source issue:** `project-commands-are-a-trust-boundary`
- **Landed:** 2026-08-22

### an unrecognised CI provider should be refused rather than trusted

- **Scenario id:** `TRC-B5`
- **Intent:** `INT-2`
- **Source issue:** `project-commands-are-a-trust-boundary`
- **Landed:** 2026-08-22

### No sentence is left broken by an earlier find-and-replace

- **Scenario id:** `PBW-A9`
- **Intent:** `INT-2`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### A document leads with the point

- **Scenario id:** `PBW-B1`
- **Intent:** `INT-2`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### Each sentence makes one point

- **Scenario id:** `PBW-B2`
- **Intent:** `INT-2`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### A set of items is a vertical list

- **Scenario id:** `PBW-B3`
- **Intent:** `INT-2`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### "must", "can" and "do not" say which is which

- **Scenario id:** `PBW-B4`
- **Intent:** `INT-2`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### The actor is named before the action

- **Scenario id:** `PBW-B5`
- **Intent:** `INT-2`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### A test docstring says what the file tests and cites its issue by slug

- **Scenario id:** `PBW-C5`
- **Intent:** `INT-2`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### A rewritten instruction still instructs the same behaviour

- **Scenario id:** `PBW-F7`
- **Intent:** `INT-2`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### A clarity review that read less than the sampling rule is refused

- **Scenario id:** `PBW-F8`
- **Intent:** `INT-2`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### a retired stage name alone in a table cell should be caught

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-2`
- **Source issue:** `public-docs-tell-the-truth`
- **Landed:** 2026-08-22

### a retired stage name alone in a bold run should be caught

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-2`
- **Source issue:** `public-docs-tell-the-truth`
- **Landed:** 2026-08-22

### every retired stage name should be bound to the label shape, not only Frame

- **Scenario id:** `TRC-B3`
- **Intent:** `INT-2`
- **Source issue:** `public-docs-tell-the-truth`
- **Landed:** 2026-08-22

### the scan should report the count it found, not only that it found some

- **Scenario id:** `TRC-B4`
- **Intent:** `INT-2`
- **Source issue:** `public-docs-tell-the-truth`
- **Landed:** 2026-08-22

### a retired stage name used mid-sentence should be caught

- **Scenario id:** `TRC-B5`
- **Intent:** `INT-2`
- **Source issue:** `public-docs-tell-the-truth`
- **Landed:** 2026-08-22

### history should stay exempt and stay honest

- **Scenario id:** `TRC-D3`
- **Intent:** `INT-2`
- **Source issue:** `public-docs-tell-the-truth`
- **Landed:** 2026-08-22

### the spec-author should be told to write the Summary during Specify

- **Scenario id:** `TRC-A5`
- **Intent:** `INT-2`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### the guide should show S7 applied to four kinds of artifact

- **Scenario id:** `TRC-E1`
- **Intent:** `INT-2`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### each worked example should show the weak version beside the improved one

- **Scenario id:** `TRC-E2`
- **Intent:** `INT-2`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### the guide should be reachable from the docs a new reader opens

- **Scenario id:** `TRC-E4`
- **Intent:** `INT-2`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### A first write records no re-assessment

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-2`
- **Source issue:** `reassessment-log-drops-reading-only-changes`
- **Landed:** 2026-08-30

### a second friction note should not destroy the first

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-2`
- **Source issue:** `record-keeping-integrity`
- **Landed:** 2026-08-03

### re-running the capture should not duplicate derived entries

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-2`
- **Source issue:** `record-keeping-integrity`
- **Landed:** 2026-08-03

### An unstamped red written before the cutoff still unlocks

- **Scenario id:** `RIC-2`
- **Intent:** `INT-2`
- **Source issue:** `red-record-identity-cutoff`
- **Landed:** 2026-09-24

### A project with no cutoff behaves as today

- **Scenario id:** `RIC-3`
- **Intent:** `INT-2`
- **Source issue:** `red-record-identity-cutoff`
- **Landed:** 2026-09-24

### A stamped red is judged by its digest in every project

- **Scenario id:** `RIC-4`
- **Intent:** `INT-2`
- **Source issue:** `red-record-identity-cutoff`
- **Landed:** 2026-09-24

### the upgrade notes name the removed skills

- **Scenario id:** `REL-3`
- **Intent:** `INT-2`
- **Source issue:** `release-5-0-0`
- **Landed:** 2026-09-24

### landing must not be recorded over gates that have not passed

- **Scenario id:** `SCN-11`
- **Intent:** `INT-2`
- **Source issue:** `release-blockers-2026-08`
- **Landed:** 2026-08-13

### a receipt must not report a clean land over pending gates

- **Scenario id:** `SCN-12`
- **Intent:** `INT-2`
- **Source issue:** `release-blockers-2026-08`
- **Landed:** 2026-08-13

### the analyze summary must agree with the findings above it

- **Scenario id:** `SCN-13`
- **Intent:** `INT-2`
- **Source issue:** `release-blockers-2026-08`
- **Landed:** 2026-08-13

### a lint must report a malformed file, not crash on it

- **Scenario id:** `SCN-14`
- **Intent:** `INT-2`
- **Source issue:** `release-blockers-2026-08`
- **Landed:** 2026-08-13

### a different test command must not read as a rerun-to-green

- **Scenario id:** `SCN-17`
- **Intent:** `INT-2`
- **Source issue:** `release-blockers-2026-08`
- **Landed:** 2026-08-13

### the contract exists once

- **Scenario id:** `SB-B1`
- **Intent:** `INT-2`
- **Source issue:** `session-bootstrap`
- **Landed:** 2026-08-27

### the two Claude Code documents share no sentence

- **Scenario id:** `SB-B2`
- **Intent:** `INT-2`
- **Source issue:** `session-bootstrap`
- **Landed:** 2026-08-27

### the runtime-neutral document is left alone

- **Scenario id:** `SB-B3`
- **Intent:** `INT-2`
- **Source issue:** `session-bootstrap`
- **Landed:** 2026-08-27

### the contract names every agent that exists

- **Scenario id:** `SB-B4`
- **Intent:** `INT-2`
- **Source issue:** `session-bootstrap`
- **Landed:** 2026-08-27

### Six scenarios cover the failure modes

- **Scenario id:** `SPT-2`
- **Intent:** `INT-2`
- **Source issue:** `skill-prose-pressure-tests`
- **Landed:** 2026-09-27

### each entry carries a kind

- **Scenario id:** `SCN-A4`
- **Intent:** `INT-2`
- **Source issue:** `spine-records-the-truth`
- **Landed:** 2026-08-13

### calibration counts only judgement re-frames

- **Scenario id:** `SCN-A5`
- **Intent:** `INT-2`
- **Source issue:** `spine-records-the-truth`
- **Landed:** 2026-08-13

### The safety contract names one start version

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-2`
- **Source issue:** `stale-command-names-in-shipped-prose`
- **Landed:** 2026-08-30

### the new statuses validate

- **Scenario id:** `SCN-A1`
- **Intent:** `INT-2`
- **Source issue:** `status-vocabulary`
- **Landed:** 2026-08-13

### a recorded run carries an identity unique to that run

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-2`
- **Source issue:** `tdd-green-unbound-record`
- **Landed:** 2026-08-23

### re-recording the same command produces a different identity

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-2`
- **Source issue:** `tdd-green-unbound-record`
- **Landed:** 2026-08-23

### the registry entry stores the identity of the run it was created from

- **Scenario id:** `TRC-B3`
- **Intent:** `INT-2`
- **Source issue:** `tdd-green-unbound-record`
- **Landed:** 2026-08-23

### a registered path resolves ahead of the flat filename

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-2`
- **Source issue:** `the-human-front-door`
- **Landed:** 2026-08-23

### an issue with no registry still resolves its artifacts

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-2`
- **Source issue:** `the-human-front-door`
- **Landed:** 2026-08-23

### an artifact that resolves by neither route is reported, not silently absent

- **Scenario id:** `TRC-B3`
- **Intent:** `INT-2`
- **Source issue:** `the-human-front-door`
- **Landed:** 2026-08-23

### every landed issue still resolves after the change

- **Scenario id:** `TRC-B4`
- **Intent:** `INT-2`
- **Source issue:** `the-human-front-door`
- **Landed:** 2026-08-23

### evidence-out writes the raw capture rather than printing it

- **Scenario id:** `TRC-C4`
- **Intent:** `INT-2`
- **Source issue:** `the-terminal-output-contract`
- **Landed:** 2026-08-24

### evidence-out on a verb with nothing to capture

- **Scenario id:** `TRC-C7`
- **Intent:** `INT-2`
- **Source issue:** `the-terminal-output-contract`
- **Landed:** 2026-08-24

### a spine written before the rename still reads

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-2`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### a document written before the rename still resolves

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-2`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### both spellings are accepted before any caller switches

- **Scenario id:** `TRC-B3`
- **Intent:** `INT-2`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### the retired commands answer with a pointer

- **Scenario id:** `TRC-B4`
- **Intent:** `INT-2`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### a document written after the rename resolves under its new name

- **Scenario id:** `TRC-B5`
- **Intent:** `INT-2`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### the current filename wins when both are present

- **Scenario id:** `TRC-B6`
- **Intent:** `INT-2`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### the design lint still reads a landed issue's design

- **Scenario id:** `TRC-B7`
- **Intent:** `INT-2`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### a policy floor written with a retired stage key still applies

- **Scenario id:** `TRC-B8`
- **Intent:** `INT-2`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### migrate refuses a many-to-one filename collision

- **Scenario id:** `TRC-C5`
- **Intent:** `INT-2`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### the message offers the new path when git knows the rename

- **Scenario id:** `SCN-A2`
- **Intent:** `INT-2`
- **Source issue:** `trace-rot-detection`
- **Landed:** 2026-08-13

### An acceptance record stands in for a red

- **Scenario id:** `UGR-3`
- **Intent:** `INT-2`
- **Source issue:** `unbound-green-needs-no-red`
- **Landed:** 2026-09-24

### the repository archive speaks schema 2.0

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-2`
- **Source issue:** `v2-machine-spine`
- **Landed:** 2026-08-07

### the archive carries v2 artifact names

- **Scenario id:** `TRC-A4`
- **Intent:** `INT-2`
- **Source issue:** `v2-machine-spine`
- **Landed:** 2026-08-07

### the artifact-name fallback is retired

- **Scenario id:** `TRC-A5`
- **Intent:** `INT-2`
- **Source issue:** `v2-machine-spine`
- **Landed:** 2026-08-07

### the spine template speaks v2 and is scanned

- **Scenario id:** `TRC-A6`
- **Intent:** `INT-2`
- **Source issue:** `v2-machine-spine`
- **Landed:** 2026-08-07

### the vocabulary freeze is recorded as an accepted, indexed decision record

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-2`
- **Source issue:** `v2-prd-and-freeze-adr`
- **Landed:** 2026-08-07

### code-quoted machine identifiers stay legal on scanned markdown

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-2`
- **Source issue:** `v2-session-instructions`
- **Landed:** 2026-08-07

### a banned usage in a fixture is flagged

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-2`
- **Source issue:** `v2-terminology-freeze`
- **Landed:** 2026-08-06

### an innocent usage of the same words is not flagged

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-2`
- **Source issue:** `v2-terminology-freeze`
- **Landed:** 2026-08-06

### the deep dive names the gates the policy staples

- **Scenario id:** `VOC-C1`
- **Intent:** `INT-2`
- **Source issue:** `vocabulary-debt`
- **Landed:** 2026-08-27

### the deep dive does not claim scoped gates are immovable

- **Scenario id:** `VOC-C2`
- **Intent:** `INT-2`
- **Source issue:** `vocabulary-debt`
- **Landed:** 2026-08-27

### The revival condition is readable from the record alone

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-2`
- **Source issue:** `what-compass-owes-an-unobserved-adopter`
- **Landed:** 2026-08-28

### the acceptance-before-code hook check runs instead of failing open

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-2`
- **Source issue:** `zero-friction-install`
- **Landed:** 2026-08-10

### integration records the landing rather than warning it could not

- **Scenario id:** `TRC-A4`
- **Intent:** `INT-2`
- **Source issue:** `zero-friction-install`
- **Landed:** 2026-08-10

### preparing a swarm reads the cap rather than refusing

- **Scenario id:** `TRC-A7`
- **Intent:** `INT-2`
- **Source issue:** `zero-friction-install`
- **Landed:** 2026-08-10

### an issue already in flight continues unchanged across the upgrade

- **Scenario id:** `TRC-F4`
- **Intent:** `INT-2`
- **Source issue:** `zero-friction-install`
- **Landed:** 2026-08-10

### jsonschema stays optional and unchanged

- **Scenario id:** `TRC-F5`
- **Intent:** `INT-2`
- **Source issue:** `zero-friction-install`
- **Landed:** 2026-08-10

### the bundled copy is the one used, whatever the machine has

- **Scenario id:** `TRC-G1`
- **Intent:** `INT-2`
- **Source issue:** `zero-friction-install`
- **Landed:** 2026-08-10

### the template records when the rollback was last rehearsed

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-3`
- **Source issue:** `adaptive-artifact-composition`
- **Landed:** 2026-08-24

### the evidence type stops accepting a plan as a rollback

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-3`
- **Source issue:** `adaptive-artifact-composition`
- **Landed:** 2026-08-24

### a rollback plan with no rehearsal date is caught

- **Scenario id:** `TRC-B3`
- **Intent:** `INT-3`
- **Source issue:** `adaptive-artifact-composition`
- **Landed:** 2026-08-24

### the rule is attached to a moment, not stated as advice

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-3`
- **Source issue:** `agent-speech-is-unchecked`
- **Landed:** 2026-08-23

### An existing manifest written with topology still loads

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-3`
- **Source issue:** `anthropic-aligned-vocabulary`
- **Landed:** 2026-08-28

### A retired topology word is read as the ceiling it always implied

- **Scenario id:** `TRC-B3`
- **Intent:** `INT-3`
- **Source issue:** `anthropic-aligned-vocabulary`
- **Landed:** 2026-08-28

### A retired command name still resolves

- **Scenario id:** `TRC-C2`
- **Intent:** `INT-3`
- **Source issue:** `anthropic-aligned-vocabulary`
- **Landed:** 2026-08-28

### A decision record keeps the words it was decided in

- **Scenario id:** `TRC-D4`
- **Intent:** `INT-3`
- **Source issue:** `anthropic-aligned-vocabulary`
- **Landed:** 2026-08-28

### A key rename that silently drops data fails the build

- **Scenario id:** `TRC-F2`
- **Intent:** `INT-3`
- **Source issue:** `anthropic-aligned-vocabulary`
- **Landed:** 2026-08-28

### the review skill should be within its stated length

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-3`
- **Source issue:** `bdd-adapters-and-skill-length`
- **Landed:** 

### the guide should say that project governance is executable code

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-3`
- **Source issue:** `claims-match-what-is-proved`
- **Landed:** 2026-08-22

### the guide should not offer pull-request review as the execution boundary

- **Scenario id:** `TRC-C2`
- **Intent:** `INT-3`
- **Source issue:** `claims-match-what-is-proved`
- **Landed:** 2026-08-22

### the guide should point at the work that closes the gap

- **Scenario id:** `TRC-C3`
- **Intent:** `INT-3`
- **Source issue:** `claims-match-what-is-proved`
- **Landed:** 2026-08-22

### a circular import should be impossible by construction

- **Scenario id:** `TRC-F1`
- **Intent:** `INT-3`
- **Source issue:** `cli-module-split`
- **Landed:** 

### asking the agent to build something triggers Frame without naming it

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-3`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### explicit invocation of a Compass command still works

- **Scenario id:** `TRC-C2`
- **Intent:** `INT-3`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### an exploratory request still gets framed (as a Spike)

- **Scenario id:** `TRC-C3`
- **Intent:** `INT-3`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### next reports the upcoming phase and gate in one line

- **Scenario id:** `TRC-C4`
- **Intent:** `INT-3`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### next states which phases are optional on this route

- **Scenario id:** `TRC-C5`
- **Intent:** `INT-3`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### next on a completed task reports nothing remains

- **Scenario id:** `TRC-C6`
- **Intent:** `INT-3`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### next on a task with no Frame reports that Frame is needed

- **Scenario id:** `TRC-C9`
- **Intent:** `INT-3`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### invisible triggering does not re-frame an already-framed task

- **Scenario id:** `TRC-F3`
- **Intent:** `INT-3`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### next on a task whose route.md is missing reports the missing artifact

- **Scenario id:** `TRC-F6`
- **Intent:** `INT-3`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### At least one ADR demonstrates substantive alternatives + negative consequences

- **Scenario id:** `TRC-B4`
- **Intent:** `INT-3`
- **Source issue:** `compass-self-architecture`
- **Landed:** 

### a project cannot exempt what the framework enforces

- **Scenario id:** `SCN-A4`
- **Intent:** `INT-3`
- **Source issue:** `configurable-enforced-set`
- **Landed:** 2026-08-13

### test files stay exempt whatever the config says

- **Scenario id:** `SCN-F2`
- **Intent:** `INT-3`
- **Source issue:** `configurable-enforced-set`
- **Landed:** 2026-08-13

### Stop-hook nudges when scope-bloat phrases appear in devlog

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-3`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### Stop-hook stays silent when no scope-bloat is detected

- **Scenario id:** `TRC-C2`
- **Intent:** `INT-3`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### Stop-hook stays silent when a reframe has already been filed

- **Scenario id:** `TRC-C3`
- **Intent:** `INT-3`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### Roundtable doc requires reframe on boundary or migration decisions

- **Scenario id:** `TRC-C4`
- **Intent:** `INT-3`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### compass calibration surfaces absorbed mis-frames

- **Scenario id:** `TRC-C5`
- **Intent:** `INT-3`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### Flow digest includes calibration's reframe-debt

- **Scenario id:** `TRC-C6`
- **Intent:** `INT-3`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### Stop-hook regex must not produce false positives on common devlog content

- **Scenario id:** `TRC-X3`
- **Intent:** `INT-3`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### The scripts find an issue's documents through the registry

- **Scenario id:** `DPR-2`
- **Intent:** `INT-3`
- **Source issue:** `dispatch-protocol`
- **Landed:** 2026-09-25

### A registered document outside the issue directory resolves

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-3`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### A registered path is anchored to the project, not to the caller

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-3`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### The schema says where a registered path is measured from

- **Scenario id:** `TRC-A4`
- **Intent:** `INT-3`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### A reader finds a relocated document

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-3`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### No reader builds its own path to a document

- **Scenario id:** `TRC-C2`
- **Intent:** `INT-3`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### A missed reader is caught by the test, not by a user

- **Scenario id:** `TRC-C3`
- **Intent:** `INT-3`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### The verification report is found where the registry says

- **Scenario id:** `TRC-C4`
- **Intent:** `INT-3`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### A missed reader turns a guardrail check red, never green

- **Scenario id:** `TRC-C5`
- **Intent:** `INT-3`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### The pre-tool hook accepts a relocated delivery-approach record

- **Scenario id:** `TRC-D1`
- **Intent:** `INT-3`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### The pre-tool hook still blocks when assessment really has not run

- **Scenario id:** `TRC-D2`
- **Intent:** `INT-3`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### The stop hook reads the three documents it warns about

- **Scenario id:** `TRC-D3`
- **Intent:** `INT-3`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### A document registered at a path that does not exist

- **Scenario id:** `TRC-G1`
- **Intent:** `INT-3`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### A registered path that climbs out of the project

- **Scenario id:** `TRC-G4`
- **Intent:** `INT-3`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### every CLI module's banner describes what the verbs actually write

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-3`
- **Source issue:** `docs-describe-the-old-evidence-path`
- **Landed:** 2026-08-23

### a guard taught a new shape can still fail

- **Scenario id:** `DOC-A3`
- **Intent:** `INT-3`
- **Source issue:** `docs-slimming-pass`
- **Landed:** 2026-08-26

### a retired guard says what stopped being covered

- **Scenario id:** `DOC-A4`
- **Intent:** `INT-3`
- **Source issue:** `docs-slimming-pass`
- **Landed:** 2026-08-26

### A landed issue is checked against the commit that landed it

- **Scenario id:** `EVB-5`
- **Intent:** `INT-3`
- **Source issue:** `evidence-binding`
- **Landed:** 2026-09-25

### Records without a tree are not judged

- **Scenario id:** `EVB-6`
- **Intent:** `INT-3`
- **Source issue:** `evidence-binding`
- **Landed:** 2026-09-25

### the plan template should offer the five optional sections

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-3`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### each optional section should state its own inclusion rule

- **Scenario id:** `TRC-C2`
- **Intent:** `INT-3`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### the existing plan sections should survive unchanged

- **Scenario id:** `TRC-C3`
- **Intent:** `INT-3`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### the planner's section choice should scale with the route

- **Scenario id:** `TRC-C4`
- **Intent:** `INT-3`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### a named pattern should require a stated reason

- **Scenario id:** `TRC-C5`
- **Intent:** `INT-3`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### the writing guide should carry a worked plan

- **Scenario id:** `TRC-C6`
- **Intent:** `INT-3`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### TRC-C1

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-3`
- **Source issue:** `field-feedback-2026-07`
- **Landed:** 2026-07-27

### TRC-C2

- **Scenario id:** `TRC-C2`
- **Intent:** `INT-3`
- **Source issue:** `field-feedback-2026-07`
- **Landed:** 2026-07-27

### TRC-C3

- **Scenario id:** `TRC-C3`
- **Intent:** `INT-3`
- **Source issue:** `field-feedback-2026-07`
- **Landed:** 2026-07-27

### TRC-C4

- **Scenario id:** `TRC-C4`
- **Intent:** `INT-3`
- **Source issue:** `field-feedback-2026-07`
- **Landed:** 2026-07-27

### TRC-C5

- **Scenario id:** `TRC-C5`
- **Intent:** `INT-3`
- **Source issue:** `field-feedback-2026-07`
- **Landed:** 2026-07-27

### TRC-F1

- **Scenario id:** `TRC-F1`
- **Intent:** `INT-3`
- **Source issue:** `field-feedback-2026-07`
- **Landed:** 2026-07-27

### Given any successful `finish`, when it prints its hand-off, then the h

- **Scenario id:** `FUU-6`
- **Intent:** `INT-3`
- **Source issue:** `finish-commits-unrelated-untracked-files`
- **Landed:** 2026-09-29

### A corpus-shaped scenario fails task lint while passing compass check today (baseline)

- **Scenario id:** `TRC-R3-1`
- **Intent:** `INT-3`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### After the schema fix, the corpus scenario shape passes task lint

- **Scenario id:** `TRC-R3-2`
- **Intent:** `INT-3`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### A plain-string intent still passes task lint after the widening

- **Scenario id:** `TRC-R3-3`
- **Intent:** `INT-3`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### A numeric intent still fails task lint after the widening

- **Scenario id:** `TRC-R3-4`
- **Intent:** `INT-3`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### A list intent with a non-string element still fails task lint

- **Scenario id:** `TRC-R3-5`
- **Intent:** `INT-3`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### recording no friction is a valid, common Land

- **Scenario id:** `TRC-A5`
- **Intent:** `INT-3`
- **Source issue:** `friction-loop`
- **Landed:** 2026-06-04

### a one-off friction item stays below the recurrence threshold

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-3`
- **Source issue:** `friction-loop`
- **Landed:** 2026-06-04

### friction capture never blocks Land

- **Scenario id:** `TRC-F1`
- **Intent:** `INT-3`
- **Source issue:** `friction-loop`
- **Landed:** 2026-06-04

### the friction view is read-only and never auto-tunes governance

- **Scenario id:** `TRC-F2`
- **Intent:** `INT-3`
- **Source issue:** `friction-loop`
- **Landed:** 2026-06-04

### the domain trigger is unchanged

- **Scenario id:** `SCN-A3`
- **Intent:** `INT-3`
- **Source issue:** `g5-trigger-matches-statement`
- **Landed:** 2026-08-13

### a task matching neither condition still skips G5

- **Scenario id:** `SCN-A4`
- **Intent:** `INT-3`
- **Source issue:** `g5-trigger-matches-statement`
- **Landed:** 2026-08-13

### any_of composes with sibling keys as an AND

- **Scenario id:** `SCN-B3`
- **Intent:** `INT-3`
- **Source issue:** `g5-trigger-matches-statement`
- **Landed:** 2026-08-13

### route evaluate should report which policy it read

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-3`
- **Source issue:** `governance-drift-detection`
- **Landed:** 

### a drifted project's route output should say so

- **Scenario id:** `TRC-C2`
- **Intent:** `INT-3`
- **Source issue:** `governance-drift-detection`
- **Landed:** 

### the route template should carry a provenance field

- **Scenario id:** `TRC-C3`
- **Intent:** `INT-3`
- **Source issue:** `governance-drift-detection`
- **Landed:** 

### a refactor acceptance requires a green baseline first

- **Scenario id:** `SCN-A2`
- **Intent:** `INT-3`
- **Source issue:** `honest-acceptance-for-config-and-refactor`
- **Landed:** 2026-08-13

### a refactor must run the same command it baselined

- **Scenario id:** `SCN-B3`
- **Intent:** `INT-3`
- **Source issue:** `honest-acceptance-for-config-and-refactor`
- **Landed:** 2026-08-13

### a refactor with an unchanged source tree is refused

- **Scenario id:** `SCN-B4`
- **Intent:** `INT-3`
- **Source issue:** `honest-acceptance-for-config-and-refactor`
- **Landed:** 2026-08-13

### a read-only command is allowed

- **Scenario id:** `SCN-B1`
- **Intent:** `INT-3`
- **Source issue:** `hook-bash-write-bypass`
- **Landed:** 2026-08-13

### writing a test file is allowed

- **Scenario id:** `SCN-B2`
- **Intent:** `INT-3`
- **Source issue:** `hook-bash-write-bypass`
- **Landed:** 2026-08-13

### a redirect to a non-code destination is allowed

- **Scenario id:** `SCN-B3`
- **Intent:** `INT-3`
- **Source issue:** `hook-bash-write-bypass`
- **Landed:** 2026-08-13

### a command that reverts to committed state is allowed

- **Scenario id:** `SCN-B4`
- **Intent:** `INT-3`
- **Source issue:** `hook-bash-write-bypass`
- **Landed:** 2026-08-13

### the hook adds no meaningful cost to ordinary commands

- **Scenario id:** `SCN-F2`
- **Intent:** `INT-3`
- **Source issue:** `hook-bash-write-bypass`
- **Landed:** 2026-08-13

### routes without a full Specify are unaffected

- **Scenario id:** `SCN-A3`
- **Intent:** `INT-3`
- **Source issue:** `hook-enforces-g2`
- **Landed:** 2026-08-13

### a Spike suspends the G2 check

- **Scenario id:** `SCN-A4`
- **Intent:** `INT-3`
- **Source issue:** `hook-enforces-g2`
- **Landed:** 2026-08-13

### a test file stays editable

- **Scenario id:** `SCN-B2`
- **Intent:** `INT-3`
- **Source issue:** `hook-enforces-g2`
- **Landed:** 2026-08-13

### The safety contract scopes the worktree redirect gap

- **Scenario id:** `HFM-5`
- **Intent:** `INT-3`
- **Source issue:** `hook-failure-matrix`
- **Landed:** 2026-09-24

### an inline script that opens a source file for writing is still blocked

- **Scenario id:** `SCN-A3`
- **Intent:** `INT-3`
- **Source issue:** `hotfix-1-8-1-false-blocks-and-land-scope`
- **Landed:** 2026-08-13

### a heredoc that writes a source file is still blocked

- **Scenario id:** `SCN-A4`
- **Intent:** `INT-3`
- **Source issue:** `hotfix-1-8-1-false-blocks-and-land-scope`
- **Landed:** 2026-08-13

### the 1.8.0 detection scenarios keep passing

- **Scenario id:** `SCN-F1`
- **Intent:** `INT-3`
- **Source issue:** `hotfix-1-8-1-false-blocks-and-land-scope`
- **Landed:** 2026-08-13

### an ingested brief says where it came from

- **Scenario id:** `ING-C1`
- **Intent:** `INT-3`
- **Source issue:** `ingest-an-existing-brief`
- **Landed:** 2026-08-25

### the reshaping is auditable

- **Scenario id:** `ING-C2`
- **Intent:** `INT-3`
- **Source issue:** `ingest-an-existing-brief`
- **Landed:** 2026-08-25

### a split skill says where its parts are

- **Scenario id:** `IV-C2`
- **Intent:** `INT-3`
- **Source issue:** `instruction-volume`
- **Landed:** 2026-08-27

### every frontmatter parses

- **Scenario id:** `IV-D1`
- **Intent:** `INT-3`
- **Source issue:** `instruction-volume`
- **Landed:** 2026-08-27

### the derivation should stay a derived artifact

- **Scenario id:** `TRC-F1`
- **Intent:** `INT-3`
- **Source issue:** `living-spec-and-process-impact`
- **Landed:** 

### a schema-1.0 task.yml (pre-status field) renders without error

- **Scenario id:** `TRC-D2`
- **Intent:** `INT-3`
- **Source issue:** `make-receipt-render`
- **Landed:** 2026-05-26

### a file written under the old name still loads

- **Scenario id:** `NIR-D1`
- **Intent:** `INT-3`
- **Source issue:** `name-the-issue-record`
- **Landed:** 2026-08-27

### the migrator moves the archive

- **Scenario id:** `NIR-D2`
- **Intent:** `INT-3`
- **Source issue:** `name-the-issue-record`
- **Landed:** 2026-08-27

### a delivered issue stops being recorded as abandoned

- **Scenario id:** `DEL-C1`
- **Intent:** `INT-3`
- **Source issue:** `no-status-for-work-done-elsewhere`
- **Landed:** 2026-08-26

### retro counts them as delivered

- **Scenario id:** `DEL-C2`
- **Intent:** `INT-3`
- **Source issue:** `no-status-for-work-done-elsewhere`
- **Landed:** 2026-08-26

### an issue that was decided against stays abandoned

- **Scenario id:** `DEL-C3`
- **Intent:** `INT-3`
- **Source issue:** `no-status-for-work-done-elsewhere`
- **Landed:** 2026-08-26

### A coaching reviewer brief is refused

- **Scenario id:** `OLH-6`
- **Intent:** `INT-3`
- **Source issue:** `orchestrator-loop-hardening`
- **Landed:** 2026-09-25

### the check should be registered and implemented

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-3`
- **Source issue:** `phase-2-skills-check-and-cli-split`
- **Landed:** 

### a project that has wired no runner should pass with a stated reason

- **Scenario id:** `TRC-C2`
- **Intent:** `INT-3`
- **Source issue:** `phase-2-skills-check-and-cli-split`
- **Landed:** 

### every scenario bound to a collected step definition should pass

- **Scenario id:** `TRC-C3`
- **Intent:** `INT-3`
- **Source issue:** `phase-2-skills-check-and-cli-split`
- **Landed:** 

### a scenario the runner never ran should be named

- **Scenario id:** `TRC-C4`
- **Intent:** `INT-3`
- **Source issue:** `phase-2-skills-check-and-cli-split`
- **Landed:** 

### a stale runner result should not be read as success

- **Scenario id:** `TRC-C5`
- **Intent:** `INT-3`
- **Source issue:** `phase-2-skills-check-and-cli-split`
- **Landed:** 

### the check should be advisory unless the route promotes it

- **Scenario id:** `TRC-C6`
- **Intent:** `INT-3`
- **Source issue:** `phase-2-skills-check-and-cli-split`
- **Landed:** 

### published launch copy should be under version control

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-3`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### an em dash in published copy should fail the guard

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-3`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### the filesystem fallback should not be used where git works

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-3`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### build noise should stay out of the scan

- **Scenario id:** `TRC-A4`
- **Intent:** `INT-3`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### the guard's docstring should record that the omission was silent

- **Scenario id:** `TRC-A5`
- **Intent:** `INT-3`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### an en dash should not be flagged

- **Scenario id:** `TRC-A6`
- **Intent:** `INT-3`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### falling back to the filesystem should announce itself

- **Scenario id:** `TRC-A8`
- **Intent:** `INT-3`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### a file declaring its own exclusions should not be tracked as publication copy

- **Scenario id:** `TRC-A9`
- **Intent:** `INT-3`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### a project should be able to name a script instead of writing a shell string

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-3`
- **Source issue:** `project-commands-are-a-trust-boundary`
- **Landed:** 2026-08-22

### a script path outside the project should be refused

- **Scenario id:** `TRC-C2`
- **Intent:** `INT-3`
- **Source issue:** `project-commands-are-a-trust-boundary`
- **Landed:** 2026-08-22

### the shell form should keep working, and say what it costs

- **Scenario id:** `TRC-C3`
- **Intent:** `INT-3`
- **Source issue:** `project-commands-are-a-trust-boundary`
- **Landed:** 2026-08-22

### A document describes the state now

- **Scenario id:** `PBW-B6`
- **Intent:** `INT-3`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### No document holds a changelog, a version banner or a dated count

- **Scenario id:** `PBW-B7`
- **Intent:** `INT-3`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### No document states a fact its source contradicts

- **Scenario id:** `PBW-B8`
- **Intent:** `INT-3`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### A copied block is fixed the same way in every file that holds it

- **Scenario id:** `PBW-C4`
- **Intent:** `INT-3`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### A clarity review that read less than the sampling rule is refused

- **Scenario id:** `PBW-F8`
- **Intent:** `INT-3`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### a retired word used as an ordinary verb should not be caught

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-3`
- **Source issue:** `public-docs-tell-the-truth`
- **Landed:** 2026-08-22

### a bold run that begins with a retired word but continues into a sentence should not be caught

- **Scenario id:** `TRC-C2`
- **Intent:** `INT-3`
- **Source issue:** `public-docs-tell-the-truth`
- **Landed:** 2026-08-22

### the tolerance fixture should carry every shape the patterns must walk past

- **Scenario id:** `TRC-C3`
- **Intent:** `INT-3`
- **Source issue:** `public-docs-tell-the-truth`
- **Landed:** 2026-08-22

### widening the patterns should not change what the scan reports on today's clean surfaces

- **Scenario id:** `TRC-C4`
- **Intent:** `INT-3`
- **Source issue:** `public-docs-tell-the-truth`
- **Landed:** 2026-08-22

### the self-review should list exactly the four scans

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-3`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### each scan should say concretely what it looks for

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-3`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### the self-review should be fixed inline, not re-reviewed

- **Scenario id:** `TRC-B3`
- **Intent:** `INT-3`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### the self-review should complement Clarify rather than replace it

- **Scenario id:** `TRC-B4`
- **Intent:** `INT-3`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### on a collapsed-Clarify route the self-check should be recorded on disk

- **Scenario id:** `TRC-B5`
- **Intent:** `INT-3`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### the check should name the prohibited phrases

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-3`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### an incomplete work unit should be reported

- **Scenario id:** `TRC-C1b`
- **Intent:** `INT-3`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### an advisory hit should be reported without failing the command

- **Scenario id:** `TRC-C2`
- **Intent:** `INT-3`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### the skill should tell the planner how to judge what the check reports

- **Scenario id:** `TRC-C2b`
- **Intent:** `INT-3`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### the check result should be recorded as judgement, not as evidence

- **Scenario id:** `TRC-C3`
- **Intent:** `INT-3`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### Specify should close by inviting a cold-reader review

- **Scenario id:** `TRC-D1`
- **Intent:** `INT-3`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### the Clarify and Plan hand-offs should be symmetric with Specify's

- **Scenario id:** `TRC-D2`
- **Intent:** `INT-3`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### the review-dimensions table should record who assessed each dimension

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-3`
- **Source issue:** `record-keeping-integrity`
- **Landed:** 2026-08-03

### the template should say what to write in that column

- **Scenario id:** `TRC-C2`
- **Intent:** `INT-3`
- **Source issue:** `record-keeping-integrity`
- **Landed:** 2026-08-03

### The safety contract states the cutoff

- **Scenario id:** `RIC-8`
- **Intent:** `INT-3`
- **Source issue:** `red-record-identity-cutoff`
- **Landed:** 2026-09-24

### every BDD adapter example must have the test files it declares

- **Scenario id:** `SCN-05`
- **Intent:** `INT-3`
- **Source issue:** `release-blockers-2026-08`
- **Landed:** 2026-08-13

### every shipped route example must pass its own checks

- **Scenario id:** `SCN-06`
- **Intent:** `INT-3`
- **Source issue:** `release-blockers-2026-08`
- **Landed:** 2026-08-13

### the behave adapter must report its bound scenarios correctly

- **Scenario id:** `SCN-07`
- **Intent:** `INT-3`
- **Source issue:** `release-blockers-2026-08`
- **Landed:** 2026-08-13

### a CI job that runs a Python tool must install Python first

- **Scenario id:** `SCN-08`
- **Intent:** `INT-3`
- **Source issue:** `release-blockers-2026-08`
- **Landed:** 2026-08-13

### an example's declared tests must point at real files

- **Scenario id:** `SCN-09`
- **Intent:** `INT-3`
- **Source issue:** `release-blockers-2026-08`
- **Landed:** 2026-08-13

### the onboarding transcript must match what the CLI prints

- **Scenario id:** `SCN-15`
- **Intent:** `INT-3`
- **Source issue:** `release-blockers-2026-08`
- **Landed:** 2026-08-13

### documented commands must exist

- **Scenario id:** `SCN-16`
- **Intent:** `INT-3`
- **Source issue:** `release-blockers-2026-08`
- **Landed:** 2026-08-13

### plugin-shipped paths resolve from any directory

- **Scenario id:** `SB-C1`
- **Intent:** `INT-3`
- **Source issue:** `session-bootstrap`
- **Landed:** 2026-08-27

### project governance still wins where a project has its own

- **Scenario id:** `SB-C2`
- **Intent:** `INT-3`
- **Source issue:** `session-bootstrap`
- **Landed:** 2026-08-27

### Behaviours are scored from actions and artifacts

- **Scenario id:** `SPT-3`
- **Intent:** `INT-3`
- **Source issue:** `skill-prose-pressure-tests`
- **Landed:** 2026-09-27

### a raw log declared as test-run is refused at write time

- **Scenario id:** `SCN-B1`
- **Intent:** `INT-3`
- **Source issue:** `spine-records-the-truth`
- **Landed:** 2026-08-13

### a real run record is accepted

- **Scenario id:** `SCN-B2`
- **Intent:** `INT-3`
- **Source issue:** `spine-records-the-truth`
- **Landed:** 2026-08-13

### a missing file is refused

- **Scenario id:** `SCN-B3`
- **Intent:** `INT-3`
- **Source issue:** `spine-records-the-truth`
- **Landed:** 2026-08-13

### types with no shape contract are unaffected

- **Scenario id:** `SCN-B4`
- **Intent:** `INT-3`
- **Source issue:** `spine-records-the-truth`
- **Landed:** 2026-08-13

### set-status writes the field

- **Scenario id:** `SCN-B1`
- **Intent:** `INT-3`
- **Source issue:** `status-vocabulary`
- **Landed:** 2026-08-13

### set-status refuses a value outside the vocabulary

- **Scenario id:** `SCN-B2`
- **Intent:** `INT-3`
- **Source issue:** `status-vocabulary`
- **Landed:** 2026-08-13

### landing through set-status still respects the gates

- **Scenario id:** `SCN-B3`
- **Intent:** `INT-3`
- **Source issue:** `status-vocabulary`
- **Landed:** 2026-08-13

### a citation whose record has been replaced is reported

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-3`
- **Source issue:** `tdd-green-unbound-record`
- **Landed:** 2026-08-23

### a citation that matches its record is not reported

- **Scenario id:** `TRC-C2`
- **Intent:** `INT-3`
- **Source issue:** `tdd-green-unbound-record`
- **Landed:** 2026-08-23

### the report names the evidence id, the path, and what changed

- **Scenario id:** `TRC-C3`
- **Intent:** `INT-3`
- **Source issue:** `tdd-green-unbound-record`
- **Landed:** 2026-08-23

### the dashboard names the decision required and where to start

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-3`
- **Source issue:** `the-human-front-door`
- **Landed:** 2026-08-23

### it lists every registered artifact with its status and why it exists

- **Scenario id:** `TRC-C2`
- **Intent:** `INT-3`
- **Source issue:** `the-human-front-door`
- **Landed:** 2026-08-23

### it lists what was deliberately omitted, with reasons

- **Scenario id:** `TRC-C3`
- **Intent:** `INT-3`
- **Source issue:** `the-human-front-door`
- **Landed:** 2026-08-23

### it carries no raw evidence

- **Scenario id:** `TRC-C4`
- **Intent:** `INT-3`
- **Source issue:** `the-human-front-door`
- **Landed:** 2026-08-23

### the dashboard can be generated and checked from the CLI

- **Scenario id:** `TRC-C5`
- **Intent:** `INT-3`
- **Source issue:** `the-human-front-door`
- **Landed:** 2026-08-23

### every verb accepts every mode flag

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-3`
- **Source issue:** `the-terminal-output-contract`
- **Landed:** 2026-08-24

### quiet prints nothing on success

- **Scenario id:** `TRC-C2`
- **Intent:** `INT-3`
- **Source issue:** `the-terminal-output-contract`
- **Landed:** 2026-08-24

### json is the machine mode and carries no prose

- **Scenario id:** `TRC-C3`
- **Intent:** `INT-3`
- **Source issue:** `the-terminal-output-contract`
- **Landed:** 2026-08-24

### verbose is where detail goes, not where the contract is escaped

- **Scenario id:** `TRC-C5`
- **Intent:** `INT-3`
- **Source issue:** `the-terminal-output-contract`
- **Landed:** 2026-08-24

### the map carries the stage keys

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-3`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### migrate rewrites a stale reference

- **Scenario id:** `TRC-C2`
- **Intent:** `INT-3`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### a dry run writes nothing and says what it would do

- **Scenario id:** `TRC-C3`
- **Intent:** `INT-3`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### a stopped migration says what it did and what remains

- **Scenario id:** `TRC-C4`
- **Intent:** `INT-3`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### migrate repoints the spine at the files it renamed

- **Scenario id:** `TRC-C6`
- **Intent:** `INT-3`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### the acceptance-criteria guardrail reads the current stage key

- **Scenario id:** `TRC-D3`
- **Intent:** `INT-3`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### the code-position scan knows this rename

- **Scenario id:** `TRC-D5`
- **Intent:** `INT-3`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### the coherence check reads the stage table the template writes

- **Scenario id:** `TRC-E3`
- **Intent:** `INT-3`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### every citation into the archive opens

- **Scenario id:** `TRC-E4`
- **Intent:** `INT-3`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### a landed task with a rotted trace is reported, not failed

- **Scenario id:** `SCN-B1`
- **Intent:** `INT-3`
- **Source issue:** `trace-rot-detection`
- **Landed:** 2026-08-13

### a deliberately deleted file is not trace rot

- **Scenario id:** `SCN-F1`
- **Intent:** `INT-3`
- **Source issue:** `trace-rot-detection`
- **Landed:** 2026-08-13

### An issue created before the cutoff keeps its result

- **Scenario id:** `UGR-5`
- **Intent:** `INT-3`
- **Source issue:** `unbound-green-needs-no-red`
- **Landed:** 2026-09-24

### the scan config declares its three lists

- **Scenario id:** `TRC-A4`
- **Intent:** `INT-3`
- **Source issue:** `v2-terminology-freeze`
- **Landed:** 2026-08-06

### a pending surface may still carry banned terms

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-3`
- **Source issue:** `v2-terminology-freeze`
- **Landed:** 2026-08-06

### a surface removed from pending must be clean

- **Scenario id:** `TRC-C2`
- **Intent:** `INT-3`
- **Source issue:** `v2-terminology-freeze`
- **Landed:** 2026-08-06

### the pending list only ever shrinks

- **Scenario id:** `TRC-C3`
- **Intent:** `INT-3`
- **Source issue:** `v2-terminology-freeze`
- **Landed:** 2026-08-06

### the repository scan is green on day one

- **Scenario id:** `TRC-C4`
- **Intent:** `INT-3`
- **Source issue:** `v2-terminology-freeze`
- **Landed:** 2026-08-06

### a pending entry that names no real surface is rejected

- **Scenario id:** `TRC-F1`
- **Intent:** `INT-3`
- **Source issue:** `v2-terminology-freeze`
- **Landed:** 2026-08-06

### an exempt path is never scanned

- **Scenario id:** `TRC-F2`
- **Intent:** `INT-3`
- **Source issue:** `v2-terminology-freeze`
- **Landed:** 2026-08-06

### Inv-8 resolves to a record that is not superseded

- **Scenario id:** `TRC-B3`
- **Intent:** `INT-3`
- **Source issue:** `what-compass-owes-an-unobserved-adopter`
- **Landed:** 2026-08-28

### ADR-006 is not superseded

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-3`
- **Source issue:** `what-compass-owes-an-unobserved-adopter`
- **Landed:** 2026-08-28

### Inv-8's two promises are stated separately

- **Scenario id:** `TRC-C2`
- **Intent:** `INT-3`
- **Source issue:** `what-compass-owes-an-unobserved-adopter`
- **Landed:** 2026-08-28

### The archive rule is untouched

- **Scenario id:** `TRC-C3`
- **Intent:** `INT-3`
- **Source issue:** `what-compass-owes-an-unobserved-adopter`
- **Landed:** 2026-08-28

### Orphaning Inv-8 fails the change

- **Scenario id:** `TRC-F3`
- **Intent:** `INT-3`
- **Source issue:** `what-compass-owes-an-unobserved-adopter`
- **Landed:** 2026-08-28

### nothing shipped tells a user or an adopter to install PyYAML

- **Scenario id:** `TRC-D1`
- **Intent:** `INT-3`
- **Source issue:** `zero-friction-install`
- **Landed:** 2026-08-10

### the copyable CI workflow runs with no dependency step

- **Scenario id:** `TRC-D3`
- **Intent:** `INT-3`
- **Source issue:** `zero-friction-install`
- **Landed:** 2026-08-10

### the install smoke test asserts the zero-install path

- **Scenario id:** `TRC-D4`
- **Intent:** `INT-3`
- **Source issue:** `zero-friction-install`
- **Landed:** 2026-08-10

### no test requires the removed instruction to still exist

- **Scenario id:** `TRC-D5`
- **Intent:** `INT-3`
- **Source issue:** `zero-friction-install`
- **Landed:** 2026-08-10

### no document claims Compass has no dependencies

- **Scenario id:** `TRC-D6`
- **Intent:** `INT-3`
- **Source issue:** `zero-friction-install`
- **Landed:** 2026-08-10

### the design template offers a cross-cutting concerns section

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-4`
- **Source issue:** `adaptive-artifact-composition`
- **Landed:** 2026-08-24

### the skill that governs the optional sections knows about it

- **Scenario id:** `TRC-C2`
- **Intent:** `INT-4`
- **Source issue:** `adaptive-artifact-composition`
- **Landed:** 2026-08-24

### no document was added that nothing asks for

- **Scenario id:** `TRC-D2`
- **Intent:** `INT-4`
- **Source issue:** `adaptive-artifact-composition`
- **Landed:** 2026-08-24

### both templates stay shorter than the framework's own PRD

- **Scenario id:** `TRC-D3`
- **Intent:** `INT-4`
- **Source issue:** `adaptive-artifact-composition`
- **Landed:** 2026-08-24

### the headings tell distinguishes a label from an answer

- **Scenario id:** `TRC-D1`
- **Intent:** `INT-4`
- **Source issue:** `agent-speech-is-unchecked`
- **Landed:** 2026-08-23

### no instruction tells a session both to use and to avoid reply headings

- **Scenario id:** `TRC-D2`
- **Intent:** `INT-4`
- **Source issue:** `agent-speech-is-unchecked`
- **Landed:** 2026-08-23

### a guarantee with no backing mechanism should fail the check

- **Scenario id:** `TRC-D1`
- **Intent:** `INT-4`
- **Source issue:** `claims-match-what-is-proved`
- **Landed:** 2026-08-22

### a backing mechanism that does not exist should fail the check

- **Scenario id:** `TRC-D2`
- **Intent:** `INT-4`
- **Source issue:** `claims-match-what-is-proved`
- **Landed:** 2026-08-22

### introducing the living spec adds no new phase or gate

- **Scenario id:** `TRC-B6`
- **Intent:** `INT-4`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### the five-point mental model gains zero new top-level concepts

- **Scenario id:** `TRC-D1`
- **Intent:** `INT-4`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### only two new CLI verbs are added across the three candidates

- **Scenario id:** `TRC-D2`
- **Intent:** `INT-4`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### frame_load_architecture returns the new artifacts and ADRs

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-4`
- **Source issue:** `compass-self-architecture`
- **Landed:** 

### SHA-256 is recorded per artifact (deterministic mechanism)

- **Scenario id:** `TRC-C2`
- **Intent:** `INT-4`
- **Source issue:** `compass-self-architecture`
- **Landed:** 

### Architect-lens cites Compass's own ADRs on a framework task

- **Scenario id:** `TRC-C3`
- **Intent:** `INT-4`
- **Source issue:** `compass-self-architecture`
- **Landed:** 

### Malformed ADR frontmatter fails Frame loudly

- **Scenario id:** `TRC-X1`
- **Intent:** `INT-4`
- **Source issue:** `compass-self-architecture`
- **Landed:** 

### ADRs with status: proposed are loaded but flagged

- **Scenario id:** `TRC-X2`
- **Intent:** `INT-4`
- **Source issue:** `compass-self-architecture`
- **Landed:** 

### a project that configures nothing is unaffected

- **Scenario id:** `SCN-A3`
- **Intent:** `INT-4`
- **Source issue:** `configurable-enforced-set`
- **Landed:** 2026-08-13

### an unreadable config does not block

- **Scenario id:** `SCN-F1`
- **Intent:** `INT-4`
- **Source issue:** `configurable-enforced-set`
- **Landed:** 2026-08-13

### rework-scan reports nothing when changed_files don't conflict

- **Scenario id:** `TRC-D1`
- **Intent:** `INT-4`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### rework-scan detects file added by A and deleted by B

- **Scenario id:** `TRC-D2`
- **Intent:** `INT-4`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### rework-scan detects a public-surface symbol added then removed

- **Scenario id:** `TRC-D3`
- **Intent:** `INT-4`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### rework-scan detects a migration created then dropped

- **Scenario id:** `TRC-D4`
- **Intent:** `INT-4`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### Flow digest absorbs rework-scan

- **Scenario id:** `TRC-D5`
- **Intent:** `INT-4`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### rework-scan detects the canonical add-then-delete pair

- **Scenario id:** `TRC-D6`
- **Intent:** `INT-4`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### rework-scan handles a corrupt task.yml gracefully

- **Scenario id:** `TRC-X2`
- **Intent:** `INT-4`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### A staged map is provisioned one wave at a time

- **Scenario id:** `DPR-3`
- **Intent:** `INT-4`
- **Source issue:** `dispatch-protocol`
- **Landed:** 2026-09-25

### An issue with no registry resolves exactly as it does today

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-4`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### Migration moves the documents and writes the registry

- **Scenario id:** `TRC-E1`
- **Intent:** `INT-4`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### The dry run changes nothing

- **Scenario id:** `TRC-E2`
- **Intent:** `INT-4`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### An unmigrated issue keeps working untouched

- **Scenario id:** `TRC-E3`
- **Intent:** `INT-4`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### An older install is not locked out by the move

- **Scenario id:** `TRC-E5`
- **Intent:** `INT-4`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### A half-finished migration is not mistaken for a finished one

- **Scenario id:** `TRC-G2`
- **Intent:** `INT-4`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### The same document in both places

- **Scenario id:** `TRC-G3`
- **Intent:** `INT-4`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### The safety contract states the boundary

- **Scenario id:** `EVB-7`
- **Intent:** `INT-4`
- **Source issue:** `evidence-binding`
- **Landed:** 2026-09-25

### the superseded skill should be gone

- **Scenario id:** `TRC-D1`
- **Intent:** `INT-4`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### nothing should point at the deleted skill

- **Scenario id:** `TRC-D2`
- **Intent:** `INT-4`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### the specification skill should state what it leaves to Clarify

- **Scenario id:** `TRC-D3`
- **Intent:** `INT-4`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### the clarify command should state the same split from its side

- **Scenario id:** `TRC-D4`
- **Intent:** `INT-4`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### Today's grep false-positives on a did-not-fire note and caps to 1 (baseline)

- **Scenario id:** `TRC-R4-1`
- **Intent:** `INT-4`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### Cap read from task.yml gives the correct uncapped value despite the prose

- **Scenario id:** `TRC-R4-2`
- **Intent:** `INT-4`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### A genuinely critical task still caps to 1

- **Scenario id:** `TRC-R4-3`
- **Intent:** `INT-4`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### Integration/verify streams are not counted as worktrees

- **Scenario id:** `TRC-R4-4`
- **Intent:** `INT-4`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### task.yml missing the readings block fails loudly, never a silent cap

- **Scenario id:** `TRC-R4-F1`
- **Intent:** `INT-4`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### a task.yml without a friction block stays valid and behaviour is unchanged

- **Scenario id:** `TRC-F3`
- **Intent:** `INT-4`
- **Source issue:** `friction-loop`
- **Landed:** 2026-06-04

### the published guarantee matches the trigger

- **Scenario id:** `SCN-F1`
- **Intent:** `INT-4`
- **Source issue:** `g5-trigger-matches-statement`
- **Landed:** 2026-08-13

### governance carries a new version

- **Scenario id:** `SCN-F2`
- **Intent:** `INT-4`
- **Source issue:** `g5-trigger-matches-statement`
- **Landed:** 2026-08-13

### a guardrail the project omits should be reported

- **Scenario id:** `TRC-D1`
- **Intent:** `INT-4`
- **Source issue:** `governance-drift-detection`
- **Landed:** 

### a guardrail that genuinely does not apply should still read as skipped

- **Scenario id:** `TRC-D2`
- **Intent:** `INT-4`
- **Source issue:** `governance-drift-detection`
- **Landed:** 

### the hook names which marker permitted the edit

- **Scenario id:** `SCN-C1`
- **Intent:** `INT-4`
- **Source issue:** `honest-acceptance-for-config-and-refactor`
- **Landed:** 2026-08-13

### an unreadable spine does not block

- **Scenario id:** `SCN-F1`
- **Intent:** `INT-4`
- **Source issue:** `hook-enforces-g2`
- **Landed:** 2026-08-13

### The hooks use no retired word or tool name

- **Scenario id:** `HFM-6`
- **Intent:** `INT-4`
- **Source issue:** `hook-failure-matrix`
- **Landed:** 2026-09-24

### an authenticated source is refused with a way forward

- **Scenario id:** `ING-D1`
- **Intent:** `INT-4`
- **Source issue:** `ingest-an-existing-brief`
- **Landed:** 2026-08-25

### no network, no silent failure

- **Scenario id:** `ING-D2`
- **Intent:** `INT-4`
- **Source issue:** `ingest-an-existing-brief`
- **Landed:** 2026-08-25

### a redirect is followed, and provenance names where it landed

- **Scenario id:** `ING-D3`
- **Intent:** `INT-4`
- **Source issue:** `ingest-an-existing-brief`
- **Landed:** 2026-08-25

### a URL that is not https is refused

- **Scenario id:** `ING-D4`
- **Intent:** `INT-4`
- **Source issue:** `ingest-an-existing-brief`
- **Landed:** 2026-08-25

### a pass gate cleared by wrong-typed evidence is rendered as type-mismatch

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-4`
- **Source issue:** `make-receipt-render`
- **Landed:** 2026-05-26

### a pass gate with no evidence id is rendered as unsupported

- **Scenario id:** `TRC-C2`
- **Intent:** `INT-4`
- **Source issue:** `make-receipt-render`
- **Landed:** 2026-05-26

### a task with a failed gate renders the failure prominently

- **Scenario id:** `TRC-C3`
- **Intent:** `INT-4`
- **Source issue:** `make-receipt-render`
- **Landed:** 2026-05-26

### a task with owed backfills is rendered as owing

- **Scenario id:** `TRC-C4`
- **Intent:** `INT-4`
- **Source issue:** `make-receipt-render`
- **Landed:** 2026-05-26

### a project that opted into nothing should see no change

- **Scenario id:** `TRC-F1`
- **Intent:** `INT-4`
- **Source issue:** `phase-2-skills-check-and-cli-split`
- **Landed:** 

### adding the check should not change any existing task's result

- **Scenario id:** `TRC-F2`
- **Intent:** `INT-4`
- **Source issue:** `phase-2-skills-check-and-cli-split`
- **Landed:** 

### the framework should grow by artifacts and checks only

- **Scenario id:** `TRC-F3`
- **Intent:** `INT-4`
- **Source issue:** `phase-2-skills-check-and-cli-split`
- **Landed:** 

### a sentence of thirty-one words or more should be reported

- **Scenario id:** `TRC-E1`
- **Intent:** `INT-4`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### the long-sentence report should never fail a build

- **Scenario id:** `TRC-E2`
- **Intent:** `INT-4`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### the reference workflow should declare the token permissions it needs

- **Scenario id:** `TRC-D1`
- **Intent:** `INT-4`
- **Source issue:** `project-commands-are-a-trust-boundary`
- **Landed:** 2026-08-22

### Compass's own workflow should follow the same posture

- **Scenario id:** `TRC-D2`
- **Intent:** `INT-4`
- **Source issue:** `project-commands-are-a-trust-boundary`
- **Landed:** 2026-08-22

### the security guide should say what a project must decide about untrusted pull requests

- **Scenario id:** `TRC-D3`
- **Intent:** `INT-4`
- **Source issue:** `project-commands-are-a-trust-boundary`
- **Landed:** 2026-08-22

### A stated count matches the thing it counts

- **Scenario id:** `PBW-A10`
- **Intent:** `INT-4`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### No citation points at a path git does not distribute

- **Scenario id:** `PBW-A6`
- **Intent:** `INT-4`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### A bare code carries its meaning or goes

- **Scenario id:** `PBW-A7`
- **Intent:** `INT-4`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### Every file and command a comment names exists

- **Scenario id:** `PBW-A8`
- **Intent:** `INT-4`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### No document states a fact its source contradicts

- **Scenario id:** `PBW-B8`
- **Intent:** `INT-4`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### A test docstring says what the file tests and cites its issue by slug

- **Scenario id:** `PBW-C5`
- **Intent:** `INT-4`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### a claim about every failure message should be checked or withdrawn

- **Scenario id:** `TRC-E1`
- **Intent:** `INT-4`
- **Source issue:** `public-docs-tell-the-truth`
- **Landed:** 2026-08-22

### a narrowed guarantee should still name its backing mechanism

- **Scenario id:** `TRC-E2`
- **Intent:** `INT-4`
- **Source issue:** `public-docs-tell-the-truth`
- **Landed:** 2026-08-22

### the guide should name what Compass deliberately does not adopt

- **Scenario id:** `TRC-E3`
- **Intent:** `INT-4`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### the self-review should record why no subagent critic is used

- **Scenario id:** `TRC-F3`
- **Intent:** `INT-4`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### a narrative scenario should be exempt from the resolution check

- **Scenario id:** `TRC-A4`
- **Intent:** `INT-4`
- **Source issue:** `record-keeping-integrity`
- **Landed:** 2026-08-03

### the check should register under G1 without adding a guardrail

- **Scenario id:** `TRC-A5`
- **Intent:** `INT-4`
- **Source issue:** `record-keeping-integrity`
- **Landed:** 2026-08-03

### policy lint should accept the new check

- **Scenario id:** `TRC-A6`
- **Intent:** `INT-4`
- **Source issue:** `record-keeping-integrity`
- **Landed:** 2026-08-03

### a task that has not yet claimed correctness should not be checked

- **Scenario id:** `TRC-A7`
- **Intent:** `INT-4`
- **Source issue:** `record-keeping-integrity`
- **Landed:** 2026-08-03

### a landed task should not be re-checked

- **Scenario id:** `TRC-A8`
- **Intent:** `INT-4`
- **Source issue:** `record-keeping-integrity`
- **Landed:** 2026-08-03

### capturing nothing should still record nothing

- **Scenario id:** `TRC-B3`
- **Intent:** `INT-4`
- **Source issue:** `record-keeping-integrity`
- **Landed:** 2026-08-03

### tasks already on disk should keep passing

- **Scenario id:** `TRC-F1`
- **Intent:** `INT-4`
- **Source issue:** `record-keeping-integrity`
- **Landed:** 2026-08-03

### a task.yml written before this change should still load

- **Scenario id:** `TRC-F2`
- **Intent:** `INT-4`
- **Source issue:** `record-keeping-integrity`
- **Landed:** 2026-08-03

### every file this task changes should pass house style

- **Scenario id:** `TRC-F3`
- **Intent:** `INT-4`
- **Source issue:** `record-keeping-integrity`
- **Landed:** 2026-08-03

### suite-passed applies the same identity rule

- **Scenario id:** `RIC-6`
- **Intent:** `INT-4`
- **Source issue:** `red-record-identity-cutoff`
- **Landed:** 2026-09-24

### The hook has no identity rule of its own

- **Scenario id:** `RIC-7`
- **Intent:** `INT-4`
- **Source issue:** `red-record-identity-cutoff`
- **Landed:** 2026-09-24

### The releasing guide requires a run

- **Scenario id:** `SPT-4`
- **Intent:** `INT-4`
- **Source issue:** `skill-prose-pressure-tests`
- **Landed:** 2026-09-27

### a scenario may record what supersedes it

- **Scenario id:** `SCN-C1`
- **Intent:** `INT-4`
- **Source issue:** `spine-records-the-truth`
- **Landed:** 2026-08-13

### superseded_by must name a scenario that exists

- **Scenario id:** `SCN-C2`
- **Intent:** `INT-4`
- **Source issue:** `spine-records-the-truth`
- **Landed:** 2026-08-13

### the living spec still derives only from landed tasks

- **Scenario id:** `SCN-C3`
- **Intent:** `INT-4`
- **Source issue:** `status-vocabulary`
- **Landed:** 2026-08-13

### a record written before this change does not fail the check

- **Scenario id:** `TRC-D1`
- **Intent:** `INT-4`
- **Source issue:** `tdd-green-unbound-record`
- **Landed:** 2026-08-23

### an unverifiable record is reported as unverifiable, not as verified

- **Scenario id:** `TRC-D2`
- **Intent:** `INT-4`
- **Source issue:** `tdd-green-unbound-record`
- **Landed:** 2026-08-23

### a dashboard that no longer matches the spine is reported as stale

- **Scenario id:** `TRC-D1`
- **Intent:** `INT-4`
- **Source issue:** `the-human-front-door`
- **Landed:** 2026-08-23

### a drifted dashboard fails the check rather than warning

- **Scenario id:** `TRC-D2`
- **Intent:** `INT-4`
- **Source issue:** `the-human-front-door`
- **Landed:** 2026-08-23

### the currency check is wired into a guardrail

- **Scenario id:** `TRC-D3`
- **Intent:** `INT-4`
- **Source issue:** `the-human-front-door`
- **Landed:** 2026-08-23

### an identifier survives compression with its meaning attached

- **Scenario id:** `TRC-D1`
- **Intent:** `INT-4`
- **Source issue:** `the-terminal-output-contract`
- **Landed:** 2026-08-24

### the meaning still comes before the code

- **Scenario id:** `TRC-D2`
- **Intent:** `INT-4`
- **Source issue:** `the-terminal-output-contract`
- **Landed:** 2026-08-24

### retired vocabulary stays out of printed strings

- **Scenario id:** `TRC-D3`
- **Intent:** `INT-4`
- **Source issue:** `the-terminal-output-contract`
- **Landed:** 2026-08-24

### every overloaded word carries a glossary entry

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-4`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### a ban never points at a banned replacement

- **Scenario id:** `TRC-D1`
- **Intent:** `INT-4`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### no term is both defined and banned

- **Scenario id:** `TRC-D4`
- **Intent:** `INT-4`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### no new check name appears in governance

- **Scenario id:** `SCN-C1`
- **Intent:** `INT-4`
- **Source issue:** `trace-rot-detection`
- **Landed:** 2026-08-13

### The bound-green refusal names acceptance, not the bypass

- **Scenario id:** `UGR-6`
- **Intent:** `INT-4`
- **Source issue:** `unbound-green-needs-no-red`
- **Landed:** 2026-09-24

### An unbound green with no red does not claim a red

- **Scenario id:** `UGR-7`
- **Intent:** `INT-4`
- **Source issue:** `unbound-green-needs-no-red`
- **Landed:** 2026-09-24

### The supersession is navigable in both directions

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-4`
- **Source issue:** `what-compass-owes-an-unobserved-adopter`
- **Landed:** 2026-08-28

### Every link in the decisions index resolves

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-4`
- **Source issue:** `what-compass-owes-an-unobserved-adopter`
- **Landed:** 2026-08-28

### no document claims Compass has no dependencies

- **Scenario id:** `TRC-D6`
- **Intent:** `INT-4`
- **Source issue:** `zero-friction-install`
- **Landed:** 2026-08-10

### the decision is recorded with the alternative it beat

- **Scenario id:** `TRC-E1`
- **Intent:** `INT-4`
- **Source issue:** `zero-friction-install`
- **Landed:** 2026-08-10

### the shipped version is the documented version

- **Scenario id:** `TRC-G2`
- **Intent:** `INT-4`
- **Source issue:** `zero-friction-install`
- **Landed:** 2026-08-10

### the bundled library carries its licence and its attribution

- **Scenario id:** `TRC-G3`
- **Intent:** `INT-4`
- **Source issue:** `zero-friction-install`
- **Landed:** 2026-08-10

### analyze gate promotion is driven by routing-policy, not hard-coded in the CLI

- **Scenario id:** `TRC-A12`
- **Intent:** `INT-5`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### same artifacts and policy yield the same verdict

- **Scenario id:** `TRC-A5`
- **Intent:** `INT-5`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### analyze opens no network or model client on its decision path

- **Scenario id:** `TRC-A6`
- **Intent:** `INT-5`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### next writes no new task state

- **Scenario id:** `TRC-C7`
- **Intent:** `INT-5`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### next derives its answer only from task.yml and the route

- **Scenario id:** `TRC-C8`
- **Intent:** `INT-5`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### the determinism boundary holds - no model call after readings on any code path

- **Scenario id:** `TRC-D10`
- **Intent:** `INT-5`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### route composition stays byte-identical across runs

- **Scenario id:** `TRC-D9`
- **Intent:** `INT-5`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### Existing test suite still passes (161+ tests)

- **Scenario id:** `TRC-E1`
- **Intent:** `INT-5`
- **Source issue:** `compass-self-architecture`
- **Landed:** 

### Projects without architecture/ still no-op cleanly

- **Scenario id:** `TRC-E2`
- **Intent:** `INT-5`
- **Source issue:** `compass-self-architecture`
- **Landed:** 

### compass check still passes 10/10

- **Scenario id:** `TRC-E3`
- **Intent:** `INT-5`
- **Source issue:** `compass-self-architecture`
- **Landed:** 

### Lint count does not regress

- **Scenario id:** `TRC-E4`
- **Intent:** `INT-5`
- **Source issue:** `compass-self-architecture`
- **Landed:** 

### Compass's own shell scripts are enforced

- **Scenario id:** `SCN-C1`
- **Intent:** `INT-5`
- **Source issue:** `configurable-enforced-set`
- **Landed:** 2026-08-13

### Unchecked DoD with no evidence and no backfill fails Land

- **Scenario id:** `TRC-E1`
- **Intent:** `INT-5`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### Unchecked DoD backed by typed evidence passes

- **Scenario id:** `TRC-E2`
- **Intent:** `INT-5`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### Unchecked DoD enumerated as owed_backfill passes Land but blocks the next sibling

- **Scenario id:** `TRC-E3`
- **Intent:** `INT-5`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### USER TO APPLY devlog notes no longer clear DoD

- **Scenario id:** `TRC-E4`
- **Intent:** `INT-5`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### human-approval evidence is accepted for human-actionable DoD items

- **Scenario id:** `TRC-E5`
- **Intent:** `INT-5`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### guardrails.yml registers the new DoD check

- **Scenario id:** `TRC-E6`
- **Intent:** `INT-5`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### Typed DoD does not break tasks that have empty DoD

- **Scenario id:** `TRC-X4`
- **Intent:** `INT-5`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### A conflict in Compass's records does not stop integration

- **Scenario id:** `DPR-4`
- **Intent:** `INT-5`
- **Source issue:** `dispatch-protocol`
- **Landed:** 2026-09-25

### Only ship-commit marks an issue landed

- **Scenario id:** `DPR-7`
- **Intent:** `INT-5`
- **Source issue:** `dispatch-protocol`
- **Landed:** 2026-09-25

### A quick fix reads one command and one skill

- **Scenario id:** `TRC-F1`
- **Intent:** `INT-5`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### A quick fix writes only the delivery-approach record

- **Scenario id:** `TRC-F2`
- **Intent:** `INT-5`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### The resident cost is measured and pinned

- **Scenario id:** `TRC-F5`
- **Intent:** `INT-5`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### a project that opted into nothing should see no change

- **Scenario id:** `TRC-F5`
- **Intent:** `INT-5`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### the framework should grow by artifacts and skills only

- **Scenario id:** `TRC-F6`
- **Intent:** `INT-5`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### the skill count should not grow on net

- **Scenario id:** `TRC-F7`
- **Intent:** `INT-5`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### An auto-formatter rewrite makes the commit no-op and HEAD does not move (baseline)

- **Scenario id:** `TRC-R5-1`
- **Intent:** `INT-5`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### Pre-commit-clean-then-commit advances HEAD (happy path)

- **Scenario id:** `TRC-R5-2`
- **Intent:** `INT-5`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### A no-op commit is detected, hook fixes re-staged, and the retry advances HEAD

- **Scenario id:** `TRC-R5-3`
- **Intent:** `INT-5`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### HEAD is always verified to have advanced

- **Scenario id:** `TRC-R5-4`
- **Intent:** `INT-5`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### HEAD still unmoved after the retry → Land ERRORS loudly

- **Scenario id:** `TRC-R5-F1`
- **Intent:** `INT-5`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### Nothing-to-commit is distinguished from a stash-rollback no-op

- **Scenario id:** `TRC-R5-F2`
- **Intent:** `INT-5`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### drift should be advisory by default

- **Scenario id:** `TRC-B6`
- **Intent:** `INT-5`
- **Source issue:** `governance-drift-detection`
- **Landed:** 

### a project may opt into failing on drift

- **Scenario id:** `TRC-B7`
- **Intent:** `INT-5`
- **Source issue:** `governance-drift-detection`
- **Landed:** 

### a project with current governance should see no drift report

- **Scenario id:** `TRC-F1`
- **Intent:** `INT-5`
- **Source issue:** `governance-drift-detection`
- **Landed:** 

### a project with no local governance should not be compared to itself

- **Scenario id:** `TRC-F2`
- **Intent:** `INT-5`
- **Source issue:** `governance-drift-detection`
- **Landed:** 

### a project ahead of the framework should not be reported as drifted

- **Scenario id:** `TRC-F3`
- **Intent:** `INT-5`
- **Source issue:** `governance-drift-detection`
- **Landed:** 

### an unreadable framework policy should not break the lint

- **Scenario id:** `TRC-F4`
- **Intent:** `INT-5`
- **Source issue:** `governance-drift-detection`
- **Landed:** 

### drift detection should not change any computed route

- **Scenario id:** `TRC-F5`
- **Intent:** `INT-5`
- **Source issue:** `governance-drift-detection`
- **Landed:** 

### the framework should grow by artifacts and checks only

- **Scenario id:** `TRC-F6`
- **Intent:** `INT-5`
- **Source issue:** `governance-drift-detection`
- **Landed:** 

### the evidence types the CLI writes should be accepted by the task schema

- **Scenario id:** `TRC-F7`
- **Intent:** `INT-5`
- **Source issue:** `governance-drift-detection`
- **Landed:** 

### rendering the receipt mutates nothing on disk

- **Scenario id:** `TRC-E1`
- **Intent:** `INT-5`
- **Source issue:** `make-receipt-render`
- **Landed:** 2026-05-26

### An interrupted run resumes losing nothing

- **Scenario id:** `OLH-3`
- **Intent:** `INT-5`
- **Source issue:** `orchestrator-loop-hardening`
- **Landed:** 2026-09-25

### A rehearsal interrupted mid-review and mid-integration resumes

- **Scenario id:** `OLH-8`
- **Intent:** `INT-5`
- **Source issue:** `orchestrator-loop-hardening`
- **Landed:** 2026-09-25

### "un-conflate" should be gone from governance

- **Scenario id:** `TRC-B5`
- **Intent:** `INT-5`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### no em dash should remain in published copy

- **Scenario id:** `TRC-G1`
- **Intent:** `INT-5`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### no structural use of "seam" should remain

- **Scenario id:** `TRC-G2`
- **Intent:** `INT-5`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### the living spec's stale title should be fixed by re-deriving it

- **Scenario id:** `TRC-G3`
- **Intent:** `INT-5`
- **Source issue:** `plain-language-3-2-0`
- **Landed:** 2026-08-16

### a project whose command stops running should be told

- **Scenario id:** `TRC-E1`
- **Intent:** `INT-5`
- **Source issue:** `project-commands-are-a-trust-boundary`
- **Landed:** 2026-08-22

### the guarantee about declared guardrails should still hold

- **Scenario id:** `TRC-E2`
- **Intent:** `INT-5`
- **Source issue:** `project-commands-are-a-trust-boundary`
- **Landed:** 2026-08-22

### A comment states what the code does

- **Scenario id:** `PBW-C1`
- **Intent:** `INT-5`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### A comment gives its reason before its detail

- **Scenario id:** `PBW-C2`
- **Intent:** `INT-5`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### A CLI module's header describes that module

- **Scenario id:** `PBW-C3`
- **Intent:** `INT-5`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### the decay rule should say what it asks of the reader

- **Scenario id:** `TRC-F1`
- **Intent:** `INT-5`
- **Source issue:** `public-docs-tell-the-truth`
- **Landed:** 2026-08-22

### the launch article should read as publication copy throughout

- **Scenario id:** `TRC-F2`
- **Intent:** `INT-5`
- **Source issue:** `public-docs-tell-the-truth`
- **Landed:** 2026-08-22

### adding the Summary should leave the scenario machinery untouched

- **Scenario id:** `TRC-A4`
- **Intent:** `INT-5`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### the check should not introduce a sixth guardrail

- **Scenario id:** `TRC-C4`
- **Intent:** `INT-5`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### the check should not fire on prose that quotes it

- **Scenario id:** `TRC-C5`
- **Intent:** `INT-5`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### the check should stay advisory on every route

- **Scenario id:** `TRC-C6`
- **Intent:** `INT-5`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### the new subcommand should appear in the documented CLI surface

- **Scenario id:** `TRC-C7`
- **Intent:** `INT-5`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### each hand-off prompt should be written in exactly one file

- **Scenario id:** `TRC-D3`
- **Intent:** `INT-5`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### specs written before this change should keep passing

- **Scenario id:** `TRC-F1`
- **Intent:** `INT-5`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### every file this task adds or changes should pass house style

- **Scenario id:** `TRC-F4`
- **Intent:** `INT-5`
- **Source issue:** `readable-specs-and-flow`
- **Landed:** 2026-08-03

### The pilot and one measured change are on record

- **Scenario id:** `SPT-5`
- **Intent:** `INT-5`
- **Source issue:** `skill-prose-pressure-tests`
- **Landed:** 2026-09-27

### task.yml files written before this keep working

- **Scenario id:** `SCN-F1`
- **Intent:** `INT-5`
- **Source issue:** `spine-records-the-truth`
- **Landed:** 2026-08-13

### an unknown status is still rejected

- **Scenario id:** `SCN-A2`
- **Intent:** `INT-5`
- **Source issue:** `status-vocabulary`
- **Landed:** 2026-08-13

### a task.yml with no status still behaves as active

- **Scenario id:** `SCN-F1`
- **Intent:** `INT-5`
- **Source issue:** `status-vocabulary`
- **Landed:** 2026-08-13

### landed is the only privileged value

- **Scenario id:** `SCN-F2`
- **Intent:** `INT-5`
- **Source issue:** `status-vocabulary`
- **Landed:** 2026-08-13

### the instructions tell a stage to link evidence rather than paste it

- **Scenario id:** `TRC-E1`
- **Intent:** `INT-5`
- **Source issue:** `the-human-front-door`
- **Landed:** 2026-08-23

### a report opens with a summary a reader can stop at

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-5`
- **Source issue:** `the-terminal-output-contract`
- **Landed:** 2026-08-24

### a report's own detail is never truncated by the contract

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-5`
- **Source issue:** `the-terminal-output-contract`
- **Landed:** 2026-08-24

### every verb declares which contract it is under

- **Scenario id:** `TRC-C6`
- **Intent:** `INT-5`
- **Source issue:** `the-terminal-output-contract`
- **Landed:** 2026-08-24

### governance files are scanned for retired vocabulary

- **Scenario id:** `TRC-D2`
- **Intent:** `INT-5`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### the guard fails when handed nothing

- **Scenario id:** `TRC-E2`
- **Intent:** `INT-5`
- **Source issue:** `the-vocabulary-rename`
- **Landed:** 2026-08-25

### The retired slash commands no longer exist

- **Scenario id:** `TRC-D1`
- **Intent:** `INT-5`
- **Source issue:** `what-compass-owes-an-unobserved-adopter`
- **Landed:** 2026-08-28

### The hidden CLI alias no longer resolves

- **Scenario id:** `TRC-D2`
- **Intent:** `INT-5`
- **Source issue:** `what-compass-owes-an-unobserved-adopter`
- **Landed:** 2026-08-28

### Read-side migration survives, for the archive's reason

- **Scenario id:** `TRC-D3`
- **Intent:** `INT-5`
- **Source issue:** `what-compass-owes-an-unobserved-adopter`
- **Landed:** 2026-08-28

### The vocabulary has one value per concept again

- **Scenario id:** `TRC-D4`
- **Intent:** `INT-5`
- **Source issue:** `what-compass-owes-an-unobserved-adopter`
- **Landed:** 2026-08-28

### A stale exemption fails the build

- **Scenario id:** `TRC-D5`
- **Intent:** `INT-5`
- **Source issue:** `what-compass-owes-an-unobserved-adopter`
- **Landed:** 2026-08-28

### The release that carries the removal says so

- **Scenario id:** `TRC-D6`
- **Intent:** `INT-5`
- **Source issue:** `what-compass-owes-an-unobserved-adopter`
- **Landed:** 2026-08-28

### Nothing is left over from the removal

- **Scenario id:** `TRC-D7`
- **Intent:** `INT-5`
- **Source issue:** `what-compass-owes-an-unobserved-adopter`
- **Landed:** 2026-08-28

### Every list of the governance files names all of them

- **Scenario id:** `TRC-D8`
- **Intent:** `INT-5`
- **Source issue:** `what-compass-owes-an-unobserved-adopter`
- **Landed:** 2026-08-28

### the hook allows a code file outside the project

- **Scenario id:** `FF-1`
- **Intent:** `INT-57`
- **Source issue:** `field-feedback-hook-scope-and-restage`
- **Landed:** 2026-08-14

### the hook still blocks a code file inside the project

- **Scenario id:** `FF-2`
- **Intent:** `INT-57`
- **Source issue:** `field-feedback-hook-scope-and-restage`
- **Landed:** 2026-08-14

### the re-stage does not widen the commit beyond what was staged

- **Scenario id:** `FF-3`
- **Intent:** `INT-58`
- **Source issue:** `field-feedback-hook-scope-and-restage`
- **Landed:** 2026-08-14

### the issue's artifact directory is still re-staged

- **Scenario id:** `FF-4`
- **Intent:** `INT-58`
- **Source issue:** `field-feedback-hook-scope-and-restage`
- **Landed:** 2026-08-14

### a greenfield project Lands with no pre-existing system spec

- **Scenario id:** `TRC-B5`
- **Intent:** `INT-6`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### every new capability functions on a bare repo with no /compass:init

- **Scenario id:** `TRC-D8`
- **Intent:** `INT-6`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### CLAUDE.md notes Compass itself ships an architecture/

- **Scenario id:** `TRC-D1`
- **Intent:** `INT-6`
- **Source issue:** `compass-self-architecture`
- **Landed:** 

### CLAUDE.md does not claim unbuilt features

- **Scenario id:** `TRC-D2`
- **Intent:** `INT-6`
- **Source issue:** `compass-self-architecture`
- **Landed:** 

### Frame remains mandatory, unchanged

- **Scenario id:** `TRC-F1`
- **Intent:** `INT-6`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### The guardrail count is still five

- **Scenario id:** `TRC-F2`
- **Intent:** `INT-6`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### Adaptive routing is unchanged

- **Scenario id:** `TRC-F3`
- **Intent:** `INT-6`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### Flow still advises, never gates

- **Scenario id:** `TRC-F4`
- **Intent:** `INT-6`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### Architect-lens does not fork the spec

- **Scenario id:** `TRC-F5`
- **Intent:** `INT-6`
- **Source issue:** `cross-task-architectural-integrity`
- **Landed:** 

### Run 1 is recorded

- **Scenario id:** `DPR-6`
- **Intent:** `INT-6`
- **Source issue:** `dispatch-protocol`
- **Landed:** 2026-09-25

### Two skills merge into their neighbours

- **Scenario id:** `TRC-F3`
- **Intent:** `INT-6`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### The framework's own documents are off the adopter's path

- **Scenario id:** `TRC-F4`
- **Intent:** `INT-6`
- **Source issue:** `docs-compass-artifacts`
- **Landed:** 2026-09-11

### a created worktree should carry the task's artifacts

- **Scenario id:** `TRC-E1`
- **Intent:** `INT-6`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### a builder in a seeded worktree should be able to resolve its task

- **Scenario id:** `TRC-E2`
- **Intent:** `INT-6`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### re-running the swarm should not clobber a builder's work

- **Scenario id:** `TRC-E3`
- **Intent:** `INT-6`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### A wrong-type gate-evidence mismatch surfaces only at compass check today (baseline)

- **Scenario id:** `TRC-R6-1`
- **Intent:** `INT-6`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### A task with two wrong-type gates already reports both, as one joined string (baseline)

- **Scenario id:** `TRC-R6-2`
- **Intent:** `INT-6`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### compass gate pass rejects wrong-type evidence at write time with the accepted-type list

- **Scenario id:** `TRC-R6-3`
- **Intent:** `INT-6`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### compass gate pass accepts a correct-type evidence and flips the gate to pass

- **Scenario id:** `TRC-R6-4`
- **Intent:** `INT-6`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### compass check reports ALL gate-evidence mismatches in one enumerated pass

- **Scenario id:** `TRC-R6-5`
- **Intent:** `INT-6`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### The seeded gates block carries each gate's accepted evidence types as a comment

- **Scenario id:** `TRC-R6-6`
- **Intent:** `INT-6`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### Each half of the review catches its own seeded defect

- **Scenario id:** `OLH-9`
- **Intent:** `INT-6`
- **Source issue:** `orchestrator-loop-hardening`
- **Landed:** 2026-09-25

### Every identifier keeps its spelling

- **Scenario id:** `PBW-D1`
- **Intent:** `INT-6`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### The frozen vocabulary still names the words it bans

- **Scenario id:** `PBW-D2`
- **Intent:** `INT-6`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### The archive quotes are unchanged

- **Scenario id:** `PBW-D3`
- **Intent:** `INT-6`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### The deliberately bad text survives

- **Scenario id:** `PBW-D4`
- **Intent:** `INT-6`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### Every CLI module keeps its DEPENDENCY: line

- **Scenario id:** `PBW-D5`
- **Intent:** `INT-6`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### A test that pinned the old wording changes in the same commit

- **Scenario id:** `PBW-D6`
- **Intent:** `INT-6`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### The help text in scripts/release.sh stays inside its printed range

- **Scenario id:** `PBW-D7`
- **Intent:** `INT-6`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### The excluded files are untouched

- **Scenario id:** `PBW-D8`
- **Intent:** `INT-6`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### The case study and the launch article keep their form

- **Scenario id:** `PBW-D9`
- **Intent:** `INT-6`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### No changed file alters behaviour

- **Scenario id:** `PBW-E4`
- **Intent:** `INT-6`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### A prose edit that changes behaviour is refused

- **Scenario id:** `PBW-F1`
- **Intent:** `INT-6`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### An out-of-scope defect folded into a batch is refused

- **Scenario id:** `PBW-F2`
- **Intent:** `INT-6`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### An edit that adds an em dash or an attribution line is refused

- **Scenario id:** `PBW-F3`
- **Intent:** `INT-6`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### An edit made from a stale line number is refused

- **Scenario id:** `PBW-F5`
- **Intent:** `INT-6`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### A rewritten instruction still instructs the same behaviour

- **Scenario id:** `PBW-F7`
- **Intent:** `INT-6`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### A batch that does not record its changed files is refused

- **Scenario id:** `PBW-F9`
- **Intent:** `INT-6`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### the evaluator computes the artifact set from the assessment

- **Scenario id:** `TRC-F1`
- **Intent:** `INT-6`
- **Source issue:** `the-human-front-door`
- **Landed:** 2026-08-23

### a trivial atomic change earns almost nothing

- **Scenario id:** `TRC-F2`
- **Intent:** `INT-6`
- **Source issue:** `the-human-front-door`
- **Landed:** 2026-08-23

### a policy rule can add an artifact the way it adds a gate

- **Scenario id:** `TRC-F3`
- **Intent:** `INT-6`
- **Source issue:** `the-human-front-door`
- **Landed:** 2026-08-23

### the same assessment computes the same artifact set every time

- **Scenario id:** `TRC-F4`
- **Intent:** `INT-6`
- **Source issue:** `the-human-front-door`
- **Landed:** 2026-08-23

### The record says what it adds beyond the release

- **Scenario id:** `TRC-A4`
- **Intent:** `INT-6`
- **Source issue:** `what-compass-owes-an-unobserved-adopter`
- **Landed:** 2026-08-28

### A record that only restates the existing schedule is refused

- **Scenario id:** `TRC-F1`
- **Intent:** `INT-6`
- **Source issue:** `what-compass-owes-an-unobserved-adopter`
- **Landed:** 2026-08-28

### recording acceptance for a second scenario does not destroy the first one's evidence

- **Scenario id:** `TRC-F7`
- **Intent:** `INT-6`
- **Source issue:** `zero-friction-install`
- **Landed:** 2026-08-10

### re-deriving from unchanged scenarios produces no diff

- **Scenario id:** `TRC-B3`
- **Intent:** `INT-7`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### every entry in the system spec traces to a landed scenario

- **Scenario id:** `TRC-B7`
- **Intent:** `INT-7`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### the derivation is not the sole source of truth

- **Scenario id:** `TRC-B8`
- **Intent:** `INT-7`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### a command that fails to run should not be recorded as a red

- **Scenario id:** `TRC-G1`
- **Intent:** `INT-7`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### a run that collects no tests should not be recorded as a red

- **Scenario id:** `TRC-G2`
- **Intent:** `INT-7`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### a genuinely failing test should still be recorded as a red

- **Scenario id:** `TRC-G3`
- **Intent:** `INT-7`
- **Source issue:** `executable-bdd-and-richer-plans`
- **Landed:** 

### A coverage-gated micro-run refuses green today (baseline)

- **Scenario id:** `TRC-R7-1`
- **Intent:** `INT-7`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### The micro-run neutralises the project coverage floor and records green

- **Scenario id:** `TRC-R7-2`
- **Intent:** `INT-7`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### The full-suite coverage gate at Verify is unaffected

- **Scenario id:** `TRC-R7-3`
- **Intent:** `INT-7`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### A non-pytest micro-run is left untouched by the coverage logic

- **Scenario id:** `TRC-R7-4`
- **Intent:** `INT-7`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### A configured test_micro_command takes precedence when present

- **Scenario id:** `TRC-R7-5`
- **Intent:** `INT-7`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### A budget overrun is a finding

- **Scenario id:** `OLH-4`
- **Intent:** `INT-7`
- **Source issue:** `orchestrator-loop-hardening`
- **Landed:** 2026-09-25

### Each sweep reports a planted breach

- **Scenario id:** `PBW-E1`
- **Intent:** `INT-7`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### A result of zero is believed only after the sweep has reported

- **Scenario id:** `PBW-E2`
- **Intent:** `INT-7`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### A sweep is never loosened to clear a report

- **Scenario id:** `PBW-E3`
- **Intent:** `INT-7`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### A batch that cannot show its sweeps ran is refused

- **Scenario id:** `PBW-F6`
- **Intent:** `INT-7`
- **Source issue:** `prose-breaks-the-writing-style`
- **Landed:** 2026-09-23

### analyze completes within the interactive latency target

- **Scenario id:** `TRC-A13`
- **Intent:** `INT-8`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### next returns under the interactive latency target

- **Scenario id:** `TRC-C10`
- **Intent:** `INT-8`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### A wiring change with no unit red is blocked today (baseline)

- **Scenario id:** `TRC-R8-1`
- **Intent:** `INT-8`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### tdd-red --verified-by typecheck records the guard and allows the edit

- **Scenario id:** `TRC-R8-2`
- **Intent:** `INT-8`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### The verified-by guard is tied to the scenario's acceptance at Verify

- **Scenario id:** `TRC-R8-3`
- **Intent:** `INT-8`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### A plain tdd-red with no real failure and no --verified-by is still rejected

- **Scenario id:** `TRC-R8-4`
- **Intent:** `INT-8`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### --verified-by rejects an unrecognised kind

- **Scenario id:** `TRC-R8-5`
- **Intent:** `INT-8`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### A verified-by guard that does not actually fail is rejected

- **Scenario id:** `TRC-R8-6`
- **Intent:** `INT-8`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### The agent and skill prose state each adopted rule

- **Scenario id:** `OLH-7`
- **Intent:** `INT-8`
- **Source issue:** `orchestrator-loop-hardening`
- **Landed:** 2026-09-25

### no fixed-tier ladder is shipped

- **Scenario id:** `TRC-D3`
- **Intent:** `INT-9`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### the five roles remain lenses on one shared spec

- **Scenario id:** `TRC-D4`
- **Intent:** `INT-9`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### pipeline phases still flex by route

- **Scenario id:** `TRC-D5`
- **Intent:** `INT-9`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### phases and gates remain enforced

- **Scenario id:** `TRC-D6`
- **Intent:** `INT-9`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### TDD remains a strategy that Spike suspends

- **Scenario id:** `TRC-D7`
- **Intent:** `INT-9`
- **Source issue:** `comparison-requirements`
- **Landed:** 2026-05-25

### task.yml blocks below readings are hand-authored today (baseline)

- **Scenario id:** `TRC-R9-1`
- **Intent:** `INT-9`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### compass scenario add writes a well-formed entry that passes task lint

- **Scenario id:** `TRC-R9-2`
- **Intent:** `INT-9`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### compass changed-file add traces a production file to a scenario

- **Scenario id:** `TRC-R9-3`
- **Intent:** `INT-9`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### compass evidence add appends a typed registry entry

- **Scenario id:** `TRC-R9-4`
- **Intent:** `INT-9`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### A mutator rejects a duplicate id rather than silently overwriting

- **Scenario id:** `TRC-R9-5`
- **Intent:** `INT-9`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### A mutator rejects malformed input with non-zero exit and no write

- **Scenario id:** `TRC-R9-6`
- **Intent:** `INT-9`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### compass gate pass is the shared R6/R9 command and is schema-valid

- **Scenario id:** `TRC-R9-7`
- **Intent:** `INT-9`
- **Source issue:** `framework-field-feedback`
- **Landed:** 2026-06-23

### the identifier-expansion rule is stated where agent speech is governed

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-F0`
- **Source issue:** `identifiers-and-vocabulary-in-printed-output`
- **Landed:** 2026-08-13

### the receipt prints a scenario's title beside its id

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-F0`
- **Source issue:** `identifiers-and-vocabulary-in-printed-output`
- **Landed:** 2026-08-13

### a printed identifier is never truncated

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-F0`
- **Source issue:** `identifiers-and-vocabulary-in-printed-output`
- **Landed:** 2026-08-13

### the identifier check can fail

- **Scenario id:** `TRC-A4`
- **Intent:** `INT-F0`
- **Source issue:** `identifiers-and-vocabulary-in-printed-output`
- **Landed:** 2026-08-13

### the approach evaluator prints no retired vocabulary name

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-F1`
- **Source issue:** `identifiers-and-vocabulary-in-printed-output`
- **Landed:** 2026-08-13

### the printed-output scan can fail

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-F1`
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

### compass check counts clearances that checked nothing apart from verified ones

- **Scenario id:** `TRC-D1`
- **Intent:** `INT-F5`
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

### YAML values are scanned for retired vocabulary

- **Scenario id:** `TRC-D1`
- **Intent:** `INT-R2`
- **Source issue:** `dry-run-2-rulings`
- **Landed:** 2026-08-14

### every position exemption names its reason

- **Scenario id:** `TRC-D2`
- **Intent:** `INT-R2`
- **Source issue:** `dry-run-2-rulings`
- **Landed:** 2026-08-14

### the widened scan can fail in the newly covered position

- **Scenario id:** `TRC-D3`
- **Intent:** `INT-R2`
- **Source issue:** `dry-run-2-rulings`
- **Landed:** 2026-08-14

### triage states permitted parallel streams and no topology

- **Scenario id:** `TRC-A1`
- **Intent:** `INT-R3`
- **Source issue:** `dry-run-2-rulings`
- **Landed:** 2026-08-14

### the stream ceiling is an integer, not a sentence

- **Scenario id:** `TRC-A2`
- **Intent:** `INT-R3`
- **Source issue:** `dry-run-2-rulings`
- **Landed:** 2026-08-14

### an uncapped approach permits more than one stream

- **Scenario id:** `TRC-A3`
- **Intent:** `INT-R3`
- **Source issue:** `dry-run-2-rulings`
- **Landed:** 2026-08-14

### a passing check summary prints no denominator

- **Scenario id:** `TRC-B1`
- **Intent:** `INT-R4`
- **Source issue:** `dry-run-2-rulings`
- **Landed:** 2026-08-14

### a failing check summary keeps its denominator

- **Scenario id:** `TRC-B2`
- **Intent:** `INT-R4`
- **Source issue:** `dry-run-2-rulings`
- **Landed:** 2026-08-14

### suite-passed does not present a binding as coverage

- **Scenario id:** `TRC-C1`
- **Intent:** `INT-R5`
- **Source issue:** `dry-run-2-rulings`
- **Landed:** 2026-08-14

### a skipped test does not count as a resolving test

- **Scenario id:** `TRC-C2`
- **Intent:** `INT-R5`
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

### every id prefix in use is defined

- **Scenario id:** `GL-B1`
- **Intent:** `NO-CODE-DICTIONARY`
- **Source issue:** `id-prefix-vocabulary-and-glossary`
- **Landed:** 2026-08-13

### the guard fails on an undefined prefix

- **Scenario id:** `GL-B2`
- **Intent:** `NO-CODE-DICTIONARY`
- **Source issue:** `id-prefix-vocabulary-and-glossary`
- **Landed:** 2026-08-13

### the glossary page is derived, not hand-written

- **Scenario id:** `GL-C1`
- **Intent:** `NO-CODE-DICTIONARY`
- **Source issue:** `id-prefix-vocabulary-and-glossary`
- **Landed:** 2026-08-13

### drift between source and page fails the build

- **Scenario id:** `GL-C2`
- **Intent:** `NO-CODE-DICTIONARY`
- **Source issue:** `id-prefix-vocabulary-and-glossary`
- **Landed:** 2026-08-13

### compass terminology renders a code

- **Scenario id:** `GL-C3`
- **Intent:** `NO-CODE-DICTIONARY`
- **Source issue:** `id-prefix-vocabulary-and-glossary`
- **Landed:** 2026-08-13

### measure-before-arguing is in the operating model

- **Scenario id:** `RR-6`
- **Intent:** `PRACTICE`
- **Source issue:** `rehearsal-recordings`
- **Landed:** 2026-08-13

### the new guard can fail

- **Scenario id:** `RR-7`
- **Intent:** `PRACTICE`
- **Source issue:** `rehearsal-recordings`
- **Landed:** 2026-08-13

### the hook finds the project from a subdirectory

- **Scenario id:** `RCD-A1`
- **Intent:** `REH-1`
- **Source issue:** `rehearsal-cli-defects`
- **Landed:** 2026-08-13

### an unresolvable project root fails closed, not open

- **Scenario id:** `RCD-A2`
- **Intent:** `REH-1`
- **Source issue:** `rehearsal-cli-defects`
- **Landed:** 2026-08-13

### the message names the real cause

- **Scenario id:** `RCD-A3`
- **Intent:** `REH-1`
- **Source issue:** `rehearsal-cli-defects`
- **Landed:** 2026-08-13

### a genuine triage-has-not-run still says so

- **Scenario id:** `RCD-A4`
- **Intent:** `REH-1`
- **Source issue:** `rehearsal-cli-defects`
- **Landed:** 2026-08-13

### design lint defaults to the live artifact filename

- **Scenario id:** `RCD-B1`
- **Intent:** `REH-2`
- **Source issue:** `rehearsal-cli-defects`
- **Landed:** 2026-08-13

### the not-found message names the path actually used

- **Scenario id:** `RCD-B2`
- **Intent:** `REH-2`
- **Source issue:** `rehearsal-cli-defects`
- **Landed:** 2026-08-13

### a nested test id resolves

- **Scenario id:** `RCD-C1`
- **Intent:** `REH-3`
- **Source issue:** `rehearsal-cli-defects`
- **Landed:** 2026-08-13

### a test name ending in a non-word character resolves

- **Scenario id:** `RCD-C2`
- **Intent:** `REH-3`
- **Source issue:** `rehearsal-cli-defects`
- **Landed:** 2026-08-13

### a genuinely missing test still fails the check

- **Scenario id:** `RCD-C3`
- **Intent:** `REH-3`
- **Source issue:** `rehearsal-cli-defects`
- **Landed:** 2026-08-13

### the current-issue pointer is in shipping scope

- **Scenario id:** `RCD-D1`
- **Intent:** `REH-5`
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

### the samples use the current vocabulary

- **Scenario id:** `EX-1`
- **Intent:** `REVIEW`
- **Source issue:** `consolidate-trc-and-scn-prefixes`
- **Landed:** 2026-08-13

### the canonical id prefix is used throughout

- **Scenario id:** `EX-2`
- **Intent:** `REVIEW`
- **Source issue:** `consolidate-trc-and-scn-prefixes`
- **Landed:** 2026-08-13

### every sample still passes its own checks

- **Scenario id:** `EX-3`
- **Intent:** `REVIEW`
- **Source issue:** `consolidate-trc-and-scn-prefixes`
- **Landed:** 2026-08-13

### the guard can fail

- **Scenario id:** `EX-4`
- **Intent:** `REVIEW`
- **Source issue:** `consolidate-trc-and-scn-prefixes`
- **Landed:** 2026-08-13

### the enforcement path exempts by anchored name

- **Scenario id:** `PRF-1`
- **Intent:** `REVIEW`
- **Source issue:** `pr-50-review-findings`
- **Landed:** 2026-08-13

### the session-end hook reads the spine

- **Scenario id:** `PRF-2`
- **Intent:** `REVIEW`
- **Source issue:** `pr-50-review-findings`
- **Landed:** 2026-08-13

### the scan reads the hook's own messages

- **Scenario id:** `PRF-3`
- **Intent:** `REVIEW`
- **Source issue:** `pr-50-review-findings`
- **Landed:** 2026-08-13

### an explicit project root is trusted

- **Scenario id:** `PRF-4`
- **Intent:** `REVIEW`
- **Source issue:** `pr-50-review-findings`
- **Landed:** 2026-08-13

### the warners say when they cannot find the project

- **Scenario id:** `PRF-5`
- **Intent:** `REVIEW`
- **Source issue:** `pr-50-review-findings`
- **Landed:** 2026-08-13

### the tests that could not fail can now fail

- **Scenario id:** `PRF-6`
- **Intent:** `REVIEW`
- **Source issue:** `pr-50-review-findings`
- **Landed:** 2026-08-13

### the suite passes on a clean clone

- **Scenario id:** `PRF-7`
- **Intent:** `REVIEW`
- **Source issue:** `pr-50-review-findings`
- **Landed:** 2026-08-13

### the script is the eight-shot re-cut

- **Scenario id:** `RR-1`
- **Intent:** `RULE-2`
- **Source issue:** `rehearsal-recordings`
- **Landed:** 2026-08-13

### the post-3.0.0 shots are marked pending and listed for re-check

- **Scenario id:** `RR-2`
- **Intent:** `RULE-2`
- **Source issue:** `rehearsal-recordings`
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

### no retired slash command remains

- **Scenario id:** `RCD-F1`
- **Intent:** `RULE-5`
- **Source issue:** `rehearsal-cli-defects`
- **Landed:** 2026-08-13

### a retired CLI verb is an unknown verb

- **Scenario id:** `RCD-F2`
- **Intent:** `RULE-5`
- **Source issue:** `rehearsal-cli-defects`
- **Landed:** 2026-08-13

### a retired flag is an unknown flag

- **Scenario id:** `RCD-F3`
- **Intent:** `RULE-5`
- **Source issue:** `rehearsal-cli-defects`
- **Landed:** 2026-08-13

### the migrator keeps its v1-to-v2 mapping

- **Scenario id:** `RCD-F4`
- **Intent:** `RULE-5`
- **Source issue:** `rehearsal-cli-defects`
- **Landed:** 2026-08-13

### a v1 name in a markdown code span or fenced block is caught

- **Scenario id:** `RCD-G2`
- **Intent:** `RULE-5`
- **Source issue:** `rehearsal-cli-defects`
- **Landed:** 2026-08-13

### the archive is exempt and unedited

- **Scenario id:** `RCD-G4`
- **Intent:** `RULE-5`
- **Source issue:** `rehearsal-cli-defects`
- **Landed:** 2026-08-13

### the tightened guard can fail

- **Scenario id:** `RCD-G5`
- **Intent:** `RULE-5`
- **Source issue:** `rehearsal-cli-defects`
- **Landed:** 2026-08-13

### the version is consistent across every location

- **Scenario id:** `RCD-H1`
- **Intent:** `RULE-5`
- **Source issue:** `rehearsal-cli-defects`
- **Landed:** 2026-08-13

### conventional comments is a shipped default

- **Scenario id:** `SR-1`
- **Intent:** `RULE-S1`
- **Source issue:** `strategy-rulings-2026-08`
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

### the cross-issue board names each computed approach

- **Scenario id:** `RCD-E2`
- **Intent:** `SWEEP`
- **Source issue:** `rehearsal-cli-defects`
- **Landed:** 2026-08-13

### a v1 name in a Python single-token literal is caught

- **Scenario id:** `RCD-G1`
- **Intent:** `SWEEP`
- **Source issue:** `rehearsal-cli-defects`
- **Landed:** 2026-08-13

### the hooks directory is a scanned surface

- **Scenario id:** `RCD-G3`
- **Intent:** `SWEEP`
- **Source issue:** `rehearsal-cli-defects`
- **Landed:** 2026-08-13

### routing ids are RP- and kinds are distinct

- **Scenario id:** `GL-D1`
- **Intent:** `WRONG-PREFIX`
- **Source issue:** `id-prefix-vocabulary-and-glossary`
- **Landed:** 2026-08-13

### the evaluator is unchanged by the rename

- **Scenario id:** `GL-D2`
- **Intent:** `WRONG-PREFIX`
- **Source issue:** `id-prefix-vocabulary-and-glossary`
- **Landed:** 2026-08-13

### the archive keeps the id that fired

- **Scenario id:** `GL-D3`
- **Intent:** `WRONG-PREFIX`
- **Source issue:** `id-prefix-vocabulary-and-glossary`
- **Landed:** 2026-08-13
