# Configuration

Every setting of a project: what it does, its values, its default and the
file that holds it. One reader, `cli/compass_pkg/project_settings.py`
(ADR-043), serves the CLI and the pre-tool hook. It also finds the project
root (`find_project_root`: the first folder at or above the start that holds
`.compass` or `.git`) and reads `owner` and `approvers` (`project_file`).

## Where the settings live

| File | Holds | Read when |
|---|---|---|
| `compass.yml` at the project root | The settings. The one file a person edits. | It has a top-level `schema:` key, or it is the only settings file. |
| `.compass/config.yml` | The same settings for a project from 5.x. The adoption setting is called `mode` here. | `compass.yml` is absent, or has no `schema:`. |
| `.compass/state.yml` | What the CLI writes: `initialized` and `records_signed_since`. Do not edit it. | Always. A project created before ADR-043 keeps both values in `.compass/config.yml`, and Compass reads them there. |

- `compass.yml` holds settings only. Compass runs one fixed check set
  (ADR-094), and only the tighten-only settings below change what an issue
  owes. For waivers and approvers see [waivers.md](waivers.md).
- Compass refuses a key that appears twice in `compass.yml`.
- Every `compass.yml` that Compass creates carries `schema:`.
- No 9.0.0 command writes `.compass/config.yml` or moves its settings.
  `compass policy migrate` did that on 8.x, and 9.0.0 removed it (ADR-094).

### What a new project and an existing project get

- **A new project.** `compass init`, run by any entry point, creates
  `.compass/state.yml`, `.compass/work/` and `.compass/work/.gitignore`. It
  writes no settings file. `/compass:init` then writes a minimal
  `compass.yml`: `schema`, `owner`, `project.name` and `project.test_command`.
- **A project from 5.x** with a `.compass/config.yml` or copied governance.
  Nothing changes, and Compass reads the old files. `/compass:init` stops
  and says so. `compass init` adds nothing.

A missing file means every default below. A file the CLI cannot read, or a
duplicate key in `compass.yml`, is a broken file. Then:

- `adoption` falls back to `enforced`;
- `autonomy` and `record` refuse and name the file;
- `project` and `allow_project_commands` read as not set.

### A project with both files

| `compass.yml` | `.compass/config.yml` | What happens |
|---|---|---|
| has `schema:` | holds a settings key | Compass refuses (`settings-conflict`). |
| has `schema:` | holds only `initialized`, `records_signed_since` or unread keys | `compass.yml` is read. |
| has no `schema:` | present | `.compass/config.yml` is read, and a warning on stderr says `compass.yml` is ignored. Add `schema:` if it is Compass's file. |
| only file | absent | `compass.yml` is read, with or without `schema:`. |

- **What counts as a settings key in the old file:** `mode`, `autonomy`,
  `allow_project_commands`, `enforcement`, `record`, `project`, `prices`,
  `models`, `multiagent`, `preset_index`, `governance_drift`, `github_labels`,
  `language`, `acceptance_strategy`, `signoff_labels`, `require_evidence`,
  `agent_review` and `project_checks`. `worktree_root`, `max_worktrees` and
  `test_command` also count when they are outside `multiagent:` and
  `project:`.
- **How the refusal shows.** The pre-tool hook exits 2 with `settings-conflict`
  for an edit to a path its built-in rules neither guard nor exempt. Each CLI
  command that reads settings stops with the same text, and `compass check`
  fails. The text names the keys, up to five and then "and N more".
- **The way out.** Move those keys into `compass.yml` (write `mode` as
  `adoption`) and delete them from `.compass/config.yml`. The text names no
  migration command: 9.0.0 has none (ADR-094).
- **A broken file.** A file that cannot be parsed is refused and named. A
  `compass.yml` that cannot be parsed counts as Compass's file, so Compass
  does not read the old file in its place.

## Settings

| Setting | What it does | Values | Default |
|---|---|---|---|
| `adoption` (`mode` in `.compass/config.yml`) | Whether a failed check blocks | `enforced`, `advisory` | `enforced` |
| `autonomy` | How often a session stops for a person | `controlled`, `balanced`, `autonomous` | `balanced` |
| `project` | The project's name and commands, and the untracked paths the base copy links | `name`, `test_command`, `test_micro_command`, `bdd_run_command`, `base_copy_links` | none |
| `enforcement` | Extra paths the pre-tool hook guards | `code_globs`: a list of patterns | none |
| `record` | Where the delivery record is kept, and whether each issue's record is committed with its code | `remote`, `paths`, `names_key`, `commit` | no record repository; the record is committed |
| `allow_project_commands` | Lets `compass check` run commands the project declares | `true`, `false` | `false` |
| `language` | The language the agent writes prose in | a BCP 47 tag such as `en-US` | unset: no instruction |
| `acceptance_strategy` | Whether the four-layer acceptance strategy (`S17`) is on for the project | `state`: `on` or `off`; `reason`: text, needed with `off` | unset: on |

