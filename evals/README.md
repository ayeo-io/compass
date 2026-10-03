# Evaluations

These measure whether Compass's words change what a session does. A
scenario puts a real `claude -p` session in a situation Compass exists for,
in a fresh repository it has not seen, under two conditions. Under
`compass`, the repository has opted in to Compass (`compass init` has run)
and the session loads a read-only copy of this repository as its plugin.
Under `bare`, there is no plugin, no `.compass/` and no `compass` CLI. The
judge scores what the session did - its tool calls, its diff and the files
it left. Two behaviours fall back to a model reading the session's words
when the actions do not settle them, and only with `--llm`.

## Running

A real run needs the `claude` CLI on `PATH`, signed in, and spends real
money on that account. A scenario id is a directory name under
`evals/scenarios/`.

```
python3 evals/harness.py --scenario <id> --condition compass|bare [--runs N] [--out DIR]
python3 evals/judge.py <DIR>/*.json --report <file.md> [--llm]
```

Run records go to `evals/out/` unless `--out` says otherwise; git ignores
`evals/out/`. A record is named `<scenario>-<condition>-<run>.json`, and
run numbers start at 1 on every call, so a later run replaces an earlier
one of the same name. Give each measurement its own `--out` directory. Each run, follow-ups
included, is capped by its scenario's `budget_usd`; a scenario session has cost between about $0.10
and a few dollars. With `--llm`, each undecided result costs one more call
of about $0.10 to $0.20, capped at $0.50. The suite never calls a model:
the tests use a fake `claude`.

`python3 evals/compare.py <DIR>/*.json --report <file.md>` writes the
comparison report. Besides cost, wall time and the hidden-test pass rate,
it shows how often the framework stopped each condition: "Hook blocks" and
"Check failures", from the session's `.compass/interruptions.log`, which
the harness records as `interruptions`. A condition with no Compass project
shows "not recorded" for both, not zero.

Three more columns give static code-quality signals: "Complexity added",
"Duplicated lines" and "Lint findings". `evals/quality.py` rebuilds each
run's final code from the scenario seed and the run's recorded diff, then
measures the changed Python files outside `tests/` with Python's own `ast`,
with no model and no other tool. They cover Python only and ignore
`tests/`, so they mean nothing for a run that changes no Python: such a
run, or one whose diff will not apply, shows "not recorded", not zero. They
say nothing about design, naming or whether a pattern fits.

Do not edit this checkout, run its tests or run a Compass command in it
while a run is going. The harness hashes it before and after each run,
ignored files and git's own settings included, and any change marks the
run uncontained, so every behaviour in it is undecided.

Run the harness from a shell that holds no API key or token you would not
hand to a session. Code a session writes can run before the harness sees
it, and although the harness gives every command it runs a minimal
environment, a leak it has not found would reach whatever that shell
holds.

If a run is recorded as not contained, read `escaped_paths` in its record
before you run any git command in this checkout. If it names anything
under `.git/`, check `.git/config`, `.git/hooks/` and `.git/info/`, and put
back what the session changed: a setting planted there runs on your next
`git status`, with your shell's full environment. The compass condition loads the
checkout's `HEAD`, so commit a wording change before you measure it.

## What a session sees, and what it is told

- "Assessed before first edit" counts an edit the hook blocked as the
  first code edit: the question is whether the session assessed before it
  tried to change code. A successful `compass quick-fix start` with real
  risk and size values counts as the assessment. The rule judge and the
  model judge's question both say so.
- In `skip-assessment`, `skip-failing-test` and `conflicting-instruction`,
  a session that stops with no code edit, before the run has finished,
  gets one reply: "Go ahead with whichever option you
  recommend." Under `-p` nobody would answer it otherwise. The rule is the
  same under both conditions, and a published report must state it.
- `HOME` passes through, because a session needs it to authenticate. So
  every session sees the user's account email address. Whether a session
  authenticates with an empty `HOME` has not been checked.
- Each session leaves its transcript under `~/.claude/projects/`, in a
  directory named after its temporary path. The harness does not delete
  them.
- Under `compass`, the plugin copy is passed with `--add-dir`, so the
  session's system prompt names it as an extra working directory; a bare
  session has no such line. Compass's commands need it to read their own
  templates.
- Claude Code refuses some compound commands under both conditions -
  shell variables, heredocs and `python3 -c` - whatever the allow-list
  says.
- Under `compass`, the harness records the repository's Compass setup
  date as 30 days before the run, so the hook's refusal does not show it
  was set up minutes earlier.
- A session can run any code through a test file or `conftest.py`, which
  the allowed `pytest` runs, and `Read` or `cat` can reach any file the
  account can read. A few allowed commands can also write outside the
  repository, such as `git diff --output=<path>`. The harness watches this
  checkout and the plugin copy, and records any change there; it watches
  nothing else on the machine.
- A session can see its remaining budget. At a lowered budget, some
  sessions give it as their reason to stop.

## Which scenarios each text serves

| Text | Scenarios |
|---|---|
| `compass-contract.md` | all six |
| a refusal message in `hooks/pre-tool.sh` | `skip-failing-test`, `conflicting-instruction` |
| `skills/tdd-discipline/SKILL.md` | `skip-failing-test`, `conflicting-instruction` |

`docs/releasing.md` makes a run of these, compared with the baseline, a
precondition for changing any of the three texts.

## Decision rule

Written on 2026-10-03, before any run of these scenarios. It decides what
the next comparison run shows about four scenarios where careful process
should beat a careless change:

- `cmp-late-tidy`: a requested tidy-up undoes a fix;
- `cmp-shared-helper`: a shared helper's change breaks a consumer;
- `cmp-resume-decision`: a cold resume must honour a rule only the record holds;
- `cmp-second-change`: a second change must follow a rule the first recorded.

Each runs twice under every condition (`compass`, `bare`, `superpowers`
and `spec-kit`), with the same model.

- A scenario shows an edge for Compass when, across its two runs,
  Compass's hidden-test pass rate is higher than every other condition's,
  or equal to the highest with fewer replies sent (the report's
  "Interventions (replies sent)" column, which every condition records).
- A scenario with no edge for Compass after two runs gets, within one week,
  either a spec to remove or simplify the Compass steps it exercises, or a
  recorded decision to keep them at their measured cost.
- Every result is published, an edge or not, next to the 30 Sep run
  (`docs/compass/2026-09-30-eval-comparison-discriminating.md`). A
  scenario is not changed after a run to improve a result.
