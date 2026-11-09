---
id: ADR-098
title: Compass migrate moves an 8.x project and the legacy readers end
status: proposed
date: 2026-11-07
supersedes: ''
superseded_by: ''
---

## Context

Compass 9.0.0 is an ATDD framework with a proof trail (ayeo-io/compass-delivery#359 [Add compass migrate and the 9.0.0 upgrade guide], under #345 [Reposition Compass 9.0.0 as an ATDD framework with a proof trail]). The issue asks:

> Give a project on 8.x a path to 9.0.0 that keeps its evidence.
> - `compass migrate`: keeps the manifest, scenarios, evidence and approvals; moves an issue at define, refine or plan to Specify, and an issue at verify to Ship; moves subtask, artifact-status and document records under `legacy:` in the manifest; asks for the request link when it is missing.
> - `compass policy lint` names each removed `compass.yml` key with its replacement or "removed".
> - `compass check` names each project check or waiver that names a deleted check, and refuses until it is gone.
> - Delete the legacy readers. A project on 6.x or 7.x upgrades to 8.x first.
> - Write the 9.0.0 upgrade guide, with the removed slash commands and their replacements.
> - State in the release notes that 8.x gets security fixes only, for 90 days.

Earlier records hand parts of this to #359:

- `governance/decisions/2026-10-25-legacy-readers-readable-until-9-0-0.md` lists the readers that end at 9.0.0: old words, old approach names, copied 5.x governance, the generated views `governance/routing-policy.yml` and `governance/guardrails.yml`, `.compass/config.yml` when `compass.yml` is absent, the waivers that the 8.x settings migration wrote, and the role flags (`--justify role=` and `quick-fix start --role`). `docs/upgrade-7-0-0.md` promises users the same list.
- ADR-092 maps a legacy stage to a path stage through `stable_ids.LEGACY_TO_PATH`, and leaves the rewrite of stored stage values to this change.
- ADR-094 keeps the frozen presets, the generated views and the `extends:` pin "until #359". A pin of `compass:default@6` or `@7` keeps the acceptance strategy `S17` off until this change writes `acceptance_strategy: off` in its place.
- ADR-097 decisions 4 and 7 keep the `old_names` row of the deleted alias skill and the hook's fallback to `delivery-approach.md` for this change.

What is in place before this change:

- **An 8.x issue already becomes a path issue when it is assessed again.** `compass approach evaluate --write` calls `path_writer.write`. It writes the path keys, commits a new generation from the check set, keeps the state of each gate, and drops the keys in `path_writer.LEGACY_ONLY` (`stages`, `subtask_ceiling`, `max_worktrees`, `orchestration`). The dropped keys are lost.
- **A path issue's stage follows its records.** It is at Specify once every scenario has an id, an intent and a declared test. It is at Build until every scenario that is not narrative has a red no later than its first green (ADR-088).
- **The lint names removed keys but no replacements.** Six tables hold the removed keys: `settings_lint.REMOVED` and the `SETTINGS`, `SETTING_FIELDS`, `SWITCHES`, `EFFECTS` and `CAPABILITIES` tables of `removed_parts`. None of them names what replaces a key.
- **A deleted check is shown as nothing to check.** `check_registry.REMOVED` holds `dashboard-current` (7.0.0) and seven 9.0.0 ids. `removed_parts.READY_CHECKS` holds the Definition of Ready checks, which have no implementation. `compass waiver add` accepts any check the issue's policy holds, and an 8.x stored generation can hold `artifacts-approved`. So a project check or a waiver can name a deleted check, and nothing says so.
- **The top-level verb `migrate` is free.** `compass issue migrate` is the 1.x-to-2.0 migration, and `compass issue migrate --config` moves one issue to a new generation.
- **`SECURITY.md` says only the latest release gets security fixes.** No document states a support period for 8.x.

### What the archive reaches

The archive is this repository's own issue records: 622 issue folders and 616 manifests, all 8.x, kept out of git in the main checkout. Of the manifests, 47 are open and 569 are closed. None holds a waiver, a `policy:` block, a request link or a `trail.md`.

The measurement ran `compass check --json` on every folder and compared the exit code and the status of every row, issue by issue. It ran three CLIs:

1. the `v9` integration branch as it was;
2. a copy that logs each call of a legacy reader;
3. a copy with the two generated views and the two frozen presets deleted, and with the other legacy readers replaced by stubs. `find_governance` raises, the retired-word tables and the `old_names` table are empty, `pinned_below` returns nothing, and the governance-copy detection returns false.

`compass check` reaches four legacy readers on the archive:

| Reader | Archived issues that reach it | What it changes |
|---|---|---|
| The retired-word table of `word_map`, through `generation.load` | 73 stored generations | nothing |
| `acceptance_strategy.pinned_below` | 613 | the text of a notice only |
| `core.find_governance`, for the quarantine list of `no-trusted-rerun` | 535 | nothing: the project's list and the framework's are the same file |
| `old_names`, through the project state | 535 | nothing: the state file holds neither old nor new word |

The copied-governance adapter, the drift report, the old manifest words, the hook fallback, `.compass/config.yml` and the role flags are reached by no archived issue.

**Result: the third CLI gives the same exit code and the same status on every row of every issue as the first: 0 pass to fail, 0 fail to pass, 0 other changes.** 493 issues exit 0, 123 exit 1 and 6 exit 2, in both runs. So every legacy reader that `compass check` reaches can be removed with no verdict change over the 622 issues.

The measurement covers `compass check` only. The hook, `compass next`, `compass approach evaluate` and the lint were not compared on the archive. The comparison runs again after each deletion step, because a stub is not a deletion.

## Decision

1. **`compass migrate` is one verb, a dry run by default, and `--apply` writes.**

   ```text
   compass migrate [--apply] [--issue <slug>] [--settings-only | --issues-only]
                   [--request <url> --requester <name>]   (with --issue only)
   ```

   - The dry run prints each change on one line. It exits 0 when there is nothing to do, 1 when there is something to do and 2 when it refuses. `--apply` prints the same lines in the past tense.
   - It refuses with exit 2, before it writes anything:
     - a project with both governance files and no `compass.yml`, with "run `compass policy migrate` on Compass 8.x first";
     - an `extends: github:...` parent;
     - a manifest with a 1.x key or file name, with "run `compass issue migrate --apply` first";
     - an issue whose generation is not whole.
   - It takes the issue lock for each manifest and the project lock for `compass.yml`.
   - Each changed manifest gets a `reassessments:` entry with the reason "compass migrate to 9.0.0".

2. **An open, assessed 8.x issue becomes a path issue through `path_writer`, and its 8.x records move under `legacy:`.** A closed issue, a path issue and an issue that was never assessed are left as they are, and the output says why. For an issue it converts, `compass migrate`:
   - runs the write path of `compass approach evaluate --write`, which commits a new generation from the check set. `path_writer.write` gains a `keep` argument, so the keys it drops go under `legacy:`. `compass approach evaluate` passes none, so its output does not change;
   - moves these records under `legacy:`:

     | Key now | Under `legacy:` | Why it moves |
     |---|---|---|
     | `stages`, `subtask_ceiling`, `orchestration`, `max_worktrees` | the same names | `path_writer.write` drops them |
     | `subtasks` | `subtasks` | multiagent runs were removed (ADR-090) |
     | `models` | `models` | not read since 9.0.0 (ADR-090) |
     | `page_ticks` | `page_ticks` | only an 8.x issue's item records read it |
     | `readiness` | `readiness` | removed (ADR-093) |
     | each `artifacts:` entry whose kind is not `acceptance-criteria` | `documents` | 9.0.0 keeps one issue document (ADR-091) |
     | each field of the `acceptance-criteria` entry other than `id`, `kind`, `path`, `reason` and `status` | `artifact_status`, by the entry's id | a path issue does not read the artifact status; the entry keeps `status` because the manifest schema needs it, and keeps the rest so the spec is still found |

   - keeps `scenarios`, `evidence`, `gates` with their states, `checkpoint_outcomes`, `delegations_used`, `waivers`, `changed_files`, the `land_*` fields, `github`, `follow_ups`, `friction`, `reassessments`, `depends_on` and `raised_by` where they are;
   - rewrites a legacy stage value in `depends_on[].until` and `raised_by.found_at` to its path stage, and keeps the old value in `legacy.stage_values`;
   - writes `trail.md` again after the manifest when it exists, so its manifest digests match.

   `compass check` and every reader of a path issue ignore `legacy:`. The manifest schema gains `legacy` as an object. A manifest without it stays valid.

3. **The stage follows the records, and `compass migrate` writes nothing to move it.** An issue at `define`, `refine` or `plan` lands at Specify. An issue at `verify` or `ship` lands at Ship only when its records show a red before each green. When they do not, the output names the scenario that holds the issue at Build, for example "TRC-002 has a green and no red before it". `compass migrate` never writes a red, a green or a checkpoint outcome to place an issue.

4. **`compass migrate` never writes an approval or evidence.** It never:
   - writes or changes a file under `evidence/`, a `.red` or `.acceptance` marker, `approval-requests/` or `scenario_freeze`;
   - adds an evidence entry, a `checkpoint_outcomes` entry or a `delegations_used` entry. A `define` outcome stays a `define` outcome;
   - changes the state of a gate. A new gate starts at `pending`.

   A test checks this on an issue with a red, a green, `evidence/SHA256SUMS`, a `human-approval`, a `checkpoint-approval`, a delegation and a `trail.md`. The bytes of `evidence/` stay the same, `SHA256SUMS` and `compass trail --check` pass, and the count of approval records stays the same.

5. **`compass migrate` asks for the request link by listing, not by a prompt.** When `request.link` is missing and the manifest has a `github` link, it writes the link as ADR-096 does. When the requester is missing, it lists the issue under "needs a request link" with the `compass issue link set` command to run. `--request` and `--requester` with `--issue` answer it in the same run. The new `evidence_required` holds the request, so `request-recorded` fails until a person sets it.

6. **`compass migrate` rewrites the settings with a line edit that keeps comments.**

   | In `compass.yml` | `compass migrate` writes |
   |---|---|
   | `extends: compass:default@6` or `@7` | deletes the line and adds `acceptance_strategy: {state: off, reason: ...}`, unless `acceptance_strategy` is set |
   | `extends: compass:default@8` or later | deletes the line |
   | `gates.G5` with a `set:` on `when.labels_any` | `signoff_labels:` with the added labels |
   | a `rules:` floor whose effect is `add_gate` | a `require_evidence:` entry with the rule's `when`, when the gate has an evidence token; otherwise a line that names the rule and says no setting replaces it |
   | a project guardrail with `check: command-passes` | a `project_checks:` entry, with its stage mapped through `LEGACY_TO_PATH` to `build` or `ship` |
   | a set `require_phase` | dropped, with a line that says so |
   | a floor with `force_minimum_approach`, `forbid_approach` or `never_skip` | dropped, with a line that names the rule and suggests `require_evidence` or `require_skill` where the rule also used one |
   | the agent review block of `docs/judged-checks.md` | `agent_review: on` |
   | `multiagent:`, `models:`, `living_spec:`, `artifacts:`, `approaches:`, `readiness:`, `prices:`, `github_labels:`, `preset`, `preset_index`, `governance_drift`, the six removed `project.*` fields, `approvers.project-waiver` | deleted, with the key and "removed" |
   | `approvers.issue-waiver` | renamed `approvers.waiver` |

   A removed top-level key goes with its indented lines and the comment block directly above it. New settings go at the end, under one comment line that names `compass migrate`. The dry run prints the diff. After the edit, `compass policy lint` must pass with no `L-SETTING-REMOVED` finding. If it does not, nothing is written and the output names the lines a person must edit.

7. **`compass policy lint` names a replacement for each removed key.** One table, `removed_parts.REPLACEMENTS`, keyed as the lint paths are, gives each removed key its replacement or "removed". Every key of the six removed-key tables must have a row, and a test fails on a missing one. The message ends "Replacement: `<setting>`." or "Removed: nothing replaces it.", then "`compass migrate` rewrites it." when migrate handles the key. `--json` adds a `replacement` field to each `L-SETTING-REMOVED` finding. For `extends: compass:default@6` and `@7` the replacement is `acceptance_strategy: {state: off, reason: ...}`; for `@8` and later it is "removed".

8. **`compass check` refuses while anything names a deleted check.** `DELETED_CHECKS` holds the keys of `check_registry.REMOVED` and `removed_parts.READY_CHECKS` in one place. `compass check` refuses with exit 2 and the refusal code `names-deleted-check`, before it runs any row, and names each of these:
   - a `project_checks` entry whose `id` is a deleted check;
   - a check or gate entry of a removed catalogue key in `compass.yml` that lists a deleted check;
   - a waiver of the issue that is not withdrawn and names a deleted check, with `compass waiver withdraw W-<n>` as the fix.

   `compass waiver add` refuses a deleted check, and the settings lint refuses such a `project_checks` id. No archived issue holds a waiver, and this repository's `compass.yml` holds no `project_checks`, so no archived verdict moves.

9. **Two legacy readers are deleted now.** Each deletion step ends with the archive comparison at 0 changes.
   - The drift report and the framework lint: `governance.governance_drift`, the drift lines of `compass approach evaluate`, and the legacy reports of `policy_cmd`. `compass policy lint` is the settings lint in every project, the framework's included. `governance_drift` becomes a removed setting.
   - Old typed names and the role flags: the old names typed on the command line (the reassessment kind, the check id given to `evidence approve`, `evidence request` and `evidence review`, and the refusal code), the `old_names` rows and functions that only those read, the `shape_display` section of `cli/migrate-map.yml`, `quick-fix start --role` and `--justify role=`. A typed old name fails as any unknown name does. `retired.DIMENSIONS` stays, so the stored `assessment.role` readings still read.

   Typed input takes only the 9.0.0 names, and stored files keep reading as stored (VD-043 decisions 8 and 9). So the old size `standard` typed on the command line (`routing.read_size`) and the `old_names` row of the refusal code are deleted too, and fail as any unknown value does. The readers of old words in a stored file stay (decision 10): the manifest half of `word_map`, the old-word mapping in `generation.load`, and the `old_names` rows that a stored record reads. Deleting them would change compatibility contract 3 or how 616 archived manifests and 73 archived stored generations read.

10. **These readers stay, with the reason:**
    - `stable_ids.LEGACY_TO_PATH` and the readers of a legacy stage. All 616 archived manifests are 8.x, and `depends_on`, `--found-at` and `retro --lineage` values name legacy stages. ADR-092 added them in 9.0.0; the 2026-10-25 decision did not end them.
    - `compass issue migrate` and its 1.x readers. They are not on the 2026-10-25 list, and no archived manifest needs them. A 6.x project upgrades through 8.x, which runs them.
    - `generation.load`, the major refusal and `compass issue migrate --config`, because every stored generation needs them.
    - The legacy stage names of the checkpoint outcomes, so an old outcome still reads (ADR-092).
    - `.compass/config.yml` when `compass.yml` is absent. 9.0.0 still reads it (open question 5). No archived issue and no file in this repository reads it, so keeping it changes no verdict. Stopping would add a hook refusal and change about 100 test files. `compass migrate` rewrites `compass.yml` only, and tells a project with only the old file that 9.0.0 still reads it.
    - The readers of old words in a stored file: the manifest half of `word_map` with the `values` and `friction_keys` sections of `cli/migrate-map.yml`, the old-word mapping in `generation.load`, and the `old_names` rows `reassessment_kind`, `check_id`, `skill`, `state_key` and `term`. 616 archived manifests and 73 archived stored generations hold those words, contract 3 reads them through `compass issue migrate`, and an 8.x `state.yml` stores the old state key. `term` is the other form of `catalog` that ADR-041 keeps. Each row says `removed_in: 10.0.0`, so `old_names.removal_problems` lists none of them in 9.x.

11. **The other readers on the 2026-10-25 list wait for the owner.** Each changes what a compatibility contract asserts or a frozen file, so the owner decides (open questions 1 to 4, 6, 7 and 9):
    - copied governance, the generated views, `find_governance` and the `None` answer of `view_or_legacy`. The legacy adapter would move into a test helper, and every command would refuse a governance copy with `governance-copy-removed`;
    - the frozen presets `default@6` and `default@7`, and the `extends:` pin `pinned_below`;
    - the hook's fallback to `delivery-approach.md`.

    Until then they stay as they are, and the archive measurement shows they hold no `compass check` verdict.

12. **The 9.0.0 upgrade guide is a new `upgrade-9-0-0.md` in `docs/`.** It follows the form of `docs/upgrade-8-0-0.md`, with these sections:
    1. Before you start: a project on 6.x or 7.x upgrades to 8.x and moves its settings there. Copy the issue records outside the project first.
    2. Run `compass migrate`, then `compass migrate --apply`: what it changes and what it never does.
    3. The settings: the table of `removed_parts.REPLACEMENTS`, written into the page by a script, so the page cannot disagree with the lint.
    4. The removed slash commands:

       | Removed | Use instead |
       |---|---|
       | `/compass:define`, `/compass:refine`, `/compass:plan` | the Specify stage of `/compass:go` |
       | `/compass:breakdown`, `/compass:implement` | the Build stage of `/compass:go` |
       | `/compass:verify` | the Ship stage of `/compass:go`, and `/compass:ship` |
       | `/compass:intent`, `/compass:position`, `/compass:design`, `/compass:consult` | nothing (ADR-093 decision 1) |

       `/compass:flow` is still shipped. A test checks the table against the commands of `v8.0.4` and of 9.0.0.
    5. Removed verbs and flags, from `removed_parts.COMMANDS`, written the same way.
    6. The deleted checks, and what `compass check` refuses.
    7. The readers that ended, and the readers that stay.
    8. The record: committed by default (ADR-096).
    9. Support.

13. **8.x gets security fixes only, for 90 days after 9.0.0 is released.** The line is: "Compass 8.x gets security fixes only, for 90 days after 9.0.0 is released. After that, only 9.x is supported." It goes into the upgrade guide, into the "Supported versions" section of `SECURITY.md`, and into `docs/releasing.md` as the text the 9.0.0 release notes must hold. A test checks all three. The release commit adds the date to `SECURITY.md`. The 8.x branch for those fixes is outside this change.

## As built

#359 was built on `v9` from commit 10da100f (this record, step 1) to the commit that adds this section. VD-037 decided what to build before the owner answers the open questions: steps 1, 2, 3, 4, 5, 7, part of step 9, 12 and 13. The decisions above hold, with the corrections below. Each point says how the build differs from, or adds to, the first text of this record.

What shipped:

- **Decision 1** is built in a new module, `migrate_9` (commit 89d95d38), with two refusal codes, `governance-copy-removed` and `git-parent-removed` (VD-038). A 1.x manifest or a generation that is not whole refuses that issue only. The run lists it under "refused", lists the other issues and exits 2. The settings half (commit ad97b20f) adds `--settings-only` and `--issues-only`. `--issue` runs the issues half only, so moving one issue never rewrites `compass.yml`, and `--issue` with `--settings-only` is refused (VD-039).
- **Decision 2** is built as written, with four details (VD-038):
  - `compass migrate` asks for no justification of an assessed value, because it writes the assessment the issue already holds. `routing.cmd_route_evaluate` skips that refusal only when `compass migrate` calls it.
  - The `reassessments:` entry is of kind `policy-correction`: the assessment was right and the policy under it moved, so the entry does not read as a misread assessment.
  - The acceptance-criteria entry keeps `status`, because the manifest schema needs it on every `artifacts:` entry. Decision 2's table now says so.
  - A spike keeps its approach and stage map, and an issue that holds `legacy:` is left as it is ("already moved by compass migrate").

  A dry run over a copy of this repository's archive lists the 15 open assessed issues. No agent ran `--apply` on this repository (open question 7).
- **Decision 6** is built in a new module, `migrate_settings` (commit ad97b20f), with seven details (VD-039). `removed_parts.REPLACEMENTS` drives it, so a row a later step adds is migrated with no change to migrate. A removed key that holds a part no setting carries, such as `rules:` with `rules.caps`, is left whole with the edit to make; a left key does not change the exit code. A project check at a specify stage runs at build, the earliest stage a project check runs at. Only `compass.yml` is rewritten: decision 6's table no longer names `.compass/config.yml`, because 9.0.0 still reads that file (decision 10).
- **Decision 7** is built as written (commit 59799e72). `docs/configuration.md` holds the table of `REPLACEMENTS`, and `tests/test_lint_names_replacements.py` fails when it differs.
- **Decision 8** is built as written (commit 11a3cf96). `DELETED_CHECKS` lives in `check_registry`, beside `REMOVED`. The archive comparison over 622 issue folders showed 0 changes.
- **Decision 9**, the drift report (commit 395704ea). `governance.py` keeps only the structural lint of a governance copy (`legacy_structure` and `cmd_policy_lint`), because contract 4 (`policy-lint-copied`, `policy-lint-broken`) and `compass ci` read it until copied governance goes (open question 1). `governance_drift` is a removed setting; it stays a settings key for the settings-conflict check of an old `.compass/config.yml`. The tests that covered only the drift report were deleted with it.
- **Decision 9**, old names and role flags (commit 41ee4476, VD-040). Only the typed old names, the `old_names` rows and functions nothing else reads, the `shape_display` section and the two role flags are deleted. The first text of this record said all of the retired-word half of `word_map` and all of `old_names` go; decision 9 now says what went, and decision 10 lists what stays.
- **Decision 12** is built in `docs/upgrade-9-0-0.md`, with the sections it lists. `scripts/render-upgrade-guide.py` writes four tables between markers: the removed settings from `REPLACEMENTS`, the removed verbs and flags from `removed_parts.COMMANDS`, the removed slash commands, and the deleted checks from `DELETED_CHECKS`. `tests/test_upgrade_9_0_0_guide.py` fails when a table is stale, when a slash command that `v8.0.4` shipped is gone with no row, or when the two pages that show `REPLACEMENTS` disagree. The page also lists the parts that wait for the owner. `tests/test_documented_slash_commands_exist.py` skips the page, as it skips the release table of `docs/releasing.md`, and the new test checks every slash command the page names outside its table.
- **Decision 13** is built as written. The support line is in the guide, in "Supported versions" of `SECURITY.md` and in "What changes at 9.0.0" of `docs/releasing.md`, and the new test checks all three. The release commit adds the date.
- **Open question 18**: `governance/terminology.yml` gains `legacy-record`, at version `2.0.0-pre30`. It holds no term for the drift report or the generated views, so none is removed. The `old_names` row `term` stays: the accepted vocabulary decision (ADR-041) keeps `catalogue` as the other form of `catalog`, and `tests/test_terminology.py` (`TRC-069`) checks it.

What was kept, and why:

- The manifest half of `word_map`, with the `values` and `friction_keys` sections of `cli/migrate-map.yml`. Contract 3 runs `compass issue migrate` over an archive sample, which rewrites old manifest words through `word_map.map_manifest`; without that half, `issue lint` exits 1 instead of 0 on 16 of those issues. Contract 5 stores `define: full` (VD-040).
- `routing.read_size` until #359 step 9 deleted it (VD-043 decision 9). Contract 4's regular issue, which stores `size: standard`, still reads; the two entries that type `standard` on a project 9.0.0 reads exit 2 and are listed in `EXIT_CHANGED_IN_9_0_0`.
- The old-word mapping in `generation.load`. 73 archived stored generations hold an old check id or skill name. Without the mapping they would read in their stored words.
- The copied-governance reader, its word mapping and the structural lint of a copy, until copied governance goes (open questions 1 to 3).
- The `old_names` rows `reassessment_kind`, `check_id`, `skill`, `state_key` and `term`, each marked `removed_in: 10.0.0`, so `old_names.removal_problems("9.0.0")` lists none. The `refusal_code` row went with step 9: no stored file holds a refusal code.
- `.compass/config.yml` when `compass.yml` is absent (open question 5, VD-037).

What waits for the owner:

- Step 6: delete copied governance, the generated views, `find_governance` and the legacy adapter, and move the adapter into the test helper `legacy_copy` (open questions 1 to 3).
- Step 10: delete the frozen presets and the `extends:` pin `pinned_below` (open questions 6 and 9).
- Step 11: delete the hook's fallback to `delivery-approach.md` (open question 4).
- The rest of step 9: the readers of old words in a stored file, listed above. They need open question 13 reversed or contracts 3, 4 and 5 changed, and the owner's acceptance that 73 archived generations read in their stored words.
- Step 8 is dropped while open question 5 stays answered no.
- Open question 7: `compass migrate` on this repository's settings and its 15 assessed open issues is the owner's to run.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| Store the 8.x stage as a floor that the path stage honors | An issue at `verify` would land at Ship, as the issue text says | It would show an issue at Ship whose reds `G1` still refuses |
| Write a red or a checkpoint outcome to place an issue | It would place each issue at its 8.x stage | Migrate would write evidence and approvals, which it must keep as they are |
| Drop the keys `path_writer` drops, as `compass approach evaluate --write` does now | No reader of a path issue uses them | It loses the 8.x record the issue asks to keep |
| Prompt for the request link | The issue says "asks for the request link" | A session runs the command, and a prompt stops it; the listed command and `request-recorded` ask instead |
| Dump `compass.yml` as YAML | It is simpler than a line edit | It loses every comment, and this repository's file holds many |
| Show a deleted check as nothing to check, with a warning | It changes nothing for a project that names one | The issue says `compass check` refuses until it is gone |
| Let a governance copy with no `compass.yml` pass in silence | Nothing breaks at once | The project's own guardrails would stop applying without a word; a git parent is refused for the same reason (ADR-094) |
| Delete `LEGACY_TO_PATH` and the legacy-stage readers | They read old stage names | All 616 archived manifests read through them |
| Delete every legacy reader now | The archive measurement shows none holds a verdict | Copied governance, the frozen presets, the pin and the hook fallback change compatibility contracts or frozen files, which the owner decides |
| Stop reading `.compass/config.yml` now | The 2026-10-25 decision ends it at 9.0.0 | No archived issue or file here reads it; stopping adds a hook refusal and about 100 test changes before the owner answers the contract questions |
| Name a calendar date in the support line now | A reader can plan against a date | The release date is not known; the release commit adds it |

## Consequences

What changes for a user:

- `compass migrate` moves an 8.x project to 9.0.0 without a hand edit of each issue, and shows the change first.
- An open 8.x issue becomes a path issue and keeps its evidence, approvals, gates and outcomes. Its 8.x records stay readable under `legacy:`.
- An issue whose records show a green with no red before it shows at Build, not at Ship, and the output says which scenario holds it.
- `compass policy lint` says what replaces each removed key.
- `compass check` refuses while a project check or an open waiver names a deleted check, and names the fix.
- `compass policy lint` reports no drift. The `governance_drift` setting is removed.
- A typed old name, `quick-fix start --role` and `--justify role=` are refused as unknown.
- 8.x gets security fixes only, for 90 days after 9.0.0 is released.

What stays:

- Every archived `compass check` verdict. The comparison runs after each deletion step and must show 0 changes.
- `governance/check-set.yml` and `generation.RESOLVER_VERSION`. No check is added or removed, and a stored generation is read as stored.
- Contracts 1 to 5, their corpora and `tests/fixtures/frozen-digests.yml`, until the owner answers open questions 1 to 4.
- `S17` stays off for this repository until the owner edits `compass.yml` or runs `compass migrate --apply --settings-only`.

What a project must do:

- Upgrade to 8.x first if it is on 6.x or 7.x.
- Run `compass migrate`, read the diff, and run it again with `--apply`.
- Give a request link and a requester for each issue it lists.
- Remove any waiver or project check that names a deleted check.

## Open questions

Questions 1 to 4, 6, 7 and 9 are the owner's. Each changes a compatibility contract, the owner's files or what a user sees. This change does not build them. Each states the default the build plan proposes.

1. **How do contracts 1 and 2 read the 8.0.4 copy once the adapter leaves the CLI?** Proposed: the adapter and the copy resolution move into a new test helper, `legacy_copy`, used only by contracts 1 and 2 and the tests that compare with 8.0.4. No pin changes. The other answer retires contracts 1 and 2, because 9.0.0 routes no delivery approach for a new issue.
2. **Does configuration C, the 5.6.0 copy, stay?** Proposed: it stays for contracts 1 and 2, through the helper. It is retired for contracts 3, 4 and 5, because a 9.0.0 CLI would refuse a project with copied governance.
3. **Which contract 4 entries change, and how are they recorded?** Proposed: the four governance-copy entries go into the lists of entries that changed in 9.0.0, with their new exit codes, as ADR-094 did. The corpus and its digest do not change.
4. **Does the contract 5 builder write the 9.0.0 file shapes?** Proposed: yes. It writes `compass.yml` in place of `.compass/config.yml`, `initialized` in the state file and a `delivery_approach` key in the manifest. The corpus does not change. The other answer keeps the hook fallback for contract 5.
5. **Does 9.0.0 stop reading `.compass/config.yml`?** Decided: no, not now (decision 10). The reader stays in 9.0.0. The build plan's default was to stop reading it.
6. **When does `S17` change for a pinned project, this repository included?** Proposed: `pinned_below` is deleted after the owner moves this repository's `compass.yml` to `acceptance_strategy: off`. A pinned project that does not run `compass migrate` gets `S17` at its next assess, and its lint names the replacement. The other answer keeps `pinned_below` in 9.x.
7. **Is `compass migrate` run over this repository's archive and settings?** Proposed: the settings, yes, by the owner. For each of the 15 assessed open issues the owner chooses to finish, abandon or migrate it. No agent runs `compass migrate --apply` on this repository. Nothing here needs those issues migrated, because no deleted reader holds a verdict.
8. **What does "moves an issue to Specify or Ship" mean?** Decided: the issue becomes a path issue and its stage follows its records (decision 3).
9. **Do the frozen presets go?** Proposed: yes. Only `artifact_kinds.entry` (2 archived issues, no verdict change) and `compass _derive-glossary` read them. `tests/test_frozen_files_unchanged.py` lists `default@6` as frozen, so the deletion changes that test. The other answer keeps them as data with no reader.
10. **Does a governance copy with no `compass.yml` get a refusal or silence?** Decided: a refusal with exit 2. `compass migrate` refuses it now (decision 1). Every other command refuses it with `governance-copy-removed` once copied governance is deleted (open question 1).
11. **Where do `stages` and the other dropped keys go?** Decided: under `legacy:` (decision 2).
12. **Do `LEGACY_TO_PATH` and the legacy-stage readers go?** Decided: no (decision 10).
13. **Do the 1.x readers of `compass issue migrate` go?** Decided: no (decision 10). Their removal is a separate change with its own archive run.
14. **What does `compass check` refuse for a deleted check?** Decided: the three cases of decision 8, with exit 2.
15. **How is `compass.yml` rewritten?** Decided: a line edit that keeps comments, checked by the lint before it is written (decision 6).
16. **Does `compass migrate` prompt for the request link?** Decided: no (decision 5).
17. **Does the support line name a date?** Decided: "for 90 days after 9.0.0 is released"; the release commit adds the date (decision 13).
18. **Names.** Decided: the verb `compass migrate`, the manifest key `legacy`, the refusal codes `names-deleted-check` and `governance-copy-removed`, the table `removed_parts.REPLACEMENTS`, the set `DELETED_CHECKS` and the test helper `legacy_copy`. The refusal code `git-parent-removed` names a git parent that `compass migrate` refuses (VD-038). `governance/terminology.yml` gains the term `legacy-record`. The refusal code `settings-file-moved` is not used while `.compass/config.yml` is read.

## References

- ayeo-io/compass-delivery#359 [Add compass migrate and the 9.0.0 upgrade guide] and its parent, #345 [Reposition Compass 9.0.0 as an ATDD framework with a proof trail].
- `governance/decisions/2026-10-25-legacy-readers-readable-until-9-0-0.md`, `docs/upgrade-7-0-0.md`, `docs/upgrade-8-0-0.md`.
- ADR-088 (a red before each green), ADR-090, ADR-091, ADR-092 (the path and `LEGACY_TO_PATH`), ADR-093, ADR-094 (the fixed check set, the frozen presets and the pin), ADR-096 (the committed record and the request link), ADR-097 (the kept `old_names` row and hook fallback).
- `cli/compass_pkg/path_writer.py`, `cli/compass_pkg/removed_parts.py`, `cli/compass_pkg/settings_lint.py`, `cli/compass_pkg/check_registry.py`, `cli/compass_pkg/stable_ids.py`, `cli/compass_pkg/acceptance_strategy.py`, `cli/compass_pkg/legacy_adapter.py`, `cli/compass_pkg/word_map.py`, `cli/compass_pkg/old_names.py`, `cli/compass_pkg/governance.py`, `cli/compass_pkg/project_settings.py`, `hooks/py/pre_tool_route_probe.py`, `cli/migrate-map.yml`, `SECURITY.md`, `docs/releasing.md`.
- `tests/compat_baseline.py`, `tests/compat_commands.py`, `tests/compat_hook.py`, `tests/test_compat_configurations.py`, `tests/test_frozen_files_unchanged.py`.
- `cli/compass_pkg/migrate_9.py`, `cli/compass_pkg/migrate_settings.py`, `docs/upgrade-9-0-0.md` and `scripts/render-upgrade-guide.py`, written by this change. The test helper `legacy_copy` is not written; it waits for open question 1.
