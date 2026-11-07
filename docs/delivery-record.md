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

In committed mode it also adds `delegations/`, `cache/`, `private/`, `current-task` and `interruptions.log` to `.compass/.gitignore`. A ship commit in committed mode stages both ignore files, so a clone skips the same files and neither file stays untracked. Exclude `.compass/work/` from formatters: a formatter that rewrites a record file changes a digest `trail.md` states.

## The landing in each mode

`compass ship-commit --issue <slug>` (and `compass quick-fix finish`, which calls it) stages the record itself. The agent never stages `.compass/` by hand.

In committed mode, when every gate of the issue has passed:

1. The refusals and the scope check run as before, and the staged code is checked against the newest green before anything is written.
2. One manifest save writes status `completed`, `land_timestamp` and `landed_with_record: true`, with the release line as before. It writes no `land_commit`: the manifest cannot hold the id of the commit that holds it. `landing.land_commit` reads that commit from git (`docs/github-links.md`).
3. It writes `trail.md`.
4. It completes the ignore files and stages the issue folder, the documents folder, `.compass/work/.gitignore` and `.compass/.gitignore`, each by its path. `git add` skips the files the ignore files name. A folder git ignores as a whole is not staged.
5. Right before each commit try, when a pre-commit step changed a file `trail.md` names, it writes `trail.md` again and stages it, and says so.
6. It commits. After the commit it compares each sum line of the committed `trail.md` with the file in the commit. A git hook that staged a change during the commit gets one line per file: "a git hook changed <path> during the commit; `trail.md` no longer matches it". The exit code does not change.
7. When no commit is made, the manifest and `trail.md` are put back and the record paths it staged are unstaged.
8. When a check after the commit fails (a hook put a path outside the scope in the commit, or changed an issue file after the green), the working manifest is put back as it was before the landing and `trail.md` is written again. The output says the commit holds a record that says the issue landed, and that `git reset --soft HEAD^` removes an unpushed commit. The exit code stays 2.

With nothing staged (every file the issue changed is committed already), committed mode commits the record alone, with the `-m` message: "landed at HEAD <id>; the record was committed as <new id>". That commit holds the same code as HEAD. The traced files under the issue folder and the documents folder, such as the acceptance criteria, need not be committed yet, because this commit stages them.

Only `--issue` lands the record. `compass ship-commit -m <message>` without it commits the staged code and writes no record. In committed mode, when the current issue's gates have all passed, it is not landed yet and a staged file is one it traces, the output ends with two lines: the record of the issue is not in this commit and the issue is not marked done, and the command that lands the record, `compass ship-commit --issue <slug> -m "<message>"`. The exit code stays 0, because the commit of the code stands.

In committed mode the scope of a ship commit holds the issue folder, the documents folder and both ignore files. In kept-out mode it holds neither the issue folder nor the ignore files, so a record path staged by hand is refused, and nothing under `.compass/` but `.compass/current-task` can ship. Kept-out mode lands as before: `land_commit` is written after the commit, then `trail.md`, so the trail names the commit.

When git ignores the issue folder and no setting chose the mode, ship prints one line that names the ignore rule. `record.commit: false` keeps the record out without the line.

## After the merge

The ship approval, the merge time and the merge commit come after the merge, so the merged commit cannot hold them (ADR-096). Until they are committed, the merged `trail.md` says the ship approval is read from the pull request after the merge.

1. `compass issue link set --pr <n> --issue <slug>` writes the merge fields and the `pr-approval` records (`docs/github-links.md`), then writes `trail.md` again, in both modes. In committed mode it writes no `land_commit`: git gives the land commit. Section 4 of the trail then names the merge commit as the commit to check the code lines at.
2. In committed mode, on a landed issue, it ends with `next: compass record commit --issue <slug>`. `compass next` names the same command while the issue folder holds a change git has not committed.
3. `compass record commit --issue <slug> [-m <message>]` writes `trail.md`, stages the issue folder, its documents folder and both ignore files (git skips the files they name), and commits them with the message "Record the merge of <slug>", or the `-m` message. Git's own hooks run; Compass runs no check of its own and calls no network. The person pushes the commit, in a pull request or not.

