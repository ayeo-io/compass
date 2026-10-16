# Compass in Codex

Read the framework's `compass-contract.md` before changing files. The source
root is two levels above this file. The `$compass:compass` skill maps each stage and
role to its shared source. Read those files; do not recreate their procedures.

Run the unchanged kit as `python3 <source-root>/cli/compass`, from the project
you are changing. Use `--issue <slug>` on issue commands. Check that the issue
exists in this checkout before resuming it. An inherited `COMPASS_ISSUE` can
belong to another session. Keep the current-task pointer and all issue records
in the worktree where the work happens.

On an implementation request, assess before changing delivery files. Resume
an existing assessed issue from its manifest, approach and artifacts. Read
`skills/compass-runtime/SKILL.md` for stage ownership and the `next` command
for the recorded next action. Use the shared flow, retrospective, rework,
follow-up and ADR commands as that stage map describes.

For distinct agent contexts, use Codex's available delegation tool with the
shared agent file and an explicit brief. Keep model choices from the current
session; Claude-specific frontmatter does not configure Codex. Builders work
only in assigned isolated workspaces. If delegation or isolation is unavailable,
record a solo plan within the computed ceiling before implementing.

Project installation adds instructions, the entry skill and local hooks. A
plugin installation gives the same skill and hook adapter. Choose one
installation method per project to avoid duplicate hook calls. Restart after
installation and review the hooks in Codex's trust interface. Installation does
not grant trust or change sandbox permissions. Do not bypass that review.

Pre-action hooks adapt patch headers and pass them to Compass's existing
checks. Hooks are a partial control: Codex can skip untrusted hooks, and a host
timeout or unsupported tool path can allow an action without a completed check.
Always record red/green with the kit and run `check` at `verify` and before `ship`.
Never treat a missing hook response as passing evidence. Keep human approval
for irreversible actions. Native Windows is outside this adapter's scope
because the shared hooks need Bash. See `docs/codex.md` for tested scope.
