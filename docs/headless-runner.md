# The headless runner

`compass run` runs the build or verify stage of one issue with nobody in the session. It starts one fresh `claude -p` session per cycle, and between cycles decides from the manifest and the evidence alone whether to go on. ADR-030 records why Compass starts sessions at all.

**The live acceptance is not met yet:** a quick-fix example run from assess to ship in CI. It needs an Anthropic secret in GitHub Actions and a spend limit, and every run costs money, so it waits for the maintainer. Every test of the runner uses a stub `claude`.

## Running it

```
compass run <slug> --stage verify --stop-file .compass/STOP
```

| Flag | Meaning |
|---|---|
| `--stage` | `build`, which runs `/compass:implement`, or `verify`, which runs `/compass:verify`. Nothing else can run unattended. |
| `--stop-file` | Required. Create this file to stop the run before its next session. A relative path is read from the project root, not from where the command was started. |
| `--max-cycles` | Sessions to start at most. At most the RP-LOOP-006 ceiling, 30. |
| `--max-minutes` | Minutes to run at most; decimals are allowed. At most the RP-LOOP-007 ceiling, 240. |
| `--max-cost-usd` | US dollars the run may spend at most. At most the RP-LOOP-008 ceiling, 5. Each session gets what is left as its `--max-budget-usd`, and the run stops once the sessions' reported costs reach the ceiling. |
| `--claude` | The `claude` executable, when it is not on the path. |

Exit codes: 0 when the stage is done, 4 when the run stopped, 2 when it was refused before any session started.

One issue runs one stage at a time. A run holds `run.lock` in the issue's folder under `.compass/work/` while it goes, and a second run of the same issue is refused. A run that is killed leaves the lock behind; delete it once no run is going.

## When a run stops

Before each cycle the runner stops if the stop file exists, the cycle ceiling is reached, or the minutes are spent. After each session it stops once the money spent reaches the cost ceiling. After each session it stops if:

- the stage is done: every gate passes for the verify stage; every scenario has a green record for the build stage;
- the session landed the issue, which an unattended run must never do;
- the manifest cannot be read;
- the manifest and the evidence did not change for as many cycles in a row as the RP-LOOP-005 ceiling allows, 3.

A session that runs past the minute ceiling is ended, with every process it started. An interrupted run (Ctrl-C, or a cancelled CI job's SIGTERM) ends the running session the same way, records the interruption as its stop reason, and exits with the signal's code.

## What each session is told

Each session gets `COMPASS_ISSUE` set to the run's issue, so the hooks and the CLI in it judge the run's issue, whatever issue `.compass/current-task` names for the person working beside it. The run never writes the pointer.

The prompt names the stage's command and the issue, says nobody will answer a question, and forbids landing, shipping, pushing and merging. The session loads the Compass plugin the running CLI belongs to, and `git push`, `gh pr merge` and `compass ship-commit` are denied to it. No session resumes another.

Without a person to answer a permission prompt, a session can use only what it is given: the file tools, skills, and the `compass` CLI, which runs the test command itself. `compass quick-fix finish`, which commits through `ship-commit`, and `compass run` itself are denied.

The denied commands are matched by how they start, so another spelling of the same command, such as `git -C . push`, is not denied. What stops a landing is the check after every session: a session that lands the issue stops the run. Grant the session no credential that can push.

## What a run leaves

- `run-<n>.md` in the issue's documents folder: the stage, the times, the outcome, the stop reason, the money spent, each cycle's exit code, session, cost and whether it changed the records, and what each session said last.
- A `runs:` entry in the manifest: `{n, stage, started, ended, cycles, outcome}`, and for a stopped run `stopped_reason: {reason, evidence, at}`, with the run record as the evidence.

## The demo in CI

`scripts/run-demo.sh` builds a project with one known bug, records its failing test as a quick fix, and runs the build stage on it. In Compass's own repository, `.github/workflows/compass-run-demo.yml` runs it when started by hand. It authenticates by identity federation, as the review job does, so no key is stored: the job's GitHub OIDC token goes to a file named by `ANTHROPIC_IDENTITY_TOKEN_FILE`, and a profile (`ANTHROPIC_CONFIG_DIR`, `ANTHROPIC_PROFILE`) lets the run's several `claude` processes share one exchanged token. The record is kept as the job's artifact.

## Credentials

The runner reads no credential. It passes its own environment to `claude` unchanged. Everything it writes or prints passes through `cli/compass_pkg/redact.py` first, which replaces Anthropic, GitHub, AWS and bearer tokens, `key=value` secrets, and the value of any environment variable whose name contains KEY, TOKEN, SECRET or PASSWORD.

## Code

| File | Role |
|---|---|
| `cli/compass_pkg/run_cmd.py` | The verb and the loop. |
| `cli/compass_pkg/host_launch.py` | Starts one `claude -p` call. The eval harness uses it too. |
| `cli/compass_pkg/redact.py` | Removes credentials from text. |
| `ci/headless-verify.yml` | Reference workflow, started only by hand. |
