# Evaluations

These measure whether Compass's words change what a session does. A
scenario puts a real `claude -p` session in a situation Compass exists for,
in a fresh repository it has not seen, once with this repository loaded as a
plugin (`compass`) and once without any Compass plugin (`bare`). The judge
scores what the session did - its tool calls, its diff and the files it left
- not what it said it would do.

## Running

```
python3 evals/harness.py --scenario <id> --condition compass|bare [--runs N]
python3 evals/judge.py evals/out/*.json --report <file.md> [--llm]
```

Run records go to `evals/out/`, which git ignores. Each session is capped by
its scenario's `budget_usd`; a scenario session has cost between about $0.10
and a few dollars. The suite never calls a model: the tests use a fake
`claude`.

## Which scenarios each text serves

| Text | Scenarios |
|---|---|
| `compass-contract.md` | all six |
| a refusal message in `hooks/pre-tool.sh` | `skip-failing-test`, `conflicting-instruction` |
| `skills/tdd-discipline/SKILL.md` | `skip-failing-test`, `conflicting-instruction` |

`docs/releasing.md` makes a run of these, compared with the baseline, a
precondition for changing any of the three texts.
