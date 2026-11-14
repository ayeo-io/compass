# Upgrading to 6.0.0: renamed words and commands

This page lists every word, key and command that 6.0.0 renames, what reads the old form until 9.0.0, and what to do. 6.0.0 has no supported rollback. The decisions are `architecture/decisions/ADR-044-vocabulary-and-cli-naming.md` and `architecture/decisions/ADR-045-the-issue-lifecycle-is-derived-from-records.md`.

## What to do

1. Update every checkout and every installed plugin together. Do not run a v5 CLI or plugin on a 6.0.0 tree.
2. Copy `.compass/work` to a folder outside the repository.
3. Run `compass issue migrate --apply --i-have-a-copy`. It rewrites every issue in one run. Without the flag it refuses with exit 2 when git does not track `.compass/work`.
4. Replace each old command spelling in your scripts (see "Commands").

## Words in a manifest, a policy or a flag

| Where | Old | New |
|---|---|---|
| Stage mode and artifact depth | `full` | `thorough` |
| Stage mode and artifact depth | `light` | `lightweight` |
| Stage mode and artifact depth | `full-plus-backfill` | `thorough-with-follow-up` |
| Size | `standard` | `medium` |
| Run stage (the stage flag of the headless runner, which 9.0.0 removed) | `build` | `implement` |
| Friction record key and flag | `phase`, `--phase` | `stage`, `--stage` |
| Stored issue status | `queued`, `parked` | `backlog` (a hold) |
| Stored issue status | `landed` | `done` with close reason `completed` |
| Stored issue status | `abandoned` | `done` with close reason `not-planned` |
| Stored issue status | `active` | not stored: the state is read from the records |

- The delivery approach `full` keeps its name.
- An issue's state is `backlog`, `ready`, `in-progress`, `in-review` or `done`. A person sets only `backlog` and `done`.
- A manifest is written at schema `3.0`. A 6.0.0 command reads schemas 1, 2 and 3. A v5 `check`, `issue lint`, `ci`, `gate pass`, `approach evaluate` and `approach summary` refuse a 3.0 file and exit 2. A v5 `next`, `flow`, `analyze`, `retro` and `issue dashboard` read it and exit 0, so they can read it wrongly, and `tdd-green` writes to it. Do not run a v5 CLI or plugin on a 6.0.0 tree: every checkout and plugin must be updated together.
- The first save of a manifest that holds old words writes the original to `manifest.yml.v5.bak` beside it, and prints one notice per rewritten word.
- A v5 `ship-commit` on a 6.0.0 tree does not read the new words, and drops the issue from the living spec.
- Configuration files (`compass.yml`, copied governance and `.compass/config.yml`) are read in their old words until 9.0.0. `compass policy migrate --words` rewrites a project's `compass.yml` and its policy-test fixtures. 9.0.0 removed the command (ADR-094).

## `compass flow --json`

| Removed key | New key |
|---|---|
| `held`, `next_up`, `landed_this_week`, `abandoned` | `backlog`, `ready`, `in_progress`, `in_review`, `done_this_week`, `closed` |

A `closed` entry carries its `close_reason`. The `counts` are keyed by the new states.

## Commands

6.0.0 renamed these 8 released spellings and kept each one as an alias. The 8 spellings were removed at 7.0.0: each now exits 2 with the parser's usual error. `docs/upgrade-7-0-0.md` ("What is removed") lists each removed spelling beside its new one. This table gives the new spelling as 6.0.0 named it.

| Old | New |
|---|---|
| `approach summary` | `approach show` |
| `issue set-status` | `issue status set`, or `issue status remove` for `active` |
| `policy review-rules` | `review-rule list` |
| `issue dashboard` | `issue dashboard render` |
| `issue artifact` | `issue artifact set` |
| `migrate` | `issue migrate` |
| `issue subtask update` | `issue subtask set` |
| `run --stage build` | `run --stage implement` |

- A spelling that no release held has no alias.
- `issue status remove` also reopens a closed issue. It removes `status`, `close_reason` and `duplicate_of`, keeps the land time and records a reason.
- A v5.6.0 script that ran `issue set-status active` on a landed issue exits 2. It must run `issue status remove`.

## Upgrade and rollback

- 6.0.0 offers no supported rollback. A problem is fixed in a later 6.0.x release.
- The first rewrite of each manifest keeps the original as `manifest.yml.v5.bak`. Restoring it discards everything recorded after that rewrite.
