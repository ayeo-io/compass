# Upgrading to 9.0.0

This page says how to move a project from Compass 8.x to 9.0.0 and keep its evidence. It lists what 9.0.0 removed, what replaces each part, what stays readable and what to do. The decision behind it is `architecture/decisions/ADR-098-compass-migrate-moves-an-8x-project-and-the-legacy-readers-end.md`.

Compass 8.x gets security fixes only, for 90 days after 9.0.0 is released. After that, only 9.x is supported (see "Support" below).

## Before you start

- A project on 6.x or 7.x must upgrade to 8.x first. On 8.x, run `compass policy migrate` to move copied `governance/` files or `.compass/config.yml` into `compass.yml`. 9.0.0 does not have that command.
- Copy `compass.yml`, `.compass/work` and `docs/compass` to a folder outside the project.
- Update every checkout and every installed plugin together.

## Run `compass migrate`

`compass migrate` rewrites `compass.yml` for 9.0.0, then moves each open issue that 8.x assessed onto the 9.0.0 four-stage path: assess, specify, build and ship (ADR-092). Run it from the project root:

```
compass migrate                   # a dry run: lists what it would change, writes nothing
compass migrate --apply           # writes the changes the dry run listed
compass migrate --settings-only   # compass.yml only
compass migrate --issues-only     # the issues only
compass migrate --issue <slug> --apply
```

`--issue` moves one issue and leaves `compass.yml` as it is. The dry run exits 0 when there is nothing to do, 1 when there is, and 2 when it refuses. `cli/compass_pkg/migrate_9.py` holds the command and the issues half; `cli/compass_pkg/migrate_settings.py` holds the settings half.

### What it changes in `compass.yml`

9.0.0 does not read a removed key (ADR-094), so deleting one changes no verdict. `compass migrate` deletes each removed key that `removed_parts.REPLACEMENTS` marks as rewritten (the table under "Removed settings" below), and writes the setting that carries what the key asked for, where one does:

| In `compass.yml` | `compass migrate` writes |
|---|---|
| `extends: compass:default@6` or `@7` | deletes the line and adds `acceptance_strategy: {state: off, reason: ...}`, so the acceptance strategy `S17` stays off as the pin kept it. A file that already sets `acceptance_strategy` keeps its value. |
| `extends: compass:default@8` or later | deletes the line |
| the labels `gates.G5` adds to `when.labels_any` | `signoff_labels:` with those labels |
| a rule whose effect is `add_gate`, for a gate that has an evidence token | a `require_evidence:` entry with the rule's `when` and the token |
| a check with `impl: command-passes` and the guardrail gate that lists it | a `project_checks:` entry with the gate's name and `when`, and the check's command. The gate's stage maps to its path stage; a specify stage runs at build, the earliest stage a project check runs at. |
| the agent review block (`checks.agent-review` and its `stages.ship` entry) | `agent_review: on`, unless the file sets `agent_review` |
| `approvers.issue-waiver`, with no `approvers.waiver` | renamed `approvers.waiver` |
| `approvers.project-waiver`, the removed `project.*` fields and every other key the table marks | deleted |

Each part of a deleted key that no setting carries, such as an `add_gate` of `verify.analyze` or a rule that forces an approach, is listed under "settings not carried over".

A key the table marks as not rewritten, such as `dimensions` or a legacy stage under `stages:`, is left in the file and listed under "settings left for you to edit" with the edit. A rewritten key that holds one is left whole: `rules:` with a `caps` rule set is left, and the line says to delete `rules.caps` and run `compass migrate` again.

How the file is written:

- It is a line edit, not a YAML dump, so the file's comments stay. A deleted key goes with its indented lines and the comment block directly above it. A key one level down, such as `project.build_command`, goes the same way.
- The new settings go at the end, under one comment line that names `compass migrate`.
- The dry run prints the diff.
- Before it writes, the edited text must parse to the settings the change list names, and `compass policy lint` must find no error and no removed key except the ones left for you. If either fails, nothing is written to `compass.yml`, the run exits 2, and the output names the lines to edit.