The five tighten-only settings and the removed settings have their own
sections below.

### `adoption`

| Value | `compass check` and `compass ci` |
|---|---|
| `enforced` | Exit non-zero on any failure. A failed check blocks. |
| `advisory` | Report every failure and exit 0, so CI does not fail. The `compass ci` summary line still says FAIL. |

Under `advisory` the pre-tool hook still refuses a code edit before the
scenarios exist or, where owed, before a person approves them. Any other
value reads as `enforced`.

### `autonomy`

How often a session waits for a person at a checkpoint, the end of a stage
(`docs/checkpoints.md`). No value changes a gate, evidence, the pre-tool hook
or `compass check`. Assess writes each issue's checkpoints to its manifest,
and `compass approach show` shows them.

| Value | A session waits |
|---|---|
| `controlled` | A delivery issue: at assess and specify, and at build and ship where `S17` applies. A spike: at assess. |
| `balanced` | Only at specify, when the scenarios owe a person's approval (a `G5` label or critical risk). |
| `autonomous` | As `balanced`. Every other hand-off is shown and logged. |

Any other value is refused, and the refusal names the file.

### `project`

| Key | What it does |
|---|---|
| `name` | The project's name. `/compass:init` asks for it; no check reads it. |
| `test_command` | The command `compass tdd-red` and `compass tdd-green` run when none is given. Left empty, `tdd-red` and `tdd-green` need the command after `--`, and refuse without it. |
| `test_micro_command` | Used before `test_command` by those two commands. |
| `bdd_run_command` | The command the `compass bdd` run step uses when none is given. |
| `base_copy_links` | A list of untracked paths, relative to the project root, that `compass quick-fix finish` links into the copy of the base commit. Name build output or generated files the tests need. `node_modules`, `.venv` and `venv` are linked without it. `finish` refuses a path that is absolute or leaves the project. See `docs/base-copy.md`. |

```yaml
project:
  base_copy_links:
    - build
```

`compass quick-fix finish` takes its test command after `--`.

### `enforcement`

`code_globs` is a list of path patterns the pre-tool hook treats as code, in
addition to its own rules.

- A string in place of a list, or an unreadable file, makes the hook refuse
  the edit (`config-invalid` in `docs/refusal-codes.md`). The refusal names
  the file the hook read.
- The hook reads the setting only for an edit to a path that its built-in
  rules neither guard nor exempt, and only when the project has a settings
  file. With neither file the hook starts no Python process for that edit.
- The hook reads `initialized` only when it is about to refuse an edit, to
  say who initialized the project.

### `record`

| Key | What it does |
|---|---|
| `remote` | Names the record repository. |
| `paths` | The folders and files `compass record sync` copies into it. |
| `names_key` | Optional. A path inside the project to a file of names that must not reach the record. |
| `commit` | The record mode: `true` or `false`. `compass policy lint` refuses any other value. `commit: false` is valid with no `remote`. |

See `docs/delivery-record.md`. The record mode says whether each issue's
folder (`.compass/work/<slug>/`) is committed with its code or kept out of
git history. `record_mode.mode` decides, in this order:

| Condition | Mode | Reason given |
|---|---|---|
| `commit: false` | kept out | "record.commit is false" |
| `remote` set, `commit` not set | kept out | "the record is synced to <remote>; set record.commit to choose" |
| `commit: true`, or neither set | committed, unless a row below applies | none |
| not inside a git work tree | kept out | "not a git repository" |
| git ignores the issue folder | kept out | "<path> is ignored by <file>:<line>:<pattern>" |

- A project's own ignore rule wins. Compass does not force-add an ignored
  folder and does not refuse the landing.
- `compass record sync` runs whenever `remote` is set, in either mode.

`compass init` writes `.compass/work/.gitignore` in every project. It holds
the files of an issue folder that belong to one checkout:

