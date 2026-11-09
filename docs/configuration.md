# Configuration

A project's settings: what each one does, its values, its default and which
file holds it. The Python reader is `cli/compass_pkg/project_settings.py`
(ADR-043). The pre-tool hook calls it too, so every reader of a setting
follows the same file. It also finds the project root
(`project_settings.find_project_root`: the first folder at or above the start
that holds `.compass` or `.git`), and reads the `owner` and `approvers` of
`compass.yml` for the approval rules (`project_settings.project_file`).

## Where the settings live

- **`compass.yml` at the project root** holds the settings, and from 6.0.0 it
  is the one file a person edits. The CLI reads it when it is Compass's file,
  and refuses a key that appears twice. It is Compass's file when it has a
  top-level `schema:` key, or when it is the only settings file. It holds
  settings only: Compass runs one fixed check set (ADR-094), and the
  tighten-only settings below are the one way to change what an issue owes.
  A catalog key or `extends:` is a removed setting (see `docs/policy-lint.md`;
  for waivers and approvers see [waivers.md](waivers.md)). `/compass:init` writes a minimal one for a new
  project. `compass policy migrate` on 8.x wrote one for an existing project;
  9.0.0 removed that command (ADR-094).
- **`.compass/config.yml`** holds the same settings for a project from 5.x that
  has not moved. The CLI reads it when `compass.yml` is absent, or present
  without `schema:`, until 9.0.0. `compass policy migrate` on 8.x moves its
  settings into `compass.yml`, and 9.0.0 stops reading it. In this file
  the adoption setting is called `mode`; in `compass.yml` it is called
  `adoption`. No 6.0.0 command writes this file.
- **The state file in `.compass/`** holds what the CLI writes, not what a
  person edits: `initialized` (what created the project, and when) and
  `records_signed_since`. Do not edit it. `compass init` writes this file and
  no other settings or state file, so a new project has `.compass/state.yml`
  and no `.compass/config.yml`. It also writes the ignore lines of the record
  (see `record` below). A project created before ADR-043 keeps both values in
  `.compass/config.yml`, and the CLI and the hook read them there. `init` adds
  nothing to such a project, and `compass policy migrate` on 8.x moves them to
  the state file.

### What a new project and an existing project get

| Project | Gets | Reads |
|---|---|---|
| New (no `.compass/`) | `compass init`, run by any entry point, creates `.compass/state.yml`, `.compass/work/` and `.compass/work/.gitignore`. Its `settings` line names `compass.yml` when the project has one, and otherwise says the defaults are in force. `/compass:init` then writes a minimal `compass.yml` (`schema`, `owner`, `project.name`, `project.test_command`) and copies nothing. | `compass.yml`, over the check set |
| From 5.x with a `.compass/config.yml` or copied governance | Nothing changes until it runs `compass policy migrate` on 8.x. `/compass:init` stops and says so in place of writing a fresh file; the upgrade guide names the 9.0.0 settings. | The old files, as 5.x did |
| This repository | A hand-written `compass.yml` that holds settings keys and the owner, and `.compass/state.yml`. It also holds a `readiness:` override and two readiness commands, which 9.0.0 no longer reads (see `readiness` below). | `compass.yml` |

A missing file means every default below. A file the CLI cannot read, or a
duplicate key in `compass.yml`, is a broken file. Each command then does what
it did before: the adoption setting falls back to `enforced`, `autonomy` and
`record` refuse and name the file, and the project and `allow_project_commands`
settings read as not set.

### A project with both files

The state decides what Compass reads, and no state loses a setting silently:

| `compass.yml` | `.compass/config.yml` | What happens |
|---|---|---|
| has `schema:` | holds a settings key | Compass refuses (`settings-conflict`). |
| has `schema:` | holds only `initialized`, `records_signed_since` or unread keys | `compass.yml` is read. |
| has no `schema:` | present | `.compass/config.yml` is read, and a warning on stderr says `compass.yml` is ignored. Add `schema:` if it is Compass's file. |
| only file | absent | `compass.yml` is read, with or without `schema:`. |

- **What counts as a settings key in the old file:** `mode`, `autonomy`,
  `allow_project_commands`, `enforcement`, `record`, `project`, `prices`,
  `models`, `multiagent`, `preset_index`, `governance_drift`, `github_labels`, `language`,
  `acceptance_strategy`, `signoff_labels`, `require_evidence`, `agent_review`
  and `project_checks`. The three keys the multiagent scripts read
  before 9.0.0, `worktree_root`, `max_worktrees` and `test_command`, also
  count when they are outside `multiagent:` and `project:`, because the
  scripts found them at any depth in the old file.
