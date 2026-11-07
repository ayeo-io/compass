# The delivery record

Each issue's folder (`.compass/work/<slug>/`) is its record. The record mode decides whether that folder is committed with the code or kept out of the project's git history (#356). A project that keeps its record out can use `compass record` to keep it in a second repository instead, so it survives the machine it was made on (ADR-031).

## The record mode

`record.commit` in `compass.yml` sets the mode; `record_mode.mode` decides it:

- `record.commit: false` keeps the record out.
- A project that names `record.remote` and does not set `record.commit` keeps the record out: it chose a separate record store, so an upgrade does not start committing its records.
- Otherwise the record is committed: `record.commit: true`, or neither key set.
- A committed record is kept out after all when the project is not a git work tree, or when git ignores the issue folder. The reason names the ignore rule. Compass does not force-add the folder and does not refuse the landing.

`record: {commit: false}` is valid with no `remote`. `docs/configuration.md` gives the full table and the reasons.

`compass init` writes `.compass/work/.gitignore` in every project, so a committed record leaves out the files that belong to one checkout:

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

In committed mode it also adds `delegations/`, `cache/`, `private/`, `current-task` and `interruptions.log` to `.compass/.gitignore`. A ship commit can hold both ignore files. Nothing stages the record yet: `compass ship-commit` lands as before in both modes.

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

Where `.compass/work` is a record path, the record holds each manifest as it stands, so it carries the `checkpoint_outcomes` of every issue and the `approver` of every `checkpoint-approval` record. An issue landed before 9.0.0 can also hold a `usage` block, with session ids and token counts; 9.0.0 writes none (ADR-093). No transcript text, no transcript path and no summary file is added. A record that lists only `docs/compass` carries neither. `docs/checkpoints.md` owns those fields.

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
| `cli/compass_pkg/record_mode.py` | The record mode, the ignore lines and the helper that appends them. |
| `cli/compass_pkg/init_cmd.py` | `compass init` writes the ignore files. |
| `cli/compass_pkg/manifest.py` | `ship-commit` runs the sync after a landing. |
