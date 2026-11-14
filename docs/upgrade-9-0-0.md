# Upgrading to 9.0.0

This page says how to move a project from Compass 8.x to 9.0.0 and keep its evidence. It lists what 9.0.0 removed and what replaces each part. The decision record is `architecture/decisions/ADR-098-compass-migrate-moves-an-8x-project-and-the-legacy-readers-end.md`.

Compass 8.x gets security fixes only, for 90 days after 9.0.0 is released. After that, only 9.x is supported. `SECURITY.md` says how to report a vulnerability.

## What to do

1. On 6.x or 7.x, upgrade to 8.x first.
2. On 8.x, run `compass policy migrate`. It moves copied `governance/` files or `.compass/config.yml` into `compass.yml`. 9.0.0 does not have that command.
3. Copy `compass.yml`, `.compass/work` and `docs/compass` to a folder outside the project.
4. Update every checkout and every installed plugin together.
5. Run `compass migrate` and read the list and the diff.
6. Run `compass migrate --apply`.
7. Make each edit listed under "settings left for you to edit", then run `compass migrate` again.
8. Run each `compass issue link set` command the report lists.
9. Change the skill names `compass:bdd-specification` and `compass:behavior-mapping` to `compass:atdd` in your `CLAUDE.md` and lessons.

## Run `compass migrate`

`compass migrate` rewrites `compass.yml` for 9.0.0. Then it moves each open issue that 8.x assessed onto the four-stage path: assess, specify, build and ship (ADR-092). Run it from the project root:

```
compass migrate                   # a dry run: lists what it would change, writes nothing
compass migrate --apply           # writes the changes the dry run listed
compass migrate --settings-only   # compass.yml only
compass migrate --issues-only     # the issues only
compass migrate --issue <slug> --apply   # one issue; leaves compass.yml as it is
```

The dry run exits 0 when there is nothing to do, 1 when there is, and 2 when it refuses.

### What it changes in `compass.yml`

It deletes each key that the table under "Removed settings" marks "rewrites it". 9.0.0 reads no removed key (ADR-094), so this changes no verdict. It writes a setting where one carries what the key asked for:

| In `compass.yml` | `compass migrate` writes |
|---|---|
| `extends: compass:default@6` or `@7` | deletes the line and adds `acceptance_strategy: {state: off, reason: ...}`, so the acceptance strategy `S17` stays off. A file that already sets `acceptance_strategy` keeps its value. |
| `extends: compass:default@8` or later | deletes the line |
| the labels `gates.G5` adds to `when.labels_any` | `signoff_labels:` with those labels |
| a rule whose effect is `add_gate`, for a gate that has an evidence token | a `require_evidence:` entry with the rule's `when` and the token |
| a check with `impl: command-passes` and the guardrail gate that lists it | a `project_checks:` entry with the gate's name and `when`, and the check's command. A specify stage runs at build, the earliest stage a project check runs at. |
| the agent review block (`checks.agent-review` and its `stages.ship` entry) | `agent_review: on`, unless the file sets `agent_review` |
| `approvers.issue-waiver`, with no `approvers.waiver` | renamed `approvers.waiver` |
| every other key the table marks | deleted |

The report has two more lists:

- **"settings not carried over":** each part of a deleted key that no setting carries, such as an `add_gate` of `verify.analyze` or a rule that forces an approach.
- **"settings left for you to edit":** each key the table marks "no", such as `dimensions`, with the edit. A rewritten key that holds one is left whole. For example, `rules:` with a `caps` rule set is left: delete `rules.caps` and run `compass migrate` again.

How it writes the file:

- It edits lines, so comments stay. A deleted key goes with its indented lines and the comment block directly above it.
- New settings go at the end, under one comment line that names `compass migrate`.
- It writes only when the edited file parses to the listed settings, and `compass policy lint` finds no error and no removed key except the ones left for you. If not, it writes nothing to `compass.yml`, exits 2 and names the lines to edit.
- It does not change `.compass/config.yml`. 9.0.0 still reads that file when `compass.yml` is absent.