- **How the refusal shows.** The pre-tool hook exits 2 with `settings-conflict`
  for an edit to a path its built-in rules neither guard nor exempt. Each CLI
  command that reads settings stops with the same text, and `compass check`
  fails. The text names the keys, up to five and then "and N more".
- **The way out.** Move those keys into `compass.yml` (write `mode` as
  `adoption`) and delete them from `.compass/config.yml`. The text names no
  migration command: 9.0.0 has none (ADR-094).
- **A broken file.** A file that cannot be parsed is refused and named, in
  either position, as for a lone file. A `compass.yml` that cannot be parsed
  counts as Compass's file, so Compass does not read the old file in its place.
- **The marker.** Every `compass.yml` that Compass creates carries `schema:`.
  `compass init` writes no `compass.yml`. `/compass:init` writes a project's
  first one, as `compass policy migrate` did on 8.x.

## Settings

| Setting | What it does | Values | Default |
|---|---|---|---|
| `adoption` (`mode` in `.compass/config.yml`) | Whether a failed check blocks | `enforced`, `advisory` | `enforced` |
| `autonomy` | How often a session stops for a person | `controlled`, `balanced`, `autonomous` | `balanced` |
| `project` | The project's name and commands | `name`, `test_command`, `test_micro_command`, `bdd_run_command`; six readiness keys that 9.0.0 no longer reads (see `project` below) | none |
| `enforcement` | Extra paths the pre-tool hook guards | `code_globs`: a list of patterns | none |
| `record` | Where the delivery record is kept, and whether each issue's record is committed with its code | `remote`, `paths`, `names_key`, `commit` | no record repository; the record is committed |
| `prices` | Removed in 9.0.0 and not read (see `prices` below) | - | - |
| `models` | Removed in 9.0.0 and not read (see `models` below) | - | - |
| `multiagent` | Removed in 9.0.0 and not read (see `multiagent` below) | - | - |
| `allow_project_commands` | Lets `compass check` run commands the project declares | `true`, `false` | `false` |
| `governance_drift` | Removed in 9.0.0 and not read (see `governance_drift` below) | - | - |
| `living_spec` | Removed in 9.0.0 and not read (see `living_spec` below) | - | - |
| `language` | The language the agent writes prose in (see `language` below) | a BCP 47 tag such as `en-US` | unset: no instruction |
| `acceptance_strategy` | Whether the four-layer acceptance strategy (`S17`) is on for the project (see `acceptance_strategy` below) | `state`: `on` or `off`; `reason`: text, needed with `off` | unset: on |
| `preset_index` | Removed in 9.0.0 and not read (ADR-094); `compass policy lint` names it with `L-SETTING-REMOVED` | - | - |
| `github_labels` | Removed in 9.0.0 and not read (see `github_labels` below) | - | - |

### `adoption`

- `enforced`: `compass check` and `compass ci` exit non-zero on any failure.
  A failed check blocks.
- `advisory`: `compass check` and `compass ci` report every failure clearly
  but exit 0, so CI does not fail. The `compass ci` summary line still says
  FAIL when a check failed. The pre-tool hook still refuses a code edit
  with no failing test on record.

Use advisory mode to try Compass without blocking delivery. A value other
than these two reads as `enforced`.

### `autonomy`

How often a session stops to wait for a person at a checkpoint, the end of a
stage of the path: confirming the assessment, approving the scenarios, and
the stage 2 and 3 reviews of the four-layer acceptance strategy (`S17`).
Assess writes the checkpoints of each issue to its manifest, and `compass
approach show` shows the answer for an issue. No value changes a gate,
evidence, the pre-tool hook or `compass check`.

- `controlled`: a delivery issue waits at assess and specify, and also at
  build and ship where `S17` applies. A spike waits at assess.
- `balanced`: a delivery issue does not stop, except at specify when its
  scenarios owe a person's approval (a `G5` label or critical risk).
- `autonomous`: never wait, except at specify when the scenarios owe a
  person's approval, as under `balanced`. Every other hand-off is shown and
  logged instead. From 7.0.0 to 8.x an issue on `autonomous` had to meet
  the readiness floor. 9.0.0 removed the floor (ADR-093), so no value is
  refused.

