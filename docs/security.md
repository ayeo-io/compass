# Security

Compass adds executable hooks, a Python CLI and agent instructions to a
development environment. Review it as tooling that can read and change the
repositories available to your user account.

## Trust boundaries

| Surface | What it can do | Primary control |
|---|---|---|
| Claude Code hooks | Inspect and block tool calls; write issue state | Review the scripts and pin the installed source. |
| Compass CLI | Read project files, write `.compass/`, run configured checks | Limit project-command execution and CI permissions. |
| Commands, agents and skills | Instruct Claude Code how to act on a repository | Install only from a trusted, reviewed revision. |
| Project governance | Change routing and, when enabled, run project checks | Treat governance changes as code changes. |
| `.compass/` artifacts | Persist issue content and command evidence in Git | Keep secrets and sensitive output out of artifacts. |

## Before installing

### Review and pin the source

Compass publishes through the Claude Code plugin **marketplace**. A marketplace
install is still third-party executable code arriving in your environment -
treat it with the same care you would give any dependency, and pin what you
install.

Do not install a fork or mutable branch you do not trust. For organisational
use:

1. pin Compass to a reviewed commit SHA;
2. mirror it to a location your organisation controls where appropriate;
3. review changes before updating the pin; and
4. protect the mirror and release process like other development tooling.

The most important executable surfaces are:

```text
cli/compass
cli/compass_pkg/
hooks/
scripts/install.sh
governance/*.yml
```

Commands, agents, skills and always-loaded instructions are also security
relevant: they influence an agent that can change your repository.

### Understand the hooks

The Claude Code adapter registers four local hooks:

| Hook | Purpose | Can block? |
|---|---|---|
| `pre-tool.sh` | Applies approach-aware red-before-green checks before edits. | Yes |
| `post-tool.sh` | Updates the issue history after relevant actions. | No |
| `stop.sh` | Warns about unfinished or inconsistent issue state. | No |
| `session-start.sh` | Loads the operating contract into the session. In every repository, it also keeps the status line launcher, `compass-statusline`, in the plugin's own data folder under `~/.claude/plugins/data/`; it writes nothing else and prints nothing for it. | No |

They run locally with the same permissions as your user. The shipped hooks do
not need network access, but check the installed revision rather than
relying on this document.

## Git parents

A project can extend a git parent, `github:<owner>/<repo>@<ref>#<sha>`, which
makes the CLI fetch one pinned commit from a remote. A git parent is data: the
CLI reads one file, `compass.yml` at the repository root, as strict YAML, and
runs nothing from the repository. It refuses a settings key (so a parent cannot
authorise project commands), an `unlock:` and a check implementation outside the
registry. It refuses a fetched commit that is not the pinned sha, and a
`compass.yml` that is a symbolic link or larger than 1 MiB.

