# Repository readiness

`compass readiness` measures whether a repository is fit for unattended agent
work. It checks a set of binary readiness signals, prints one line per signal,
the score and whether the readiness floor is met, and writes the readiness
record, `.compass/readiness.yml`. This doc owns the command, the signals, the
project commands it runs, the record and its freshness rules.

The decisions behind it are in ADR-058 to ADR-061 under
`architecture/decisions/`.

## The command

```text
compass readiness [--json] [--fix-list]
```

- **No option:** measure, write the record, and print one line per signal
  (present or absent, with the reason), then the score and the floor.
- **`--json`:** the same run. The output is the record with `score`, `of`,
  `floor_met`, `below_floor` and `path` added.
- **`--fix-list`:** read a fresh record and print a checklist, one
  `- [ ] <signal>: <change> (<file>)` item per absent signal. The signals on
  the floor come first, then the higher weight, then the catalog order. It
  runs nothing and writes nothing. With no fresh record it prints the readiness
  line and asks for `compass readiness`.

The command exits 0 for any measured result, a project below the floor
included. It exits 2 only for an error, such as a project key that is not a
string; then it writes no record.

## The signals

A readiness signal is one entry of the `readiness` catalog. The default
preset ships eleven in `governance/presets/default/readiness.yml`. A project
layer in `compass.yml` can add, change or remove one, as for any catalog;
taking a signal off the floor needs the owner's waiver in that entry.

Each signal names an implementation, registered with a version in
`cli/compass_pkg/readiness_registry.py`. Its result is `present` or `absent`,
with a one-line reason. Nothing else is a result.

| Signal | Present when | Floor |
|---|---|---|
| `agent-instructions-present` | `AGENTS.md` or `CLAUDE.md` is at the repository root | yes |
| `build-declared-and-succeeds` | `project.build_command` is declared and exits 0 | yes |
| `tests-declared-and-under-two-minutes` | the timed test command is declared and passes within two minutes | yes |
| `lint-declared-and-clean` | `project.lint_command` is declared and exits 0 | yes |
| `typecheck-declared-and-clean` | `project.typecheck_command` is declared and exits 0 | no |
| `format-declared-and-clean` | `project.format_check_command` is declared and exits 0 | no |
| `no-flaky-tests-on-record` | no scenario's last two green records disagree, and no green record carries `rerun_without_change: true` | no |
| `structured-logging-declared` | `project.structured_logging` is a non-empty string | no |
| `secret-scan-declared` | `project.secret_scan` is a non-empty string | no |
| `codeowners-present` | a `CODEOWNERS` file is at the root or in `.github/`, `docs/` or `.gitlab/` | no |
| `pre-commit-hooks-present` | `.pre-commit-config.yaml` (or `.yml`), `lefthook.yml` (or `lefthook.yaml`, `.lefthook.yml`) or `.husky/pre-commit` is in the repository | no |

- **The score** counts the present signals: "9 of 11 signals". `weight` only
  orders the fix list.
- **The readiness floor** is met when every signal with
  `required_for_autonomous: true` is present.
- **The timed test command** is `project.test_command`, unless a project layer
  sets the test signal's `command` parameter to `test_micro_command`:

  ```yaml
  readiness:
    tests-declared-and-under-two-minutes:
      set: {params: {set: {command: test_micro_command}}}
  ```

  Write it in map form, as above. The inner `set:` changes `command` and keeps
  the shipped `limit_seconds`. A plain map, `set: {params: {command: ...}}`,
  replaces the whole `params` map and drops the limit, and the write-time lint
  refuses it as `C-INCOMPARABLE`. In the readiness registry,
  `tests-under-limit.command` has the direction `equivalent`: a swap between
  its two choices, `test_command` and `test_micro_command`, classifies as
  equivalent and needs no waiver. `compass policy diff` names the swap on its
  own line (governance decision
  2026-10-14-a-declared-equivalent-parameter-choice-classifies-as-equivalent).

- **The flaky-test signal** reads the green records under
  `.compass/work/<issue>/evidence/`. `compass tdd-green` keeps one record per
  scenario, so the re-run marker is the sign it usually finds. The reason names
  the issue and the scenario.
- **No signal reads anything outside the repository.** Branch protection and
  secret scanning are declarations, not API calls. A declared command can still
  make a network call; Compass makes none itself.

## Project commands

Five signals run a command the project declares: build, tests, lint, type
check and format check.

**Permission.** `project_commands.command_permission` decides, once per run,
in the order `command-passes` uses (see `docs/security.md`):

1. the contribution trust decision, from the CI runner's environment only. An
   untrusted contribution, or an unknown one on CI, is refused, and
   `allow_project_commands` is not read;
2. the `allow_project_commands` opt-in.