```
# Written by Compass. Each issue folder is the record that ships with the code;
# these files are per-checkout state and stay out (#356).
*/generations/
*/.*.lock
*/.red
*/.acceptance
*/start-state.json
*/evidence/.tdd-state.json
*/approval-requests/pending/
```

In committed mode only, it also adds `delegations/`, `cache/`, `private/`,
`current-task` and `interruptions.log` to `.compass/.gitignore`. Each run
adds only the missing lines and keeps the person's own lines.

### `allow_project_commands`

`compass check` runs the command of a project check (`project_checks`, below)
only when this setting is `true`. It is read from the project's own
`compass.yml` only. See `docs/security.md`.

### `language`

The language the agent writes the project's prose in, as a BCP 47 tag:

```yaml
language: en-US
```

- Unset means no instruction: the agent follows the repository's existing
  prose.
- When it is set, the session-start hook adds one line that names the
  language. The setting does not apply to code identifiers.
- It is read from the project's own settings file: `compass.yml`, or
  `.compass/config.yml` when `compass.yml` is absent or has no `schema:`.
- A malformed value adds no line to a session. `compass policy lint` refuses
  a malformed `language` key in `compass.yml`; it does not check
  `.compass/config.yml`.
- When `language` is set, a `CLAUDE.md` or `AGENTS.md` that names a language
  should drop that sentence, and Compass never edits those files.

| Language | Tag |
|---|---|
| English (US) | `en-US` |
| English (UK) | `en-GB` |
| English (Australia) | `en-AU` |
| English (Canada) | `en-CA` |
| English (India) | `en-IN` |
| English (Ireland) | `en-IE` |
| English (New Zealand) | `en-NZ` |
| English (South Africa) | `en-ZA` |
| Spanish (Spain) | `es-ES` |
| Spanish (Mexico) | `es-MX` |
| Spanish (Latin America) | `es-419` |
| Portuguese (Brazil) | `pt-BR` |
| Portuguese (Portugal) | `pt-PT` |
| French (France) | `fr-FR` |
| French (Canada) | `fr-CA` |
| German (Germany) | `de-DE` |
| German (Switzerland) | `de-CH` |
| Italian | `it` |
| Dutch | `nl` |
| Polish | `pl` |
| Czech | `cs` |
| Swedish | `sv` |
| Danish | `da` |
| Norwegian (Bokmål) | `nb` |
| Finnish | `fi` |
| Greek | `el` |
| Turkish | `tr` |
| Ukrainian | `uk` |
| Russian | `ru` |
| Hebrew | `he` |
| Arabic | `ar` |
| Hindi | `hi` |
| Indonesian | `id` |
| Vietnamese | `vi` |
| Thai | `th` |
| Japanese | `ja` |
| Korean | `ko` |
| Chinese (Simplified) | `zh-Hans` |
| Chinese (Traditional) | `zh-Hant` |