### What it changes in an issue

It changes each open issue that holds a `delivery_approach` and no `evidence_required`:

- It does the same write as `compass approach evaluate --write --reason "compass migrate to 9.0.0"`. The issue gets the evidence it owes (`evidence_required`), its gates, its checkpoints and a new stored generation. Each gate keeps its state. A new gate starts at pending.
- It adds a `reassessments:` entry of kind `policy-correction`.
- It moves the 8.x record that 9.0.0 does not use under the manifest's `legacy:` key. No check reads `legacy:`.

  | Key in 8.x | Under `legacy:` |
  |---|---|
  | `stages`, `subtask_ceiling`, `orchestration`, `max_worktrees`, `subtasks`, `models`, `page_ticks`, `readiness` | the same names |
  | each `artifacts:` entry that is not the acceptance criteria | `documents` |
  | the fields of the acceptance-criteria entry other than `id`, `kind`, `path`, `reason` and `status` | `artifact_status`, by the entry's id |
  | a legacy stage in `depends_on[].until` or `raised_by.found_at` | `stage_values`; the key gets the path stage |

- It writes `request.link` from a linked GitHub issue when the link is missing.
- It writes `trail.md` again when the issue has one, so its sum lines match the new manifest.

Every other manifest key stays where it is.

### Where each issue lands

| 8.x stage | Path stage |
|---|---|
| `define`, `refine`, `plan` | specify |
| `breakdown`, `implement` | build |
| `verify`, `ship` | ship, when each scenario has a red before its green; otherwise build, and the report names the scenario |

- An issue lands earlier when its records say so, and the report gives the reason. A scenario with no declared test, or a listed `specify` checkpoint with no outcome, keeps the issue at specify.
- An 8.x quick fix has its red in `evidence/red.json`, bound to no scenario. `compass quick-fix finish` also proves the red on the base copy for the issue's scenario, in `evidence/red-<scenario>.json`, and keeps `red.json`.

### What it never does

- It writes no approval, checkpoint outcome, delegation copy, red or green.
- It writes no file under `evidence/`, no `.red` or `.acceptance` marker, nothing under `approval-requests/` and no `scenario_freeze`. `sha256sum -c` over `evidence/SHA256SUMS` passes after it as before.
- It does not change a closed issue, an issue already on the path, or an issue that was never assessed. The report lists each with the reason.

### The request link

9.0.0 asks each issue who requested it and where (`request`, ADR-096). The check `request-recorded` fails until both parts are on record. `compass migrate` does not prompt. It lists each converted issue with no requester, with the command that records it:

```
compass issue link set --issue <slug> --request <url> --requester <name>
```

Or record it in the same run:

```
compass migrate --issue <slug> --apply --request owner/repo#12 --requester "Dana Smith"
```

### What it refuses

It refuses the project with exit 2, before it writes anything:

| Project | Refusal code | What to do |
|---|---|---|
| a copy of `governance/routing-policy.yml` or `governance/guardrails.yml` and no `compass.yml` | `governance-copy-removed` | On Compass 8.x, run `compass policy migrate` to write `compass.yml`. Then run `compass migrate` again. |
| a `compass.yml` whose `extends:` names a git parent | `git-parent-removed` | Move the checks the parent adds into the settings of `compass.yml` and delete `extends:`. Then run `compass migrate` again. |

It refuses one issue, and lists it under "refused", when the issue has:

- a 1.x manifest: run `compass issue migrate --apply` first;
- a stored generation that is not whole.

## A change takes two commands, and what it owes

In 9.0.0 Compass writes the record of a change itself (`architecture/decisions/ADR-099-compass-keeps-the-record-itself-and-a-change-takes-two-commands.md`). A session runs two commands:

1. `compass quick-fix start <slug> --intent "..." --request <URL or owner/repo#N> --requester "<who>"` opens the issue.
2. `compass quick-fix finish -m "<message>" -- <test command>` writes the whole record, asks for each approval a person owes, and commits once a person has approved.

