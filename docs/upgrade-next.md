# Upgrading to the next release

This page lists what the next release changes about delegation, and what to do about it. The release has no number yet. The owner chooses it when the change ships, and this page then takes that number as its name. The decision behind it is `architecture/decisions/ADR-077-delegations-cover-the-typing-session-until-revoked.md`.

## Delegation

`/compass:delegate` now takes flags, and a delegation reaches every worktree of the repository. The new form is:

```
/compass:delegate [--agent <name>] [--until <time>] [--on <issues>] [--for <forms>] [--max <n>]
```

Every flag is optional, and the flags can come in any order.

### What breaks

- The positional form of `/compass:delegate` is refused. `/compass:delegate compass:architect until 08:00 on my-issue` now gives a message that shows the flag form. Write `/compass:delegate --agent compass:architect --until 08:00 --on my-issue`.
- `--labels` is refused. The message says to name the issues with `--on <issues>`. A delegation file that Compass 7.0.0 wrote with `labels` keeps that limit.
- A delegated approval needs `--issue <slug>`. The agent runs `compass evidence approve ... --issue <slug> --delegated --as <agent>` as a plain command in its Bash tool, with `compass` as the command that runs. A command inside a script, an argument of `echo` or another command, or a command whose words hold a variable, a glob, a back-tick or a tilde gets no call ticket from the pre-tool hook, so the CLI refuses it. The CLI no longer reads `CLAUDE_CODE_SESSION_ID`. `docs/safety-contract.md` names the two short windows in which a ticket written for one call can still be taken by another process.
- A delegation file in a linked worktree's own `.compass/delegations/` gives no approval. Compass reads one common store, `.compass/delegations/` in the main checkout. The refusal names the old file. Type `/compass:delegate` again.

### What changes without breaking

- A bare `/compass:delegate` covers the agents of the session it was typed in, on every issue, until you type `/compass:revoke`. It does not cover the guardrail 5 sign-off. `--for g5` still needs the code that you type back, and after that code the delegation can have no end time and cover every issue.
- The 24-hour limit and the limit of five delegations in force are removed. You set the bounds.
- Compass lists each delegation with no end time when a new session starts, after `/clear` and after compaction, with its age, who it covers and how many approvals it has given. A resumed session gets no list, although a delegation typed in it still covers it. After `/clear`, a session delegation of the earlier session no longer covers the new session. Type `/compass:delegate` again.
- `/compass:approve <n>` and `/compass:reject <n> <reason>` search the current issue of each worktree. `--issue <slug>` reaches any issue in any worktree.
- `/compass:approve` with nothing pending marks reviewed only the approvals that your last summary in the same session showed.