Any other value is refused, naming the file, because a typo that silently
changed how often a session stops would give no sign.

### `project`

- `name`: the project's name. `/compass:init` asks for it; no check reads it.
- `test_command`: the command `compass tdd-red` and `compass tdd-green` run
  when none is given. Left empty, `tdd-red` and `tdd-green` need the command
  after `--`, and refuse without it.
- `test_micro_command`: used before `test_command` for those two commands.
- `bdd_run_command`: the command the `compass bdd` run step uses when none is given.
- `lint_command`, `format_check_command`, `build_command`, `typecheck_command`,
  `secret_scan` and `structured_logging`: removed in 9.0.0 (ADR-093) and not
  read. Only the `readiness` verb read them, and it is gone. Each stays valid,
  so a project that holds one keeps working, and nothing reads it.
  `compass policy lint` names each with `L-SETTING-REMOVED`. Delete them from
  `compass.yml`.

`compass tdd-red` and `compass tdd-green` read `test_micro_command` and
`test_command` only.

### `enforcement`

`code_globs` is a list of path patterns the pre-tool hook treats as code, in
addition to its own rules. A string instead of a list, or an unreadable file,
makes the hook refuse the edit, because it cannot tell whether the path is
guarded. The refusal (`config-invalid` in `docs/refusal-codes.md`) names the
file the hook read, `compass.yml` or `.compass/config.yml`.

The hook reads this setting for an edit to a path that its built-in rules
neither guard nor exempt, and only when the project has a settings file. A
project with neither file makes the hook start no Python process for that edit. It
reads `initialized` only when it is about to refuse an edit, to say who
initialized the project.

### `models`

9.0.0 removed model tiers and effort per dispatch (ADR-090). The key stays
valid, so a project that holds it keeps working, and nothing reads it.
`compass policy lint` names it with `L-SETTING-REMOVED`. Delete it from
`compass.yml`.

### `multiagent`

9.0.0 removed the multiagent scripts that read `worktree_root` and
`max_worktrees` (ADR-090). The key stays valid, so a project that holds it
keeps working, and nothing reads it. `compass policy lint` names it with
`L-SETTING-REMOVED`. Delete it from `compass.yml`.

### `prices`

9.0.0 removed the usage record and the cost per change that `prices` priced
(ADR-093). The key stays valid, so a project that holds it keeps working, and
nothing reads it. `compass policy lint` names it with `L-SETTING-REMOVED`.
Delete it from `compass.yml`.

### `record`

`remote` names the record repository and `paths` lists the folders and files
`compass record sync` copies into it. `names_key` is an optional path inside
the project to a file of names that must not reach the record. See
`docs/delivery-record.md`.

`commit` sets the record mode: whether each issue's folder
(`.compass/work/<slug>/`) is committed with its code or kept out of the
project's git history. It must be `true` or `false`; `compass policy lint`
refuses any other value. `record: {commit: false}` is valid with no `remote`.
`record_mode.mode` decides, in this order:

| Condition | Mode | Reason given |
|---|---|---|
| `commit: false` | kept out | "record.commit is false" |
| `remote` set, `commit` not set | kept out | "the record is synced to <remote>; set record.commit to choose" |
| `commit: true`, or neither set | committed, unless a row below applies | none |
| not inside a git work tree | kept out | "not a git repository" |
| git ignores the issue folder | kept out | "<path> is ignored by <file>:<line>:<pattern>" |

A project's own ignore rule wins: Compass does not force-add an ignored
folder and does not refuse the landing. `compass record sync` runs whenever
`remote` is set, in either mode. This repository names a `remote` and no
`commit`, so its record is kept out.

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
`current-task` and `interruptions.log` to `.compass/.gitignore`. A kept-out
project can track that file, so it does not change there. Each run adds only
the lines that are missing and keeps the person's own lines, so running
`compass init` twice adds nothing.

### `allow_project_commands`

A project check (`project_checks`, below) declares a command. `compass check`
runs one only when this setting is `true`. The setting is read from the
project's own `compass.yml` only. See `docs/security.md`.

### `github_labels`