`compass tdd-red`, `compass tdd-green`, `compass scenario add`, `compass changed-file add`, `compass evidence add` and `compass gate pass` still work, and a record they wrote still checks. A 9.0.0 delivery issue does not need them.

### What no longer applies by default

Every delivery issue owes the same evidence: the request link, the scenarios, the red before the green, a green suite, the three gates `verify.correctness`, `verify.governance` and `verify.traceability`, and the ship approval. Risk, size, familiarity and urgency add no review and no record.

An issue does not owe these unless the project adds the token with `require_evidence` in `compass.yml` (`docs/configuration.md`):

| Not owed by default | Its `require_evidence` token |
|---|---|
| the review gate `verify.regression` | `regression` |
| the review gate `verify.security` | `security` |
| the review gate `verify.clarity` | `clarity` |
| the review gate `verify.architecture` | `architecture` |
| the Definition of Done | `definition-of-done` |
| the reproduction of a live defect before anything else | `reproduce-first` |
| the outer-loop records of the four-layer acceptance strategy `S17` | `outer-loop` |
| the isolation proof of `S17` | `isolation` |
| the layering record of `S17` | `layering` |

- The pre-tool hook no longer refuses a code edit on a 9.0.0 delivery issue for a missing failing test.
- `compass check` passes on less evidence than in 8.x.
- For an issue that owes an added item, `finish` prints one `next:` line for each item, commits nothing and exits 1. Record each item with the older commands, then run the same `finish` again.

### Approvals by a person

- An issue with the label `auth`, `payments`, `personal-data` or `migrations`, or with a label in `signoff_labels`, owes a person's approval of the scenarios before any code edit, and the `G5` sign-off before it lands.
- New: an issue with `critical` risk owes a person's approval of the scenarios before any code edit.
- The session asks with `compass evidence request --checkpoint specify` and stops. Until a person approves, the pre-tool hook refuses a code edit with the code `code-before-approval`.
- An approval records `change_sha256`, a digest of the code and test files of the change. When they change after an approval, `compass check` fails `ship-approval-present`, and `human-approval-present` on an issue with such a label, until a person approves the new state.
- `ship-approval-present` also passes when `compass issue link set --pr <n>` reads the approving review of the merged pull request (ADR-095).

### The red is proved on a base copy

`finish` runs the tests of the change on a copy of the commit the issue started from. They must fail. The red record says `proved_on: base-copy`.

- That record shows that the tests fail without the change. It does not show that a test was written before the code. Only a red recorded earlier with `compass tdd-red` shows that order.
- The copy holds tracked files only, with `node_modules`, `.venv` and `venv` linked in. Name any other untracked path the tests need in the new setting `project.base_copy_links`.
- `docs/base-copy.md` states the limits.

## Removed settings

9.0.0 reads none of these `compass.yml` keys. `compass policy lint` warns about each with `L-SETTING-REMOVED` and names its replacement. `docs/configuration.md` explains each replacement.

- "rewrites it": `compass migrate` deletes the key and writes the replacement.
- "no": `compass migrate` leaves the key and names the edit you must make.

