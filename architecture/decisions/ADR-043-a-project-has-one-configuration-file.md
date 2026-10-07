---
id: ADR-043
title: A project has one configuration file, compass.yml
status: accepted
date: 2026-10-06
supersedes: ''
superseded_by: ''
---

## Context

The maintainer accepted this record on 2026-10-06.

A project configures Compass in up to three places today:

- `governance/routing-policy.yml` and `governance/guardrails.yml`, copied whole when the project wants to change anything;
- `.compass/config.yml`, which `compass init` creates from `CONFIG_TEMPLATE` (`cli/compass_pkg/init_cmd.py:32-86`). The CLI reads these settings from it: the adoption setting `mode`, `autonomy`, `project`, `enforcement`, `record`, `prices`, `multiagent` and `allow_project_commands`.

`.compass/config.yml` also holds two values the CLI writes, not a person: `initialised` and `records_signed_since` (`init_cmd.py:68-76`). `ensure_initialised` writes the file for every project, because every entry point calls it (`init_cmd.py:118-141`). The hook reads `initialised` to explain its first refusal (`hooks/pre-tool.sh:648-658`). `red_first.signed_since` reads `records_signed_since` and treats a missing file as "no cutoff" (`cli/compass_pkg/red_first.py:98-100`).

The configurable-framework design adds a project overlay and, from a later release, a parent fetched from git. Each needs a home. On 6 October 2026 the maintainer set the principle that fewer configuration files are better.

## Decision

**A project has one file a person edits: `compass.yml` at the project root.** It holds the project's overlay and the settings that `.compass/config.yml` holds today. The project root is the first directory, walking up, that holds `.compass` or `.git` (`cli/compass_pkg/core.py:87`). A team or community preset is published in the same format.

**Settings keys are read from the project's own `compass.yml` only.** They are `autonomy`, `adoption`, `allow_project_commands`, `enforcement`, `record`, `project`, `prices`, `multiagent`, `governance_drift` and `preset_index`, which is reserved for published presets and has no behaviour yet. Lint rejects a settings key in a parent or a preset. `owner:` and `approvers:` are not settings keys: they are layer keys, allowed in a parent too (ADR-039). `autonomy` is also valid in the issue layer. A parent that could set `adoption: advisory` or `allow_project_commands: true` would loosen every project that extends it, and no classifier would see it.

**The pin of a git parent is the `#<sha>` suffix on `extends:`, and there is no lock file.** A form such as `github:<owner>/<repo>@<ref>#<sha>` names the parent's commit. The CLI refuses a remote ref with no sha, and a fetched commit that does not match the sha. `compass:default@<major>` carries no sha, because the CLI ships it.

**The CLI always writes the full 40-character sha.** It accepts a hand-written sha of 7 or more characters when it names one commit, and refuses one that is ambiguous (decided by jed72 on 6 October 2026).

**State the CLI writes lives in `state.yml` in `.compass/`.** It holds `initialised: {by, at}` and `records_signed_since`. `compass init` writes it, as it writes `.compass/config.yml` today. `compass init` writes no `compass.yml`: that file is configuration, so only `/compass:init` or `compass policy migrate` creates it (decided by jed72 on 6 October 2026).

**`allow_project_commands` moves into `compass.yml`** (decided by jed72 on 6 October 2026). Today the key sits apart from the checks it authorises, "because that file is the thing being constrained and a declaration should not be able to authorise itself" (`cli/compass_pkg/project_commands.py:31-33`). In `compass.yml` the declaration and the authorisation share a file. This is accepted for two reasons:

- the separation was never a security control: "the file is in the repository, so a contribution can set it" (`project_commands.py:35-38`);
- the trust decision still runs first. `compass check` calls `contribution_trust` before it reads the opt-in (`cli/compass_pkg/checks.py:1012-1031`, then `checks.py:1051`). `trust.py` reads only the process environment and the CI runner's event payload, and nothing inside the project (`cli/compass_pkg/trust.py:24-33`).

The key stays project-file-only, so a published preset cannot authorise its own commands.

**Amendment, 7 October 2026: which file counts when both exist.** The decision above does not say what happens when a project has both `compass.yml` and `.compass/config.yml`. It was made on the maintainer's behalf while they were away and stands until they reverse it.