9.0.0 removed the label sync (ADR-093). Compass writes no label to GitHub, and
`compass issue github sync` is gone. The key, with its switches `domain`,
`status` and `page`, stays valid, so a project that holds it keeps working, and
nothing reads it. `compass policy lint` names it with `L-SETTING-REMOVED`:
once, by `github_labels.page` (ADR-091) when that switch is `true`, and by
`github_labels` otherwise. Delete it from `compass.yml`. `compass issue link
set` still records the link (`docs/github-links.md`).

### `readiness`

9.0.0 removed the `readiness` verb, the `--readiness` flag of `compass init`,
the readiness floor and the session-start readiness line (ADR-093). Nothing measures the
repository, and the shipped default declares an empty `readiness:` catalog,
as ADR-091 did for `artifacts:`. A project's `readiness:` stays valid, so a
file that holds it keeps working. It is read as if absent, and its value is
not checked. `compass policy lint` names it with
`L-SETTING-REMOVED`. Delete it from `compass.yml`. An issue's stored
generation keeps the catalog it was written with, and lint still reads it. A
`.compass/readiness.yml` left in a checkout is not read.

### `governance_drift`

9.0.0 removed the drift report, which compared a project's copy of the
governance files with the framework's, and this setting, which made the report
fail `compass policy lint` (ADR-098). The key stays valid, so a project that
holds it keeps working, and nothing reads it. `compass policy lint` names it
with `L-SETTING-REMOVED`. Delete it from `compass.yml`.

### `living_spec`

9.0.0 removed the living spec, its archive and the command that merged a
base branch and re-derived them (ADR-091). No landing derives the spec. The key stays
valid, so a project that holds it keeps working, and nothing reads it.
`compass policy lint` names it with `L-SETTING-REMOVED`. Delete it from
`compass.yml`.

### Governance edits 9.0.0 removed

9.0.0 runs every new delivery issue on one four-stage path (ADR-092). A
project's `compass.yml` can no longer change these parts of the governance:

- `approaches`, the whole catalog;
- a legacy stage the path does not keep, under `stages`: `define`, `refine`,
  `plan`, `breakdown`, `implement` or `verify`;
- the caps rule set, `rules.caps`;
- a Definition of Ready check (`dor-summary-filled`, `dor-problem-traces-up`,
  `dor-behavior-is-gwt`, `dor-traceability-ids`, `dor-affected-surface-named`,
  `dor-no-open-questions`, `dor-approach-still-fits`), as an entry under
  `checks` or as an id in a gate's `checks` or a stage's `entry` or `exit`;
- the `require_phase` effect of `RP-FLOOR-002`, which forced the define stage
  to thorough; the path has no stage modes, and the floor keeps its skill.

A file that still holds one keeps working. Since 9.0.0 the whole catalog
key is a removed setting and is not read (ADR-094), so a `set:` on a stage the
check set does not declare stops no command, and its value is not checked.
`compass policy lint` names the key with `L-SETTING-REMOVED`. Delete it from
`compass.yml`.

An issue's stored generation keeps the configuration it was assessed with:
the 8.x approaches, stages, caps and lists. 9.0.0 ships no 8.x preset; the
`default@6` and `default@7` folders are test fixtures. Resolution reads only
the check set, whatever major
`extends:` names (decided 2026-10-30), so a project that extends
`compass:default@6` or `@7` gets the path; `compass policy lint` names
`extends:` with `L-SETTING-REMOVED`.

Three more rules keep an older file or issue working:

- An issue's `config:` that sets a legacy stage or a Definition of Ready
  check, or picks an 8.x approach (`approach:`), that its configuration does
  not hold was merged without it in 8.x, and named with `L-SETTING-REMOVED` on
  the issue layer by the issue mode of the 8.x `compass policy lint`, which
  9.0.0 removed. Over a stored generation that
  holds it, it is kept. 9.0.0 reads no new issue layer (ADR-094): the manifest's
  `config:` is not read, and `compass issue lint` warns about one that the
  issue's stored generation was not committed with.
- A gate a copy of the 9.0.0 governance files places at a
  legacy stage the configuration does not declare is read at the path stage
  that shows it (`define`, `refine`, `plan` at specify; `breakdown`,
  `implement` at build; `verify` at ship). `stages.assess` and `stages.ship` are path stages, so a
project can still change them. An `autonomy_checkpoints` table can name the
path stages `specify`, `build` and `ship` beside the legacy ones; an issue
assessed before 9.0.0 still waits only at the legacy hand-offs.

### `language`

The language the agent writes the project's prose in, as a BCP 47 tag:

```yaml
language: en-US
```

