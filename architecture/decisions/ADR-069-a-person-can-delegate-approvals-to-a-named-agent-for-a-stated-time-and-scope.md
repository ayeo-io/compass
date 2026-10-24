---
id: ADR-069
title: A person can delegate approvals to a named agent for a stated time and scope
status: accepted
date: 2026-10-15
supersedes: ''
superseded_by: ''
---

## Context

ADR-068 lets a person approve inside Claude Code by typing `/compass:approve`, and says the agent only requests. On 2026-10-15 jed72 widened the goal: either a person or an agent they delegated to gives the approval, and that approval is recorded ("I just want AN approval to be given and recorded."). A new adopter approves each item. Later they want to leave a well-formed spec running overnight and delegate the approvals, including irreversible items such as an archive `issue migrate --apply` and a VERSION bump and tag ("yes it can").

Four facts bound the answer:

- **The person-only event already exists.** ADR-068 records from Claude Code's `UserPromptExpansion` on plugin commands that set `disable-model-invocation: true`, which the model, a scheduled task and another session cannot raise (measured on Claude Code 2.1.300 on 2026-10-15).
- **`PreToolUse` reports the agent, and absence is not proof of the main agent.** The value comes from Claude Code, not from the tool call. Measured on Claude Code 2.1.300 on 2026-10-15 (the host measurement of 2026-10-15):
  - the main agent of a plain session reports neither `agent_type` nor `agent_id`;
  - the main agent of a session started with `--agent X` reports `agent_type` `X` and no `agent_id`;
  - a plugin subagent reports `agent_type` with the plugin prefix, such as `compass:architect`, and an `agent_id`;
  - a built-in subagent reports `agent_type` such as `general-purpose`, and an `agent_id`;
  - an internal Claude Code agent that the model did not launch reported an `agent_id` and no `agent_type` on a `PreToolUse` for Bash.
- **Approver lists name people.** `approval_records.approver_listed` returns false for `agent` and any name starting `agent:`, and `judge` reads `approver`.
- **A `G5` sign-off cannot be withdrawn today.** `human-approval-present` counts the first approved record given for `G5`, and ADR-066 decision 4 refuses a rejected `G5` record because it would not withdraw it.

## Decision