- `compass.yml` is Compass's file when it has a top-level `schema:` key, or when it is the only settings file. A `compass.yml` with no `schema:` beside an old file is ignored with a warning on stderr, and the old file keeps guarding.
- When both files exist, `compass.yml` is Compass's file, and the old file still holds a settings key, the reader refuses. The hook exits 2 with the refusal code `settings-conflict`, each CLI command that reads settings stops with the same text, and `compass check` fails. A settings key is one of the keys listed above except `adoption`, plus `mode` (the old name of `adoption`), `governance_drift`, and `worktree_root`, `max_worktrees` and `test_command` when they sit outside `multiagent:` and `project:`. An old file that holds only `initialised`, `records_signed_since` or keys no code reads is not a conflict. The refusal text names the keys and the fix (move them into `compass.yml` and delete them from the old file), and names no migration command until one exists.
- `/compass:init` and `compass policy migrate` must write `schema:` into every `compass.yml` they create. Nothing writes one yet, because `compass init` writes no `compass.yml`.
- The reasons: ignoring an old file that sets `enforcement.code_globs` switches a guard off without a word, a file of another product with the same name must not switch Compass's guards off, and merging the two files would need a precedence rule for every key and would make two files count. No 5.6.0 project has a Compass `compass.yml`, so no working project starts to refuse by upgrading (ADR-006).

## Alternatives considered

- **A project overlay in `governance/` beside a separate `.compass/config.yml`.** Rejected: a person would edit two files with different rules, and every reader of settings would have to know which file holds which key. A copied `governance/` directory is also what the legacy adapter detects (ADR-042), so an overlay there would be easy to mistake for a copy.
- **A lock file with a content digest.** Rejected: a git commit sha already identifies the content, so a digest adds nothing. A second file can also disagree with `extends:`, and the CLI would need a rule for which one wins.
- **Write CLI state into `compass.yml`.** Rejected: the CLI would then rewrite a file a person edits on every `compass init`, and the file would mix configuration with facts about the project's history.
- **`compass init` writes nothing in place of `.compass/config.yml`.** Rejected: a new project would lose its signed-record cutoff, because `red_first.py:99-100` reads a missing file as no cutoff, and the hook would lose its explanation of where Compass came from.
- **Accept only the full 40-character sha.** Rejected: people copy short shas from git output, and refusing one that names exactly one commit adds friction without adding safety.

## Consequences

- Every reader of `.compass/config.yml` must move to one settings reader. That reader keeps reading the old file for a project with no `compass.yml`, until 7.0.0 (ADR-042). The readers include `core.py` (`load_mode`, `load_autonomy`), `tdd._read_config` (`cli/compass_pkg/tdd.py:209-217`), `red_first.py`, `record.py`, `quick_fix_cmd.py` and `hooks/pre-tool.sh`.
- `compass policy migrate` writes `compass.yml` from the old file and renames `mode` to `adoption` (ADR-041). It moves `initialised` and `records_signed_since` to `state.yml` in `.compass/`. It keeps the superseded files in `.compass/legacy/`.
- A hand-edited pin skips the waiver re-check that `compass policy update` does. `compass policy lint` closes that gap by comparing the pin in the working file with the pin at git `HEAD`.
- `docs/security.md` must record that the declaration and the authorisation share a file, and that the trust decision is the control.
- A key in `.compass/config.yml` that no code reads, such as `artifacts.work_dir` in this repository's file, is not copied. The migration lists it.

**Amendment, 7 October 2026: `governance_drift` is a settings key.** The list above left out `governance_drift`, which `docs/configuration.md` documents and `cli/compass_pkg/governance.py` reads. `SETTINGS_KEYS` now holds it, so a project layer accepts it in `compass.yml` and the loader splits it off as a setting. It is the only documented or read setting that was missing. The settings-conflict set does not change: `OLD_FILE_EXTRA_KEYS` now holds only `mode`.

## References

- ADR-006: backward compatibility is non-negotiable.
- ADR-041: the configuration vocabulary, amending ADR-012.
- ADR-042: shipped defaults live in a preset directory.
- `cli/compass_pkg/init_cmd.py`: `CONFIG_TEMPLATE` (lines 32-86) and `ensure_initialised` (lines 118-141).
- `cli/compass_pkg/project_commands.py` (lines 28-43) and `cli/compass_pkg/trust.py` (lines 9-34).
- `cli/compass_pkg/checks.py`: the trust decision before the opt-in (lines 1012-1051).
- `governance/decisions/2026-10-06-cli-state-lives-in-state-yml.md`, `governance/decisions/2026-10-06-allow-project-commands-moves-to-compass-yml.md` and `governance/decisions/2026-10-06-the-cli-writes-full-shas.md`: the ledger entries for the three product decisions.