A refused command is a result, not an error. Each command signal is absent
with "not run: project commands are disabled - set `allow_project_commands:
true` in compass.yml", or with the trust reason. No worktree is made. A
command the project does not declare is absent with the key to declare, and
needs no permission.

**The temporary worktree.** Every command runs in one detached `git worktree
add` of HEAD in the system temp folder, named
`compass-readiness-<process id>-<random>`.

- It is outside `multiagent.worktree_root` and not counted against
  `max_worktrees`.
- It holds no ignored or uncommitted file. A command that needs installed
  dependencies or a `.env` file must set them up itself; the reason of a failed
  command says it ran in a clean checkout of HEAD.
- Whatever a command writes is removed with the worktree, so the working tree
  never changes.
- It is removed in a `finally` block with `git worktree remove --force`, then
  `git worktree prune`.
- Each run first removes any `compass-readiness-` worktree whose process id is
  no longer alive, which is what a killed run leaves. It never removes one
  whose process is alive, because that run may still be going on in another
  checkout of the same repository.
- A repository with no commit has no HEAD to check out; each command signal is
  absent with `not_run: no-checkout`.

**The time budget.** A run finishes within 300 seconds.

- The project commands share 270 seconds, one at a time, in this order: build,
  then tests, then lint, then type check, then format check. The floor's
  commands go first.
- The timed test command also stops at two minutes (its `limit_seconds`
  parameter); its signal is then absent with "over two minutes".
- A command still running when the budget ends is absent with "ran over the
  time limit", and the output names it. A command not started by then is
  absent with "not run: the time limit was reached".
- Each command starts in a new session. When the wait for a command ends, its
  whole process group is sent SIGTERM, then SIGKILL two seconds later, so a
  child process cannot outlive the run. This happens when the command exits,
  when it reaches its limit, when the run is interrupted (Ctrl-C or SIGTERM)
  and when an error is raised. The group is stopped before the temporary
  worktree is removed.
- `COMPASS_READINESS_BUDGET_SECONDS` lowers the 270 seconds, never raises them,
  and only tests set it. A value that is not a positive number is ignored with
  a warning.

## The readiness record

`.compass/readiness.yml` holds:

- `schema: 1`, `measured_at` (UTC) and `head`, the commit measured;
- `settings`: the path and digest of the settings file read (`compass.yml`, or
  `.compass/config.yml` in a project without one; both null with neither);
- `catalog_digest`: the digest of the readiness catalog this CLI ships (the record also holds
  the old key `catalogue_digest` with the same value, until 8.0.0);
- `budget`: the command seconds and the seconds the run used;
- `signals`: each signal's `id`, `impl`, `version`, `weight`,
  `required_for_autonomous`, `result`, `reason` and `not_run`, and for an
  absent signal its `fix` (`change` and `file`). A command signal also holds
  `key` and `command`; the test signal holds `duration_seconds`.

`not_run` is `undeclared`, `disabled`, `untrusted`, `budget`, `no-checkout`, or
null when the command ran or the signal runs none.
`schemas/readiness-record.schema.json` describes the file.

The record is per-checkout state. Compass never commits it; add
`/.compass/readiness.yml` to `.gitignore`. It is a plain file a person can
edit, like the project commands themselves.

## Fresh and stale

`cli/compass_pkg/readiness_record.py` is the one reader. A record is fresh when
all of these hold, tested in this order:

1. the settings file has the digest the record holds;
2. the shipped catalog has the digest the record holds, and every recorded
   implementation version is the one this CLI ships;
3. `measured_at` is at most seven days before now, and not after now;
4. the recorded commit exists, and is in HEAD's history
   (`git merge-base --is-ancestor <recorded> HEAD`), so a record measured on
   another branch is stale after a branch switch;
5. HEAD is at most 25 commits past the recorded commit
   (`git rev-list --count <recorded>..HEAD`).

Without Git history only the first three apply; a record with no commit, read
where history now exists, is stale. The reason of a stale record names the
first rule that failed. A missing record is "not measured", and one that
cannot be read or parsed is "unreadable".

A layer change is a change of the settings file, and a preset change is a
change of the shipped catalog, so freshness needs neither the layer chain
nor the check implementations. The module imports only the standard library,
the YAML reader, `project_settings` and `readiness_registry`, so the
session-start hook can import it cheaply; a test pins that list.

## The readiness summary and line

`readiness_record.summary` gives the readiness summary of a checkout:

```yaml
{status: measured, score: 9, signals: 11, floor_met: true,
 absent: [codeowners-present, secret-scan-declared], measured_at: '2026-10-13T10:00:00Z'}
# or
{status: not-measured, reason: stale, detail: compass.yml changed since the record was written}
```

`reason` is `missing`, `stale` or `unreadable`. `readiness_record.line` turns
a summary into the one line every reader shows:

```text
Repository readiness: 9 of 11 signals, floor met
Repository readiness: 3 of 11 signals, floor not met
Repository readiness: not measured (record stale: compass.yml changed since the record was written)
```

`readiness_record.hook_line` gives the session-start warning: empty unless
`autonomy` is `autonomous` and the floor is not met or the record is not
fresh. The warning says assess will refuse autonomous work until the absent
signals are present or `autonomy` changes, or names `compass readiness` when
the record is missing, stale or unreadable. `hooks/session-start.sh` adds it
after the contract, inside its own guard, and never blocks.

## The floor at assess

`compass approach evaluate --write` reads the record through the same module
and refuses an issue on `autonomous` (ADR-058), with exit 2 and before it
prints or writes anything, when:

- the CI runner reports an untrusted contribution (read from the environment
  first, so a committed record cannot clear it);
- the record is missing, stale or unreadable;
- the record was measured for an untrusted contribution; or
- a signal on the floor is absent. The message names each one with its
  `fix`.

Every refusal names `autonomy` as the setting to change; `balanced` and
`controlled` are never refused. Every `--write` writes the summary into the
manifest's `readiness:` key, outside the generation (`docs/generation-store.md`).
`governance/routing-policy.md` describes the refusal with the other routing
behavior.

## Modules

| Module | What it does |
|---|---|
| `cli/compass_pkg/readiness_cmd.py` | the verb: plan, permission, run, decide, write, print |
| `cli/compass_pkg/readiness_signals.py` | one function per implementation |
| `cli/compass_pkg/readiness_run.py` | the temporary worktree, the order, the budget and the process-group stop |
| `cli/compass_pkg/readiness_record.py` | the record: read, write, freshness, summary and line |
| `cli/compass_pkg/readiness_registry.py` | the implementations and their versions |
| `cli/compass_pkg/readiness_catalogue.py` | the catalog in force and the floor |