Unset means no instruction: Compass says nothing about language, and the
agent follows the repository's existing prose. When it is set, the session-start
hook adds one line that names the language. The setting does not apply to code identifiers.
The setting is read from the project's own settings file: `compass.yml`, or `.compass/config.yml` when `compass.yml` is
absent or has no `schema:`. A malformed value adds no line to a session.
`compass policy lint` refuses a malformed `language` key in `compass.yml`; it
does not check `.compass/config.yml`.
A project's own `CLAUDE.md` or `AGENTS.md` that names a language should drop
that sentence when `language` is set, and Compass never edits those files.

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
- Norwegian is `nb` or `nn` (`nb` is Bokmål and `nn` is Nynorsk). Do not write
  an unquoted `no`: YAML reads it as false, and Compass refuses it. Hebrew is
  `he`, not `iw`.


### `acceptance_strategy`

Turns the four-layer acceptance strategy (`S17`, `governance/strategies.md`)
off for the project, with the reason assess records:

```yaml
acceptance_strategy:
  state: "off"
  reason: "no deployable candidate yet"
```

Quote `"on"` and `"off"`: YAML reads them unquoted as true and false, which
Compass also accepts. Unset means on. `off` needs a reason that is not blank.
Any other value makes `compass approach evaluate` and `compass check` exit 2
with a message that names the key, the file and the accepted values, and
`compass policy lint` reports it in `compass.yml`. In a project pinned at
`compass:default@6` or `@7` the strategy never reads the value, but
`compass.yml` must still pass its schema check. `compass policy lint`,
`compass approach evaluate --write` and `compass check` on an issue not yet
assessed refuse a bad value there. `compass check` on an assessed issue reads
the configuration stored with the issue, so it does not refuse it. The
setting needs no
owner's approval: the manifest's `acceptance_strategy` block shows the choice. It takes effect for an issue at its next
`compass approach evaluate --write`; until then `compass check` reports the
changed setting as advice. The setting is read from `compass.yml`, or
`.compass/config.yml` when `compass.yml` is absent or has no `schema:`.

The check set holds the strategy, as the shipped default did from major 8. A project whose
`compass.yml` extends `compass:default@6` or `compass:default@7` does not get
it: assess stores no applicability and `compass check` adds no row for it. A
project with no `compass.yml` or no `extends:` runs on the check set and gets
it. The setting is the one way to turn the strategy off: no other setting can
suspend it on an approach that ships.

## Tighten-only settings

Compass runs one fixed set of checks (ADR-094). Five settings of
`compass.yml` can change what an issue owes, and each can only make it owe
more. No value removes a check, lowers a severity or narrows when a check
applies. Only the project's own `compass.yml` can hold them.

The resolver (`effective.resolve_live`) applies them to the check set with
`compass_pkg.tighten`, and `compass policy lint` and every generation commit
check them with `compass_pkg.settings_lint`. Each issue's `policy:` block
records the ones applied, as written (see `docs/generation-store.md`).

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
owe: the `G5` sign-off (`human-approval`), a person's approval of the
scenarios (`scenario-approval`), the architecture review and the standard
evidence row. The labels join the `when` of gate `G5`. An exploration issue
with one of them is refused, as for a shipped label. A shipped label cannot be
taken away.

### `require_evidence`

Each rule adds evidence tokens to a delivery issue whose assessment matches
`when`:

- `when` is a condition on the assessment, such as `risk: [critical]`,
  `size: {at_least: medium}`, `labels_any: [billing]` or `any_of: [...]`.
  Absent or empty, the rule applies to every delivery issue.
- `add` is one or more tokens of the closed set: `request`, `scenarios`,
  `red-before-green`, `suite-green`, `correctness`, `governance`,
  `traceability`, `regression`, `security`, `clarity`, `architecture`,
  `outer-loop`, `isolation`, `layering`, `definition-of-done`,
  `reproduce-first`, `scenario-approval`, `human-approval` and
  `ship-approval`. Every delivery issue already owes `request` and
  `ship-approval`, so a rule that adds either changes nothing.

The rules fire as `RP-SETTING-1`, `RP-SETTING-2` and so on, in file order. A
spike owes none of them, because it ships nothing.

### `agent_review`

`on` adds the check set's optional judged check `agent-review` at the entry
of `ship`, as advisory evidence (ADR-090 decision 7). See
`docs/judged-checks.md`. Write `on` or `true`; YAML reads an unquoted `on` as
`true`, and both are accepted. `off` and `false` are the default.

