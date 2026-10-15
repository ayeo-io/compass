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
merges Compass entries into `.codex/hooks.json`. Other instructions and hooks
remain. A conflicting skill, changed managed block or changed Compass hook
stops installation before it writes anything. The receipt lives at
`.compass/codex-install.json`.

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

## What has been checked

The subprocess tests install, reinstall and remove wiring in scratch projects.
They check collisions, preserved instructions, patch target checks, the spike
exception, shell payloads, contract injection and edit logging. When Codex is
installed, `tests/test_codex_native.py` also checks the advertised skill name
and that the four discovered hooks remain untrusted. It sends no model turn.
The registry
at `schemas/adapter-contract.yml` names each capability and its limitations.

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
