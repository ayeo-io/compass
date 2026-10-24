---
id: ADR-077
title: Delegations cover the typing session until revoked
status: accepted
date: 2026-10-24
supersedes: ''
superseded_by: ''
---

## Context

ADR-069 let a person delegate approvals to one named agent for up to 24 hours, with up to five delegations in force, in the checkout where the person typed the command. Three facts made that too narrow:

- **Work spans worktrees.** An agent that works in a linked git worktree could not use a delegation made in the main checkout, because `delegations.authorise` read the `.compass/delegations/` folder next to the issue. A person had to type a delegation in each worktree.
- **The person, not Compass, knows how long a run lasts.** The owner decided on 2026-10-23 that Compass sets no upper limit on how long a delegation lasts or on how many are in force. The person sets the bounds with flags.
- **A request number is not unique across worktrees.** `/compass:approve 1` could not find a request raised in a worktree, and its refusal told the person to add `owner:` to the wrong checkout.

The owner confirmed the call ticket in decision 5 on 2026-10-23, including its two effects on agents: a delegated approval names `--issue`, and runs as a plain Bash command that the pre-tool hook reads.

## Decision

This record amends ADR-069 decisions 1, 2, 3 and 5. Decisions 4, 6, 7 and 8 stand, with decision 4 now tested through the ticket of decision 5 below.

1. **The flag form (amends ADR-069 decision 1).** The command is `/compass:delegate [--agent <name>] [--until <time>] [--on <issues>] [--for <forms>] [--max <n>]`. Every flag is optional and the flags can come in any order. The old positional form, which gave the agent first and then `until` and a time, is refused with the flag form. `--labels` is refused with a message that says to name the issues with `--on`. A flag given twice, an unknown flag, a flag with no value, `--flag=value` and a stray word are each refused and named. `/compass:revoke [DL-n]` is unchanged.
2. **The defaults, and the limits that go (amends ADR-069 decision 2).**
   - With no `--agent`, a delegation covers the agents of the session it was typed in: its main agent and every subagent that session runs, in any worktree. It names the session, not an agent. With `--agent <name>`, it covers that agent in any session. `any` is still refused.
   - With no `--until`, a delegation lasts until `/compass:revoke`. A time given with `--until` has no upper limit.
   - With no `--on`, a delegation covers every issue in the repository's worktrees, including issues created later, at any generation. With `--on <issues>`, it covers the named issues, each at the generation it had when the delegation was made.
   - The 24-hour limit and the limit of five delegations in force are removed. `--max <n>` still caps the approvals one delegation can give.
   - A delegation file now has `format: 2`. A file with no `format` is a 7.0.0 file and keeps the 7.0.0 rules: a missing end time or issue list grants nothing, and `labels` still limits it.
