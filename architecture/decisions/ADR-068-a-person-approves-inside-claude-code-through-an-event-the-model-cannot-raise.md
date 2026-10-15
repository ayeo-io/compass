---
id: ADR-068
title: A person approves inside Claude Code through an event the model cannot raise, and the agent only requests
status: proposed
date: 2026-10-15
supersedes: ''
superseded_by: ''
---

## Context

`compass evidence approve` records a person's approval, including the sign-off of guardrail `G5`. It refuses unless standard input is a terminal (`cli/compass_pkg/approve_cmd.py`), and a shell that Claude Code runs has none. So an agent prints the command and the person pastes it into a terminal. jed72 decided on 2026-10-15 that a person must approve or reject by typing a short prompt inside Claude Code, never by copying a command or opening a terminal, and that the agent never records an approval.

Five facts bound the answer. The Claude Code facts come from the official documentation, read on 2026-10-15 (`code.claude.com/docs/en/hooks`, `/scheduled-tasks`, `/cross-session-messaging` and `/skills`), and from a measurement on Claude Code 2.1.300 the same day (`.compass/work/approve-inside-claude-code/evidence/u0-host-measurement/u0-results.txt`).

- **`UserPromptSubmit` is not person-only.** It fires when a scheduled task fires, when a background subagent reports back and when another session sends a message. The model can create a scheduled task with the `CronCreate` tool. The input holds the common fields (`session_id`, `transcript_path`, `cwd`, `permission_mode`, `hook_event_name`) and `prompt`, and no field says who produced the prompt.
- **`UserPromptExpansion` fires when a command expands, and its input does not say who typed it.** It fires for a command a person types. It also fires, with the same fields, for a scheduled task whose prompt is a command without `disable-model-invocation: true`, and for a nested `claude -p "/<command>"`. Its input holds the common fields, `prompt_id`, `expansion_type`, `command_name`, `command_args`, `command_source` and `prompt`. `prompt_id` is a UUID, the same on every event of one turn and new on the next. Its output can block, with a reason shown to the person and not to the model, or add `additionalContext`. `systemMessage` is shown to the person.
- **`disable-model-invocation: true` is what keeps a command from the model.** With it set, the Skill tool refuses the command, and a scheduled task whose prompt is the command delivers it as plain text through `UserPromptSubmit`, with no expansion. A command in a message from another session, or in a background subagent's report, never expands, with or without the flag. So the flag on the command file, not the event alone, holds the boundary.
- **The terminal check is not a hard boundary either.** A process can give a command a pseudo-terminal; this repository's own tests do (`tests/test_approval_scoped_to_guardrail_5.py`). Anyone who can write `manifest.yml` can add a record, as the `approve_cmd` docstring says.
- **Codex** has a `UserPromptSubmit` hook with a `prompt` field (`learn.chatgpt.com/docs/hooks`, read 2026-10-15). The page does not say whether prompts that automation produces fire it, and it lists no command-expansion event.

## Decision

