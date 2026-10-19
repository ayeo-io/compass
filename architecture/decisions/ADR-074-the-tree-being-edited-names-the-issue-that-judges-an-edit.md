---
id: ADR-074
title: The tree being edited names the issue that judges an edit
status: accepted
date: 2026-10-19
supersedes: ''
superseded_by: ''
---

Decided for worktree-issue-from-edited-path on 2026-10-19, from GitHub issues #216 and #58, where builders in sibling worktrees were refused for an issue that was not theirs.

## Context

The pre-tool hook finds the project of an Edit or Write from the path the call names. It then chose the issue from the session: `COMPASS_ISSUE` first, then the project's pointer, then the most recently changed issue. For a session that edits a sibling git worktree, this judged the edit by the session's issue and the worktree's failing test was never read. A copy of the session table in the worktree also raised `pointer-moved` for a move the session did not see.

Four earlier decisions bound the answer:

- ADR-005: state lives in the tree it describes, so the worktree's pointer is the truth for the worktree.
- ADR-006: a session with no Compass project behaves as before, and an older record keeps working.
- ADR-048: a tree can hold thousands of issue folders that are copies, so a guess by modification time is arbitrary there.
- ADR-063: the session record names the issue that judged the edit.

## Decision

1. **A project is foreign when its real path differs from the session's Compass project.** The session's project is the Compass root found by walking up from `CLAUDE_PROJECT_DIR`, so a session started in a sub-folder is not foreign. When the project's path text equals `CLAUDE_PROJECT_DIR`, nothing else runs. A Bash call always takes this path.
2. **In a foreign project the pointer decides.** A pointer that names anything is not empty. If its folder exists that is the issue; if not, the hook refuses with `bad-session-issue`. `COMPASS_ISSUE` applies only to an empty pointer, and only when its folder exists in that tree.
3. **A foreign project never uses the most-recently-changed guess.** A foreign project with a `.compass/` folder and no issue to name refuses. A tree with no `.compass/` folder is left alone, as before.
4. **The lease is skipped for a foreign project.** `pointer-moved` applies in the session's own project. A visiting session neither reads nor writes the foreign tree's session table.
5. **A foreign tree must be tied to the session's repository.** `git rev-parse --git-common-dir` is run in the edited tree and in the session's project. The trees are tied when both succeed and the real paths are equal. Any other result refuses with `bad-session-issue`. The result is cached for the hook call. This is a consistency check, not a defence against a forged `.git` file.
6. **The session record follows the same selection.** For a foreign project the session is recorded on the issue that judges the edit, with `via=tree`.
7. **A record in the session table carries the real path of the Compass folder it was written in.** A record with no root, or another root, is ignored. This part is built by the subtask that owns the session table.
8. **Bash is documented, not fixed.** A shell write still resolves from the session's project. The safety contract states the gap, and GitHub issue #104 stays open for it.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| Compare the edited project with `CLAUDE_PROJECT_DIR` as text | No process is started | A symbolic link or a session started in a sub-folder looks foreign |
| Treat every Compass tree as foreign when the session has no Compass project | The guard would be stricter | The hook runs in every repository, and such a session has no issue to borrow, so people would be refused for no gain |
| Keep the variable first in a foreign project | No change to the order | It is the reported fault |
| Treat a pointer to a missing issue as empty | A worktree then falls back to the variable | The variable would judge the edit by an issue the worktree does not point at |
| Keep the most-recently-changed guess in a foreign tree | Matches the own project | The newest folder is arbitrary there (ADR-048) and its red would unlock the edit |
| Tie the tree by a path prefix | No `git` call | The default worktree root is outside the project |
| Read `.git` and `commondir` in shell | No `git` call | It repeats git's layout rules and cannot see that git would refuse the tree |

## Consequences

**Positive:**
- A builder in a sibling worktree is judged by that worktree's issue and failing test.
- The guard stays closed: no borrowed, guessed or cross-repository issue allows an edit.

**Negative:**
- A foreign edit starts at most two `git` processes, and the hook depends on `git` for them.
- A worktree with no pointer and no `COMPASS_ISSUE` refuses until `compass issue use <slug>` is run there.
- A move made by another session inside a worktree is not reported to a visiting session.
- A shell write in a worktree is still judged by the session's issue.

## References

- ADR-005, ADR-006, ADR-048, ADR-063.
- `docs/safety-contract.md` states the rule and the Bash limit; `docs/refusal-codes.md` holds the refusal texts.
