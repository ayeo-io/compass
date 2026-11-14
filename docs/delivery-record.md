# The delivery record

Each issue's folder, `.compass/work/<slug>/`, is its record. This page says
when the record is committed with the code, what `trail.md` holds, and how
`compass record` keeps a record in a second repository (ADR-031, ADR-096).

## The record mode

`record.commit` in `compass.yml` sets the mode. `docs/configuration.md` has
the full table.

| Settings | Mode |
|---|---|
| `record.commit: true`, or neither key set | Committed with the code |
| `record.commit: false` (valid with no `remote`) | Kept out |
| `record.remote` set, `record.commit` not set | Kept out |
| Committed, but the project is not a git work tree | Kept out |
| Committed, but git ignores the issue folder | Kept out |

Compass does not force-add an ignored folder and does not refuse the
landing. When git ignores the issue folder and no setting chose the mode,
ship prints one line that names the ignore rule.

`compass init` writes `.compass/work/.gitignore` in every project. It keeps
the files of one checkout out of a committed record:

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

In committed mode:

- `compass init` also adds `delegations/`, `cache/`, `private/`,
  `current-task` and `interruptions.log` to `.compass/.gitignore`.
- A ship commit stages both ignore files.
- Exclude `.compass/work/` from formatters. A formatter that rewrites a
  record file changes a digest that `trail.md` states.

## The landing in each mode

`compass ship-commit --issue <slug>` stages the record itself, and `compass
quick-fix finish` calls it. The agent never stages `.compass/` by hand.

| | Committed mode | Kept-out mode |
|---|---|---|
| Scope of the ship commit | The code, the issue folder, the documents folder and both ignore files | The code. A record path staged by hand is refused. Under `.compass/`, only `.compass/current-task` can ship. |
| `land_commit` | Not written. `landing.land_commit` reads the commit from git ([GitHub links](github-links.md)). | Written after the commit |
| `trail.md` | Written before the commit | Written after `land_commit`, so it names the commit |

In committed mode, when every gate has passed, `ship-commit --issue`:

1. Checks the scope, and the staged code against the newest green.
2. Saves the manifest: status `completed`, `land_timestamp`,
   `landed_with_record: true` and the release line.
3. Writes `trail.md`, and writes it again when a pre-commit step changes a
   file it names.
4. Stages the issue folder, the documents folder and both ignore files, each
   by its path. It does not stage a folder git ignores as a whole.
5. Commits, then compares each sum line of the committed `trail.md` with
   the file in the commit.

| Case | Result |
|---|---|
| A git hook changed a file during the commit | One line: "a git hook changed <path> during the commit; `trail.md` no longer matches it". The exit code does not change. |
| No commit is made | The manifest and `trail.md` are put back, and the record paths are unstaged. |
| A hook put a path outside the scope in the commit, or changed an issue file after the green | Exit 2. The working manifest is put back. The output says the commit holds a record of a landed issue, and that `git reset --soft HEAD^` removes an unpushed commit. |
| Nothing is staged, because the code is committed already | It commits the record alone with the `-m` message: "landed at HEAD <id>; the record was committed as <new id>". |
| No `--issue` | `compass ship-commit -m <message>` commits the staged code and writes no record. When the current issue's gates have passed and a staged file is one it traces, the output names `compass ship-commit --issue <slug> -m "<message>"`. Exit 0. |

## After the merge

The ship approval, the merge time and the merge commit come after the merge,
so the merged commit cannot hold them (ADR-096). Until then the merged
`trail.md` says the ship approval is read from the pull request.

1. Run `compass issue link set --pr <n> --issue <slug>`. It writes the merge
   fields and the `pr-approval` records ([GitHub links](github-links.md)),
   then `trail.md`, in both modes. Section 4 of the trail then names the
   merge commit.
2. In committed mode it ends with `next: compass record commit --issue
   <slug>`. `compass next` names the same command while the issue folder
   holds an uncommitted change.
3. Run `compass record commit --issue <slug> [-m <message>]`. It writes
   `trail.md` and commits the record with "Record the merge of <slug>" or
   the `-m` message. Git's hooks run. Compass runs no check and calls no
   network. You push the commit.

`compass record commit` refuses, and commits nothing, when:

- the record is kept out (it names the reason and `compass record sync`);
- a path outside the record is staged (it names the paths);
- the record has no change.

In kept-out mode `issue link set --pr` moves `land_commit` to the merge
commit, and `compass record sync` carries the merge fields.

## The trail

`compass trail --issue <slug>` writes `.compass/work/<slug>/trail.md`. A
reviewer checks it with `sha256sum -c`, without Compass. It has six
sections:

| Section | Holds |
|---|---|
| 1. Who asked | The request link, the requester, when they were recorded and the command that recorded them (`request.recorded_by`). The requester is a claim: Compass does not check it. |
| 2. What was agreed | The scenarios, the freeze at the first red, and the scenario sign-off where one is owed |
| 3. Red, for each scenario | Each red record, or "no red on record" |
| 4. Green | Each green record, then the files as the newest green tested them |
| 5. Who approved, and by what authority | Each approval, withdrawal and waiver, and when the ship approval is due if it is not on record |
| 6. What shipped | The landing, the pull request and the release line |

