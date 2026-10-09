# Portability

Compass runs on Claude Code today, but most of Compass is deliberately runtime
neutral. A port should replace the adapter, not fork the methodology or
reimplement the policy engine.

## The three-layer boundary

| Layer | Responsibility | Representative files | Porting rule |
|---|---|---|---|
| Methodology | Defines the flow, roles, artifacts, guardrails and strategies. | `docs/`, `approaches/`, templates, governance Markdown | Reuse. |
| Kit | Computes delivery approaches, checks state and writes mechanical evidence. | `cli/`, governance YAML, schemas, `manifest.yml` | Invoke. |
| Adapter | Maps Compass into a particular agent runtime. | commands, agents, skills, hooks, runtime instructions and install wiring | Rebuild. |

The boundary follows the determinism model:

- the adapter produces an assessment because assessment needs judgement;
- the kit computes the delivery approach because that must be deterministic; and
- the adapter orchestrates the resulting flow while calling the kit for
  checks and state mutations.

A port that independently implements routing or guardrails may resemble
Compass, but it will drift from Compass policy.

## Runtime adapter contract

### The Claude Code adapter layer

The shipped adapter is Claude Code: `commands/` are the stage interface,
`agents/` the distinct contexts, `skills/` the loadable procedures, `hooks/`
the pre-action enforcement, and `.claude-plugin/` the install wiring. A port
rebuilds that layer and reuses everything under it.

```
commands/        the stage interface (the /compass: namespace)
agents/          router, spec-author, planner, orchestrator, builder,
                 verifier, reviewer, product-owner, product-marketer,
                 architect
skills/          adaptive-routing, bdd-specification, behaviour-mapping,
                 compass-runtime, evidence-gates, flow-management,
                 governance-check, intent-interview, plan-authoring,
                 quick-fix, receiving-code-review, systematic-debugging,
                 tdd-discipline, worktree-multiagent
hooks/           pre-tool.sh, post-tool.sh, stop.sh, session-start.sh
bin/compass      the shim that puts the kit on PATH
.claude-plugin/  the plugin manifest and marketplace entry
```

Take care with `architect`: it advises across the pipeline and is not a
sixth role, so a one-to-one role mapping drops it or turns it into a role.

A conforming adapter must satisfy the following requirements.

### 1. Assess before changing delivery artifacts

The runtime must recognise intent to build, change or fix files, even when the
user does not type an explicit Compass command.

Before the first delivery change it must:

1. assess risk, familiarity, size, goal and role;
2. record the assessment in the manifest;
3. call `compass approach evaluate --write`; and
4. present the human-readable approach for approval.

Conversation and read-only exploration do not need an issue. A delivery
change does.

### 2. Expose the delivery flow

The adapter must expose the eight methodological stages, whether as eight
commands or an equivalent interface:

```text
assess → define → refine → plan → breakdown → implement → verify → ship
```

It must honour the stage weights and omissions computed by the delivery
approach, and write the selected artifacts using Compass templates.

### 3. Call the kit

The adapter must invoke, rather than reproduce, the kit's deterministic
operations. At minimum:

| Need | Kit command |
|---|---|
| Compute or update a delivery approach | `compass approach evaluate` |
| Check an issue | `compass check` |
| Record red and green tests | `compass tdd-red`, `compass tdd-green` |
| Check governance and issue schemas | `compass policy lint`, `compass issue lint` |
| Check cross-artifact consistency | `compass analyze` |
| Run the CI lane | `compass ci` |
| Surface retrospective signals | `compass retro`, `compass rework-scan`, `compass flow` |

Schema-owning state changes must also use kit commands where one exists,
rather than editing `manifest.yml` ad hoc.

### 4. Preserve the safety contract

The adapter must call `compass check` at the verify stage and before ship,
honour its exit code and preserve required human approvals.

**Getting the contract into a session.** Compass's rules of behaviour live in
`compass-contract.md`, and on Claude Code a `SessionStart` hook injects it at
startup, on clear and on compact, so the model has it without choosing to load
anything. That is an adapter feature, not a portable one: a runtime with no
session-start event has to reach the same outcome another way - a system
prompt, an always-loaded instruction file, or the equivalent of `CLAUDE.md`.
What must not change is that the contract exists once. Keep one copy: two
copies drift apart.

BDD and TDD are default strategies. When the runtime supports pre-action hooks,
the adapter enforces red-before-green mechanically, with the hook made
approach-aware so it does not block spikes. Without hooks, the adapter must
make the check an explicit implementation step.

An adapter limitation can reduce convenience or parallelism. It must not
silently weaken a guardrail.

### 5. Support the five entry-point roles

The runtime needs distinct entry paths for product, design, engineering,
marketing and QA. All five contribute to the same acceptance specification and
produce their normal Compass artifacts.

The adapter must preserve role-dependent gates such as intent fidelity and
claim traceability. Otherwise the role is decorative rather than operational.

