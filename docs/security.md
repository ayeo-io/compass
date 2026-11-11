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
| `pre-tool.sh` | Checks before an edit that scenarios exist and, where the issue owes it, that a person approved them. | Yes |
| `post-tool.sh` | Updates the issue history after relevant actions. | No |
| `stop.sh` | Warns about unfinished or inconsistent issue state. | No |
| `session-start.sh` | Loads the operating contract into the session. In every repository, it also keeps two launchers in the plugin's own data folder under `~/.claude/plugins/data/`: `compass-statusline` for the status line, and `compass` for the person's own terminal. It writes nothing else and prints nothing for them. | No |

They run locally with the same permissions as your user. The shipped hooks do
not need network access, but check the installed revision rather than
relying on this document.

## What Compass runs, sends and fetches

Compass works on your machine and in your repository. It reaches the network
only in the cases below, and each one starts only when you ask for it.

- **Fetches nothing for a configuration.** Since 9.0.0 Compass runs one fixed
  check set (ADR-094). An `extends:` that names a git parent
  (`github:<owner>/<repo>@<ref>#<sha>`) is refused with `L-PARENT-REMOVED`, and
  no command runs `git` to fetch one: not `compass policy lint`, `compass
  policy show`, `compass approach evaluate --write` or `compass check`. In 8.x
  the first three fetched a pinned commit that was not cached.
- **Sends** your delivery record to a git repository you configure, with
  `compass record sync`, which `compass ship-commit` also runs. It happens
  only when `compass.yml` (or `.compass/config.yml` in a project without one)
  names a `record:` remote; it redacts
  credentials, and rival product names when `record.names_key` is set.
- **Runs** commands on your machine: the test command you give `compass
  tdd-red`, `compass tdd-green` and `compass quick-fix finish`, your
  project's own guardrails declared with `check: command-passes`, git in your
  repository, and the CLI itself from the plugin's hooks.
- **Clones and installs** no other framework. The evaluation harness that
  compares frameworks is `harness.py` in the sdd-bench `tools` folder, which
  maintainers run by hand (ADR-093).

## Git parents

9.0.0 removed git parents (ADR-094). An `extends:` that names one is refused
with `L-PARENT-REMOVED`, and no command runs `git` to fetch it, so no remote
content reaches a configuration. A `.compass/cache/parents/` folder that an
8.x run left is not read; you can delete it.

## Calls to GitHub

Compass writes nothing to GitHub. 9.0.0 removed the label sync (ADR-093), so a
project's `github_labels` setting is not read, and `compass policy lint` names
it with `L-SETTING-REMOVED`.

`compass issue link set --pr` reads one pull request with `gh pr view`: its
number, state, author, head commit, merge commit, merge time and URL. After
the merge it also reads the pull request's reviews with `gh api` and the
login `gh` reads as with `gh api user`, to record the ship approval. Compass
runs `gh` with an argument list and no shell, with your own login. It reads
no token and stores none. It checks the repository and number against a
strict pattern before the call. A call that takes longer than 15 seconds is
abandoned. Of a review Compass reads its id, state, time, commit, URL and
the reviewer's login and account type, and never its text. It stores no other
text from GitHub.

Review
[github-links.md](https://github.com/ayeo-io/compass/blob/main/docs/github-links.md).

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

## Project governance is executable code

A project check (`project_checks` in `compass.yml`, see
`docs/configuration.md`) uses `command-passes` - a shipped check **whose
parameter is the command**, not a setting that selects one. `compass check`
runs that string with `subprocess.run(..., shell=True)` from the project
root, with the Compass process's permissions.

```yaml
project_checks:
  - id: arch-fitness
    name: Architecture fitness
    command: "python3 scripts/architecture-fitness.py"
    stage: build
```

Treat a `compass.yml` that declares a project check **as code, not as configuration** - anything a shell can do, a project check can do. It matters because
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
repository change can edit both the command and the setting. A project check
is in `compass.yml`, the same file that holds `allow_project_commands`, so
one change can add both. That was so from 6.0.0; before, the setting lived
apart from the governance files that held the checks. That separation was
never a control. The control is the trust decision, which runs first and
reads nothing from the project.

### The script form, for an 8.x project guardrail

A project check takes only `command`, which still runs a shell. An 8.x
project guardrail, kept in an issue's stored generation or in a project's
copy of the governance files, can also use the script form, which runs a
file directly, so a value cannot add a pipeline or a substitution:

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
contribution controls every environment variable Compass sees. The simple
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
  default production-file classification of the pre-tool hook.
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