Under each statement are lines in `sha256sum` format, `<64 hex>  <path>`,
with paths relative to the repository root. A statement with no evidence
says so and has no sum line. From the repository root:

```
grep -E '^[0-9a-f]{64}  ' .compass/work/<slug>/trail.md | sha256sum -c -
```

`shasum -a 256 -c` reads the same lines. Plain `sha256sum -c <trail.md>`
passes too, with a warning about the prose lines.

- **Section 4 digests** come from the newest green record's `file_sha256`,
  not from the disk. The check shows that the committed code is the code
  that was tested. It holds at the commit that holds this `trail.md`; a
  later change to a file makes its line fail.
- **Same record, same bytes.** The file holds no time of its own writing.
- **Not hashed:** `trail.md` itself, the red-time digests of the tests, the
  files `.compass/work/.gitignore` keeps out, a delegation's `sha256` and
  commit ids.
- **`compass trail --check`** writes nothing. It exits 1 and names the first
  line that differs when the file is missing or out of date. A command that
  writes the manifest after `trail.md` makes it out of date. `compass check`
  prints `Trail: up to date`, or that it is not.
- **A spike** ships no code, so `compass trail` refuses it.
- The trail writes no approval and never shows the requester as one.
- `compass ship-commit`, `compass issue link set --pr` and `compass record
  commit` each write the trail.

## A record in a second repository

A project that keeps its record out can copy it to a second repository.
Name the repository and the paths in `compass.yml`, or in
`.compass/config.yml` for a project that has no `compass.yml`:

```yaml
record:
  remote: https://github.com/<owner>/<project>-delivery-record.git
  paths:
    - .compass/work
    - docs/compass
```

The repository must be private. Compass cannot check that. One record
repository serves one project.

| Command | Does |
|---|---|
| `compass record sync` | Copies the paths into a clone of the record repository, redacts credentials in text, commits and pushes. It deletes nothing. With no change it makes no commit. |
| `compass record sync --prune` | Counts the record files this checkout does not hold, lists up to 20 with rival names masked, commits nothing and exits 2. |
| `compass record sync --prune --apply` | Deletes those files and names each one in the commit message. Run it only from a checkout that holds the whole record. `--apply` without `--prune` is refused. |
| `compass record sync --redact-existing` | Rewrites record files that name a rival product (see below). |
| `compass record restore` | Copies the record back into this project, such as a fresh clone. |

Sync:

- `ship-commit` runs the sync after every landing. If the sync fails, ship
  exits 2, the commit stands and the issue is landed. Fix the cause, then
  run `compass record sync`.
- A full sync from a linked worktree is refused. `ship-commit` there syncs
  only the landed issue's folders.

Restore:

- It refuses to overwrite a file that differs from the record, unless you
  give `--force`.
- It refuses, even with `--force`, a generation file that holds
  `[REDACTED]`, and copies nothing. A `compass record sync` from a whole
  copy repairs the record. If the file has a line shaped like a credential,
  store a new generation with `compass approach evaluate --write`.
- A restore that finds nothing under the configured paths says so.
- On a new machine: clone the project, then run `compass record restore`.

Limits:

- A record path must be a folder or file inside the project. `.`, `.git`
  and anything inside `.git` are refused. Symbolic links are not followed.
- Text that is not UTF-8 is copied without redaction.
- Sync and restore refuse a record that holds a symbolic link or a submodule
  entry. A `.gitignore` in the record cannot hide files from a sync. The
  clone runs with LFS filters off.
- The clone lives in `$XDG_CACHE_HOME/compass/record/`, or
  `~/.cache/compass/record/`. A cached clone whose remote changed is
  replaced.
- Where `.compass/work` is a record path, the record holds each manifest:
  the `checkpoint_outcomes` of every issue, the `approver` of every
  `checkpoint-approval` record, and the `usage` block of an issue landed
  before 9.0.0. It holds no transcript text or path
  ([checkpoints](checkpoints.md)).

## Keeping rival names out of the record

Set `record.names_key` to a key file inside the project that is never
committed. The key maps each code to the product's name, aliases and URLs
(`governance/decisions/2026-10-04-rival-names-never-committed.md`).

- Sync replaces every name in copied text and paths with its code, then
  scans what it wrote. A file or path that still names a product stops the
  sync before any commit or push.
- Sync finds the key from `COMPASS_RIVALS_KEY`, then the configured path,
  then the same path in the main checkout. When it cannot find a configured
  key, it exits 2 and sends nothing.
- Sync scans the printable runs of a binary file. It skips a binary file
  pinned in `scripts/rival-name-binary-pins.txt` by blob hash and path.
- Sync does not refuse files that were in the record before the key covered
  them. It gives their count and lists up to five, masked.
- `compass record sync --redact-existing` rewrites those files: names become
  codes, and a file whose path names a product moves to its coded path. It
  deletes nothing. It leaves a file when the coded path is taken, or when a
  binary file has a name in its content. Edit those in the record repository
  by hand.
- `compass record restore` brings back the codes, not the names.

## Code

`cli/compass_pkg/record.py` (`sync`, `restore`, `commit`), `record_mode.py`
(the mode and the ignore lines), `trail.py`, `init_cmd.py` (the ignore
files), `manifest.py` (`ship-commit`), `committed_landing.py` and
`quick_fix_cmd.py`.
