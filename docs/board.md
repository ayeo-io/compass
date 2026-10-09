# The delivery board page

`compass board render` writes the delivery board as one page and opens it in the browser. The page shows every issue in a lane for its stage and, for each open issue, why it has its delivery approach. This document owns the board commands and the modules behind them.

The page is advisory. Nothing the board does changes issue state.

## Commands

| Command | What it does |
|---|---|
| `compass board render` | Writes the page, prints its path and asks the default browser to open it once. |
| `compass board render --no-open` | Writes the page and prints its path. No browser is asked. |
| `compass board refresh` | Rewrites the page in place and prints its path. It says whether it created or refreshed the file. It never opens a browser. |
| `compass flow --html FILE` | Writes the same page to FILE. It is the page `compass board render --out FILE` writes. |

Both board commands take two options. A `refresh` does not remember the options of an earlier `render`.

| Option | Meaning |
|---|---|
| `--out FILE` | Write to FILE instead of the checkout's board file. |
| `--worktrees` | Also read the issues in this repository's other git worktrees. |

A command outside a Compass project refuses, as every other command does.

## Where the file goes

The default file is one stable file per checkout in the folder Python's `tempfile.gettempdir()` returns. Its name is `compass-board-<folder>-<8 hex digits>.html`:

- `<folder>` is the checkout root's folder name, with every character other than an ASCII letter, a digit, `-`, `_` or `.` replaced by `-`;
- the hex digits are the start of the SHA-256 of the checkout root's resolved path, so each worktree has its own file.

The system can clear its temp folder. `compass board refresh` creates the file again.

The default file is mode 0600. A file named with `--out`, and the page `compass flow --html` writes, are mode 0644.

### What the commands refuse

Every target passes the path guard before any manifest is read. The refusal names the command that ran, the target and the reason. Nothing is written. The guard refuses:

- a path inside `.compass/` or `docs/compass/`, which hold issue state, whether it is reached by a link or by a different letter case;
- a directory;
- a path in a folder that does not exist.

The default path has one more check. It is refused, with a message that suggests `--out`, when it already exists as a link, as something other than a regular file, or (where the system has `os.getuid`) as a file another user owns. On a shared temp folder another user can plant a link at a predictable name.

The page is written to a new file made exclusively in the same folder, with a fixed prefix that is not formed from the board file's name, and then moved into place. A link planted at a guessed temporary name is never followed, and no temporary file is left behind.

### When no browser opens

`render` asks the first browser the machine knows, once. With the `BROWSER` environment variable set, that is the command it names. If the browser reports that it could not open the file, the command says "Could not open a browser" and exits 0, because the file is written.

## What the page shows

- **Ten lanes**, in this order: `backlog`, `assess`, `define`, `refine`, `plan`, `breakdown`, `implement`, `verify`, `ship`, and "done, last 7 days". Each lane heading shows its count. Stage lane names are the names `compass` displays for the stages.
- **A card** for each placed issue: its slug, its delivery approach, its state word (backlog, ready, in-progress, in-review, or done with its close reason), its stage, and for issues under way its gate fraction. A card can also say "set aside" with the recorded reason, "blocked: <reason>", "stale evidence" and "recommendation". Blocked and stale cards also differ in border style, so the flags do not depend on colour.
- **The lane is the stage; the word on the card is the state.** The page says so in its legend. The backlog lane holds issues not yet assessed and issues set aside, whatever stage their records reached. Every other open issue sits in the lane of its current stage.
- **A panel** for each card, opened by selecting it. It shows the five assessment dimensions and the labels, each policy rule that fired with its rationale and changed lines, the depth of each stage with the current stage marked "current", each gate with its status, the manifest path and the tree, and the next command as text to copy. The page has no script, so the panel opens with a `:target` anchor.
- **A header** with the total, a count for each state, the blocked count, the stale evidence count, a count of done issues by close reason, the time the page was generated, the trees read and skipped, and a line saying the page is advisory.
- **An "unplaceable" note** that lists each folder the page cannot place, with its tree and the reason: a missing or unreadable manifest, a field of the wrong type, a stored status word Compass does not set, a done issue with no close reason, a `schema_version` major this Compass does not read, a `current_phase` that names no stage, and, with `--worktrees`, a folder in another tree that leads out of that tree.

The page holds no script, no form, no external resource and no web font. Every recorded value is escaped, and a Content-Security-Policy tag makes a browser refuse script and external loads even if escaping failed. The page is dark by default and follows a light preference, and the text colours meet a 4.5 to 1 contrast ratio in both.

