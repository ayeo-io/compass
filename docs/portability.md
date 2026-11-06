# Portability

Compass 9.0.0 supports Claude Code only; the Codex adapter stays on 8.x. Most
of Compass is still deliberately runtime neutral. A port should replace the
adapter, not fork the methodology or reimplement the policy engine.

## The three-layer boundary

| Layer | Responsibility | Representative files | Porting rule |
|---|---|---|---|
| Methodology | Defines the flow, roles, artifacts, guardrails and strategies. | `docs/`, `approaches/`, templates, governance Markdown | Reuse. |
| Kit | Computes the evidence each change owes, checks state and writes mechanical evidence. | `cli/`, governance YAML, schemas, `manifest.yml` | Invoke. |
| Adapter | Maps Compass into a particular agent runtime. | commands, agents, skills, hooks, runtime instructions and install wiring | Rebuild. |

The boundary follows the determinism model:

- the adapter produces an assessment because assessment needs judgement;
- the kit computes the evidence the change owes because that must be
  deterministic; and
- the adapter runs the path while calling the kit for checks and state
  mutations.

A port that independently implements routing or guardrails may resemble
Compass, but it will drift from Compass policy.

## Runtime adapter contract

### The Claude Code adapter layer

The shipped adapter is Claude Code: `commands/` are the path interface,
`skills/` the loadable procedures, `hooks/`
the pre-action enforcement, and `.claude-plugin/` the install wiring. A port
rebuilds that layer and reuses everything under it.

```
commands/        the path interface (the /compass: namespace)
skills/          adaptive-routing, atdd, bdd-specification, behavior-mapping,
                 compass-runtime, evidence-gates, flow-management,
                 governance-check, intent-interview,
                 receiving-code-review, systematic-debugging,
                 tdd-discipline
hooks/           pre-tool.sh, post-tool.sh, stop.sh, session-start.sh,
                 prompt-approval.sh, approval-summary.sh
bin/compass      the shim that puts the kit on PATH
.claude-plugin/  the plugin manifest and marketplace entry
```

Take care with `architect`: it is a perspective the session takes across
the path, not a separate agent or command, so a port must not turn it into
one.

A conforming adapter must satisfy the following requirements.

### 1. Assess before changing delivery artifacts

The runtime must recognise intent to build, change or fix files, even when the
user does not type an explicit Compass command.

Before the first delivery change it must:

1. assess risk, familiarity and size, and any goal or urgency switch;
2. record the assessment with `compass quick-fix start`, or in the manifest
   and then with `compass approach evaluate --write`; and
3. show the person the three lines of `compass approach show`: the
   approach, the evidence the change owes and where the files go.

Conversation and read-only exploration do not need an issue. A delivery
change does.

### 2. Expose the delivery flow

The adapter must expose the four stages of the path, whether as one command
that runs them all, as the shipped `/compass:go` does, or an equivalent
interface:

```text
assess → specify → build → ship
```

It must collect the evidence the change owes, as `compass approach show`
lists it, and follow the `next:` line each kit call prints. From 9.0.0 the
stages have no modes, and the one document Compass needs is
`acceptance-criteria.md` (ADR-091, ADR-092).

### 3. Call the kit

The adapter must invoke, rather than reproduce, the kit's deterministic
operations. At minimum:

| Need | Kit command |
|---|---|
| Compute or update the evidence a change owes | `compass quick-fix start`, `compass approach evaluate` |
| Name the next step | `compass next` |
| Check an issue | `compass check` |
| Record red and green tests | `compass tdd-red`, `compass tdd-green` |
| Check governance and issue schemas | `compass policy lint`, `compass issue lint` |
| Run the CI lane | `compass ci` |
| Show every issue's state | `compass flow` |

Schema-owning state changes must also use kit commands where one exists,
rather than editing `manifest.yml` ad hoc.

### 4. Preserve the safety contract

The adapter must call `compass check` at the ship stage and before the commit,
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
aware of the spike so it does not block one. Without hooks, the adapter must
make the check an explicit step of build.