1. **The agent requests, Compass shows, the person answers.** `compass evidence request` takes the five subject forms of `compass evidence approve`, runs the same refusals and writes one request file under the issue. The request holds facts the CLI derives (issue, generation, subject, labels, and a document's digest) and the agent's description of the scope. The Stop hook shows an unshown request to the person through `systemMessage` and stamps the digest it showed. No check reads a request file, and a request is not evidence.
2. **The only recording trigger is `UserPromptExpansion`, on a command the model cannot invoke.** The hook is matched on `compass:approve` and `compass:reject`, acts only for `expansion_type` `slash_command` and `command_source` `plugin`, and the command files set `disable-model-invocation: true`. The hook refuses unless the command file it serves sets that flag, so a later edit that drops it fails closed instead of letting a scheduled task record an approval. A test checks the flag on all four command files (`approve`, `reject`, `delegate`, `revoke`). No `UserPromptSubmit` hook records an approval. This differs from the event named in the owner's decision, for the reason in the first fact above.
3. **The hook records one shown, current request or nothing.** It refuses, blocking the prompt and writing nothing, when no request is pending, when several are and no number was typed, when the generation or the document changed, when the request changed since it was shown, when the request was already answered (each request carries a single-use nonce that its record copies), when a record already holds the hook input's `prompt_id`, or when the session's issue cannot be named. It names the issue as the pre-tool hook does (`COMPASS_ISSUE`, then the pointer, refusing a moved pointer) and never guesses. Any error blocks.
4. **One set of writers.** The terminal verb and the hook call the same function to write a record. The terminal check stays in the terminal verb only.
5. **Approver.** `COMPASS_APPROVER` from Claude Code's start-up environment, else the project's `owner:`. The record holds `approver_source`. The name is asserted, not authenticated, as `--approver` is today.
6. **Reject, per subject.** A human check gets a `rejected` record. A document returns to `draft` with `rejected_by`, `rejected_at`, `rejected_reason` and `rejected_digest`, and stays there while its file digest equals `rejected_digest`. This amends ADR-050 decision 2, which otherwise moves every `draft` entry with a path at the next stage record. The `G5` sign-off, a checkpoint and a set of decisions write no record, and the request closes as `rejected`. A `G5` rejection does not withdraw an earlier sign-off (ADR-066 decision 4).
7. **Provenance is shown, never judged.** A record gains `via` (`prompt`, `terminal` or, under ADR-069, `delegation`) and, for a prompt, `host`, `session_id`, `prompt_id`, `request`, `nonce` and `approver_source`. None is a subject key (ADR-066). No verdict reads them; the detail of `human-approval-present` and the receipt name them, and a record with no `via` reads "written without a Compass command" and still counts (ADR-006). This record changes only wording; ADR-069's withdrawal is what moves the check to 1.2.0.
8. **An adapter wires the prompt path only on a person-only event.** It must show, with a dated measurement, that its host fires the event only for a command a person typed and that the model cannot raise it. `schemas/adapter-contract.yml` records the capability. Codex does not meet it today, so its users approve with `compass evidence approve` in their own terminal.
9. **The terminal verb stays** as that fallback and for a Claude Code version without `UserPromptExpansion`. Its records gain `via: terminal`.
10. **The remaining limit is stated.** A process running as the same operating system user can still pipe forged input into the hook's entry point, start a nested session, or write `manifest.yml`, as it can already defeat the terminal check. The pre-tool hook refuses the agent's Edit, Write and Bash calls that name a request file or the hook's entry point, which stops ordinary use and not a deliberate workaround.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| A `UserPromptSubmit` hook with an exact-text match | The owner named it | A scheduled task, a subagent report or a message from another session submits text the model chose |
| Check the transcript for the typed command | It looks like proof that the person typed it | The documentation says the transcript is written asynchronously and may lag, and the model can write the file |
| The person types the subject and scope as arguments | No request file to trust | The owner asked for a short prompt |
| Record whatever is pending with no display | Fewest steps | The person would approve the agent's description only |
| A separate writer for the prompt path | Simpler to start | Two writers can drift; ADR-066 decision 1 counts writers |
| Remove the terminal verb | The owner said "never a terminal" | Codex and older Claude Code versions would have no path; kept as an owner question |
| Wire Codex's `UserPromptSubmit` now | One behaviour on both hosts | Its documentation does not say the event is person-only |

A measurement on Claude Code 2.1.300 on 2026-10-15 confirmed the event rules this record needs, for a command that sets `disable-model-invocation: true`: a typed command fires `UserPromptExpansion`; the Skill tool, a scheduled task, a background subagent's report and another session's message do not; and `prompt_id` arrives. It also found that a nested `claude -p` fires the event, and that a prompt suggestion the person accepts with Tab fires it with the arguments the model worded. This record stays proposed until a person accepts it.

ADR-069 amends decision 1: an agent may also record an approval, under a delegation a person created through the same event.

## Consequences

- In Claude Code a person approves by typing `/compass:approve`, sees one line from Compass, and the work goes on.
- The guarantee is as strong as the terminal check, and no stronger against a same-user process. `docs/safety-contract.md` says so.
- The design depends on host behaviour. A measurement on a real host is evidence for the issue, and a change in Claude Code's event rules would need this record revisited.
- ADR-050 decision 2 gains an exception for a rejected document. ADR-050's text is not edited; this record carries the change.
- The operating contract tells the agent to request and never to print a terminal command, except where `compass evidence request` prints one for a host without the prompt path.

## References

- ADR-006 (backward compatibility), ADR-050 decision 2 (documents move at a stage record), ADR-066 (an approval names its subject), ADR-069 (delegation).
- `cli/compass_pkg/approvals.py` (the one writer), `cli/compass_pkg/approval_requests.py` (`compass evidence request`), `cli/compass_pkg/prompt_approval.py` (the prompt hook), `cli/compass_pkg/approve_cmd.py` (the terminal verb), `hooks/prompt-approval.sh`.
- The U0 host measurement: `.compass/work/approve-inside-claude-code/evidence/u0-host-measurement/u0-results.txt`.
- `tests/test_approval_request.py`, `tests/test_prompt_approval.py`, `tests/test_approval_provenance.py`.
