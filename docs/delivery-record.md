# The delivery record

Compass keeps each issue's records out of the project's git history, so a public repository does not publish working notes. `compass record` keeps them in a second repository instead, so they survive the machine they were made on (ADR-031).

## Setting it up

Name the repository and the paths it holds in `compass.yml` at the project root, or in `.compass/config.yml` for a project that has no `compass.yml` (the CLI reads one file, `compass.yml` first):

```yaml
record:
  remote: https://github.com/<owner>/<project>-delivery-record.git
  paths:
    - .compass/work
    - docs/compass
```

The repository must be private: Compass cannot check that. A project with no `record:` is unchanged.

## What happens

- `compass record sync` copies the paths into a clone of the record repository, redacts credentials in text, and commits and pushes, naming the project's commit. It adds and updates files; without `--prune --apply` it deletes no content from the record (`--redact-existing` moves a file to its coded path), so a checkout that holds only part of the record loses nothing from it. With nothing changed it makes no commit.
- `compass record sync --prune` also deletes from the record every file this checkout does not hold, such as the records of issues landed from another worktree or machine. When it would delete any file, it gives the count and lists up to 20 of them, with rival names masked, commits and pushes nothing, and exits 2. `compass record sync --prune --apply` deletes them and names each deleted file, masked, in its output (up to 20) and in the record's commit message (all of them). `--apply` without `--prune` is refused. Run it only from a checkout that holds the whole record.
- From a linked worktree, which holds only part of the record, a full sync is refused. `ship-commit` there syncs just the landed issue's own folders.
- `ship-commit` runs the sync after every landing. If the sync fails for any reason, ship exits 2: the commit stands and the issue is landed, and `compass record sync` is the fix once the cause is fixed.
- `compass record restore` copies the record back into this project, such as a fresh clone. It refuses to overwrite a file that differs from the record unless `--force` is given. It refuses, even with `--force`, a generation file (`generations/<n>/resolved.yml` and the other stored files) that holds `[REDACTED]`, because the copy would make the generation broken. It copies nothing, names each file and says how to repair it. A `compass record sync` from a whole copy repairs the record, unless the file has a line shaped like a credential: a sync redacts that line again. Then the repair is to store a new generation with `compass approach evaluate --write`.

Where `.compass/work` is a record path, the record holds each manifest as it stands, so it carries the `checkpoint_outcomes` and the `usage` block of every issue, with the session ids and the cost, and the `approver` of every `checkpoint-approval` record. No transcript text, no transcript path and no summary file is added. A record that lists only `docs/compass` carries neither. `docs/autonomy-and-cost.md` owns those fields.

A record path must be a folder or file inside the project; `.`, `.git` and anything inside `.git` are refused. Symbolic links are not followed. Text that is not UTF-8 is copied as it is, without redaction.

Nothing in the record is trusted. A record that holds a symbolic link or a submodule entry is refused by sync and restore; a `.gitignore` in the record cannot hide files from a sync; the clone runs with LFS filters off, so a record cannot make git contact another server. A restore that finds nothing under the configured paths says so.

## Keeping rival names out of the record

A project that refers to other products by codes can set `record.names_key` to a key file inside the project, never committed. The key maps each code to the product's name, aliases and URLs.

- Sync replaces every name in copied text and paths with its code, then scans what it wrote. A file or path that still names a product stops the sync before anything is committed or pushed.
- The key is found from `COMPASS_RIVALS_KEY`, then the configured path, then the same path in the main checkout, so a ship from a linked worktree finds it.
- When the setting names a key that cannot be found, sync exits 2 and sends nothing.
- Sync scans a binary file's printable runs, as the tracked-tree gate does. A binary file pinned in `scripts/rival-name-binary-pins.txt` by blob hash and path is skipped there too; the path inside the record must match the pin. See `governance/decisions/2026-10-04-rival-names-never-committed.md`.
- Files already in the record from before the key was set, or before a product was added to it, are not refused. Sync says how many still name a product and lists up to five, with the names masked.
- `compass record sync --redact-existing` rewrites those files in place: names become codes in their text, and a file whose path names a product moves to its coded path. It deletes nothing. It leaves a file as it is when the coded path, or a folder on it, is already taken by another file, or when the file is binary with a name in its content. Sync then gives the count of files left and lists up to five, masked, to edit in the record repository by hand.
- `compass record restore` brings back the codes, not the names.

One record repository serves one project. The clone lives in the user's cache folder (`$XDG_CACHE_HOME/compass/record/`, or `~/.cache/compass/record/`), never inside the project, and a cached clone whose remote changed is replaced.

## Restoring onto a new machine

1. Clone the project.
2. Run `compass record restore` in it.

## Code

| File | Role |
|---|---|
| `cli/compass_pkg/record.py` | `sync`, `restore`, and the settings. |
| `cli/compass_pkg/manifest.py` | `ship-commit` runs the sync after a landing. |