### `project_checks`

Each entry adds one blocking check and one guardrail, both under `id`, that
run `command` from the project root through the `command-passes`
implementation. Exit 0 passes.

- `id` must not be the id of a shipped check or gate, nor `agent-review`, nor a
  check Compass deleted (`check_registry.DELETED_CHECKS`). `compass check`
  refuses a project whose `project_checks` names a deleted check
  (`names-deleted-check`, `docs/waivers.md`).
- `stage` is `build` or `ship`.
- `when` is optional, in the form `require_evidence` uses.
- `compass check` runs the command only when `allow_project_commands` is
  `true` (see `docs/security.md`).

### `capabilities`

`entry-exit-evaluation: true` evaluates the Definition of Done items at the
end of `build` (`docs/entry-exit-evaluation.md`). `false` is the default and
changes nothing. Any other capability is refused, except
`artifact-freshness`, which 9.0.0 removed and which lint names with
`L-SETTING-REMOVED`.

### Removed settings and their replacements

`compass policy lint` names each removed key with what replaces it. One
table, `removed_parts.REPLACEMENTS`, holds the replacement of every removed
key, and the lint message and the `replacement` field of `--json` both come
from it (ADR-098 decision 7). The message ends with one of:

- "Replacement: `<setting>`." when a setting replaces the key;
- "Removed: nothing replaces it." when nothing does.

It then adds "`compass migrate` rewrites it." when `compass migrate` changes
the key for you. Otherwise, edit `compass.yml` by hand.

`compass migrate` reads the same table (`cli/compass_pkg/migrate_settings.py`):

- It deletes each key marked "rewrites it", and writes the setting that
  replaces it where the key held something a setting carries.
- It leaves each key marked "no" in the file, and names the edit.
- It leaves whole a rewritten key that holds a key marked "no", such as
  `rules:` with `rules.caps`.

It edits `compass.yml` line by line, so comments stay, and it writes nothing
unless this lint passes on the result. `docs/upgrade-9-0-0.md` lists each
conversion. `tests/test_migrate_settings.py` walks every row of the table.

`extends:` has a row for each pin of the shipped default:

- `extends@6` is a pin at `@6` or below, and `extends@7` a pin at `@7`. The
  pin keeps the acceptance strategy `S17` off, so `acceptance_strategy: off`
  replaces it.
- `extends@8` is a pin at `@8` or later, or no pin. Nothing replaces it.
- `extends` is any other value.

A key with `*` is an effect of any rule that picked a delivery approach.
`tests/test_lint_names_replacements.py` fails when a removed key has no row,
or when this table differs from `REPLACEMENTS`.

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

`compass_pkg.settings_lint.lint` reads `compass.yml` as a file of settings.
It gives each finding a code:

| Code | Level | When |
|---|---|---|
| `L-SETTING-UNKNOWN` | error | a key `compass.yml` cannot hold |
| `L-SETTING-INVALID` | error | a malformed value, or a tighten-only value that would not only add, such as a token outside the closed set, an extra field such as `remove:` or `severity:`, a project check that reuses a shipped id, or an assessment value the check set does not declare |
| `L-SETTING-REMOVED` | warning | a key 9.0.0 removed, read as if absent: the catalogs (`dimensions`, `stages`, `rules`, `checks`, `gates`, `vocabulary`, and the earlier `approaches`, `artifacts`, `readiness`), `extends: compass:...`, `preset`, `preset_index`, `approvers.project-waiver` and the removed settings above. The message names what replaces the key (see "Removed settings and their replacements" below) |
| `L-PARENT-REMOVED` | error | `extends:` names a git parent, which could hold checks this file does not show. Every command that resolves a policy refuses with exit 2 and says what to do: move the team's checks into the five settings above, or stay on 8.x until the 9.0.0 upgrade command (#359) |
| `L-IMPL-UNKNOWN` | error | the integrity rule: a check, after the settings apply, names an implementation the CLI does not hold |

The JSON Schema in `schemas/compass.schema.json` describes the same shapes. It
holds the settings above and nothing else, so an editor marks a removed
setting as one the file cannot hold. `settings_lint.schema()` generates it,
with the descriptions in `catalogue_spec.TOP_DESCRIPTIONS`, and
`tests/test_catalogue_spec.py` keeps the committed file equal to it.
