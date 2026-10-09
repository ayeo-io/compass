# Configuration

A project's settings: what each one does, its values, its default and which
file holds it. The Python reader is `cli/compass_pkg/project_settings.py`
(ADR-043). The pre-tool hook and the two multiagent scripts call it too, so
every reader of a setting follows the same file.

## Where the settings live

- **`compass.yml` at the project root** holds the settings, and from 6.0.0 it
  is the one file a person edits. The CLI reads it when it is Compass's file,
  and refuses a key that appears twice. It is Compass's file when it has a
  top-level `schema:` key, or when it is the only settings file. The same file
  can also hold the project's edits to the shipped governance (see
  `docs/policy-lint.md`). `/compass:init` writes a minimal one for a new
  project, and `compass policy migrate` writes one for an existing project.
- **`.compass/config.yml`** holds the same settings for a project from 5.x that
  has not moved. The CLI reads it when `compass.yml` is absent, or present
  without `schema:`, through 6.x. `compass policy migrate` moves its settings
  into `compass.yml`, and 7.0.0 stops reading it. In this file
  the adoption setting is called `mode`; in `compass.yml` it is called
  `adoption`. No 6.0.0 command writes this file.
- **The state file in `.compass/`** holds what the CLI writes, not what a
  person edits: `initialised` (what created the project, and when) and
  `records_signed_since`. Do not edit it. `compass init` writes this file and
  no other, so a new project has `.compass/state.yml` and no
  `.compass/config.yml`. A project created before ADR-043 keeps both values in
  `.compass/config.yml`, and the CLI and the hook read them there. `init` adds
  nothing to such a project, and `compass policy migrate` moves them to the
  state file.

### What a new project and an existing project get

| Project | Gets | Reads |
|---|---|---|
| New (no `.compass/`) | `compass init`, run by any entry point, creates `.compass/state.yml` and `.compass/work/`. `/compass:init` then writes a minimal `compass.yml` (`schema`, `extends`, `owner`, `project.name`, `project.test_command`) and copies nothing. | `compass.yml`, over the shipped default |
| From 5.x with a `.compass/config.yml` or copied governance | Nothing changes until it runs `compass policy migrate`. `/compass:init` runs that command (a dry run, then `--apply` on a yes) in place of writing a fresh file. | The old files, as 5.x did |
| This repository | A hand-written `compass.yml` that holds settings keys only, and `.compass/state.yml`. `compass policy migrate` refuses here, because the repository's governance files are generated from the shipped default. | `compass.yml` |

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
| has `schema:` | holds only `initialised`, `records_signed_since` or unread keys | `compass.yml` is read. |
| has no `schema:` | present | `.compass/config.yml` is read, and a warning on stderr says `compass.yml` is ignored. Add `schema:` if it is Compass's file. |
| only file | absent | `compass.yml` is read, with or without `schema:`. |

- **What counts as a settings key in the old file:** `mode`, `autonomy`,
  `allow_project_commands`, `enforcement`, `record`, `project`, `prices`,
  `multiagent`, `preset_index`, `governance_drift` and `github_labels`. The three keys the
  multiagent scripts read, `worktree_root`, `max_worktrees` and `test_command`,
  also count when they sit outside `multiagent:` and `project:`, because the
  scripts find them at any depth in the old file.
- **How the refusal shows.** The pre-tool hook exits 2 with `settings-conflict`
  for an edit to a path its built-in rules neither guard nor exempt. Each CLI
  command that reads settings stops with the same text, and `compass check`
  fails. The text names the keys, up to five and then "and N more".
- **The way out.** Move those keys into `compass.yml` (write `mode` as
  `adoption`) and delete them from `.compass/config.yml`. The text names no
  migration command, because `compass policy migrate` refuses a project that
  already has a `compass.yml` Compass reads.
- **A broken file.** A file that cannot be parsed is refused and named, in
  either position, as for a lone file. A `compass.yml` that cannot be parsed
  counts as Compass's file, so the old file cannot hide it.
- **The marker.** Every `compass.yml` that Compass creates carries `schema:`.
  `compass init` writes no `compass.yml`. `/compass:init` and
  `compass policy migrate` write a project's first one. `compass policy update`
  rewrites it, and `compass preset init` writes one inside the new preset
  folder it scaffolds.

## Settings

