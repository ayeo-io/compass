# Install smoke test

Use this checklist after you install Compass or change its installation.
Run it in a scratch Git repository, so the test issue does not enter a real
project.

Compass supports Claude Code only; the Codex adapter stays on 8.x.

For each case, record the host version, the Compass revision, the OS, the
installation method, the hook trust state, the raw output, and the expected
and observed result. Mark each case `passed`, `failed`, `unsupported` or
`unmeasured`.

An independent acceptance needs another person to install Compass and
complete a scratch issue; record who tested. A run by the author is a local
installation check only. The [adapter behavior guide](adapter-conformance.md)
says why.

## 1. Check the prerequisites

```bash
python3 --version
git --version
```

Compass needs Python 3.10 or later. Its CI tests Python 3.11. The CLI
bundles its YAML parser; `jsonschema` is optional.

Without Python 3.10 or later, `scripts/install.sh` warns and installs
anyway. The first session in a Compass project then says so in place of the
operating contract. `docs/safety-contract.md` says what each hook does then.

## 2. Install Compass

### Plugin marketplace

From a shell:

```bash
claude plugin install compass --marketplace ayeo-io/compass
```

Or inside Claude Code:

```text
/plugin marketplace add ayeo-io/compass
/plugin install compass@compass
```

Restart Claude Code if the new commands do not show.

The marketplace installs the copy on the `plugin` branch, not the whole
repository. Check the install folder:

- it has no `tests/` or `docs/` folder;
- its `.claude-plugin/plugin.json` names the release's version.

On a profile that has an earlier version, run `claude plugin update
compass@compass` and check that the version rises.

### From source

```bash
git clone https://github.com/ayeo-io/compass.git
cd compass
bash scripts/install.sh --global
```

Add `bin/` to your `PATH` to make `compass` invokable, or call it as
`python3 cli/compass`.

- `--project <directory>` installs for one project.
- `--copy` installs copies, not symlinks.
- For an organization, pin the checkout to a reviewed commit, not a branch.
  See [Security](security.md).

## 3. Check the CLI

From a source checkout:

```bash
python3 cli/compass --version
python3 cli/compass policy lint
```

Expect:

```text
compass 9.0.0 (issue schema 3.0)
PyYAML 6.0.2 at .../cli/vendor/yaml/__init__.py
```

The PyYAML path must be the bundled copy, not one from your environment.
Policy lint must end in `PASS`.

To check that the CLI uses no package from your Python environment:

```bash
python3 -m venv --without-pip /tmp/compass-bare-check
/tmp/compass-bare-check/bin/python3 cli/compass --version
```

For full JSON Schema validation only, install `jsonschema`:

```bash
python3 -m pip install jsonschema
```

## 4. Create a scratch issue

In a scratch Git repository, open Claude Code and run:

```text
/compass:assess "Test the Compass installation"
```

Compass must create:

```text
.compass/current-task
.compass/work/<issue-slug>/manifest.yml
```

The slug can vary. `.compass/work/<issue-slug>/` holds the manifest, the
evidence and the markers. The manifest holds the delivery approach. The
acceptance criteria go in
`docs/compass/<date>-<issue-slug>/acceptance-criteria.md`, where `<date>` is
the manifest's `created:` date.

Run `compass approach show --issue <issue-slug>`. It must show the approach,
the gates and where the issue's files go. `compass next` names the next
action.

If `/compass:assess` is unknown, the adapter is not loaded. Restart Claude
Code, then check the installation.

## 5. Confirm an incomplete issue fails honestly

```bash
compass check --issue <issue-slug>
```

A newly assessed issue must fail: its evidence does not exist yet. A correct
result:

- names the failed check;
- gives a fix; and
- exits non-zero without a Python traceback.

A traceback or a "governance not found" error shows an installation or path
problem.

## 6. Check the hooks

Assess a small delivery issue with `/compass:assess`. Then try to edit
production code before you add a scenario. The pre-tool hook must block the
edit and name `compass scenario add`.

Do not run this check on a spike: the hook never refuses a spike's edits.

For a source install, the Claude Code settings must contain Compass entries
for:

- `hooks/pre-tool.sh`;
- `hooks/post-tool.sh`;
- `hooks/stop.sh`;
- `hooks/session-start.sh`;
- `hooks/prompt-approval.sh`; and
- `hooks/approval-summary.sh`.

These hooks run with your user permissions. Review them before you use
Compass in a sensitive environment.

## 7. Test source uninstall and reinstall

Source installs only:

```bash
bash scripts/install.sh --global --uninstall
bash scripts/install.sh --global
bash scripts/install.sh --global
```

- `--uninstall` removes the install that the same scope flag made. Without
  `--global` it looks in the current directory's `.claude` and, after a
  global install, removes nothing.
- Uninstall must remove only what the installer added.
- Both reinstall runs must succeed without duplicate hook entries.

## Troubleshooting

| Symptom | Check |
|---|---|
| Command is unknown | Restart Claude Code; check the plugin or source adapter path. |
| `policy lint` cannot find governance | Run from the project, or use the CLI from a complete Compass checkout. |
| Edit is blocked | Read the refusal. Add a scenario, get the scenario approval it names, or confirm the issue is a spike. |
| Hooks were not registered | Install `jq` and rerun the source installer, or follow its manual instructions. |
| Existing Compass directory is not overwritten | Move the unrelated directory aside; the installer stops with an error. |

If a failure is not covered here, report the exact command, exit code and
output. Remove secrets before you attach logs.
