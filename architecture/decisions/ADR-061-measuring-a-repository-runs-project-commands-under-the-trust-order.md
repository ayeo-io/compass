---
id: ADR-061
title: Measuring a repository runs project commands under the trust order
status: proposed
date: 2026-10-13
supersedes: ''
superseded_by: ''
---

## Context

Five readiness signals run a command the project declares: lint, format check, build, type check and the timed test command. That is code execution on a verb with no checking role. `command-passes` already runs project commands, and its order is the security property: the contribution trust decision (`trust.py`, which reads only what the CI runner owns) comes first, then the `allow_project_commands` opt-in. `command-passes` runs a command with `subprocess.run(..., timeout=...)` in the project root, which stops the shell at the timeout but not the processes the shell started.

A command can also write files: a formatter declared without its check flag, or a suite that writes snapshots. The worktree rule of the multiagent protocol lets only the orchestrator create worktrees under `multiagent.worktree_root`, within `max_worktrees`.

## Decision

1. **One permission function.** `project_commands.command_permission(project_root)` returns allowed, refused as untrusted (with the trust reason), or refused as disabled (naming `allow_project_commands` and the settings file). It decides trust first and reads the opt-in only when trust allows. `command-passes` and `compass readiness` both call it; each keeps its own wording.
2. **A refused command is a result, not an error.** Its signal is absent with "not run: project commands are disabled" or the untrusted-contribution reason, and no worktree is created. A repository with no commit has no HEAD to check out, so each command signal is absent with the reason that says so.
3. **Every project command runs in one temporary worktree of HEAD.** `git worktree add --detach` creates it under the system temp folder with the prefix `compass-readiness-`, the process id and a random suffix. It is outside `multiagent.worktree_root` and not counted against `max_worktrees`: it is a short-lived checkout for measuring, not a subtask worktree. It holds no ignored or uncommitted file, so the reason of a failed command says it ran in a clean checkout of HEAD. Whatever a command writes is removed with the worktree, so the working tree never changes.
4. **Cleanup.** The worktree is removed in a `finally` block with `git worktree remove --force`, then `git worktree prune`. A run first removes any `compass-readiness-` worktree whose process id is no longer alive, which is what a killed run leaves. It never removes one whose process is alive.
5. **Commands stop with their process group.** Each command starts in a new session. At its limit the whole process group is sent `SIGKILL`, as `host_launch.py` does for a host session.
6. **One time budget.** A run finishes within 300 seconds. Project commands share 270 of them, one at a time, in the order build, tests, lint, type check, format check, so the floor's evidence gets the time first. The timed test command also stops at 120 seconds. A command still running at the end of the budget is absent with "ran over the time limit"; one not started is absent with "not run: the time limit was reached". The environment variable `COMPASS_READINESS_BUDGET_SECONDS` can only lower the command budget, and only tests set it.
7. **Signals read nothing outside the repository and its declared commands.** Branch protection and secret scanning are declarations (`project.secret_scan`, `project.structured_logging`), not API calls.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| Copy the trust and opt-in code into the readiness verb | Keeps `checks.py` untouched | Two copies of a security order drift; one function is the order |
| Run commands in the working tree, in check mode | No worktree to manage | Correctness then depends on every project declaring the check form; one mistake edits a person's uncommitted work |
| Create the worktree under `multiagent.worktree_root` | One place for worktrees | It would count against `max_worktrees` and could be refused while subtasks run |
| Stop only the shell at the limit | What `command-passes` does | A build's child processes keep running after the run ends |
| A budget per signal | Simpler accounting | Eleven signals could then run far past the five minutes a person is promised |

## Consequences

**Positive:**
- A project command never edits the working tree and never runs on an untrusted contribution.
- A killed run leaves nothing the next run does not remove.

**Negative:**
- A command that needs installed dependencies or a `.env` file reads as absent unless the project declares a command that sets them up within the budget.
- `command-passes` still stops only the shell at its timeout. Moving it onto the process-group runner changes a locked check's behaviour, so it is a separate change.

**Neutral / follow-on:**
- Compass cannot stop a declared command from making a network call; it only makes none itself.

## References

- ADR-009: project fitness functions run as `command-passes`.
- ADR-025: the multiagent interface and its worktrees.
- ADR-058: the readiness floor.
- `docs/security.md` owns the trust order and `allow_project_commands`.
- `docs/readiness.md` owns the budget and the temporary worktree.