`compass migrate` rewrites `compass.yml` only. A project with only `.compass/config.yml` keeps that file, because 9.0.0 still reads it (ADR-098 open question 5).

### What it changes in an issue

For each open issue that holds a `delivery_approach` and no `evidence_required`:

- It runs the same write as `compass approach evaluate --write --reason "compass migrate to 9.0.0"`. The issue gets the evidence it owes (`evidence_required`), the gates derived from it, the checkpoints and a new stored generation from the check set. Each gate keeps the state it held; a new gate starts at pending.
- It adds a `reassessments:` entry of kind `policy-correction` with the reason `compass migrate to 9.0.0`. It asks for no justification of an assessed value, because it writes the assessment the issue already holds.
- It moves the 8.x record that no 9.0.0 reader of a path issue uses under the manifest's `legacy:` key. No check reads `legacy:`.

  | Key in 8.x | Under `legacy:` |
  |---|---|
  | `stages`, `subtask_ceiling`, `orchestration`, `max_worktrees` | the same names |
  | `subtasks`, `models`, `page_ticks`, `readiness` | the same names |
  | each `artifacts:` entry that is not the acceptance criteria | `documents` |
  | the fields of the acceptance-criteria entry other than `id`, `kind`, `path`, `reason` and `status` | `artifact_status`, by the entry's id |
  | a legacy stage in `depends_on[].until` or `raised_by.found_at` | `stage_values`, by where it was; the key gets the path stage |

  The acceptance-criteria entry stays in `artifacts:`, so Compass still finds the spec.
- It writes `request.link` from a linked GitHub issue when the link is missing.
- It writes `trail.md` again when the issue has one, so its sum lines match the new manifest.

The scenarios, the evidence registry, the gates, `checkpoint_outcomes`, `delegations_used`, `waivers`, `changed_files`, the landing fields, `github`, `follow_ups`, `friction`, `reassessments`, `depends_on` and `raised_by` stay where they are.

### Where each issue lands

The stage follows the records, as on every path issue. The report prints the 8.x stage, the path stage and, when the records place the issue earlier, the reason.

| 8.x stage | Path stage |
|---|---|
| `define`, `refine`, `plan` | specify |
| `breakdown`, `implement` | build |
| `verify`, `ship` | ship, when each scenario has a red before its green; otherwise build, and the report names the scenario |

An issue can land earlier than this table when its records say so. For example, a scenario with no declared test, or a listed `specify` checkpoint with no outcome, keeps the issue at specify. `compass migrate` writes no red, green or outcome to move an issue.

### What it never does

- It writes no approval, no checkpoint outcome and no delegation copy.
- It writes no file under `evidence/`, no `.red` or `.acceptance` marker, nothing under `approval-requests/` and no `scenario_freeze`. `sha256sum -c` over `evidence/SHA256SUMS` passes after it as before.
- It does not change a closed issue, an issue already on the path, or an issue that was never assessed. The report lists each with the reason.

### The request link

9.0.0 asks each issue who requested it and where (`request`, ADR-096). `compass migrate` does not prompt. It lists each converted issue with no requester, with the command that records it:

```
compass issue link set --issue <slug> --request <url> --requester <name>
```

To record it in the same run, give `--request` and `--requester` with `--issue`:

```
compass migrate --issue <slug> --apply --request owner/repo#12 --requester "Dana Smith"
```

The check `request-recorded` fails until both parts are on record.

### What it refuses

It refuses with exit 2, before it writes anything:

- a project with a copy of `governance/routing-policy.yml` or `governance/guardrails.yml` and no `compass.yml` (`governance-copy-removed`). On Compass 8.x, run `compass policy migrate` to write `compass.yml`, then run `compass migrate` again.
- a `compass.yml` whose `extends:` names a git parent (`git-parent-removed`). Move the checks the parent adds into the settings of `compass.yml`, delete `extends:`, then run `compass migrate` again.

It refuses one issue, and lists it under "refused", when the issue has a 1.x manifest (run `compass issue migrate --apply` first) or a stored generation that is not whole.

