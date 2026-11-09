---
id: ADR-094
title: Compass runs one fixed check set
status: proposed
date: 2026-11-06
supersedes: ''
superseded_by: ''
---

## Context

Compass 9.0.0 is an ATDD framework with a proof trail (ayeo-io/compass-delivery#357 [Replace configuration layers and presets with one fixed check set], under #345 [Reposition Compass 9.0.0 as an ATDD framework with a proof trail]). Decision 7 of #345 binds this change:

> One fixed set of checks. A waiver needs a reason and an approver. `compass.yml` settings can only tighten the set. The configuration layers and presets are deleted. Each issue keeps a digest of the policy in force.

Three more points of #345 bind it:

- its "What stays" list: the guardrails, the hooks and fail-closed behavior, typed evidence, digests and the manifest, approvals, delegations and the safety contract;
- decision 10: "The digest format changes in 9.0.0";
- decision 6: a project can turn the agent review on as advisory evidence. ADR-090 decision 7 built that as a `compass.yml` catalogue block, which this change removes, so the agent review needs a setting of its own.

Before 9.0.0 a project's policy was the result of a configuration chain:

- a shipped preset in `governance/presets/default/` (ADR-042), named by `extends: compass:default@<n>`;
- an optional git parent, `extends: github:<owner>/<repo>@<ref>#<sha>` (ADR-043, `docs/git-parents.md`);
- the project layer in `compass.yml`, with the entry operations `set`, `replace` and `remove` (ADR-010, ADR-035);
- an issue layer in the manifest's `config:`, written by `compass issue configure`;
- locks and unlocks on catalogue entries, and waivers written inside the entries (ADR-039);
- a classifier that compared each layer with its parent over the assessment grid (ADR-037, ADR-073);
- the verbs that managed the chain: `compass policy diff`, `policy update`, `preset init`, `preset test` and `policy migrate`;
- `governance/guardrails.yml` and `governance/routing-policy.yml`, generated from the preset as views for old readers (ADR-042);
- `governance/signals.yml`, the scope-bloat phrases of the stop hook.

The modules that held this are about 8,100 CLI lines in 18 whole modules, and 32 test files. A reviewer of one change cannot name the rules it ran under without resolving the chain, and an auditor cannot name them by one file and one digest.

The archive must stay readable. The main checkout holds 616 manifests. 162 hold a stored generation (112 on `compass:default@6`, 49 on `@7`, 1 on `@8`), and no generation names a git parent. 454 have no `generation:` key and read the live policy. No stored generation holds a waiver. No archived issue may go from pass to fail.

## Decision

1. **One check set ships, in one file.** A new file in `governance/`, the check set, with `id: compass-checks` and a `version`, holds the shipped default as it is at 9.0.0, less the two empty catalogues (`artifacts`, `readiness`):
   - the 16 gates (the guardrails `G1` to `G5`, `S1`, `S2`, the eight review gates and `spike.conclude`), each with its `stage`, `checks`, `accepts`, `applies_to` and `when`;
   - the 32 checks: 25 deterministic checks with their `impl`, `severity`, `on_skipped` and `blocking_when`, and the 7 human items of the Definition of Done;
   - the 16 evidence types, the six dimensions, the four path stages with the build exit list and the spike's modes, the approaches `delivery` and `spike`, the rules (`default_shapes`, `floors`, `loop_ceilings`, `immovable_gates`, `advisory`, `biases`), the display names and `capabilities: {entry-exit-evaluation: false}`;
   - `never_waived: [checks.human-approval-present, gates.G5]`, from the 8.x hard locks;
   - one optional entry, the judged check `agent-review` (ADR-090 decision 7), off unless a project sets `agent_review: on`.

   Entries carry no `locked:` field: only a tighten-only setting changes an entry.
2. **The version names the release that last changed the set.** It starts at `9.0.0`. A change that makes a check owe less, or removes a check, raises the major. A change that adds or tightens raises the minor. Each check implementation keeps its own version (ADR-038). A new digest fixture pins the file's sha256 for each version, and a new test fails when the bytes change and the pin does not. Like `tests/fixtures/preset-digests.yml`, it is not an owner pin: the change that edits the set repins it.
3. **One loader reads the set.** A new module, the `check_set` module, loads the file, checks its shape and returns the resolved mapping in the shape a generation's `resolved.yml` holds now. The read path of `compass check` does not change: it asks `effective.view_or_legacy`, and `EffectiveView` gives the gates. Every project with a `compass.yml`, and every project with no configuration, the framework's own repository included, reads the check set. Only a project with copied governance and no `compass.yml` reads its copy, through `legacy_adapter.adapt`.
4. **Each issue records the policy in force.** Each generation commit writes a `policy:` block into the manifest:

   ```yaml
   policy:
     check_set: compass-checks@9.0.0
     check_set_sha256: 3f1c...   # sha256sum of the check set file in that release
     settings_sha256: 9ab0...    # sha256sum of compass.yml at commit; null without one
     tightened:                  # the tighten-only settings applied, as written
       signoff_labels: [billing]
     resolved: sha256:5d2e...    # equals the generation marker's digest of resolved.yml
   ```

   The two `*_sha256` values are lowercase hex as `sha256sum` prints it, the form evidence digests use since #348 [Make evidence digests checkable with sha256sum]. `tightened` makes the record readable without the history of `compass.yml`. `schemas/manifest.schema.json` adds `policy`, and a manifest without it stays valid. #356 [Commit the issue record with the code and add trail.md] keeps generation folders out of the commit, so the manifest copy is the one a reviewer reads. `compass check` prints one line, `Policy: compass-checks@9.0.0 (sha256 3f1c...)`, with the tightenings and the approved waivers.
5. **The generation store stays.** A generation is still the stored copy of the policy an issue runs against (ADR-036), with the same `resolved.yml` shape. `generation.RESOLVER_VERSION` goes from `1.0.0` to `1.1.0`. A new major would refuse every open issue whose generation names the old one, and the stored shape does not change. `versions.yml` keeps its keys; its first parent becomes the check set, with `source: shipped`.
6. **`compass.yml` keeps its settings.** `schema`, `owner`, `approvers`, `autonomy`, `adoption`, `allow_project_commands`, `enforcement`, `record`, `project`, `language`, `governance_drift` and `acceptance_strategy` stay as they are. Two of them can make a project owe less, and stay because an owner decided them: `acceptance_strategy: {state: off, reason: ...}` turns `S17` off (decision `governance/decisions/2026-10-30-the-strategy-follows-the-pinned-major-and-the-settings-key.md`), and `adoption: advisory` sets the exit code of `compass check`, not the set.
7. **Five settings can tighten the set, and nothing can loosen it.**

   | Key | Value | What it adds | Replaces in 8.x |
   |---|---|---|---|
   | `signoff_labels` | a list of label names | Each label also owes `G5` sign-off and scenario approval, as the four shipped labels do | A `set:` on `gates.G5.when.labels_any` |
   | `require_evidence` | a list of `{when: <assessment clause>, add: [tokens]}` | Evidence tokens of the closed set `evidence_required.TOKENS`, for assessments that match | An `add_gate` floor in `rules:` |
   | `agent_review` | `on` | The advisory judged check `agent-review` at ship | The `checks:` and `stages:` block of `docs/judged-checks.md` |
   | `project_checks` | a list of `{id, name, command, stage, when}`, `stage` being `build` or `ship` | A `command-passes` check, run only with `allow_project_commands: true` | A project guardrail with `check: command-passes` |
   | `capabilities` | `{entry-exit-evaluation: true}` | Evaluation of the Definition of Done items | The same key |

   Three things hold the rule:
   - construction: the function that applies the settings only unions lists, adds entries and switches a capability or the agent review on. No code path removes an entry, lowers a severity or narrows a `when`;
   - lint: `compass policy lint` lints `compass.yml` as a settings file. It refuses an unknown key, a token outside `TOKENS`, a project check id that matches a shipped id, a stage other than `build` or `ship`, and a capability other than `entry-exit-evaluation`. It keeps the integrity rule of safety-contract guarantee 2: every check names an implementation the CLI holds;
   - a test: each key is applied on every point of the contract 1 grid (1,200 points) and every subset of the labels, and the gates, checks and evidence tokens after must be a superset of those before, with no severity lower.

   `evidence_required.G5_LABELS` stops being a constant, because `signoff_labels` adds to it.
8. **A waiver excuses one check on one issue, with a reason and a person's approval.**
   - `compass waiver add --issue <slug> --check <id> --reason "..."` writes `waivers: [{id: W-1, check, reason, requested_at, requested_by}]` into the manifest. `compass waiver withdraw W-1` removes an unapproved waiver and marks an approved one withdrawn.
   - `waiver add` refuses a check in `never_waived`, a check the issue's policy does not hold, and an empty reason.
   - The approval is a `human-approval` record with `waiver: W-1`. `approval_records.SUBJECT_KEYS` already lists `waiver`, so the record never clears `G5`.
   - A person approves by typing `/compass:approve waiver W-1` in Claude Code, or with `compass evidence approve --waiver W-1` at a terminal. An agent asks with `compass evidence request --waiver W-1` and stops. `/compass:reject <record id>` withdraws the approval.
   - A delegation covers waivers only when typed with `--for waivers`, as `g5` is covered only when typed. A waiver lowers what the issue owes, so the default forms do not cover it.
   - The approvers are the names in `approvers.waiver`, else the project's `owner`. No `owner` means nobody can approve (`W-NO-OWNER`). `approvers.issue-waiver` is read as `approvers.waiver`.
   - In `compass check`, an approved, unwithdrawn waiver turns its check's row into `waived`, with the reason, the approver and the record id. A waived row is not a failure and is counted apart. An unapproved waiver changes nothing, and a notice names the request command.
   - There is no project-wide waiver.
9. **The configuration chain is deleted.** These go: the merge, git parents and their states, the issue layer and `compass issue configure`, the preview of a proposal, locks and unlocks, the classifier with `CLASSIFIER_VERSION`, the layer lint and the field schema generator, `compass policy diff`, `policy update`, `preset init`, `preset test` and `compass policy migrate` with `--words` and `--undo`. In `cli/compass_pkg/layers.py`, `find_project_root` moves to `cli/compass_pkg/project_settings.py`, and only `PROJECT_FILE` and `layer_digest` stay. `cli/compass_pkg/catalogue_spec.py` is cut to the constants kept readers use. `cli/compass_pkg/waivers.py` keeps the approver list with the owner fallback and the record check, and loses everything that derives a waiver from a catalogue operation. `docs/git-parents.md`, `docs/policy-diff.md`, `docs/policy-update.md`, `docs/policy-test.md`, `docs/policy-migrate.md` and `docs/issue-configure.md` go. `docs/waivers-and-locks.md` becomes a page on waivers alone.
10. **`compass policy show` and `compass policy lint` stay, rewritten.** `show` prints the check set, its digest, the tightenings and, with `--issue`, the issue's `policy:` block and waivers. `lint` runs the settings lint of decision 7 for a project with a `compass.yml`, and the legacy lint otherwise. Both keep exit codes 0, 1 and 2, because the release scripts, the `Makefile` and CI run `lint`. `schemas/compass.schema.json` shrinks to the settings keys.
11. **Removed settings warn, and a git parent is refused.** `cli/compass_pkg/removed_parts.py` names each removed key with ADR-094 and the reason "Compass runs one fixed set of checks". `compass policy lint` warns with `L-SETTING-REMOVED`, and the file is read without the key:
    - the catalogue keys `dimensions`, `stages`, `approaches`, `rules`, `checks`, `gates` and `vocabulary`, with every entry operation inside them (`set`, `replace`, `remove`, `locked`, `unlock`, `waiver`). `artifacts` and `readiness` keep their ADR-091 and ADR-093 lines;
    - `extends: compass:default@<n>`, which replaces `L-EXTENDS-FROZEN-MAJOR`. `acceptance_strategy.pinned_below` still reads it, so a project pinned at `@6` or `@7` stays out of `S17` until #359 [Add compass migrate and the 9.0.0 upgrade guide];
    - `preset`, `preset_index` and `approvers.project-waiver`.

    `extends: github:...` is an error, `L-PARENT-REMOVED`, and every command that resolves a policy refuses with exit 2. A manifest's `config:` stays valid in the schema, is not read for a new issue, and `compass issue lint` warns on it.
12. **Removed verbs and flags fail with one line.** Each goes into `removed_parts.COMMANDS`, so a command line that names it fails to parse with a line that names ADR-094 and what to do instead:

    | Tokens | Instead |
    |---|---|
    | `policy diff` | one check set ships; compass policy show prints it with its digest |
    | `policy update` | one check set ships with each release; nothing to move between |
    | `preset`, `preset init`, `preset test` | presets were removed; a project sets tighten-only settings in compass.yml |
    | `issue configure` | the issue layer was removed; record a waiver with compass waiver add |
    | `approach evaluate --reset-config` | an issue has no config layer |
    | `approach evaluate --offline`, `policy lint --offline`, `policy show --offline` | git parents were removed; nothing is fetched |
    | `policy lint --issue`, `policy lint --exhaustive` | an issue has no config layer; the classifier was removed |
    | `policy migrate` | run compass policy migrate on 8.x; the upgrade guide names the 9.0.0 settings |
    | `policy migrate --words` | compass.yml is read as settings only; the upgrade guide names the 9.0.0 settings |
    | `policy migrate --undo` | run it on 8.x before upgrading; the upgrade guide names the 9.0.0 settings |

    The contract 4 corpus (`tests/fixtures/compat/contract-4-commands.yml`) and its digest do not change. Its entries for the removed verbs move to `REMOVED_IN_9_0_0` in `tests/compat_commands.py`. `policy-effective-shipped` and `policy-lint-git-parent-no-sha` move to `PHRASE_CHANGED_IN_9_0_0`, and `evidence-review-recorded` moves to `EXIT_CHANGED_IN_9_0_0` (exit 0 to 2), because no judged check named `design-review` can be added through `compass.yml`.
13. **The data old issues read stays.** These stay unchanged:
    - the frozen presets `governance/presets/default@6/` and `default@7/`, as data for `artifact_kinds`, `terminology_cmd`, `readiness_registry` and the compatibility tests. No new frozen copy is made for 9.0.0, because a stored generation holds its own resolved policy;
    - `governance/guardrails.yml` and `governance/routing-policy.yml`, byte for byte except one banner line that says they are frozen. Nothing generates them, and only the legacy readers read them until #359;
    - `legacy_adapter.adapt`, for a project with copied governance and no `compass.yml`;
    - `generation.load`, the retired-word tables it reads through, the major refusal and `compass issue migrate --config`.

    `governance/presets/default/` is deleted when nothing reads it. `governance/signals.yml` and its schema go: the six scope-bloat phrases move into `hooks/py/stop_scan.py`, and a project's own copy is no longer read.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| Keep the layers, and let lint refuse any layer that loosens | Less code to delete, and an 8.x `compass.yml` keeps working | The merge, the classifier and the locks stay, and the rules of one change still need the chain to name them; decision 7 of #345 deletes the layers |
| Keep presets as named sets a project picks | A team can ship a stricter set | A pick is a second source of rules; the five tighten-only settings carry what the layers were used for, and the issue's `policy:` block names the result |
| Refuse every old catalogue key | A project sees at once that its file holds a removed setting | ADR-091 and ADR-092 warned and dropped their keys, and #359 rewrites the file; a refusal would stop every 8.x project at its first 9.0.0 command |
| Warn on a git parent and drop it, as the #351 build did for its removed settings | One rule for every removed key | A team parent can hold checks the team added. Dropping it lowers what each project owes, and the project's own file does not show the change |
| Drop `extends: compass:default@6` now, with no `S17` effect | One less reader of a removed key | It reverses the owner decision of 2026-10-30 for every pinned project, this repository included, before #359 gives them `acceptance_strategy: off` |
| Store the digest only in the generation folder | The marker already holds it | #356 keeps generation folders out of the commit, so a reviewer of the change would not see it |
| Keep project-wide waivers | A project can excuse a check once for every issue | It lowers what every issue owes with one edit; `acceptance_strategy: off`, with a reason, stays the one project-wide opt-out |
| Keep `compass policy migrate` until #359 | A 6.x or 7.x project can upgrade in one step | Its output is a catalogue overlay that 9.0.0 drops, and keeping it keeps the classifier, the merge and the old lint; `v9` is not released, so no user meets the gap |
| Raise the resolver to `2.0.0` | The policy source changed | A new major refuses every open issue whose generation names `1.x`, and the stored shape does not change |
| Make a frozen `default@9` copy next to `@6` and `@7` | The same pattern as earlier majors | The check set file is the single copy, pinned by its digest, and each generation holds its own resolved policy |

## Consequences

What breaks for a user:

- A `compass.yml` that sets a catalogue key, `extends: compass:default@<n>`, `preset`, `preset_index` or `approvers.project-waiver` gets an `L-SETTING-REMOVED` warning, and the key has no effect. Tightenings written as catalogue entries (an `add_gate` floor, a project guardrail, a `G5` label, the agent review block) are dropped with the rest until the project moves them into the five settings. This is the main risk of the change: a project that tightened through the catalogue owes less until it moves those settings, and only its lint says so. #359's `compass migrate` rewrites them.
- A project that extends a git parent stops: every command that resolves a policy exits 2 until the parent's checks move into the project's settings.
- `compass policy diff`, `policy update`, `preset init`, `preset test`, `policy migrate` and `compass issue configure` fail to parse, with a line naming ADR-094. A 6.x or 7.x project upgrades through 8.x, runs `compass policy migrate` there, then `compass migrate`.
- A per-issue `config:` has no effect on a new issue. A departure for one issue is a waiver, which a person must approve.
- `compass policy show` prints `compass-checks@9.0.0` and a digest, not `default@8.0.0` and a layer chain. `compass check` and `compass approach show` print no conformance or parent lines.
- A delegation must be typed with `--for waivers` to approve a waiver.
- The 18 deleted modules, the classifier pins and 32 test files go. The governance decisions on the merge, locks, parents, the policy diff, pins and the preset flag stay in the ledger as history, because the ledger is never edited: `2026-10-05-one-merge-grammar`, `2026-10-05-floors-win-over-the-issue-layer`, `2026-10-06-locks-allow-tightening-and-g5-is-hard` (its `G5` half stays true as `never_waived`), `2026-10-06-parent-waivers-count-as-applied`, `2026-10-06-set-on-a-map-is-key-by-key`, `2026-10-06-policy-diff-has-an-exit-code-flag`, `2026-10-06-lint-rechecks-a-hand-edited-pin`, `2026-10-06-the-preset-flag-is-not-on-compass-init` and `2026-10-06-default-6-x-never-changes-a-6-0-value`.

What old issues keep:

- Each verdict. The 162 issues with a generation read their stored generation, as now. The 454 without one read the check set, and their verdicts hold because the check set resolves to the same gates as the live preset does now; a parity test checks that before the preset is deleted. An archived issue keeps its verdict or moves from fail to pass, never from pass to fail.
- Their keys. `config:` and `generation:` stay valid, and `policy:` and `waivers:` are optional.
- Contracts 1 to 5. Configuration B (`extends: compass:default@6`) gets the warning and the verdicts of configuration A. Configuration C (copied 5.6.0 governance) runs through the legacy adapter. `tests/fixtures/frozen-digests.yml` and the contract 4 corpus do not change.

How the decisions taken while #351 and #354 were built change:

- **A frozen major resolves to the live preset.** ADR-092's As built section records that `extends: compass:default@6` or `@7` loads the live preset with `L-EXTENDS-FROZEN-MAJOR`. The outcome holds: every project runs the one check set. The key becomes a removed setting, and `L-SETTING-REMOVED` replaces `L-EXTENDS-FROZEN-MAJOR`. Its one remaining effect, keeping a pinned project out of `S17`, stays until #359. Contracts 1 and 2 under configuration B keep reading the 8.0.4 governance copy.
- **An issue layer drops what the configuration below it lacks.** The #351 build dropped a legacy stage, an approach pick and a removed Definition of Ready check from an issue layer. These no longer apply: there is no issue layer. A new issue's `config:` is not read, and an old issue's generation keeps what it stored. The tests that held those drops are deleted with the issue layer. The contract 4 entry `issue-configure-refused-proposal-exits-1` leaves `EXIT_CHANGED_IN_9_0_0` for `REMOVED_IN_9_0_0`, so ADR-092 open question 17 has no subject.
- **A git parent's removed settings are dropped, as a project layer's are.** This is replaced: a git parent is refused as an error (decision 11).
- **A project rule that forces an approach is dropped.** This no longer applies: the whole `rules:` key is dropped, so no effect inside it needs a rule. The functions that drop or map entries inside a layer go. `L-STAGE-MAPPED` stays only for the legacy adapter's copies.

For the owner:

- This repository's `compass.yml` sets `extends: compass:default@6`, so `compass policy lint` warns once the check set is the resolver's source. Open question 7 decides whether `S17` stays off for this repository.
- `CLAUDE.md` names `compass policy migrate`, and says `governance/routing-policy.yml` and `governance/guardrails.yml` are what the CLI runs and what `compass check` runs. An agent does not edit `CLAUDE.md`, so the owner must change these lines.

Superseded in part, when this record is accepted: ADR-010 (layers over defaults), ADR-033 (the classifier and lock mechanisms, and project catalogue additions), ADR-035 (`extends:`, floors over the issue layer, locks and waivers), ADR-037 (the classifier), ADR-039 (locks, unlocks and waivers in entries), ADR-042 (the preset directory and the generated views), ADR-043 (git parent pins) and ADR-073 (the list-parameter classification). Their `superseded_by` fields, and this record's `supersedes`, are set when the owner accepts it.

### As built

These decisions were taken while #357 was built. The decisions above hold them; each point says how the build differs from, or adds to, the first text of this record (commit d87b532f). Every point keeps the rule that a setting can only add to what an issue owes.

- Decisions 1 to 3 are built as written: `governance/check-set.yml` is `compass-checks@9.0.0`, with 16 gates, 32 checks (25 deterministic, 7 human), 16 evidence types, `never_waived` and the optional agent review (commit 4c6c38a4). The `check_set` module has `load`, `sha256`, `ref`, `resolved` and `shared`. Decision 3 did not say how often the file is parsed. Every resolution reads it, and `compass flow` resolves every issue, so a board of 345 issues took 9.0 s, not 0.54 s. `load` now parses the file once per path, modification time and size and returns a copy, and the board takes 0.43 s (commit c845d6f3).
- Decision 4 did not settle four details (commit 9e539e50):
  - a reassess that commits nothing still writes the `policy:` block, for the generation in force;
  - `compass issue migrate --config` writes no block, because it keeps a configuration the check set did not resolve;
  - a project read from its own governance copy writes `check_set: legacy` and a null `check_set_sha256`;
  - the `Policy:` line of `compass check` shows the full sha256, taken from the manifest's block for an issue with a stored generation. An issue committed before 9.0.0 has no block and gets no line. `versions.yml` `project.digest` is the digest of the tighten-only settings applied.
- Decision 7 named one function that applies the settings. It is `tighten.apply`, in a module of its own, `cli/compass_pkg/tighten.py`, and the lint is `cli/compass_pkg/settings_lint.py` (commit f4aca9cf). The shapes the record did not give:
  - a label in `signoff_labels` owes all that a `G5` label owes: the standard evidence row, `architecture`, `scenario-approval` and `human-approval`. Exploration on such a label is refused;
  - a `require_evidence` rule does not reach a spike, which ships nothing, and fires as `RP-SETTING-<n>` in file order;
  - `agent_review: off` and `capabilities: {entry-exit-evaluation: false}` are accepted and change nothing. YAML reads an unquoted `on` as `true`, so `true` and `false` are accepted too;
  - a project check uses one id for its check and its guardrail. The id must not be a shipped check or gate id or `agent-review`. It takes `command` only, not the 8.x `script` and `args`;
  - the integrity rule reports `L-IMPL-UNKNOWN`. The superset test is `tests/test_tighten.py`, on the contract 1 grid under 32 subsets of the labels.
- Decision 8 is built in two new modules, `waiver_records.py` and `waiver_cmd.py`, not by rewriting `waivers.py` (commit 4db666ce). It adds five rules (commits 4db666ce and 8e2bdf22):
  - a delegation typed `--for waivers` needs the confirmation code typed back, as `--for g5` does, because a waiver lowers what an issue owes;
  - `/compass:approve waiver W-<n>` answers a pending request and never approves without one. It refuses when the waiver's check or reason changed after the request was written;
  - the approval record copies the waiver's check and reason (`waived_check`, `waiver_reason`) and the issue, so a waiver edited after its approval, or copied to another issue, excuses nothing;
  - an approval holds only at the generation it was given for. A reassessment can raise what the issue owes, so a waiver approved before it needs a new approval;
  - `compass waiver add` refuses a reason that holds a control, format or line-separator character, and a second waiver in force for the same check. The approvers are `approvers.waiver`, then `approvers.issue-waiver`, then the `owner`.
- Decision 9 said `layers.py` and `waivers.py` would be cut. Both are deleted whole, because nothing calls what the plan kept: `effective` reads `project_settings.COMPASS_YML` and `atomic_io.digest`, and `waiver_records.py` holds the approver list and the approval check (commit fa72a599). Further changes in the same commit:
  - `at_least` moves to `catalogue_spec.py`, not to `core.py`, which is at its 1,200-line bound;
  - `catalogue_spec` keeps the closed sets the governance copy check reads (`CHECK_KINDS`, `GATE_KINDS`, `LOCKS`, `DIMENSION_TYPES`, `TIGHTER`), and `SEVERITIES` and `ON_SKIPPED`. `OBLIGATION_FIELDS` goes: no code reads it;
  - functions left with no caller go too, among them `retired.merge_hint`, `acceptance_strategy.suspended_findings`, `word_map.advisory_lines`, the generator half of `legacy_adapter` and the `removed_parts` functions that worked inside a layer;
  - the build deleted 26 CLI modules (11,497 lines), with `policy migrate` and the view generator, and 38 test files and 4 test helpers (22,656 lines). `docs/waivers-and-locks.md` is deleted, and `docs/waivers.md` is the page for the 9.0.0 waiver;
  - no frozen `default@8` folder is made, and the `default@8.0.0` pin leaves `tests/fixtures/preset-digests.yml`. The one archived generation that names `compass:default@8` reads its own `resolved.yml`.
- Decision 10 did not give the JSON shapes. `compass policy show --json` gives `check_set`, `check_set_sha256`, `settings_sha256`, `tightened` and, with `--issue`, `issue`. `compass policy lint --json` keeps the 8.x top-level keys with `mode: settings`, so a script that reads `result` and `counts` keeps working. The legacy lint's JSON moves into `policy_cmd.legacy_json`, unchanged in shape. `schemas/compass.schema.json` is generated by `settings_lint.schema()` and lists the settings keys only, with `additionalProperties: false`, so an editor marks a removed key (commit fa72a599). `compass policy lint --file` on a file that is not there exits 2 (commit 963059b5).
- Decision 11 did not say when the settings lint runs. Every resolution runs it, and a `compass.yml` with a lint error resolves nothing (exit 2), as 8.x refused a project layer that did not pass its check (commit 9e539e50). No owner is read from such a file either: `approval_records.owner_and_cause` gives the lint's first error as the reason the file cannot be read, so approvals and waivers need `COMPASS_APPROVER` until the file is fixed (commit d0cc60d6).
- Decision 13 kept `legacy_adapter.adapt` for a governance copy, and the build reads the copy without the 8.x merge. `effective._legacy_config` adds each entry as it stands and keeps every refusal the merge made for such an entry. A gate at a legacy stage is mapped by `removed_parts.with_mapped_stages`, and the provenance names the layer `legacy` (commit 616c1063). That commit dropped the 8.x value checks of the copy. Commit 61b9b2da restores them in `effective._legacy_value_problems`: a value of the wrong type, a value outside its field's closed set, an incomplete dimension and an `at_least:` that cannot match are refused again. A commit from a copy also refuses a gate that names a check the copy does not declare (commit 963059b5). `EffectiveView.pending_config` compares the raw `config:` with the overlay digest an 8.x generation stored.
- `/compass:init` writes `schema`, `owner` and `project`, and no `extends:` line (commit c4a580ec). A project that already extends `compass:default@6` or `@7` kept `S17` off through `pinned_below` until ADR-098 open question 6 deleted that reader. Such a project now gets `S17` at its next assess unless it sets `acceptance_strategy: off`.
- With `compass issue configure` gone, no command adopts a complete generation folder the manifest does not name. The next reassess writes such a folder again when it holds only files a commit writes, and refuses a folder that holds any other file (commit 18c346b3).
- Configuration B of contracts 1 and 2 has no can-fail case. No setting B can hold reaches `evaluate_route`, so a planted fault there cannot be seen. Two tests apply a tightening to B and assert that B routes and owes as configuration A on every row; a setting that started to reach the routing would fail them. Configuration C keeps its can-fail cases, and contracts 3, 4 and 5 under B keep theirs (commits 5f3acd5a and 30a291cb).
- The archive comparison over 622 issue folders shows no verdict that moves, and contract 3 passes, after the resolver switch (commit 9e539e50) and after the governance copy change (commit 61b9b2da).

## Open questions

Each question has the default this change builds, and #357 built each default as written. The owner decides questions 6, 7, 9, 10, 12 and 19 when accepting this record, because each changes what a user or a pinned contract sees.

1. **Where does the check set live?** Default: one file in `governance/`, so one name, one version and one `sha256sum` name the rules.
2. **How is it versioned?** Default: `version` is the release that last changed it, from `9.0.0`; owing less is a major. A digest fixture pins the bytes, and an agent repins it in the change that edits the set.
3. **Where is the digest?** Default: the manifest's `policy:` block (decision 4), written at each generation commit, and the generation folder as now. #356 needs the manifest copy, because it keeps generations out of the commit.
4. **Does the generation store stay?** Default: yes, with the same `resolved.yml` shape and resolver `1.1.0`. Rebuilding a policy from `policy:` when the folder is missing is left to #356.
5. **Which tighten-only settings?** Default: the five of decision 7. The issue names `signoff_labels`; `require_evidence` and `project_checks` keep what ADR-092 decision 3 kept (`add_gate` floors and project guardrails); `agent_review` keeps ADR-090 decision 7 and #345 decision 6.
6. **What happens to a git parent?** Default: refused, as an error. A team parent can hold checks the team added, and dropping it with a warning would lower what each project owes without the project's file showing it. This reverses the #351 build's warn-and-drop rule for the parent itself. The other answer warns and drops it.
7. **What happens to `extends: compass:default@6` or `@7`?** Default: a removed setting with a warning, but `acceptance_strategy.pinned_below` keeps reading it, so a pinned project stays out of `S17` until #359's `compass migrate` writes `acceptance_strategy: {state: off, reason: ...}` in its place. This keeps the owner decision of 2026-10-30. The other answer drops it now, so `S17` applies to a pinned project's next assess, this repository included. ADR-098 open question 6 ended the pin once this repository's `compass.yml` set `acceptance_strategy: off`.
8. **Do catalogue keys that tightened warn or refuse?** Default: warn and drop, as ADR-091 and ADR-092 did for their keys. The warning is in the project's own lint. #359 names the replacing setting and rewrites the file.
9. **What can a waiver excuse?** Default: one check on one issue, any check but `never_waived`. The approver is `owner` or a name in `approvers.waiver`; a delegation covers it only with `--for waivers`.
10. **Is there a project-wide waiver?** Default: no. `acceptance_strategy: off` with a reason stays the one project-wide opt-out, with no approver added.
11. **Does `adoption: advisory` stay?** Default: yes. It sets the exit code, not the set, and `settings_sha256` records it.
12. **Does `compass policy migrate` go in #357?** Default: yes, with `--words` and `--undo`. Its output is a catalogue overlay that 9.0.0 drops, and keeping it keeps the classifier, the merge and the old lint. A 6.x or 7.x project upgrades through 8.x, runs `policy migrate` there, then `compass migrate`. `v9` is not released, so no user meets the gap before #359.
13. **What happens to `compass policy show` and `lint`?** Default: both stay, rewritten (decision 10).
14. **Do the frozen presets stay?** Default: yes, as data (decision 13).
15. **Do the generated views stay?** Default: frozen, read only by the legacy readers, deleted by #359.
16. **What happens to `signals.yml`?** Default: the six scope-bloat phrases move into `hooks/py/stop_scan.py`; the file, its schema and `design_smell` go. A project's own copy is no longer read.
17. **Does a per-issue `autonomy` stay?** Default: no; it was an issue-layer key. `autonomy` is a project setting.
18. **What happens to `--kind configuration` on `approach evaluate`?** Default: the value stays valid in old `reassessments:` logs. The CLI no longer writes it on its own, because there is no issue layer to change.
19. **What happens to the contract 4 judged-check entries?** Default: `evidence-review-recorded` moves to `EXIT_CHANGED_IN_9_0_0` (exit 0 to 2), for the owner to look at. `evidence-review-input-missing` and `evidence-review-not-judged` keep exit 2.

## References

- ayeo-io/compass-delivery#357 [Replace configuration layers and presets with one fixed check set] and its parent, #345 [Reposition Compass 9.0.0 as an ATDD framework with a proof trail], decisions 6, 7 and 10 and its "What stays" list.
- Related issues:
  - #348 [Make evidence digests checkable with sha256sum] sets the digest form of the `policy:` block;
  - #355 [Read the ship approval from the merged PR review] owns the ship approval; this change adds only the waiver subject;
  - #356 [Commit the issue record with the code and add trail.md] keeps generation folders out of the commit;
  - #359 [Add compass migrate and the 9.0.0 upgrade guide] rewrites old settings and deletes the legacy readers.
- ADR-036 (the stored generation), ADR-038 (check implementation versions), ADR-066 (an approval names its subject), ADR-069 and ADR-077 (delegations), ADR-090 (one session, and the agent review), ADR-091, ADR-092 and ADR-093 (the 9.0.0 removals).
- `governance/decisions/2026-10-30-the-strategy-follows-the-pinned-major-and-the-settings-key.md` and `governance/decisions/2026-10-06-locks-allow-tightening-and-g5-is-hard.md`.
- `cli/compass_pkg/effective.py`, `cli/compass_pkg/generation.py`, `cli/compass_pkg/removed_parts.py`, `cli/compass_pkg/waivers.py`, `cli/compass_pkg/evidence_required.py`, `cli/compass_pkg/acceptance_strategy.py`, `governance/presets/default/preset.yml`, `tests/compat_commands.py`.
