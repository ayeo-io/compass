---
name: compass
description: Use Compass stages and roles to deliver a change or resume an issue, using the shared kit and instructions.
---

Read `adapters/codex/INSTRUCTIONS.md` at the framework root before acting.
The adapter root is two levels above this directory. Its `runtime.py context`
command prints the absolute framework root and shared instruction paths.
Use that root to read `compass-contract.md`, then `skills/compass-runtime/SKILL.md`.

The user's first argument selects a shared command: `assess`, `define`,
`refine`, `plan`, `breakdown`, `implement`, `verify`, `ship`, `quick-fix`,
`status`, `flow`, `init`, `go` or `consult`. Read `commands/<name>.md` at the
framework root and follow it. For product, design, marketing and QA use
`intent`, `design`, `position` and `consult qa`. Never invent a command path.
Without an argument, read the current issue and run the kit's `next` command.

Use the shared `agents/` files when a command calls for a distinct agent
context. An agent file's Claude-specific tool and model metadata is not a
Codex configuration; use available Codex tools and the session's model.
Keep the architect advisory and all roles on one acceptance specification.

Treat `${CLAUDE_PLUGIN_ROOT}` in shared markdown as the framework root printed
by `runtime.py context`. Treat `/compass:<stage>` as this skill with that stage
argument. Pass the user's remaining arguments as `$ARGUMENTS`.
Call `python3 <framework-root>/cli/compass` for mechanism. Use explicit
`--issue <slug>` on issue commands; never assume an inherited issue belongs
to the current checkout. No policy or evidence check is reimplemented here.