For a language not listed, see the
[IANA language subtag registry](https://www.iana.org/assignments/language-subtag-registry/language-subtag-registry).

- A bare language (`de`) is fine when the region does not change spelling. Add
  a region (`de-CH`) when it does.
- Use `zh-Hans` and `zh-Hant` for Chinese. The script, not the region, decides
  the characters.
- Norwegian is `nb` or `nn` (Bokmål or Nynorsk). Do not write an unquoted
  `no`: YAML reads it as false, and Compass refuses it. Hebrew is `he`, not
  `iw`.

### `acceptance_strategy`

Turns the four-layer acceptance strategy (`S17`, `governance/strategies.md`)
off for the project, with the reason assess records:

```yaml
acceptance_strategy:
  state: "off"
  reason: "no deployable candidate yet"
```

- Unset means on. `off` needs a reason that is not blank.
- Quote `"on"` and `"off"`. YAML reads them unquoted as true and false, which
  Compass also accepts.
- Any other value makes `compass approach evaluate` and `compass check` exit 2
  with a message that names the key, the file and the accepted values, and
  `compass policy lint` reports it in `compass.yml`. `compass check` on an
  assessed issue reads the configuration stored with the issue, so it does
  not refuse.
- The setting needs no owner's approval. The manifest's `acceptance_strategy`
  block shows the choice.
- It takes effect for an issue at its next `compass approach evaluate
  --write`. Until then `compass check` reports the changed setting as advice.
- It is read from `compass.yml`, or from `.compass/config.yml` when
  `compass.yml` is absent or has no `schema:`.
- With `state: "off"` the strategy applies to no issue, whatever a
  `require_evidence` rule adds. No other setting turns the strategy off.

By default a delivery issue owes no record of the strategy (ADR-099): assess
stores the routing `guidance`, the `atdd` skill is advice, and no check of
the strategy runs. A `require_evidence` rule that adds one of the strategy's
tokens sets the routing:

| Token added | Routing | What the routing needs |
|---|---|---|
| `outer-loop` | `existing-dsl` | the outer-loop records alone |
| `isolation` | `existing-dsl-isolation` | the isolation proof |
| `layering` | `on` | the full strategy |

When a rule adds more than one, `layering` decides before `isolation`, and
`isolation` before `outer-loop`.

## Tighten-only settings

Five settings of `compass.yml` change what an issue owes, and each can only
make it owe more. No value removes a check, lowers a severity or narrows when
a check applies. Only the project's own `compass.yml` can hold them.

`compass policy lint` and every generation commit check them
(`compass_pkg.settings_lint`). Each issue's `policy:` block records the ones
applied (`docs/generation-store.md`).

| Setting | What it adds | Values | Default |
|---|---|---|---|
| `signoff_labels` | More labels that owe what a `G5` label owes | a list of label names | none: the four shipped labels |
| `require_evidence` | More evidence a matching delivery issue owes | a list of `{when, add}` rules | none |
| `agent_review` | The advisory judged check `agent-review` at `ship` | `on` or `true`; `off` or `false` | off |
| `project_checks` | The project's own commands, each a blocking check | a list of `{id, name, command, stage, when}` | none |
| `capabilities` | The evaluation of the Definition of Done items | `{entry-exit-evaluation: true}` | `false` |

```yaml
signoff_labels: [billing]
require_evidence:
  - when: {risk: [cross-cutting, critical]}
    add: [reproduce-first]
agent_review: on
project_checks:
  - id: arch-fitness
    name: Architecture fitness
    command: python3 scripts/arch-fitness.py
    stage: build
capabilities:
  entry-exit-evaluation: true
```

### `signoff_labels`

Each label owes what `auth`, `payments`, `personal-data` and `migrations`
owe: a person's approval of the scenarios before any code edit
(`scenario-approval`) and the `G5` sign-off (`human-approval`). The labels
join the `when` of gate `G5`. An exploration issue with one of them is
refused. A shipped label cannot be taken away.

### `require_evidence`

What a delivery issue owes without a rule (ADR-099):

| Issue | Evidence owed |
|---|---|
| Every delivery issue | `request`, `scenarios`, `red-before-green`, `suite-green`, `correctness`, `governance`, `traceability`, `ship-approval` |
| With a `G5` label | also `scenario-approval` and `human-approval` |
| With critical risk | also `scenario-approval` |

Each rule adds tokens to a delivery issue whose assessment matches `when`:

- `when` is a condition on the assessment, such as `risk: [critical]`,
  `size: {at_least: medium}`, `labels_any: [billing]` or `any_of: [...]`.
  Absent or empty, the rule applies to every delivery issue.
- `add` is one or more tokens of the closed set: `request`, `scenarios`,
  `red-before-green`, `suite-green`, `correctness`, `governance`,
  `traceability`, `regression`, `security`, `clarity`, `architecture`,
  `outer-loop`, `isolation`, `layering`, `definition-of-done`,
  `reproduce-first`, `scenario-approval`, `human-approval` and
  `ship-approval`. A rule that adds `request` or `ship-approval` changes
  nothing.

The rules fire as `RP-SETTING-1`, `RP-SETTING-2` and so on, in file order. A
spike owes none of them.

`compass quick-fix finish` does not write the evidence a rule adds. It
writes its own record, prints one `next:` line for each added item, commits
nothing and exits 1. The session records each item, then runs the same
`finish` again.

### `agent_review`

`on` adds the optional judged check `agent-review` at the entry of `ship`,
as advisory evidence (ADR-090 decision 7). See `docs/judged-checks.md`.
Write `on` or `true`; both are accepted. `off` and `false` are the default.

### `project_checks`

Each entry adds one blocking check and one guardrail, both under `id`, that
run `command` from the project root through the `command-passes`
implementation. Exit 0 passes.

| Field | Rule |
|---|---|
| `id` | Must not be the id of a shipped check or gate, `agent-review`, or a check Compass deleted (`check_registry.DELETED_CHECKS`). `compass check` refuses a project whose `project_checks` names a deleted check (`names-deleted-check`, `docs/waivers.md`). |
| `stage` | `build` or `ship`. |
| `when` | Optional, in the form `require_evidence` uses. |
| `command` | Runs only when `allow_project_commands` is `true` (`docs/security.md`). |

### `capabilities`

`entry-exit-evaluation: true` evaluates the Definition of Done items at the
end of `build` (`docs/entry-exit-evaluation.md`). `false` is the default and
changes nothing. Any other capability is refused, except
`artifact-freshness`, which 9.0.0 removed and which lint names with
`L-SETTING-REMOVED`.

## Removed settings

9.0.0 does not read these keys. Each stays valid, so a file that holds one
keeps working. `compass policy lint` names each with `L-SETTING-REMOVED`.
Delete them from `compass.yml`.

| Key | Decision | Note |
|---|---|---|
| `models`, `multiagent` | ADR-090 | |
| `prices` | ADR-093 | |
| `github_labels` (`domain`, `status`, `page`) | ADR-093 | Compass writes no label to GitHub. Lint names `github_labels.page` when that switch is `true`, and `github_labels` otherwise. `compass issue link set` still records the link (`docs/github-links.md`). |
| `readiness` | ADR-093 | The `readiness` verb and the `--readiness` flag of `compass init` are gone. A `.compass/readiness.yml` is not read. |
| `project.lint_command`, `format_check_command`, `build_command`, `typecheck_command`, `secret_scan`, `structured_logging` | ADR-093 | |
| `governance_drift` | ADR-098 | |
| `living_spec` | ADR-091 | |
| `preset_index`, the catalog keys and `extends:` | ADR-094 | See below. |

### Governance edits 9.0.0 removed

9.0.0 runs every new delivery issue on one four-stage path (ADR-092). A
`compass.yml` can no longer change the approaches, the legacy stages, the
caps rule set, the Definition of Ready checks or the `require_phase` effect
of `RP-FLOOR-002`. The whole catalog key is not read (ADR-094). The table
below names each key.

What keeps an older file or issue working:

- An issue's stored generation keeps the configuration it was assessed
  with, and lint still reads it.
- Resolution reads only the check set, whatever `extends:` names. 9.0.0
  ships no 8.x preset.
- The manifest's `config:` is not read. `compass issue lint` warns about one
  that the issue's stored generation was not committed with.
- A gate at a legacy stage is read at the path stage that shows it:
  `define`, `refine` and `plan` at specify; `breakdown` and `implement` at
  build; `verify` at ship.
- An issue assessed before 9.0.0 waits only at the legacy hand-offs.

### Removed settings and their replacements

`compass policy lint` names each removed key with what replaces it. The
message, and the `replacement` field of `--json`, come from
`removed_parts.REPLACEMENTS` (ADR-098 decision 7). The message ends with
"Replacement: `<setting>`." or "Removed: nothing replaces it.", and adds
"`compass migrate` rewrites it." when `compass migrate` changes the key.
Otherwise, edit `compass.yml` by hand.

`compass migrate` reads the same table:

- It deletes each key marked "rewrites it", and writes the setting that
  replaces it.
- It leaves each key marked "no" in the file, and names the edit.
- It leaves whole a rewritten key that holds a key marked "no", such as
  `rules:` with `rules.caps`.
- It keeps comments, and writes nothing unless the lint passes on the result.

`docs/upgrade-9-0-0.md` lists each conversion. In the table:

- `extends@6` is a pin of the shipped default at `@6` or below, and
  `extends@7` a pin at `@7`. `acceptance_strategy: off` replaces both.
- `extends@8` is a pin at `@8` or later, or no pin.
- `extends` is any other value.
- A key with `*` is an effect of any rule that picked a delivery approach.

<!-- compass:replacements-table -->
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
<!-- /compass:replacements-table -->

### The settings lint

`compass policy lint` reads `compass.yml` as a file of settings
(`compass_pkg.settings_lint.lint`) and gives each finding a code:
`L-SETTING-UNKNOWN`, `L-SETTING-INVALID`, `L-SETTING-REMOVED`,
`L-PARENT-REMOVED` or `L-IMPL-UNKNOWN`. `docs/policy-lint.md` says what each
means.

`schemas/compass.schema.json` describes the same shapes, so an editor marks
a removed setting as one the file cannot hold. `settings_lint.schema()`
generates it.