**A person-only approval event.** In Claude Code a person approves by
typing `/compass:approve`; `hooks/prompt-approval.sh` records it on the
`UserPromptExpansion` event (ADR-068). An adapter may wire such a prompt path
only after a dated measurement on its host shows that the event fires for a
command a person typed and that the model cannot raise it, through a tool, a
scheduled job, a subagent or another session. Until then the adapter sets
`COMPASS_APPROVAL_CHANNEL=terminal`, and `compass evidence request` prints the
exact `compass evidence approve` command for the person's own terminal.

**A time limit on the pre-tool hook.** On Claude Code, `hooks/hooks.json` sets
`"timeout": 15` and `"onFailure": "block"` on the pre-tool hook, so a hook that
runs out of time can block the call from Claude Code 2.1.295. A source install
(`scripts/install.sh`) does not set these keys and keeps the default timeout
of 600 seconds. An adapter on another runtime needs its own bound; the safety
contract states the length limit that holds on every version.

An adapter limitation can reduce convenience or parallelism. It must not
silently weaken a guardrail.

### 5. Keep one specification for every role

From 9.0.0 there are no role entry points (ADR-093). Product, design,
engineering, marketing and QA read the same acceptance criteria, and a brief
opens them through the `intent-interview` skill.

The adapter must preserve claim traceability: the manifest's `claims:` and
the `claim-traces-to-scenario` check. Otherwise a public claim can ship with
no scenario behind it.

### 6. Persist state on disk

Nothing essential may live only in conversation. The adapter must maintain:

```text
.compass/current-task
.compass/work/<issue>/manifest.yml
.compass/work/<issue>/evidence/
docs/compass/<created>-<issue>/acceptance-criteria.md
```

From 9.0.0 Compass writes no `devlog.md` for a new issue; an archived issue
keeps its own.

A different session or runtime can resume by reading this state.

### 7. Give safe delivery orchestration

The adapter must support solo delivery. From 9.0.0 that is all it needs:
each issue runs in one session, and the session builds its scenarios one
after another (ADR-090). No adapter needs isolated
workspaces or an integration owner.

## Conformance mapping

### The mapping table

A port must document the cross-issue kit calls before implementation, listed
here because an adapter that wires up only the per-issue verbs will look
complete and lose the view across open issues:

| Kit call | What a port loses without it |
|---|---|
| `compass flow` | no view of blockers or owed follow-ups across issues |
| `compass next` | the session guesses which stage comes next |
| `compass follow-up` | an open Definition of Done item cannot be linked to the GitHub issue that tracks it, so shipping stays blocked |
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
| Distinct agent contexts |  |  |
| Isolated parallel workspaces |  |  |
| CI integration |  |  |
| Person-only approval event |  |  |
| Install surface (`bin/compass`, `.claude-plugin/`) |  |  |

An empty cell is a design question, not evidence of equivalence.

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
- the path, the spike and the rubric;
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

- the same computed approach and evidence;
- a schema-compatible `manifest.yml`;
- the same gate set;
- equivalent typed evidence and approval records;
- the same `compass check` verdict; and
- an issue that another Compass runtime can resume without translation.

Test this in both directions: start an issue in each runtime and resume it in
the other. Differences in terminal presentation are acceptable. Differences
in policy outcome or persisted meaning are not.

The [adapter behaviour checks](adapter-conformance.md) exercise real subprocess
entries, persisted records and equivalent hook payloads. Their local results do
not establish native instruction loading, trusted host dispatch, cold resumption
or context compaction. Native and independent acceptance need separate captures;
the guide defines their required fields and keeps unmeasured results visible.

## Porting sequence

1. Complete the conformance mapping.
2. Wire the target runtime to the unchanged kit CLI.
3. Implement assessment and the four stages of the path.
4. Add persistence and resumption.
5. Add the strongest enforcement the runtime supports.
6. Run cross-runtime conformance tests.
7. Document install, security and known limitations.

The methodology is the long-lived asset, the kit is its deterministic
mechanism, and the adapter is how a particular runtime reaches both.
