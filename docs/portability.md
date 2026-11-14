# Portability

This page says what a port of Compass to another agent runtime must do.
Compass 9.0.0 supports Claude Code only; the Codex adapter stays on 8.x. A
port replaces the adapter and nothing else.

## The three-layer boundary

| Layer | Responsibility | Files | Porting rule |
|---|---|---|---|
| Methodology | Defines the path, roles, artifacts, guardrails and strategies. | `docs/`, `approaches/`, templates, governance Markdown | Reuse. |
| Kit | Computes the evidence each change owes, checks state and writes mechanical evidence. | `cli/`, governance YAML, schemas, `manifest.yml` | Invoke. |
| Adapter | Maps Compass into one agent runtime. | commands, skills, hooks, runtime instructions and install wiring | Rebuild. |

The adapter produces the assessment, because that needs judgement. The kit
computes the evidence and runs the checks, because those must be
deterministic.

## Runtime adapter contract

### The Claude Code adapter layer

A port rebuilds this layer:

```
commands/        the path interface (the /compass: namespace)
skills/          adaptive-routing, atdd, compass-runtime, evidence-gates,
                 flow-management, governance-check, intent-interview,
                 receiving-code-review, systematic-debugging,
                 tdd-discipline
hooks/           pre-tool.sh, post-tool.sh, stop.sh, session-start.sh,
                 prompt-approval.sh, approval-summary.sh
bin/compass      the shim that puts the kit on PATH
.claude-plugin/  the plugin manifest and marketplace entry
```

`architect` is a perspective the session takes. A port must not make it a
separate agent or command.

A conforming adapter must meet these seven requirements.

### 1. Assess before changing delivery artifacts

The runtime must recognize intent to build, change or fix files, even when
the user types no Compass command. Before the first delivery change it must:

1. assess risk, familiarity and size, and any goal or urgency switch;
2. record the assessment with `compass quick-fix start`, or in the manifest
   and then with `compass approach evaluate --write`; and
3. show the person the three lines of `compass approach show`: the
   approach, the evidence the change owes and where the files go.

Conversation and read-only exploration do not need an issue.

### 2. Expose the delivery flow

The adapter must expose the four stages of the path - assess, specify,
build, ship - as one command that runs them all, like the shipped
`/compass:go`, or an equivalent interface.

It must collect the evidence `compass approach show` lists and follow the
`next:` line each kit call prints. The stages have no modes, and the one
document Compass needs is `acceptance-criteria.md` (ADR-091, ADR-092).

### 3. Call the kit

The adapter must call the kit's deterministic operations, not reproduce
them. At minimum:

| Need | Kit command |
|---|---|
| Compute or update the evidence a change owes | `compass quick-fix start`, `compass approach evaluate` |
| Name the next step | `compass next` |
| Check an issue | `compass check` |
| Record red and green tests | `compass tdd-red`, `compass tdd-green` |
| Check governance and issue schemas | `compass policy lint`, `compass issue lint` |
| Run the CI lane | `compass ci` |
| Show every issue's state | `compass flow` |

Where a kit command changes `manifest.yml`, use it. Do not edit the file by
hand.

### 4. Preserve the safety contract

The adapter must call `compass check` at the ship stage and before the
commit, obey its exit code and keep every required human approval. An
adapter limit must not weaken a guardrail.

- **The contract in each session.** The rules of behavior are in
  `compass-contract.md`. On Claude Code a `SessionStart` hook injects it at
  startup, on clear and on compact. A runtime with no such event must load
  it another way, such as a system prompt or an always-loaded instruction
  file. Keep one copy of the contract.
- **Edits wait for the scenarios.** Where the runtime has pre-action hooks,
  the adapter refuses a code edit before the scenarios exist and, where the
  issue owes it, before a person approves them. The hook must not block a
  spike. Without hooks, the adapter makes those checks a step of build.
