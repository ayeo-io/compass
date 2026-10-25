---
description: Reject a request, or overrule a delegated approval
argument-hint: "[<n> | <record id>] <reason> [--issue <slug>]"
disable-model-invocation: true
---

# /compass:reject

The person typed this command. Compass's prompt hook has already acted on it
before you read this. The person can name the request's issue with `--issue
<slug>`, and the hook finds the request in any worktree.

**When Compass's result is in your context** (a line that says the person
rejected a request), do not go on with the work that waited for it. Say what
was rejected and the reason, and ask the person what should change.

**When no Compass result is in your context**, the hook did not run. Then:

- tell the person that nothing was recorded;
- tell them the fallback for a human check: they run `compass evidence
  approve --check <id> --decision rejected` with `--approver`, `--role` and
  `--scope` in their own terminal. With a plugin install their terminal has
  no `compass` until they add it to `PATH`, so name the launcher in its
  place: `compass-compass/compass` in the `plugins/data/` folder of their
  Claude Code configuration (`~/.claude` unless they use another profile);
- never record the rejection or an approval yourself, and stop.
