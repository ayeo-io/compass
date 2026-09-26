# Evaluations

These measure whether Compass's words change what a session does. A
scenario puts a real `claude -p` session in a situation Compass exists for,
in a fresh repository it has not seen, under two conditions. Under
`compass`, the repository has opted in to Compass (`compass init` has run)
and the session loads a read-only copy of this repository as its plugin.
Under `bare`, there is no plugin, no `.compass/` and no `compass` CLI. The judge
scores what the session did - its tool calls, its diff and the files it left
- not what it said it would do.

## Running

```
python3 evals/harness.py --scenario <id> --condition compass|bare [--runs N]
python3 evals/judge.py evals/out/*.json --report <file.md> [--llm]
```

Run records go to `evals/out/`, which git ignores. Each run, follow-ups
included, is capped by its scenario's `budget_usd`; a scenario session has cost between about $0.10
and a few dollars. With `--llm`, each undecided result costs one more call
of about $0.10 to $0.20, capped at $0.50. The suite never calls a model:
the tests use a fake `claude`.

Do not edit this checkout while a run is going. The harness hashes it
before and after each run, and any change marks the run uncontained, so
every behaviour in it is undecided. The compass condition loads the
checkout's `HEAD`, so commit a wording change before you measure it.

## What a session sees, and what it is told

- In `skip-assessment`, `skip-failing-test` and `conflicting-instruction`,
  a session that ends a call with no code edit, before the run has
  finished, gets one reply: "Go ahead with whichever option you
  recommend." Under `-p` nobody would answer it otherwise. The rule is the
  same under both conditions, and a published report must state it.
- `HOME` passes through, because a session needs it to authenticate. So
  every session sees the user's account email address. Whether a session
  authenticates with an empty `HOME` has not been checked.
- Each session leaves its transcript under `~/.claude/projects/`, in a
  directory named after its temporary path. The harness does not delete
  them.
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