### 6. Persist state on disk

Nothing essential may live only in conversation. The adapter must maintain:

```text
.compass/current-task
.compass/work/<issue>/README.md
.compass/work/<issue>/manifest.yml
.compass/work/<issue>/delivery-approach.md
.compass/work/<issue>/evidence/
```

It adds the approach-selected product, requirements, design, delivery, quality and
launch artifacts alongside them.

A different session or runtime can resume by reading this state.

### 7. Give safe delivery orchestration

The adapter must support solo delivery. Pair and multiagent approaches need
isolated workspaces plus a single integration owner.

The reference adapter uses Git worktrees. A runtime can use another mechanism,
but each subtask must be able to run a failing test cycle without destabilising
the others. If equivalent isolation is unavailable, cap the orchestration and state
the limitation.

## Conformance mapping

### The mapping table

A port must document the cross-issue kit calls before implementation, listed
here because an adapter that wires up only the per-issue verbs will look
complete and lose the view across open issues:

| Kit call | What a port loses without it |
|---|---|
| `compass analyze` | nothing reports where an issue's own artifacts disagree |
| `compass flow` | no view of blockers or owed follow-ups across issues |
| `compass next` | the session guesses which stage comes next |
| `compass retro` | no signal that assessment is systematically mis-sizing work |
| `compass rework-scan` | add-then-delete churn stays invisible |
| `compass follow-up` | an owed follow-up can never be settled, so shipping stays blocked |
| `compass adr` | decision records are hand-numbered, and numbers get reused |

A port must document the capability mapping below it too.


| Compass capability | Target runtime mechanism | Status or limitation |
|---|---|---|
| Always-loaded operating instructions |  |  |
| Intent-triggered assessment |  |  |
| User commands or stage interface |  |  |
| Kit CLI invocation |  |  |
| Pre-action enforcement |  |  |
| Post-action issue logging |  |  |
| Session-end status check |  |  |
| Role entry points |  |  |
| Distinct agent contexts |  |  |
| Isolated parallel workspaces |  |  |
| CI integration |  |  |
| Install surface (`bin/compass`, `.claude-plugin/`) |  |  |

An empty cell is a design question, not evidence of equivalence.

Tokens per stage for an interactive quick fix come from a Claude Code adapter, `cli/compass_pkg/session_usage.py`, which reads that runtime's own session transcript. Outside Claude Code a quick fix records `usage.reason: not-claude-code` until a port gives an adapter of its own, and a count a runtime does not give is recorded as null, never 0.

`schemas/adapter-contract.yml` holds this table as data, with the Claude Code
adapter's column filled in. `tests/test_adapter_contract.py` fails when a
capability here has no row there, when an adapter's cell is empty or names a
path that does not exist, or when a directory under `adapters/` has no
column. A port adds its column before it lands. The same test fails on a new
line in `cli/` or `hooks/` that branches on not being some adapter, such as
`if adapter != "claude-code"`: code that needs a capability must ask for the
capability.

## What to reuse

A port normally keeps these unchanged:

- methodology and conceptual documentation;
- governance prose and machine-readable policy;
- approach definitions and rubric;
- artifact templates;
- CLI, schemas and vendored dependencies;
- issue directory layout; and
- CI's `compass ci` contract.

Runtime-specific quick-start instructions may be added without changing the
shared methodology.

## What to implement

The adapter normally gives:

- the target runtime's commands or modes;
- agent or persona definitions;
- skill-loading or equivalent procedural context;
- pre-action, post-action and stop behaviour where supported;
- the always-loaded runtime instruction file;
- plugin or configuration manifests;
- installation and upgrade wiring; and
- isolated parallel execution where supported.

`AGENTS.md` is the runtime-neutral starting point. The Claude Code adapter's
`CLAUDE.md`, commands and hooks are a reference implementation, not the
portable contract itself.

## Conformance test

A port is conforming when the same assessed issue and policy produce:

- the same computed approach;
- a schema-compatible `manifest.yml`;
- the same required artifact and gate set;
- equivalent typed evidence and approval records;
- the same `compass check` verdict; and
- an issue that another Compass runtime can resume without translation.

Test this in both directions: start an issue in each runtime and resume it in
the other. Differences in terminal presentation are acceptable. Differences
in policy outcome or persisted meaning are not.

## Porting sequence

1. Complete the conformance mapping.
2. Wire the target runtime to the unchanged kit CLI.
3. Implement assessment and the eight stage commands.
4. Add role entry points.
5. Add persistence and resumption.
6. Add the strongest enforcement the runtime supports.
7. Add safe parallelism, or declare an orchestration cap.
8. Run cross-runtime conformance tests.
9. Document install, security and known limitations.

The methodology is the long-lived asset, the kit is its deterministic
mechanism, and the adapter is how a particular runtime reaches both.
