---
description: Approve the request Compass showed you
argument-hint: "[<n> [--issue <slug>]]"
disable-model-invocation: true
---

# /compass:approve

The person typed this command. Compass's prompt hook has already acted on it
before you read this. The person can name the request's issue with `--issue
<slug>`, and the hook finds the request in any worktree.

**When Compass's result is in your context** (a line that starts "Compass
recorded"), the approval is recorded. Say in one line what was recorded, then
go on with the work that waited for it.

**When no Compass result is in your context**, the hook did not run, for
example on a Claude Code version without the `UserPromptExpansion` event.
Then:

- tell the person that nothing was recorded;
- tell them the fallback: they run `compass evidence approve` with the form
  the request names, `--approver <their id>`, `--role <role>` and `--scope`,
  in their own terminal. With a plugin install their terminal has no
  `compass` until they add it to `PATH`, so name the launcher in its place:
  `compass-compass/compass` in the `plugins/data/` folder of their Claude
  Code configuration (`~/.claude` unless they use another profile);
- never record the approval yourself, by any command or file edit, and stop.
