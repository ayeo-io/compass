---
id: ADR-078
title: A Bash call is judged by the worktree its working folder is in
status: accepted
date: 2026-10-30
supersedes: ''
superseded_by: ''
---

Decided for bash-follows-worktree-cwd on 2026-10-30, from ayeo-io/compass-delivery#337, where a builder in a worktree had its shell writes judged by the main checkout's issue. This record amends ADR-074 decisions 1 and 8. jed72 accepted it on 2026-10-30, and kept the session's verdict for a command that can change folder.

## Context

ADR-074 judges an Edit or Write by the issue of the tree that holds the edited path. Its decision 1 said a Bash call always takes the session's project, and decision 8 documented that gap instead of fixing it, because a Bash call names no file the hook could resolve from.

A subagent started with worktree isolation keeps the parent session's `CLAUDE_PROJECT_DIR`. Every shell write it made was judged by the main checkout's pointer: it was refused, or allowed, on the red records of an issue it was not working on, and told to record a red for that other issue. The Bash input from Claude Code carries `cwd`, the folder the call runs in, which names the worktree.

## Decision

1. **A Bash call starts from its working folder.** The hook reads `cwd` and walks up to the nearest `.compass/` folder, bounded by `.git`, as for an Edit. When that tree is foreign (ADR-074 decision 1) and tied to the session's repository (decision 5), it is the project for the call, and ADR-074 decisions 2, 3, 4 and 6 apply to it unchanged.
2. **Every other call keeps the session's project.** A `cwd` that is missing, relative or not a folder, a tree with no `.compass/` folder, the session's own project, and a tree that is not tied to the session's repository all give the verdict they gave before. An untied tree is not refused, because the old verdict judges the targets against the session's project and opens no gap.
3. **A target outside the worktree is judged first, against the session.** Before the targets are judged against the worktree, each target that lands outside it is judged against the session's project: an absolute path, and a relative path read against the worktree that climbs out with `..`. A path with a part the hook cannot know (`~`, a variable it does not expand, a backtick or a brace) is judged unchanged against the session's project, because it may name any folder. A command that can change its folder has every target judged against the session's project first, as before this decision, because the folder its relative targets are read against is unknown. The hook matches these in the command text: `cd` (also quoted), `pushd`, `popd`, a `chdir` call in an inline script, `env -C`, `sudo -D` or `--chdir`, `ruby -C`, `find -execdir`, and `patch -d` or `--directory`. A `patch` or `git apply`, whose targets are inside the diff, is judged by the worktree's issue unless the command can change folder, and then by the session's. When one of these targets needs a failing test, the session's issue judges the call, with the session's rules (`COMPASS_ISSUE`, the pointer, `pointer-moved`). So no write the hook checked before goes unchecked.
4. **`no-red-on-record` names the project** whose issue judged the write.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| Use the hook process's own working folder when the input has no `cwd` | Covers a runtime that omits `cwd` | The process folder is not the call's folder in every runtime; an existing test runs the hook in a worktree with no `cwd` and expects the session's verdict |
| Refuse a call whose working folder is in an untied tree | Matches the Edit rule (`tree-not-tied`) | New refusals for a case nobody reported, and the old verdict is not a gap |
| Judge the worktree first, and the session only when nothing in the worktree is guarded | One pass in the common case | A command that writes in both trees would be judged by the worktree alone, so a write into the main checkout could pass on the worktree's red |
| Judge each target by the tree that holds it | Also covers an absolute path into a worktree from the main checkout | One hook call judges one issue; this needs the issue checks per target. It stays the open follow-up of ADR-074 |
| Follow a `cd` inside the command | The reported command started with `cd` | Tracking the folder through `&&`, `;`, `||`, subshells and `pushd` is not small, and a mistake makes a production write look outside the project, which allows it |
| Judge a folder-changing command by the worktree alone | The reported `cd <scratch> && sed ...` would then name the worktree's issue | `cd <main checkout> && echo x > <relative production file>` from a worktree would write the main checkout's file on the worktree's red |
| Ask for both issues' reds on a folder-changing command | Strictest | One hook call judges one issue; the session's verdict alone is what the hook gave before |

## Consequences

**Positive:**
- A builder in a worktree is judged by its own issue for Bash, Edit and Write alike.
- The refusal says which tree's issue judged the write, so `compass tdd-red` is run in the right place.

**Negative:**
- Every Bash call from a worktree, read-only ones included, starts the two `git` processes of the tie check and one more `jq` read.
- A command from a worktree whose text names a folder change, or a target with a part the hook cannot know, is judged by the session's issue, as before this decision.
- A folder inside the repository with its own `.compass/`, such as an example project, is a tied foreign tree: a Bash call that runs there is judged by that folder's issue, as an Edit of a file there already is.
- A command that writes guarded files in both the worktree and the main checkout is judged by the session's issue alone.
- A command that changes folder is judged as before, by the session's project, so the reported `cd <scratch> && sed ...` from a worktree still names the main checkout's issue. An absolute path into a worktree from the main checkout is still judged by the main checkout's project.

## References

- ADR-074 (amended), ADR-005, ADR-063.
- `docs/safety-contract.md` states the rule and its limits; `docs/refusal-codes.md` holds the refusal text.