| Setting | What it does | Values | Default |
|---|---|---|---|
| `adoption` (`mode` in `.compass/config.yml`) | Whether a failed check blocks | `enforced`, `advisory` | `enforced` |
| `autonomy` | How often a session stops for a person | `controlled`, `balanced`, `autonomous` | `balanced` |
| `project` | The project's name and test commands | `name`, `test_command`, `test_micro_command`, `bdd_run_command` | none |
| `enforcement` | Extra paths the pre-tool hook guards | `code_globs`: a list of patterns | none |
| `record` | Where the delivery record is kept | `remote`, `paths`, `names_key` | no record |
| `prices` | Dollars per million tokens, to price a quick fix's usage | a mapping from model name | no cost recorded |
| `multiagent` | Where multiagent worktrees go | `worktree_root`, `max_worktrees` | `../.compass-worktrees`, 6 |
| `allow_project_commands` | Lets `compass check` run commands a project guardrail declares | `true`, `false` | `false` |
| `governance_drift` | Whether drift from the shipped governance fails | `advisory`, `strict` | `advisory` |
| `preset_index` | Reserved for published presets; no behaviour yet | - | - |
| `github_labels` | Whether Compass writes an issue's labels to its linked GitHub issue (see `docs/github-labels.md`) | `domain`, `status`: `true` or `false` each | both `false`; no GitHub call |

### `adoption`

- `enforced`: `compass check` and `compass ci` exit non-zero on any failure.
  The gate is real.
- `advisory`: `compass check` and `compass ci` report every failure clearly
  but exit 0, so CI does not fail. The pre-tool hook still refuses a code edit
  with no failing test on record.

Advisory mode suits piloting Compass without blocking delivery. A value other
than these two reads as `enforced`.

### `autonomy`

How often a session stops to wait for a person at a stage hand-off: confirming
the approach, and approving the acceptance criteria, the requirements review
and the technical design. The routing policy's `autonomy_checkpoints:` table
says which hand-offs wait for each value and delivery approach. `compass approach show`
shows the answer for an issue. No value changes a gate, evidence, the hook or
`compass check`.

- `controlled`: wait at every hand-off the table lists. That is all four on the
  regular or full approach, assess and define on a hotfix, and assess on a
  quick fix or spike.
- `balanced`: a quick fix does not stop. The regular approach waits at define
  and plan. The full approach waits at all four.
- `autonomous`: never wait. Every hand-off is shown and logged instead.

Any other value is refused, naming the file, because a typo that silently
changed how often a session stops would give no sign.

### `project`

- `name`: shown in artifact headers and the devlog.
- `test_command`: the command `compass tdd-red` and `compass tdd-green` run
  when none is given. Left empty, `tdd-red` and `tdd-green` need the command
  after `--`, and refuse without it. `scripts/integrate.sh` falls back to
  `npm test` or `make test` for the combined regression run.
- `test_micro_command`: used before `test_command` for those two commands.
- `bdd_run_command`: the command the `compass bdd` run step uses when none is given.

### `enforcement`

`code_globs` is a list of path patterns the pre-tool hook treats as code, in
addition to its own rules. A string instead of a list, or an unreadable file,
makes the hook refuse the edit, because it cannot tell whether the path is
guarded. The refusal (`config-invalid` in `docs/refusal-codes.md`) names the
file the hook read, `compass.yml` or `.compass/config.yml`.

The hook reads this setting for an edit to a path that its built-in rules
neither guard nor exempt, and only when the project has a settings file. A
project with neither file costs the hook no Python start for that edit. It
reads `initialised` only when it is about to refuse an edit, to say who
initialised the project.

### `multiagent`

`scripts/multiagent.sh` reads `worktree_root` and `max_worktrees`, and
`scripts/integrate.sh` reads `worktree_root` and `test_command` (under
`project`). In `compass.yml` they read `multiagent.worktree_root`,
`multiagent.max_worktrees` and `project.test_command` only, so a key of the
same name elsewhere is ignored. In `.compass/config.yml` they find a key by
its name at any depth, so a key under `multiagent:`, under an older heading or
at the top level all work. A missing key gives the default. A file the scripts
cannot read stops them with exit 1 and a message naming the file, because a
default would give a silent worktree cap or skip the combined regression run.

### `record`

`remote` names the record repository and `paths` lists the folders and files
`compass record sync` copies into it. `names_key` is an optional path inside
the project to a file of names that must not reach the record. See
`docs/delivery-record.md`.

### `allow_project_commands`

Project guardrails can declare a command. `compass check` runs one only when
the contribution is trusted and this setting is `true`. The setting is read
from the project's own file only, so a published preset cannot authorise its
own commands. See `docs/security.md`.

### `github_labels`

Two switches, both `false` unless set to `true`. With both off, no command
calls GitHub.

- `domain`: write the issue's declared domain labels to its linked GitHub
  issue.
- `status`: write `status:<state>` and, on a closed issue, `status:done` and
  `close:<reason>`.

Any other value, such as `"yes"`, reads as off. The setting is read from the
project's own file only. See `docs/github-labels.md` for the labels, the
limits and the failure behaviour.
