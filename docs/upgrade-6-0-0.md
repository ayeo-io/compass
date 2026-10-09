# Upgrading to 6.0.0: renamed words and commands

This page lists every word, key and command that 6.0.0 renames, what reads the old form until 7.0.0, and how to roll back. The decisions behind it are in `architecture/decisions/ADR-044-vocabulary-and-cli-naming.md` and `architecture/decisions/ADR-045-the-issue-lifecycle-is-derived-from-records.md`.

## Words in a manifest, a policy or a flag

| Where | Old | New |
|---|---|---|
| Stage mode and artifact depth | `full` | `thorough` |
| Stage mode and artifact depth | `light` | `lightweight` |
| Stage mode and artifact depth | `full-plus-backfill` | `thorough-with-follow-up` |
| Size | `standard` | `medium` |
| Run stage (`compass run --stage`) | `build` | `implement` |
| Friction record key and flag | `phase`, `--phase` | `stage`, `--stage` |
| Stored issue status | `queued`, `parked` | `backlog` (a hold) |
| Stored issue status | `landed` | `done` with close reason `completed` |
| Stored issue status | `abandoned` | `done` with close reason `not-planned` |
| Stored issue status | `active` | not stored: the state is read from the records |

- The delivery approach `full` keeps its name. Only the stage mode and artifact depth words change.
- An issue's state is `backlog`, `ready`, `in-progress`, `in-review` or `done`. A person sets only `backlog` and `done`.
- A manifest is written at schema `3.0`. A 6.0.0 command reads schemas 1, 2 and 3. A v5 `check`, `issue lint`, `ci`, `gate pass`, `approach evaluate` and `approach summary` refuse a 3.0 file and exit 2. Other v5 commands do not: `next`, `flow`, `analyze`, `retro` and `issue dashboard` read it and exit 0, and `tdd-green` writes to it, so they can read it wrongly. Do not run a v5 CLI or plugin on a 6.0.0 tree: every checkout and plugin must be updated together.
- The first save of a manifest that holds old words writes the original to `manifest.yml.v5.bak` beside it. It prints one notice per rewritten word, and each notice names the issue.
- `compass issue migrate --apply` rewrites every issue in one run.
- Configuration files (`compass.yml`, copied governance and `.compass/config.yml`) are read in their old words until 7.0.0. A tool to rewrite them is owed before 7.0.0.

## `compass flow --json`

The keys `held`, `next_up`, `landed_this_week` and `abandoned` are removed. The board now has `backlog`, `ready`, `in_progress`, `in_review`, `done_this_week` and `closed`. A `closed` entry carries its `close_reason`. The `counts` are keyed by the new states.

## Commands

These released spellings keep working through an alias until 7.0.0. Each prints the new spelling on standard error. Standard output and the exit code are the new command's.

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

A spelling that no release held has no alias, and its unknown-command message names the new spelling.

`issue status remove` also reopens a closed issue, so a v5.6.0 script that ran `issue set-status active` on a landed issue keeps working. The reopening removes `status`, `close_reason` and `duplicate_of`, keeps the land time as history and records a reason.

## Upgrade and rollback

- Update every checkout and every installed plugin together.
- Do not run a v5 `ship-commit` on a 6.0.0 tree. It does not read the new words and drops the issue from the living spec.
- 6.0.0 offers no supported rollback. A problem is fixed forward in a 6.0.x release.
- The first rewrite of each manifest keeps the original as `manifest.yml.v5.bak`. Restoring it discards everything recorded after that rewrite.