3. **A guardrail 5 delegation can be open-ended (amends ADR-069 decision 3).** `--for g5` still needs the code the hook shows, typed back in the same session within 10 minutes. After that code, a g5 delegation can have no end time and cover every issue. In practice guardrail 5 now reads: a person signs off, or types one confirmation that lets a session's agents sign off irreversible work until the person revokes it. The confirmation says so in words.
4. **One common store.** Every worktree reads and writes one delegation store: `.compass/delegations/` in the main checkout's project folder, at the same path inside the main checkout as the session's project is inside its own worktree. `/compass:delegate` and `/compass:revoke` take the approver from the folder that holds the store and need no current issue. One lock file guards every writer. A delegation file in a linked worktree's own folder gives no approval, and the refusal names it.
5. **A call ticket tells the CLI who called.** `compass evidence approve --delegated` needs `--issue <slug>`. The CLI never reads `CLAUDE_CODE_SESSION_ID`, because a command can set it. Instead, the pre-tool hook, on a plain Bash call that it reads and allows, writes a ticket into the store: the session id, the caller, and a SHA-256 of the words after `evidence approve`. The CLI takes the one ticket that matches its words and its caller, under the store lock, and deletes it. It then tests the session, the agent, the issue, the generation, the form and the use count on the ticket's values. The hook writes a ticket only when `compass` stands in command position, and binds the words up to the first shell operator, comment or redirect. A call the hook never read has no ticket of its own, so the CLI refuses it. Because the hook writes the ticket before the call runs, Compass deletes it when the call finishes, fails or has its permission denied, at the end of the turn, and at the session's next prompt; an untaken ticket expires after 10 minutes. Measured on Claude Code 2.1.310: when a person denies a permission prompt, no hook runs until the next prompt, and the turn ends with no Stop. Three windows stay open and are stated in `docs/safety-contract.md`: after a denied prompt, a process already running in the background can take the ticket before the next prompt; after a denial by auto mode's check that sends no hook, the agent can take it from a script in the same turn; and when the shell skips a `compass` command in command position (after `true ||`, `false &&` or on a heredoc line), a program the same call starts can take its ticket before the call ends. The same-user limit of ADR-069 decision 8 stands: a process running as the same operating system user can write a ticket. The owner accepted on 2026-10-24 a second limit of the same kind: a process that can start Claude Code as the person can resume a session by its id, and then uses a delegation typed in that session without `--agent`.
6. **The person reviews what the session was shown (amends ADR-069 decision 5).** Both summary hooks write the rows they show into the store's `shown/<session>.json`, keeping the two latest entries. `/compass:approve` with nothing pending in any worktree marks reviewed only the rows of the latest summary shown in the same session before the command, and only rows whose digest still matches. An approval recorded after that summary is not marked and appears in the next summary. Each delegation file indexes its records, so a summary reads only the folders that hold one, and with no delegation file it starts no git process and opens no manifest.
7. **Session start lists open-ended delegations.** The session-start hook runs for a new session, after `/clear` and after compaction, not for a resumed session. Each time it runs, it lists every delegation in force with no end time: its age in whole days, who it covers, whether it covers the starting session, and how many approvals it has given. After `/clear`, it says that a session delegation typed before `/clear` does not cover the new session, because `/clear` gives a new session id and `--resume` and `--continue` keep it. For another session's delegation it says that Compass cannot tell whether that session is still open.
8. **`/compass:approve` and `/compass:reject` search the worktrees.** A request number names a pending request on the current issue of each worktree. `--issue <slug>` reaches any issue in any worktree. A request that two issues hold is refused with a list that gives the `--issue` form. The approver is read from the folder that holds the chosen request, after the choice.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| No end time (ADR-069's rejected alternative, now accepted) | The owner wants a short command for a long run | ADR-069 rejected it because "A forgotten delegation would outlive the run it was meant for". The accepted mitigation is the session-start list of decision 7: each open-ended delegation is named when a new session starts, after `/clear` and after compaction, with its age and its count, and `/compass:revoke` ends one or all of them. A resumed session gets no list |
| The git common directory as the store | It exists even in a bare repository | It contradicts the path the owner named, needs a second protection pattern, and puts Compass files in `.git/` |
| The hook refuses a command that sets `CLAUDE_CODE_SESSION_ID` | It is smaller | A script bypasses it, and the CLI stays forgeable |
| A per-session secret in the environment, or a value injected into the call | The CLI could check it without a ticket | Neither was measured on the host, and an injected value changes the call's permission decision |
| Numbering requests across the repository | `/compass:approve 1` would never be ambiguous | It changes the request store and every request already on disk. The request text gives the `--issue` form when numbers collide |

## Consequences

- An agent in any worktree can approve under a delegation the person typed once, and the person answers any request from the session they started.
- A forgotten open-ended delegation keeps approving until it is revoked. The session-start list is the only reminder. It shows for a new session, after `/clear` and after compaction, and not for a resumed session.
- A ticket written for a call that never runs can be taken by another process in the three windows decision 5 names.
- A bare delegation covers built-in subagents such as general-purpose as well as plugin agents. A delegation made with `--for g5` and no end time can cover irreversible work in every issue after one typed-back code.
- A delegated approval must name `--issue` and must run as a plain command in the agent's Bash tool. A scope with a variable, a glob or a back-tick gets no ticket and is refused.
- A delegation file that Compass 7.0.0 wrote in a worktree's own folder no longer gives approval.
- Two sessions that type at the same moment take the one store lock in turn.

## References

- ADR-068 (the prompt hook), ADR-069 (delegation), ADR-038 (implementation versions).
- `cli/compass_pkg/worktree_lookup.py`, `cli/compass_pkg/delegation_tickets.py`, `cli/compass_pkg/delegations.py`, `cli/compass_pkg/prompt_approval.py`, `cli/compass_pkg/approve_cmd.py`, `hooks/pre-tool.sh`, `hooks/approval-summary.sh`, `hooks/session-start.sh`.
- The measurement of session ids on Claude Code 2.1.309, kept with the issue's evidence: a subagent reports its parent's session id after a `cd` into a linked worktree and under worktree isolation, `--resume` keeps the session id, and `/clear` starts a new one.
- `tests/test_delegate_flags.py`, `tests/test_delegation_worktrees.py`, `tests/test_delegation_sessions.py`, `tests/test_delegation_tickets.py`, `tests/test_prompt_approval_worktrees.py`, `tests/test_delegation_review.py`, `tests/test_delegation_session_start.py`, `tests/test_delegation_docs.py`.