<!-- compass:upgrade-settings-table -->
| Removed key | Replacement | `compass migrate` |
|---|---|---|
| `dimensions` | removed | no |
| `stages` | removed | no |
| `rules` | `require_evidence` | rewrites it |
| `checks` | `project_checks` | rewrites it |
| `gates` | `signoff_labels` or `project_checks` | rewrites it |
| `vocabulary` | removed | no |
| `extends` | removed | no |
| `extends@6` | `acceptance_strategy: {state: off, reason: ...}` | rewrites it |
| `extends@7` | `acceptance_strategy: {state: off, reason: ...}` | rewrites it |
| `extends@8` | removed | rewrites it |
| `preset` | removed | rewrites it |
| `preset_index` | removed | rewrites it |
| `approvers.project-waiver` | removed | rewrites it |
| `models` | removed | rewrites it |
| `multiagent` | removed | rewrites it |
| `living_spec` | removed | rewrites it |
| `artifacts` | removed | rewrites it |
| `approaches` | removed | rewrites it |
| `stages.<id>`: `define`, `refine`, `plan`, `breakdown`, `implement`, `verify` | removed | no |
| `rules.caps` | removed | no |
| `checks.<id>`: `dor-summary-filled`, `dor-problem-traces-up`, `dor-behavior-is-gwt`, `dor-traceability-ids`, `dor-affected-surface-named`, `dor-no-open-questions`, `dor-approach-still-fits` | removed | no |
| `prices` | removed | rewrites it |
| `github_labels` | removed | rewrites it |
| `readiness` | removed | rewrites it |
| `governance_drift` | removed | rewrites it |
| `github_labels.page` | removed | rewrites it |
| `project.<id>`: `build_command`, `lint_command`, `format_check_command`, `typecheck_command`, `secret_scan`, `structured_logging` | removed | rewrites it |
| `rules.floors.rules.RP-FLOOR-002.then.require_phase` | removed | rewrites it |
| `capabilities.artifact-freshness` | removed | no |
| `rules.*.force_minimum_approach` | removed | rewrites it |
| `rules.*.forbid_approach` | removed | rewrites it |
| `rules.*.never_skip` | removed | rewrites it |
<!-- /compass:upgrade-settings-table -->

## Removed slash commands

9.0.0 runs every change on one path through `/compass:go` (ADR-092). A removed slash command has no stub file. `/compass:flow` is still shipped.

<!-- compass:upgrade-slash-table -->
| Removed | Use instead | Decision |
|---|---|---|
| `/compass:define`, `/compass:refine`, `/compass:plan` | the specify stage of `/compass:go` | ADR-092 |
| `/compass:breakdown`, `/compass:implement` | the build stage of `/compass:go` | ADR-092 |
| `/compass:verify` | the ship stage of `/compass:go`, and `/compass:ship` | ADR-092 |
| `/compass:intent`, `/compass:position`, `/compass:design`, `/compass:consult` | nothing: the four role entry points have no replacement | ADR-093 |
<!-- /compass:upgrade-slash-table -->

## Merged skills

`compass:bdd-specification` and `compass:behavior-mapping` are now `compass:atdd`. A project that names either old skill in its `CLAUDE.md` or its lessons must change the name by hand.

## Removed verbs and flags

### What breaks

Each command line below exits 2 with the parse error, and the error adds one line that names the replacement.

