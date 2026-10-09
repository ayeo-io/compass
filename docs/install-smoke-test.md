# Install smoke test

Use this checklist after installing Compass or changing its installation.
Run it in a scratch Git repository so the test issue does not enter a real
project.

## 1. Check the prerequisites

```bash
python3 --version
git --version
```

Compass needs Python 3.10 or later. Its CI tests Python 3.11. The CLI bundles
its YAML parser; `jsonschema` is optional. Without Python 3.10 or later,
`scripts/install.sh` warns and installs anyway, and the first session in a
Compass project says so in place of the operating contract;
`docs/safety-contract.md` says what each hook does then.

## 2. Install Compass

### Plugin marketplace

Inside Claude Code:

```text
/plugin marketplace add ayeo-io/compass
/plugin install compass@compass
```

Restart Claude Code if the new commands are not immediately visible.

### From source

```bash
git clone https://github.com/ayeo-io/compass.git
cd compass
bash scripts/install.sh --global
```

Use `--project <directory>` for a project-scoped install or `--copy` when
symlinks are unsuitable.

For an organisational install, pin the checkout to a reviewed commit rather
than following a branch. See [Security](security.md).

## 3. Check the CLI

From a source checkout:

```bash
python3 cli/compass --version
python3 cli/compass policy lint
```

Expect:

```text
compass 5.6.0 (issue schema 3.0)
PyYAML 6.0.2 at .../cli/vendor/yaml/__init__.py
```

The PyYAML path is the point: it must be the bundled copy, not one from your
environment. Policy lint must end in `PASS`.

To prove the CLI is not relying on packages from your Python environment:

```bash
python3 -m venv --without-pip /tmp/compass-bare-check
/tmp/compass-bare-check/bin/python3 cli/compass --version
```

Install `jsonschema` separately only if you want full JSON Schema validation:

```bash
python3 -m pip install jsonschema
```

## 4. Create a scratch issue

In a scratch Git repository, open Claude Code and run:

```text
/compass:assess "Test the Compass installation"
```

Confirm that Compass created:

```text
.compass/current-task
.compass/work/<issue-slug>/manifest.yml
docs/compass/<date>-<issue-slug>/delivery-approach.md
```

The exact slug can vary. The manifest, evidence and markers are in
`.compass/work/<issue-slug>/`. The issue's documents are in
`docs/compass/<date>-<issue-slug>/`, where `<date>` is the manifest's
`created:` date. A change as small as this one is normally assessed as a quick fix, which
keeps `delivery-approach.md` there. For a heavier approach the record sits
beside the manifest. `compass issue artifact-path delivery-approach` prints its
path either way.

Generate the review dashboard:

```bash
compass issue dashboard render --issue <issue-slug>
```

Open the generated `README.md` in `.compass/work/<issue-slug>/`. It must show
the status and approach, the review pack, anything deliberately omitted,
whether a decision is awaited, and each scenario's traceability. `compass next`
names the next action.

If `/compass:assess` is unknown, the adapter is not loaded. Restart Claude
Code, then check the plugin installation or source-install wiring.

## 5. Confirm an incomplete issue fails honestly

From the scratch repository, run the CLI against the issue:

```bash
compass check --issue <issue-slug>
```

For a newly assessed issue, failure is expected: acceptance, implementation
and verification evidence do not exist yet. A healthy result:

- names the failed check;
- gives a fix; and
- exits non-zero without a Python traceback.

A traceback or “governance not found” error shows an installation or path
problem rather than an uncleared gate.

## 6. Check the hooks

Start a small delivery issue, define one scenario, then try to edit production
code before recording a failing test. The pre-tool hook must block the edit
and explain how to record the red test.

Do not run this check on a spike: spikes deliberately suspend the
red-before-green strategy.

For a source install, confirm the Claude Code settings contain Compass entries
for:

- `hooks/pre-tool.sh`;
- `hooks/post-tool.sh`;
- `hooks/stop.sh`; and
- `hooks/session-start.sh`.

These hooks run with your user permissions. Review them before using Compass
in a sensitive environment.

## 7. Test source uninstall and reinstall

This step applies only to source installs:

```bash
bash scripts/install.sh --global --uninstall
bash scripts/install.sh --global
bash scripts/install.sh --global
```

`--uninstall` removes the install that the same scope flag made. Without
`--global` it looks in the current directory's `.claude` and, after a global
install, removes nothing. Uninstall must remove only the Claude Code adapter wiring. Both reinstall
runs must succeed without duplicate hook entries.

## Troubleshooting

| Symptom | Check |
|---|---|
| Command is unknown | Restart Claude Code; check the plugin or source adapter path. |
| `policy lint` cannot find governance | Run from the project or use the CLI from a complete Compass checkout. |
| Edit is blocked | Record a failing test first, or confirm the issue is correctly assessed as a spike. |
| Hooks were not registered | Install `jq` and rerun the source installer, or follow its manual instructions. |
| Existing Compass directory is not overwritten | Move the unrelated directory aside; the installer fails safely. |

If a failure is not covered here, report the exact command, exit code and
output. Remove secrets before attaching logs.