`compass record commit` refuses, and commits nothing, when:

- the record is kept out. It names the reason and says that `compass record sync` copies the record instead;
- a path outside the record is staged. It names the paths and writes and stages nothing;
- the record has no change.

In kept-out mode `issue link set --pr` moves `land_commit` to the merge commit as before, and `compass record sync` carries the merge fields.

## The trail

`compass trail --issue <slug>` writes `.compass/work/<slug>/trail.md`, one file a reviewer checks with `sha256sum -c` and without Compass (#356, ADR-096). It has six sections, in this order:

1. Who asked: the request link and the requester. The session records the requester as a claim; Compass does not check it.
2. What was agreed: the scenarios, the freeze at the first red, and the scenario sign-off where the issue owes one.
3. Red, for each scenario: each red record, or "no red on record".
4. Green: each green record, then the files as the newest green tested them.
5. Who approved, and by what authority: each approval record, each withdrawal and waiver, and when the ship approval is due if it is not on record.
6. What shipped: the landing, the pull request and the release line.

Under each statement are lines in `sha256sum` format, `<64 hex>  <path>`, with each path relative to the repository root. A statement with no evidence says so and has no sum line. From the repository root:

```
grep -E '^[0-9a-f]{64}  ' .compass/work/<slug>/trail.md | sha256sum -c -
```

The `-` makes the macOS `sha256sum` read the standard input; `shasum -a 256 -c` reads the same lines. Plain `sha256sum -c .compass/work/<slug>/trail.md` passes too, with a warning about the prose lines.

- Section 4 names each code and test file with the digest from the newest green record's `file_sha256`, not from the disk, so the check proves the committed code is the code that was tested. That line holds at the commit that holds this version of `trail.md`; a later change to the same file makes it fail at a later commit.
- The same record gives the same bytes. The file holds no time of its own writing, and a landing whose record is committed with the code (`landed_with_record`) names how to find its commit in git, not a commit id.
- Not hashed: `trail.md` itself, the red-time digests of the tests (they stay in the hashed red record), the files `.compass/work/.gitignore` keeps out, a delegation's `sha256` (a digest of canonical JSON, shown as text) and commit ids (git checks them).
- `compass trail --check` writes nothing. It exits 1 and names the first line that differs when the file is missing or out of date, and 0 when it matches. A command that writes the manifest after `trail.md` makes it out of date. `compass check` prints `Trail: up to date`, or that it is out of date, on an issue that has the file.
- A spike ships no code, so `compass trail` refuses it and writes nothing.
- The trail only reads records. It writes no approval, and the requester is never shown as one.
- `compass ship-commit` writes the trail at each landing, before the commit in committed mode and after the `land_commit` write in kept-out mode. `compass issue link set --pr` and `compass record commit` write it again (see "After the merge").

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
| `cli/compass_pkg/record.py` | `sync`, `restore`, `commit`, and the settings. |
| `cli/compass_pkg/record_mode.py` | The record mode, the ignore lines and the helper that appends them. |
| `cli/compass_pkg/trail.py` | `compass trail`: writes and checks `trail.md`. |
| `cli/compass_pkg/init_cmd.py` | `compass init` writes the ignore files. |
| `cli/compass_pkg/manifest.py` | `ship-commit`: the landing in each mode, the scope check, and the sync after a landing. |
| `cli/compass_pkg/committed_landing.py` | A committed landing: writes, stages and checks the record, and puts it back when no commit is made. |
| `cli/compass_pkg/quick_fix_cmd.py` | `quick-fix finish` lands through `ship-commit` and names no `.compass/` path to stage. |