<!-- compass:upgrade-commands-table -->
| Removed | Use instead | Decision |
|---|---|---|
| `run` | run the stage in your own session | ADR-090 |
| `issue subtask` | the session builds each unit of the distribution map itself | ADR-090 |
| `profile` | nothing replaces it | ADR-090 |
| `approach show --model` | a stage command passes no model | ADR-090 |
| `approach show --effort` | a stage command passes no effort | ADR-090 |
| `retro --models` | no subtask records a model tier | ADR-090 |
| `analyze` | compass check runs the guardrails; no consistency report replaces it | ADR-091 |
| `issue receipt` | compass approach show lists the issue's gates and compass check judges its evidence | ADR-091 |
| `issue render` | compass check and compass approach show read the records; no block is written | ADR-091 |
| `spec sync` | no living spec is derived, so there is nothing to merge and re-derive | ADR-091 |
| `issue template show` | the one document's template is templates/acceptance-criteria.md | ADR-091 |
| `issue artifact set` | no document is registered or given a status; compass check reads the records | ADR-091 |
| `issue artifact-path` | the one document is docs/compass/<created>-<slug>/acceptance-criteria.md | ADR-091 |
| `evidence approve --artifact` | no document waits for approval; approve a human check with --check | ADR-091 |
| `evidence request --artifact` | no document waits for approval; ask for a human check with --check | ADR-091 |
| `plan lint` | no technical design is written, so there is no plan to scan | ADR-091 |
| `_derive-system-spec` | no living spec is derived; the issue records hold each landed scenario | ADR-091 |
| `intent ingest` | write the Summary and Intent of acceptance-criteria.md from the brief | ADR-093 |
| `retro` | sdd-bench is the measurement; compass check and compass approach show read one issue | ADR-093 |
| `rework-scan` | nothing replaces it | ADR-093 |
| `issue friction` | nothing replaces it | ADR-093 |
| `board` | compass flow lists every issue | ADR-093 |
| `flow --html` | compass flow prints the issues; no page is written | ADR-093 |
| `issue github sync` | compass issue link set keeps the link; no label is written | ADR-093 |
| `readiness` | nothing measures the repository; the hooks and compass check guard each change | ADR-093 |
| `init --readiness` | compass init sets up the project; nothing measures it | ADR-093 |
| `follow-up add --target` | link the follow-up to a GitHub issue with --github | ADR-093 |
| `issue configure` | the issue layer was removed; record a waiver with compass waiver add | ADR-094 |
| `approach evaluate --reset-config` | an issue has no config layer | ADR-094 |
| `policy diff` | one check set ships; compass policy show prints it with its digest | ADR-094 |
| `policy update` | one check set ships with each release; nothing to move between | ADR-094 |
| `preset init` | presets were removed; a project sets tighten-only settings in compass.yml | ADR-094 |
| `preset test` | presets were removed; a project sets tighten-only settings in compass.yml | ADR-094 |
| `preset` | presets were removed; a project sets tighten-only settings in compass.yml | ADR-094 |
| `policy migrate --words` | compass.yml is read as settings only; the upgrade guide names the 9.0.0 settings | ADR-094 |
| `policy migrate --undo` | run it on 8.x before upgrading; the upgrade guide names the 9.0.0 settings | ADR-094 |
| `policy migrate` | run compass policy migrate on 8.x; the upgrade guide names the 9.0.0 settings | ADR-094 |
| `approach evaluate --offline` | git parents were removed; nothing is fetched | ADR-094 |
| `policy lint --offline` | git parents were removed; nothing is fetched | ADR-094 |
| `policy show --offline` | git parents were removed; nothing is fetched | ADR-094 |
| `policy lint --issue` | an issue has no config layer; the classifier was removed | ADR-094 |
| `policy lint --exhaustive` | an issue has no config layer; the classifier was removed | ADR-094 |
<!-- /compass:upgrade-commands-table -->

A removed flag or old name below fails as any unknown one does. The error does not name the replacement.

| Removed | Where | What to do |
|---|---|---|
| `--role` | `quick-fix start` | omit it (ADR-070) |
| `--justify role=` | `approach evaluate --write` | omit it |
| the old British spelling of the reassessment kind `judgment` | `approach evaluate --kind` | type `judgment` |
| the old British spelling of the check id `dor-behavior-is-gwt` | `evidence approve --check`, `evidence request --check`, `evidence review` | nothing: the check is deleted |
| the old British spelling of the refusal code `not-initialized` | the refusal code lookup | type `not-initialized` |
| the size `standard` | `approach evaluate --assessment size=`, `quick-fix start --size` | type `medium` |

The drift report is removed:

- `compass approach evaluate` no longer prints `POLICY DRIFT`.
- `compass policy lint` no longer compares a governance copy with the shipped files.
- `policy lint --json` drops the findings `LEGACY-DRIFT`, `LEGACY-DRIFT-UNCOMPARED`, `LEGACY-WAIVER` and `LEGACY-WAIVED`.

### What changes without breaking

- `compass migrate` is a new verb. 7.0.0 removed the 6.x verb of the same spelling, which ran what is now `compass issue migrate`.
- `compass issue migrate` stays. It still moves a 1.x issue to the 2.0 shape.

## Deleted checks

A stored generation that lists one of these checks reads it as nothing to check, so an archived issue keeps its verdict.