1. **A delegation is a person's standing decision, created only by a typed command.** `/compass:delegate <agent> until <time> [on <issues>] [for <forms>] [labels <labels>] [max <uses>]` and `/compass:revoke [DL-n]` go through ADR-068's prompt hook. The hook writes `.compass/delegations/DL-<n>.yml` with the agent, the delegating person, the times, the scope, `created_via: prompt`, the session and a nonce. No CLI verb creates, extends or revokes a delegation.
2. **Limits.** An end time is required, in the future and at most 24 hours after creation. The agent is one agent type, or `main` for the session's main agent; `any` is refused. At most five delegations are in force. `max <uses>` can cap the approvals one allows. A delegation covers each named issue only at the generation it was created at. The default scope is the session's current issue and the forms checks, documents, checkpoints and decisions.
3. **The guardrail 5 sign-off is covered only when named.** `for g5` adds it, and the confirmation says in words that the agent may sign off irreversible work until the end time. This amends ADR-068 decision 1, and what guardrail 5 means in practice: a person signs off, or delegates the sign-off to a named agent for a stated time and scope. A delegation that covers g5 takes effect only after the person types back a single-use code, which the hook shows in its block message, in the same session within 10 minutes. A prompt suggestion accepted with Tab lets the model word the first command (the host measurement), so the typed-back code is what shows a person chose it. Only a hash of the code is stored. Claude Code writes the block message to the session transcript (measured on 2.1.301), so the pre-tool hook refuses the agent's Read, Grep and Bash calls that name the transcript.
4. **A delegated approval names the person, the agent and the delegation.** The agent runs `compass evidence approve <form> --delegated --as <agent>`, which needs no terminal. The CLI refuses unless a delegation in force, with `created_via: prompt`, names that agent and covers the issue, generation, form, labels and uses. The pre-tool hook names the caller from what Claude Code reports: `main` only when both `agent_type` and `agent_id` are absent; otherwise the exact `agent_type`, including its plugin prefix (`compass:architect`, never `architect`). It refuses a call that has an `agent_id` with no `agent_type` or an empty one, and a call whose caller differs from `--as`. A delegation names the agent the same way, and `/compass:delegate` states the full name in its confirmation. The record's `approver` is the delegating person, so approver lists and `judge` do not change. It also holds `approved_by_agent`, `delegation` and `via: delegation`. The check detail and the receipt read "by <person> via <agent> under DL-<n>". Each use writes an audit line to the issue's devlog.
5. **The person reviews what was approved.** Delegated approvals not yet reviewed are summarised at session start and on each submitted prompt, across sessions, through a display-only hook that never writes a record. A document approved by the agent that wrote it in the same session is flagged. `/compass:approve` with no pending request marks them reviewed.
6. **The person can overrule.** `/compass:reject <record id> <reason>` writes a `rejected` record for a check, returns a document to draft (ADR-068 decision 6), and writes an `approval-withdrawal` record for a `G5` sign-off. `human-approval-present` skips a withdrawn record. Its implementation moves to 1.2.0: the fixture corpus verdicts do not change, and the landed floor of ADR-066 decision 5 still passes a landed issue. A withdrawal records disagreement; it never reverses an action already taken, and the confirmation says so. A waiver that names a withdrawn approval fails.
7. **A delegation never covers delegation.** A delegated agent cannot create, extend or revoke a delegation, or reject or withdraw an approval.
8. **The same-user limit is stated.** The pre-tool hook refuses the agent's Edit, Write and Bash calls that name `.compass/delegations/`. A process running as the same operating system user can still write a delegation file, pass a matching `--as` outside the agent's tools, or write `manifest.yml`; the g5 confirmation code does not stop a same-user process, as ADR-068 decision 10 says for request files.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| The agent as `approver` | It names who acted | Approver lists and `judge` would have to accept agents; the person who answers for the approval would not be named |
| `g5` in the default scope | The owner said a delegation may cover irreversible work | Allowing is not defaulting; a short command would cover a migration or a tag without the person saying so |
| `any` agent | Simpler for an overnight run with several agents | No agent is accountable; `agent_type` matching means nothing |
| No end time, or a session-long default | Fewer words to type | A forgotten delegation would outlive the run it was meant for |
| A CLI verb to create a delegation | Testable without a host | The model could call it, which reverses ADR-068's guarantee |
| A rejected `human-approval` record to overrule `G5` | Reuses the existing type | ADR-066 decision 4 refuses it, because the check counts the first approved record |

## Consequences

- An overnight run can approve within a scope the person set, and the person sees and can overrule each approval in the morning.
- Guardrail 5 can be met by a delegation. The safety contract and `governance/guardrails.md` say so.
- `human-approval-present` moves to 1.2.0; `approval-withdrawal` is a new evidence type.
- The delegation limits are policy written in code for now. Making them project settings is a later decision.
- The measurement that ADR-068 cites also recorded what `agent_type` and `agent_id` hold for the main agent and each kind of subagent; decision 4 follows it. jed72 delegated its acceptance to compass:architect on 2026-10-15, who accepted it once the build confirmed the measured behaviour.

## References

- ADR-038 (implementation versions), ADR-066 decisions 4 and 5 (a rejected `G5` record, the landed floor), ADR-068 (the prompt hook).
- `cli/compass_pkg/delegations.py`, `cli/compass_pkg/prompt_approval.py` (`/compass:delegate`, `/compass:revoke`), `cli/compass_pkg/approve_cmd.py` (`--delegated --as`), `hooks/pre-tool.sh` (the caller check).
- The host measurement on Claude Code 2.1.300 of 2026-10-15, whose results this record states; the raw logs are kept with the issue's evidence, outside the repository.
- `tests/test_delegation.py`, `tests/test_approval_withdrawal.py`.