The fetch runs `git` with an argument list and no shell, only over `https`, with
hooks off and no prompts. It runs with your own git configuration, so your
credential helper runs and your `url.*.insteadOf` rules apply. Only `compass
policy lint`, `compass policy effective`, `compass policy diff` (when a
reference is a git parent) and `compass approach evaluate --write` fetch,
including a reassess that commits a `compass issue configure` proposal.
`compass policy diff` prints a line on stderr before it fetches. `compass check`
and `compass issue configure` never fetch. A cached parent is read without
warning if someone edits the cache, until the parent-state check lands. Review
[git-parents.md](https://github.com/ayeo-io/compass/blob/main/docs/git-parents.md).

## Dependencies

The CLI bundles a pinned copy of PyYAML under `cli/vendor/yaml/`. It adds that
copy to `sys.path` only inside Compass processes; it does not install packages
into the user's Python environment.

`THIRD-PARTY-NOTICES.md` records the version, source, hash and licence. Teams
with stronger supply-chain requirements can reproduce the vendored tree from
the pinned upstream source and compare it.

`jsonschema` is optional and is not bundled. Installing it enables fuller JSON
Schema validation in policy and issue linting.

Run `compass --version` to see which Compass and PyYAML versions are active.

This repository's own CI pins every action by commit SHA and installs its
test tools from `.github/requirements/`, which lists each package at an exact
version; the cucumber-js adapter installs from its lockfile with `npm ci`. The
workflows in `ci/` that you copy pin their actions the same way.

## Project guardrails are executable code

A project guardrail can use `command-passes` - a shipped check **whose
parameter is the command**, not a setting that selects one. `compass check`
runs that string with `subprocess.run(..., shell=True)` from the project root. Its `command:` form still runs a shell; the `script:`
form does not - it runs a file directly, so a value cannot smuggle in a
pipeline or a substitution. That difference is the reason to prefer the script
form, and it is the only reason.

The command form runs from the project root with the Compass process's
permissions.

```yaml
checks: [command-passes]
params:
  command: "python3 scripts/architecture-fitness.py"
```

Treat governance files that declare `command-passes` **as code, not as configuration** - anything a shell can do, a project guardrail can do. It matters because
continuous integration normally runs on a pull request **before** it is
approved, so a contribution's command runs before anyone has read it. The
explicit opt-in that closes this gap is
[issue #65](https://github.com/ayeo-io/compass/issues/65).

### Safer default

Project commands are disabled unless `compass.yml` opts in (or `.compass/config.yml`, for a project that has no `compass.yml`):

```yaml
allow_project_commands: true
```

This prevents accidental execution; it is not a security boundary because a
repository change can edit both the command and the setting.

Prefer the non-shell script form:

```yaml
checks: [command-passes]
params:
  script: scripts/architecture-fitness.py
  args: ["--strict"]
```

Compass resolves the script beneath the project root and passes arguments
without shell interpolation. A symlink that resolves outside the root is
refused.

### Untrusted pull requests

Compass refuses project commands unless the CI environment positively reports
the contribution as trusted. Unknown, blank or unreadable trust state is a
refusal, not permission.

This reduces exposure but is not an unforgeable sandbox. A pull-request branch
can often change its workflow and environment. The effective boundary remains
the CI provider's controls, including restricted secrets, read-only tokens and
approval policy.

For an unrecognised CI provider, set trust outside repository-controlled files:

```yaml
env:
  COMPASS_CONTRIBUTION_TRUST: trusted
```

Do this only for a job whose trigger and source are genuinely trusted.

## CI hardening

**Compass cannot defend against a contributor with push access.**
They can add a command, set the opt-in and merge. No arrangement of in-repo
configuration defends a repository against its own contents - GitHub's own
answer to the same problem is to withhold secrets from forks rather than to
trust a setting.

**And the refusal is not unforgeable either.** On a `pull_request`
event GitHub runs the workflow from the contribution's own merge ref, so the
contribution controls every environment variable Compass sees. The cheap
attacks fail: blanking `GITHUB_EVENT_NAME` or `CI` refuses, claiming
`COMPASS_CONTRIBUTION_TRUST=trusted` does not override GitHub's report of a
fork, and a payload inside the checkout is rejected. What remains is a forged
event payload written outside the checkout and pointed at. That takes real
work rather than one line of YAML - and you should know it is there.

What actually bounds a fork pull request is that GitHub withholds your secrets
from it and issues a read-only token. That is the boundary; the steps below
limit what a fork can reach inside it.

- Declare minimum token permissions. The reference workflow uses
  `permissions: contents: read`.
- Do not expose secrets to untrusted contributions.
- Avoid `pull_request_target` for workflows that check out and run
  untrusted code.
- Add a required-approval gate for workflows from forks where appropriate.
- Review changes to workflows, governance, scripts and hooks using code-owner
  rules or equivalent protection.
- Run project commands in an isolated, short-lived runner where possible.

## Persistent artifacts

`.compass/work/` is committed to the repository. It can contain command
output, test evidence, approvals, decisions and an append-only development
log.

Do not place secrets, access tokens, personal data or sensitive production
output in these files. Redact evidence before committing it, while retaining
enough information for the gate to remain meaningful.

## Known limits

- Shell commands can hide file writes inside scripts and build tools. Hook
  detection is best-effort for shell activity.
- Shell scripts, makefiles and extensionless scripts are not part of the
  default production-file classification for red-before-green checks.
- A contributor with trusted push and merge rights is inside the repository's
  trust boundary.
- Agent instructions are powerful even when they are Markdown rather than
  executable code.
- Compass does not sandbox Claude Code, Python, Git or project commands.

See the [safety contract](safety-contract.md) for the guarantees Compass makes
despite these limits.

## Recommended adoption posture

1. Inspect the pinned revision.
2. Install in a disposable repository.
3. Run the [install smoke test](install-smoke-test.md).
4. Start with project commands disabled.
5. Add least-privilege CI permissions.
6. Enable project commands only after reviewing each declared script.
7. Treat Compass upgrades as tooling upgrades, with diff review and rollback.

If your environment needs a stronger boundary, add sandboxing and policy at the
runner or operating-system level. Do not infer isolation from Compass itself.