### What to do

1. Copy `compass.yml`, `.compass/work` and `docs/compass` outside the project.
2. Run `compass migrate` and read the list and the diff.
3. Run `compass migrate --apply`.
4. Make each edit listed under "settings left for you to edit", then run `compass migrate` again.
5. Run each `compass issue link set` command the report lists.

## Removed settings

9.0.0 reads none of these `compass.yml` keys. Each stays valid YAML, and `compass policy lint` warns about each with `L-SETTING-REMOVED` and names its replacement. "rewrites it" means `compass migrate` deletes the key and writes the replacement for you. "no" means you edit the file: `compass migrate` leaves the key and names the edit. `docs/configuration.md` explains each replacement setting.

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

9.0.0 runs every change on one path, assess, specify, build and ship, through `/compass:go` (ADR-092). A removed slash command has no stub file. `/compass:flow` is still shipped.

<!-- compass:upgrade-slash-table -->
| Removed | Use instead | Decision |
|---|---|---|
| `/compass:define`, `/compass:refine`, `/compass:plan` | the specify stage of `/compass:go` | ADR-092 |
| `/compass:breakdown`, `/compass:implement` | the build stage of `/compass:go` | ADR-092 |
| `/compass:verify` | the ship stage of `/compass:go`, and `/compass:ship` | ADR-092 |
| `/compass:intent`, `/compass:position`, `/compass:design`, `/compass:consult` | nothing: the four role entry points have no replacement | ADR-093 |
<!-- /compass:upgrade-slash-table -->

## Merged skills

`compass:bdd-specification` and `compass:behavior-mapping` are now `compass:atdd`. The `atdd` skill holds the scenario rules, behavior mapping and the four-layer acceptance tests. A project that names either old skill in its `CLAUDE.md` or its lessons must change the name by hand. The check set's rules `RP-FLOOR-002` and `RP-ADV-002` name `atdd`.

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

These parts also changed in 9.0.0. A removed flag or old name fails as any unknown one does, with no line that names the replacement:

- `quick-fix start --role`. Role is not an assessment dimension (ADR-070), so argparse refuses the flag.
- `--justify role=` on `approach evaluate --write`. It is refused as a dimension that needs no justification.
- The old British spelling of the reassessment kind `judgment` in `approach evaluate --kind`.
- The old British spelling of the check id `dor-behavior-is-gwt`, given to `evidence approve --check`, `evidence request --check` or `evidence review`.
- The old British spelling of the refusal code `not-initialized`, given to the refusal code lookup.
- The old size `standard`, given to `approach evaluate --assessment size=` or `quick-fix start --size`. Type `medium`. A manifest or stored generation that holds `standard` still reads it as `medium`.
- The drift report. `compass approach evaluate` no longer prints `POLICY DRIFT`, and `compass policy lint` no longer compares a governance copy with the shipped files. `policy lint --json` drops the findings `LEGACY-DRIFT`, `LEGACY-DRIFT-UNCOMPARED`, `LEGACY-WAIVER` and `LEGACY-WAIVED`. The `governance_drift` setting is removed (see "Removed settings").

### What changes without breaking

- `compass migrate` is a new verb. In 6.x the same spelling ran what is now `compass issue migrate`, and 7.0.0 removed that spelling. 9.0.0 uses the name for the move from 8.x (ADR-098 open question 18).
- `compass issue migrate` stays. It still moves a 1.x issue to the 2.0 shape.

## Deleted checks

A stored generation that lists one of these checks still reads it as nothing to check, so an archived issue keeps its verdict. A setting or a waiver that names one is different: it asks for a check that never runs.

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

`compass check` refuses with exit 2 and the refusal code `names-deleted-check`, before it runs any row, when:

- a `project_checks` entry of `compass.yml` has the id of a deleted check;
- a list of checks in `compass.yml` (`gates.<id>.checks`, or `stages.<id>.entry` or `exit`) names one;
- a waiver of the issue that is not withdrawn names one.

