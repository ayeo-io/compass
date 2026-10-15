# Compass for Codex

The Codex adapter uses Compass's existing commands, agent instructions, hooks
and Python CLI. It adds one entry skill and translates Codex hook payloads.
It does not implement another policy engine.

## Install from a source checkout

Use Python 3.10 or later, Bash and Git on macOS or Linux. The inspected host
is Codex CLI 0.162.1 on macOS. Native Windows is not supported.

Pin the Compass checkout to the revision you want to use, then run:

```bash
python3 adapters/codex/install.py --project /absolute/path/to/your/project
```

The project must already exist. The installer links `.agents/skills/compass`
to the source skill, appends a managed instruction block to `AGENTS.md`, and
merges Compass entries into `hooks.json` in the project’s `.codex` directory. Other instructions and hooks
remain. A conflicting skill, changed managed block or changed Compass hook
stops installation before it writes anything. The receipt lives at
`codex-install.json` in the project’s `.compass` directory.

Restart Codex, trust the project when prompted, then use `/hooks` to review
and trust the installed hooks.
Installation never grants that trust. Keep the source checkout in place.
After updating or moving it, run the installer again from its new location.
Do not edit the managed instruction block; put project instructions outside it.

Remove only the installed wiring with:

```bash
python3 adapters/codex/install.py --project /absolute/path/to/your/project --uninstall
```

The installer preserves issue records and unrelated user files. If you changed
owned wiring, it refuses removal and names the conflict for you to resolve.

## Use the shared stages

In the inspected Codex CLI, invoke `$compass:compass assess <description>`. The same skill accepts
`define`, `refine`, `plan`, `breakdown`, `implement`, `verify` and `ship`.
For product, design, marketing and QA use `intent`, `design`, `position` and
`consult qa`. Without an argument it reads the recorded issue and asks the kit
for the next action. The skill reads the shared command source for each stage.

Use explicit `--issue <slug>` on kit calls. Each worktree keeps its own
`.compass/current-task` and records. An inherited environment variable can
name another session's issue; check the manifest before resuming it.

## Plugin packaging

`.codex-plugin/plugin.json` points at the same skill and the adapter's hook
configuration. A plugin-enabled host must review its hooks before they run.
Choose either source installation or plugin installation in a project, to
avoid duplicate hook calls. Native marketplace installation and hook discovery
were checked in an isolated Codex home on CLI 0.162.1. Hook execution through a
complete native model session remains unmeasured.

## Control support by runtime

**Enforced** means the mechanism refuses a supported action or returns a failing
exit code. **Advisory** means instructions or warnings depend on the agent
acting on them. **Absent** means no mechanism is installed for that surface.
These statuses describe the mechanism, not proof of a complete native journey.

| Control | Claude Code | Codex |
|---|---|---|
| Pre-action hook blocks | Enforced for supported file edits; shell coverage has the limits in the safety contract | Enforced by the bridge for supported patches and shell calls when hooks run; absent until hooks are trusted. Native model-turn enforcement is unmeasured; timeouts and unsupported tool paths can bypass the hook |
| Session bootstrap | Advisory: SessionStart injects the shared contract | Advisory: trusted SessionStart injects the shared contract and adapter instructions; absent while untrusted. Resume and compaction are unmeasured |
| Intent-triggered assessment | Advisory: the model follows the operating instructions | Advisory: the model follows the same contract through AGENTS.md and the entry skill |
| Post-action logging | Advisory record of supported edits; does not block | Advisory record of supported patch targets when hooks run; absent for shell edits and unsupported paths |
| Session-end check | Advisory warning; never blocks session end | Advisory warning on stderr when hooks run; native presentation is unmeasured |
| `compass check` | Enforced when invoked: failures return non-zero | Enforced when invoked: the same unchanged kit checks the same records |
| `compass ci` | Enforced when invoked and its exit code is honoured by CI | Enforced when invoked and its exit code is honoured by CI; no Codex-specific CI engine |

The kit does not force a person or agent to invoke it. Install the CI integration
and honour its exit code to make its checks a merge condition.
[The safety contract](safety-contract.md) describes the shared checks and their limits.
The machine-readable registry uses full, partial and none for capability coverage;
those labels do not mean enforced, advisory and absent.

## What has been checked

The subprocess tests install, reinstall and remove wiring in scratch projects.
They check collisions, preserved instructions, patch target checks, the spike
exception, shell payloads, contract injection and edit logging. The explicit
native smoke checks the advertised skill name and that the four discovered
hooks remain untrusted. It sends no model turn. Run it on a host
with Codex installed; it fails if Codex is missing:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/native_codex_smoke.py -q
```

The portable suite does not collect this host smoke. The registry at `schemas/adapter-contract.yml` names each capability and its limitations.

These tests do not show that a native Codex session completed the pipeline.
Cold resume, compaction, Linux host execution, clean-machine installation and
an external user delivering an issue remain unmeasured. Cross-runtime delivery
equivalence needs the behaviour conformance suite; a structural registry alone
does not prove it.

Official references checked on 15 October 2026:

- [Plugin packaging](https://developers.openai.com/plugins/build/plugins)
- [Codex hooks and their limits](https://learn.chatgpt.com/docs/hooks)
- [Local skill discovery](https://learn.chatgpt.com/docs/build-skills)
- [Project instruction discovery](https://learn.chatgpt.com/docs/agent-configuration/agents-md)
