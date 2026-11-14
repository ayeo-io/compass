# Upgrading to 8.0.0

This page says what 8.0.0 changes for a project on 7.x and what to do. 8.0.0 is a major release because of one change: delegation. The decision is `architecture/decisions/ADR-077-delegations-cover-the-typing-session-until-revoked.md`.

8.0.0 removes no reader. Old words, old approach names, copied 5.x governance, the generated governance views, `.compass/config.yml` when `compass.yml` is absent, and migrated LEGACY waivers are read until 9.0.0 (`governance/decisions/2026-10-25-legacy-readers-readable-until-9-0-0.md`).

## Delegation

`/compass:delegate` takes flags, and a delegation reaches every worktree of the repository:

```
/compass:delegate [--agent <name>] [--until <time>] [--on <issues>] [--for <forms>] [--max <n>]
```

Every flag is optional, and the flags can come in any order.

### What breaks

- The positional form of `/compass:delegate` is refused. Type `/compass:delegate --agent compass:architect --until 08:00 --on my-issue`, not `/compass:delegate compass:architect until 08:00 on my-issue`.
- `--labels` is refused. Name the issues with `--on <issues>`. A delegation file that Compass 7.0.0 wrote with `labels` keeps that limit.
- A delegated approval needs `--issue <slug>`. The agent runs `compass evidence approve ... --issue <slug> --delegated --as <agent>` as a plain command in its Bash tool, with `compass` in command position. The CLI refuses a command inside a script, in an argument of `echo` or another command, or with a variable, a glob, a back-tick or a tilde in its words. The pre-tool hook gives such a command no call ticket.
- The CLI no longer reads `CLAUDE_CODE_SESSION_ID`.
- A delegation file in a linked worktree's own `.compass/delegations/` gives no approval. Compass reads one store, `.compass/delegations/` in the main checkout. The refusal names the old file. Type `/compass:delegate` again.

`docs/safety-contract.md` names the three short windows in which another process can take a ticket written for one call.

### What changes without breaking

- A bare `/compass:delegate` covers the agents of the session it was typed in, on every issue, until you type `/compass:revoke`. It does not cover the guardrail 5 sign-off.
- `--for g5` still needs the code that you type back. After that code, the delegation can have no end time and cover every issue.
- The 24-hour limit and the limit of five delegations in force are removed. You set the bounds.
- Compass lists each delegation with no end time when a new session starts, after `/clear` and after compaction. The list shows its age, who it covers and how many approvals it has given. A resumed session gets no list.
- After `/clear`, a session delegation of the earlier session no longer covers the new session. Type `/compass:delegate` again.
- `/compass:approve <n>` and `/compass:reject <n> <reason>` search the current issue of each worktree. `--issue <slug>` reaches any issue in any worktree.
- `/compass:approve` with nothing pending marks reviewed only the approvals that your last summary in the same session showed.
