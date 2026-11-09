# Compass CLI test suite

These tests check the guarantees in `docs/safety-contract.md`. They shell out
to the `compass` CLI in a temp project per test - no shared state, no network
calls.

## Run

The canonical command (from the repo root) is:

```bash
make test
```

which expands to:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/ -q
```

PyYAML, the CLI's one runtime dependency, is bundled in the plugin at
`cli/vendor/yaml/`, and `tests/conftest.py` resolves it the same way the CLI
does - nothing to install there. The suite needs `pytest` and `jsonschema`:
`pip install pytest jsonschema`. The suite spawns one CLI subprocess per
test. Each `run_cli` call has a 10-second timeout - long enough for a real
run, short enough that a genuinely hung subprocess fails fast rather than
running out the clock on the whole suite. Run
`python3 -m pytest tests/ --collect-only -q` for the current test count; it
changes with almost every commit, so this file states no number.

### If `make test` hangs

Pytest plugin autoload (for example `ddtrace` or coverage plugins) can hang
the suite. `make test` disables it with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`.
If the suite still hangs, run these in order:

```bash
# 1. Confirm no plugin is loading
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest --version

# 2. Run a single file to isolate the hang
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/test_check_guardrails.py -v

# 3. Stop on the first failure (faster triage)
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/ -x -v

# 4. Look for hung pytest/python subprocesses
ps aux | grep -E 'pytest|python.*compass' | grep -v grep
```

If a single file or test hangs reliably, please file an issue with the
output of `python3 -m pytest --version` and the platform; subprocess
launch overhead varies wildly between filesystems.

## What the suite covers

These files check the safety-contract guarantees:

| File | Contract guarantee |
|---|---|
| `test_route_selection.py` | 1 - deterministic routing; floors and caps fire as documented |
| `test_spike_conflict.py`  | 4 - exploration cannot silently become delivery |
| `test_policy_integrity.py`| 2 - a declared guardrail cannot silently become advisory |
| `test_task_validation.py` | versioning + structural checks of `manifest.yml` |
| `test_check_guardrails.py`| 3 - typed gate evidence, traceability, follow-ups |
|                           | 5 - human approvals for irreversible work |
| `test_tdd_evidence.py`    | 1 + 3 - tdd-red/green honesty + registry upsert |
| `test_spike_safety.py`    | 4 - spike conclusion, no production changes, graduation linkage |
| `test_ci.py`              | 6 - `compass ci` exit-code aggregation |
| `test_modes.py`           | 7 - enforced vs advisory adoption mode |
| `test_house_style.py`     | this repository's own writing invariants (the cold-reader strategy, `S7`) - not a safety-contract guarantee |

## Fixtures

`tests/fixtures/routes/` holds six YAML files declaring (assessment, expected)
pairs that one parameterised test asserts the CLI's `compass approach
evaluate --json` output matches. To add a new edge case, add another YAML
file - no test code change needed.

## Isolation

Every test gets a fresh temp project from the `project` fixture - a copy of
the shipped governance prose (`governance/*.md`), an empty `.compass/work/`,
and `.compass/config.yml` set to `mode: enforced`. Tests that need a different
mode write the config file themselves. The fixture copies no
`routing-policy.yml` or `guardrails.yml`: 9.0.0 refuses a project with a copy
of either and no `compass.yml` (ADR-098). A test that needs the 8.x reader of
a copy uses `tests/legacy_copy.py`.
