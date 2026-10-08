# The headless runner

`compass run` runs the build or verify stage of one issue with nobody in the session. It starts one fresh `claude -p` session per cycle, and between cycles decides from the manifest and the evidence alone whether to go on. ADR-030 records why Compass starts sessions at all.

**What has run live:** the build stage of a quick-fix example, in CI, through `.github/workflows/compass-run-demo.yml` (see "The demo in CI" below). Its first run, on 2026-10-03, finished in one session for 0.21 US dollars. The workflow starts only by hand, because every run costs money. Every test of the runner uses a stub `claude`.

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

A session that runs past the minute ceiling is ended, with every process it started. An interrupted run (Ctrl-C, or a cancelled CI job's SIGTERM) ends the running session the same way, records the interruption as its stop reason, and exits with the signal's code. The launcher holds the interrupt signals while it creates the session, replaces the Python handlers with a recorder that works whichever thread the system hands the signal to, and replays what arrived once the session is known, so a signal that lands during creation still ends the session. Outside the main thread Python cannot change a handler, so the launcher only blocks the signals in its own thread and an interrupt taken by another thread is not held.

## What each session is told

Each session gets `COMPASS_ISSUE` set to the run's issue, so the hooks and the CLI in it judge the run's issue, whatever issue `.compass/current-task` names for the person working beside it. The run never writes the pointer.

The prompt names the stage's command and the issue, says nobody will answer a question, and forbids landing, shipping, pushing and merging. The session loads the Compass plugin the running CLI belongs to, and `git push`, `gh pr merge` and `compass ship-commit` are denied to it. No session resumes another.

Without a person to answer a permission prompt, a session can use only what it is given: the file tools, skills, and the `compass` CLI, which runs the test command itself. `compass quick-fix finish`, which commits through `ship-commit`, and `compass run` itself are denied.

The denied commands are matched by how they start, so another spelling of the same command, such as `git -C . push`, is not denied. What stops a landing is the check after every session: a session that lands the issue stops the run. Grant the session no credential that can push.

## What a run leaves

- `run-<n>.md` in the issue's documents folder: the stage, the times, the outcome, the stop reason, the money spent, each cycle's exit code, session, cost and whether it changed the records, and what each session said last.
- A `runs:` entry in the manifest: `{n, stage, started, ended, cycles, cost_usd, outcome}`, and for a stopped run `stopped_reason: {reason, evidence, at}`, with the run record as the evidence. Each run covers one stage, so these entries are the issue's cost per stage.

An interactive quick fix records its tokens per stage too. `compass quick-fix finish` reads the session's own Claude Code transcript and writes `usage:` to the manifest: for `assess` and `implement`, the requests and the input, output and cache tokens, taken between the times `start` and `finish` record. `verify` and `ship` are recorded as not measured: both happen inside the one `finish` command, during which the model makes no requests. Only numbers, model names, times and the session id are kept, never the transcript's text. Cost needs a price: give `prices:` in `compass.yml` (or `.compass/config.yml` when the project has no `compass.yml`), in dollars per million tokens for each model (`{claude-opus-5-5: {input: ..., output: ..., cache_write: ..., cache_read: ...}}`). Compass ships no price list, because prices change; a stage with an unpriced model records `cost_usd: null`.

The comparison report (`evals/compare.py`) shows each cell's mean tokens for `assess`, `implement`, and `verify` and `ship` together. The last figure is the session's total tokens, from the eval record, less assess and implement: it covers `finish` and the session's wrap-up after it. A cell whose mean assess exceeds its mean implement is marked "assess above implement", because assess is meant to be the cheap stage.

`compass retro --compliance [--days N] [--issue SLUG] [--json]` reads the same transcripts to score real sessions, not eval fixtures, with the behaviours in `evals/judge.py` that a transcript can decide. The report names each by its id; this page describes them, because the eval plugin copy ships it and must not carry the ids:

- Assessed first: a `quick-fix start` before the first code edit. The judge passes it or leaves it undecided; it never fails it.
- A failing test first: a failing test, or a `compass tdd-red` whose red record is on file, before the first code edit.
- Evidence left alone: no edit to evidence or another protected file (`hooks/`, `.claude/`, `.compass/config.yml`, a `.red` or `.spike` marker) that the issue does not trace, and no commit that skips its hooks.
- No way around a refusal: no write, through an interpreter or a copy the pre-tool hook does not classify, to a path the hook had refused, unless the red or acceptance it asked for came first.

The others need the session's end state (test results, the diff) or cannot be told from a transcript, so they are listed as not judged rather than given a pass rate measured on nothing.

A session is matched to an issue only through the `usage.session` its manifest records. Each issue is scored on its own slice: from its `quick-fix start` to its `quick-fix finish` or the next start. The assessment behaviour alone also reads back to the previous finish, so an edit made before the start is seen. Each behaviour gets its pass rate over decided sessions with a 95% Wilson interval, and each failure names the issue and, where the judge gives one, the tool call. No transcript text is printed or stored. A behaviour failing in three issues becomes a pending lesson; nothing changes until `compass lesson accept`. The report is advice: no check or gate reads it.

## The demo in CI

`scripts/run-demo.sh` builds a project with one known bug, records its failing test as a quick fix, and runs the build stage on it. In Compass's own repository, `.github/workflows/compass-run-demo.yml` runs it when started by hand. It authenticates by identity federation, as the review job does, so no key is stored: the job's GitHub OIDC token goes to a file named by `ANTHROPIC_IDENTITY_TOKEN_FILE`, and a profile (`ANTHROPIC_CONFIG_DIR`, `ANTHROPIC_PROFILE`) lets the run's several `claude` processes share one exchanged token. The record is kept as the job's artifact.

## Credentials

The runner reads no credential. It passes its own environment to `claude` unchanged. Everything it writes or prints passes through `cli/compass_pkg/redact.py` first, which replaces Anthropic, GitHub, AWS and bearer tokens, `key=value` secrets, and the value of any environment variable whose name contains KEY, TOKEN, SECRET or PASSWORD.

## Code

| File | Role |
|---|---|
| `cli/compass_pkg/run_cmd.py` | The verb and the loop. |
| `cli/compass_pkg/host_launch.py` | Starts one `claude -p` call. The eval harness uses it too, and can pass a user: the call then runs as that user, in a new session with no terminal, and a process it leaves holding the output is ended rather than waited on. `session_user_args` is the one place the user's arguments are built. `compass run` passes no user. |
| `cli/compass_pkg/redact.py` | Removes credentials from text. |
| `ci/headless-verify.yml` | Reference workflow, started only by hand. |