<!-- compass:upgrade-checks-table -->
| Deleted check | Removed in |
|---|---|
| `dashboard-current` | 7.0.0 |
| `multiagent-run-recorded` | 9.0.0 |
| `consistency-check-passes` | 9.0.0 |
| `rendered-blocks-current` | 9.0.0 |
| `artifacts-approved` | 9.0.0 |
| `design-within-word-ceiling` | 9.0.0 |
| `contracts-declared` | 9.0.0 |
| `borrowed-documents-answered` | 9.0.0 |
| `dor-summary-filled` | 9.0.0 |
| `dor-problem-traces-up` | 9.0.0 |
| `dor-behavior-is-gwt` | 9.0.0 |
| `dor-traceability-ids` | 9.0.0 |
| `dor-affected-surface-named` | 9.0.0 |
| `dor-no-open-questions` | 9.0.0 |
| `dor-approach-still-fits` | 9.0.0 |
<!-- /compass:upgrade-checks-table -->

`compass check` refuses with exit 2 and the refusal code `names-deleted-check`, before it runs any row, when one of these names a deleted check:

- a `project_checks` entry of `compass.yml`;
- a list of checks in `compass.yml` (`gates.<id>.checks`, or `stages.<id>.entry` or `exit`);
- a waiver of the issue that is not withdrawn.

The refusal names the edit that clears each item, or `compass waiver withdraw W-<n> --issue <slug>` for a waiver. `compass waiver add` refuses a deleted check, and `compass policy lint` refuses a project check of that id (`L-SETTING-INVALID`). See `docs/waivers.md`.

## Readers that ended and readers that stay

9.0.0 deletes each reader of typed input or of a copied file. It keeps each reader of a stored manifest or generation, so an archived issue reads as it was stored (`governance/decisions/2026-10-25-legacy-readers-readable-until-9-0-0.md`).

| Reader | In 9.0.0 |
|---|---|
| Old names typed on the command line | ended |
| Old words and old approach names in a stored manifest or generation, such as `standard`, `full` and `light` | still read, through 9.x. Each row of the `old_names:` section of `cli/migrate-map.yml` ends at 10.0.0. The renamed manifest values under `values:` have no end release. |
| An 8.x `state.yml` that stores the old British spelling of `initialized` | still read |
| Copied 5.x governance files with no `compass.yml` | ended. Every command that reads the policy refuses the project with exit 2 (`governance-copy-removed`). |
| The generated views `governance/routing-policy.yml` and `governance/guardrails.yml` | ended. 9.0.0 deletes them and their four schema files. `governance/check-set.yml` is the only machine-readable policy. |
| `.compass/config.yml` when `compass.yml` is absent | still read |
| Waivers that the 8.x settings migration wrote | ended (ADR-094) |
| `--justify role=` and `quick-fix start --role` | ended. A stored role reading in an assessment still reads. |
| The pre-tool hook reading `delivery-approach.md` for an issue whose manifest has no `delivery_approach` key | ended. An issue without the key is refused with `no-delivery-approach`. |
| An `extends:` pin of `compass:default@6` or `@7` keeping the acceptance strategy `S17` off | ended. The strategy owes no record unless `require_evidence` adds one of its tokens. |
| The frozen presets `default@6` and `default@7` | ended as shipped files. The artifacts catalog of 8.0.4 stays as `governance/artifacts-8.0.4.yml`. |
| The legacy stage names of an 8.x manifest or a checkpoint outcome | still read (ADR-092) |
| `compass issue migrate` and its 1.x readers | still read |
| A stored generation | still read |

## The record

9.0.0 commits an issue's record with its code by default (ADR-096). `compass ship-commit` stages the issue folder, the documents folder and `.compass/work/.gitignore` in the same commit as the change. `docs/configuration.md` describes `record`.

The record is kept out when:

- `record.commit` is `false`;
- `record.remote` is set and `record.commit` is not;
- git ignores the issue folder (remove those ignore rules to commit the record);
- the project is outside a git repository.