- **A person-only approval event.** In Claude Code a person types
  `/compass:approve`, and `hooks/prompt-approval.sh` records it on the
  `UserPromptExpansion` event (ADR-068). An adapter can wire such a prompt
  path only after a dated measurement on its host shows two things: the
  event fires for a command a person typed, and the model cannot raise it
  through a tool, a scheduled job, a subagent or another session. Until
  then the adapter sets `COMPASS_APPROVAL_CHANNEL=terminal`, and `compass
  evidence request` prints the exact `compass evidence approve` command for
  the person's own terminal.
- **A time limit on the pre-tool hook.** On Claude Code, `hooks/hooks.json`
  sets `"timeout": 15` and `"onFailure": "block"`, so a hook that runs out
  of time blocks the call from Claude Code 2.1.295. A source install
  (`scripts/install.sh`) keeps the default of 600 seconds. An adapter on
  another runtime needs its own limit.

### 5. Keep one specification for every role

There are no role entry points (ADR-093). Product, design, engineering,
marketing and QA read the same acceptance criteria, and a brief opens them
through the `intent-interview` skill.

The adapter must keep claim traceability: the manifest's `claims:` and the
`claim-traces-to-scenario` check.

### 6. Persist state on disk

Nothing essential can live only in conversation. The adapter must maintain:

```text
.compass/current-task
.compass/work/<issue>/manifest.yml
.compass/work/<issue>/evidence/
docs/compass/<created>-<issue>/acceptance-criteria.md
```

A different session or runtime resumes by reading this state.

### 7. Give safe delivery orchestration

The adapter must support solo delivery, and needs nothing more: each issue
runs in one session (ADR-090). No adapter needs isolated workspaces or an
integration owner.

## Conformance mapping

### The mapping table

Before implementation, a port must document two mappings. The first is the
kit calls that work across issues:

| Kit call | What a port loses without it |
|---|---|
| `compass flow` | no view of blockers or owed follow-ups across issues |
| `compass next` | the session guesses which stage comes next |
| `compass follow-up` | an open Definition of Done item cannot be linked to the GitHub issue that tracks it, so shipping stays blocked |
| `compass adr` | decision records are hand-numbered, and numbers get reused |

The second is the capability mapping. An empty cell is an open design
question.

| Compass capability | Target runtime mechanism | Status or limitation |
|---|---|---|
| Always-loaded operating instructions |  |  |
| Intent-triggered assessment |  |  |
| User commands or stage interface |  |  |
| Kit CLI invocation |  |  |
| Pre-action enforcement |  |  |
| Post-action issue logging |  |  |
| Session-end status check |  |  |
| Distinct agent contexts |  |  |
| Isolated parallel workspaces |  |  |
| CI integration |  |  |
| Person-only approval event |  |  |
| Install surface (`bin/compass`, `.claude-plugin/`) |  |  |

`schemas/adapter-contract.yml` holds this table as data, with the Claude
Code column filled in. A port adds its column before it lands.
`tests/test_adapter_contract.py` fails when:

- the table and the file differ;
- an adapter's cell is empty or names a path that does not exist;
- a directory under `adapters/` has no column; or
- code in `cli/` or `hooks/` branches on not being some adapter, such as
  `if adapter != "claude-code"`.

## Where to start

`AGENTS.md` is the runtime-neutral starting point. The Claude Code adapter's
`CLAUDE.md`, commands and hooks are a reference implementation, not the
portable contract.

## Conformance test

A port conforms when the same assessed issue and policy give:

- the same computed approach and evidence;
- a schema-compatible `manifest.yml`;
- the same gate set;
- equivalent typed evidence and approval records;
- the same `compass check` verdict; and
- an issue that another Compass runtime can resume without translation.

Test both directions: start an issue in each runtime and resume it in the
other. Terminal presentation can differ. Policy outcome must not.

The [adapter behavior checks](adapter-conformance.md) run these locally.
They do not show native instruction loading, trusted host dispatch, cold
resumption or context compaction. Those need separate captures, which that
page defines.

## Porting sequence

1. Complete the conformance mapping.
2. Wire the target runtime to the unchanged kit CLI.
3. Implement assessment and the four stages of the path.
4. Add persistence and resumption.
5. Add the strongest enforcement the runtime supports.
6. Run the conformance test.
7. Document install, security and known limits.