## Worktrees

Without `--worktrees`, only this checkout is read. With it, the board lists the other trees with `git worktree list --porcelain` and reads their `.compass/work/` folders.

- A tree git marks prunable or bare, or whose folder is missing, is skipped. The header says how many trees were read and how many were skipped.
- Outside a git repository, or with git missing, the board reads this checkout and the header says why the worktrees could not be listed.
- A slug found in several trees shows once, from the copy whose `manifest.yml` was changed most recently. On a tie, this checkout wins, then the tree whose path sorts first. The card names its tree and says "also in N trees".
- A slug that is done in this checkout is read from this checkout only. Its copies in other trees are not statted. A slug that is open here is still compared with the copies elsewhere.
- Choosing a copy opens no manifest. Each chosen manifest is parsed once.
- Each issue is judged by its own tree: its gates and stage depths come from its manifest, its recommendation from its tree's documents, and its evidence is checked against its tree's files.
- A folder in another tree that is a link leading out of that tree is not followed. It is listed in the note.

The decisions behind this are in ADR-048 (reading issue state across worktrees, with the measurement).

### What `--worktrees` writes to git's object store

The board writes nothing to any tree's issue state. It does write to one place outside it.

The evidence check for an in-progress issue works out the hash of the files the issue's test record was made on. For an issue in another worktree it runs git there, with a copy of that worktree's index. `git add` and `git write-tree` can write loose objects, which are file contents and trees not already stored, to the repository's shared object store. Each tree's files, its real index, `HEAD`, refs and reflogs stay as they were, and the copy of the index is deleted.

`compass flow` makes the same writes for this checkout's in-progress issues. `git gc` removes unreferenced loose objects after its prune period. A version that writes nothing would run git against a temporary object directory with the real store as an alternate. That is a follow-up.

## The data behind the page

`board()` in `cli/compass_pkg/flow.py` builds the board data once. The text board, `compass flow --json` and the page all read it (ADR-046). It takes the issue folders as an argument, so a caller can give it this checkout's folders or folders from several trees.

`compass flow --json` is additive within a major version. The keys each kind of row gains, in addition to the ones it held in 6.0.0:

- **Every row in `in_progress`, `stale`, `in_review`, `ready`, `backlog`, `done_this_week` and `closed`** gains `lane`, `stage`, `gates`, `gate_list`, `assessment`, `policy_rules_fired`, `stage_depths`, `tree`, `manifest_path`, `also_in`, `created`, `set_aside`, `recommendation` and `unplaceable`. Of these, `stage` and `gates` were already on the `in_progress`, `stale` and `in_review` rows and keep their meaning.
- **`done_this_week` rows** also gain `close_reason`, which `closed` rows already held.
- **`other` rows** gain `tree`, `manifest_path`, `also_in` and `note`.
- **`unreadable` rows** gain `tree`, `manifest_path` and `also_in`.

No key is removed, renamed or retyped, and a test pins the full key set. A row the page cannot place stays in the section it had in 6.0.0 and carries an `unplaceable` reason.

## Modules

| Module | Owns |
|---|---|
| `cli/compass_pkg/board_cmd.py` | The `board` commands, the order of their steps, and `build_page`, which `compass flow --html` also calls. |
| `cli/compass_pkg/board_page.py` | The page: a pure function from board data to one HTML string. It reads no file, and all escaping is here. |
| `cli/compass_pkg/board_file.py` | The default path, the path guard, the check of the default path, and the safe write. |
| `cli/compass_pkg/board_trees.py` | Listing the worktrees and choosing one issue folder per slug. It opens no manifest. |

`cli/compass_pkg/flow.py` keeps the board data and the text board. The decisions behind the file are in ADR-047 (generated views are written to one stable file per checkout in the system temp folder).

## Release notes for the next minor release

A new command group makes the release a minor one. The 6.x release notes carry three items:

1. `compass flow --html` now writes the board page instead of tables. Anything that read the old tables must read the page, or `compass flow --json`.
2. `compass flow --json` rows gain keys. Section membership is unchanged.
3. A manifest that stores the retired breakdown mode `swarm` <!-- vocabulary-scan: allow - names the retired value the release note must show --> now reads as `multiagent`. The first save of such a manifest by any command writes `manifest.yml.v5.bak` beside it and prints a notice.
