---
id: ADR-047
title: Generated views are written to one stable file per checkout in the system temp folder
status: accepted
date: 2026-10-09
supersedes: ''
superseded_by: ''
---

## Context

`compass board render` writes a page a person opens in a browser. A person who runs the command again expects the same file, so a page that is already open can be refreshed in place.

The page is generated output. It must not be committed, and it must not sit where Compass keeps issue state. The guard that protects state already refuses a target inside `.compass/` or `docs/compass/`.

A shared temp folder lets another local user plant a link or a file at a name that is easy to predict. A stable name is exactly that.

## Decision

**A generated view is written to one stable file per checkout in the folder Python's `tempfile.gettempdir()` returns.**

- **Name.** `compass-board-<folder>-<8 hex digits>.html`. The folder is the checkout root's folder name with every character outside `A-Z a-z 0-9 . _ -` replaced by `-`. The hex digits are the start of the SHA-256 of the checkout root's resolved path, so two checkouts with one folder name differ, and each worktree has its own file.
- **Guard first.** Every target, default or named with `--out`, passes the path guard before any manifest is read. A temp folder inside `.compass/` is refused too.
- **Default path check.** Before a write, `os.lstat` examines the default path. A link, a file that is not regular, or (where `os.getuid` exists) a file owned by another user is refused. The message names the path and suggests `--out`.
- **Safe write.** The page goes to a file the system creates exclusively in the same folder, under a fixed prefix that is not formed from the board file's name, and `os.replace` moves it into place. A link swapped in after the check is replaced, not followed. No temporary file is left after a write, including a failed one.
- **Mode.** The default file is mode 0600. A file named with `--out`, and the page `compass flow --html` writes, are mode 0644, because the person chose where it goes.
- **One shared writer.** The write extends `atomic_io.atomic_write_text` once, with a `mode` and a `temp_prefix` argument that default to nothing. Every existing caller keeps its behaviour.
- **Refresh.** `compass board refresh` rewrites the file in place, and creates it if the system has cleared the temp folder.

This is the first file the CLI writes outside the project.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| A file in the project root | Easy to find. | Each project would need its own ignore rule, and a project could commit the page. |
| A file under `.compass/cache/` | Already untracked. | The guard refuses all of `.compass/`, so it needs an exception, and the exception weakens the guard that keeps issue state safe. |
| A timestamped file per run | No shared name to attack. | The temp folder fills, and a page that is already open cannot be refreshed. |
| A random name remembered in `.compass/` | Unpredictable. | It adds state to find a derived file. |
| A second safe-write routine for the board | No change to the shared writer. | Two routines for one job. The shared one is extended once. |

## Consequences

**Positive:**
- No project can commit the page.
- A planted link or another user's file at the default path is refused, and a planted temporary name is never followed.
- Refreshing a page that is already open needs no new path.

**Negative:**
- Up to one file per worktree stays in the temp folder until the system clears it.
- The stable name is what makes the file easy to find and also predictable. The checks keep the stable name; they do not remove the risk.

**Neutral / follow-on:**
- Where the system has no `os.getuid`, the owner check is skipped. The link and file-type checks still run.

## References

- ADR-005: state is reconstructible from disk, and a generated page is not state.
- ADR-036: the configuration code's atomic writes, which the board's write extends.