The refusal names each item with the edit that clears it, or `compass waiver withdraw W-<n> --issue <slug>` for a waiver. `compass waiver add` refuses a deleted check, and `compass policy lint` refuses a project check of that id (`L-SETTING-INVALID`). `docs/waivers.md` has the details.

## Readers that ended and readers that stay

7.0.0 kept seven readers of old forms until 9.0.0 (`governance/decisions/2026-10-25-legacy-readers-readable-until-9-0-0.md`). 9.0.0 deletes each reader of typed input or of a copied file. It keeps each reader of a stored manifest or generation, so an archived issue reads as it was stored. After each deletion, a run of `compass check` over this repository's 622 archived issues showed 0 verdict changes.

| Reader | In 9.0.0 |
|---|---|
| Old names typed on the command line | ended for the reassessment kind, the check id, the refusal code and the size `standard` (see "Removed verbs and flags"). Typed input takes only the 9.0.0 names. |
| Old words and old approach names in a stored manifest or generation | still read, through 9.x. 616 archived 8.x manifests and 73 archived stored generations hold them, so `compass issue migrate`, the manifest loader and the generation loader read `standard`, `full`, `light`, the old approach names, the old check id, the old skill name and the other renamed manifest values. An 8.x `state.yml` that stores the old British spelling of `initialized` still reads. Each row of the `old_names:` section of `cli/migrate-map.yml` ends at 10.0.0; the renamed manifest values under `values:` have no end release. |
| Copied 5.x governance files with no `compass.yml` | ended. Every command that reads the policy refuses the project with exit 2 (`governance-copy-removed`). On Compass 8.x, run `compass policy migrate` to write `compass.yml` first. |
| The generated views `governance/routing-policy.yml` and `governance/guardrails.yml` | ended. 9.0.0 deletes them and their four schema files. The check set, `governance/check-set.yml`, is the only machine-readable policy. |
| `.compass/config.yml` when `compass.yml` is absent | still read. `compass migrate` rewrites `compass.yml` only. |
| Waivers that the 8.x settings migration wrote | ended with the configuration layers that held them (ADR-094). |
| `--justify role=` and `quick-fix start --role` | ended. A stored role reading in an assessment still reads. |
| The pre-tool hook reading `delivery-approach.md` for an issue whose manifest has no `delivery_approach` key | ended. The key alone decides, and an issue without it is refused with `no-delivery-approach`. No archived issue holds the document without the key. |
| The frozen presets `default@6` and `default@7` | ended as shipped files. Resolution reads only the check set, whatever major `extends:` names. The artifacts catalog 8.0.4 shipped stays as `governance/artifacts-8.0.4.yml`, because a stored 8.x generation, `compass issue migrate` and the `nfr-rows-resolved` check read it. |

These readers were never on that list, and they stay:

- The legacy stage names of an 8.x manifest, and their map to the path stages (ADR-092). Every 8.x manifest needs them.
- `compass issue migrate` and its 1.x readers. A 6.x project runs them through 8.x.
- The reader of a stored generation, so every archived issue is judged by what it was assessed against.
- The legacy stage names of a checkpoint outcome, so an old outcome still reads.

## Not yet settled

ADR-098 is proposed. One part waits for the owner's decision: when the `extends:` pin of `compass:default@6` or `@7` stops keeping the acceptance strategy `S17` off for a project that did not run `compass migrate` (open question 6). Until then it stays as 8.x left it, and it changes no archived verdict.

## The record

9.0.0 commits an issue's record with its code by default (ADR-096). `compass ship-commit` stages the issue folder, the documents folder and `.compass/work/.gitignore` in the same commit as the change. The record is kept out when `record.commit` is `false`, when `record.remote` is set and `record.commit` is not, when git ignores the issue folder, or outside a git repository. A project whose git ignore rules cover its issue folders stays kept out until it removes those rules. `docs/configuration.md` describes `record`.

## Support

Compass 8.x gets security fixes only, for 90 days after 9.0.0 is released. After that, only 9.x is supported. `SECURITY.md` says how to report a vulnerability.
