# Four-layer acceptance tests - the Python reference example

A small project to copy from when a Python project adopts the four-layer acceptance test model. The model gives each kind of knowledge one place to live:

| Layer | Here | Holds |
|---|---|---|
| Executable specification | `tests/acceptance/test_todos.py` | the scenario in its docstring, and one DSL call for each Given, When or Then line |
| Domain-specific language (DSL) | `tests/acceptance/dsl.py` | the words the specifications use; defaults; aliases for every account email. No check |
| Protocol driver | `tests/acceptance/drivers/` | every check, and how one real client talks to the system: `api.py` through the HTTP API, `cli.py` through the command line |
| System under test | `todo/` | a todo service with an HTTP API (`todo/server.py`) and a CLI (`todo/cli.py`) over one store (`todo/service.py`) |

The support code the first specification needs:

| File | What it does |
|---|---|
| `tests/acceptance/alias.py` | the alias helper: one run id for the whole run, a counter shared by the run (each worker's numbers kept apart by its worker id) and a map per scenario |
| `tests/acceptance/drivers/__init__.py` | the driver interface, and `DRIVERS`, the names the factory knows |
| `conftest.py` | the driver factory, the run id, the store every worker of the run shares, and one DSL per scenario |
| `tests/acceptance/system.py` | the data folder, and the API server, started on first use and stopped when the run ends |
| `tests/acceptance/test_layering.py` | the layering test |

The system under test uses the Python standard library only. The test tools are in `requirements.txt`, each pinned to one version.

## Run it

From this folder, with Python 3.11 or later:

```
pip install -r requirements.txt
python -m pytest -n 2 --driver api tests/acceptance/test_todos.py
python -m pytest -n 2 --driver cli tests/acceptance/test_todos.py
python -m pytest tests/acceptance/test_layering.py
```

The driver is chosen once, when the run starts: `--driver api|cli`, or the `ACCEPTANCE_DRIVER` environment variable when the option is not given, or `api`. The run's header names it (`acceptance driver: cli`). A name that is not in `DRIVERS` stops the run before any scenario, with a message that names the drivers there are.

The `driver` fixture in `conftest.py` imports the chosen driver's module. The import is inside the fixture on purpose. While you write the specifications and the DSL, before the driver exists, each scenario is an error at setup and pytest still writes its JUnit report (`--junitxml`). An import at the top of `conftest.py` would stop collection with exit 4 and no report.

## Isolation

The suite runs against a real system, so the scenarios must not share data:

- **Functional:** each scenario starts by creating its own account and works only in it.
- **Temporal:** each account email goes through the alias helper, so `ann@example.com` reaches the system as `ann@example.com-3f9a1c2e-gw0-7`: the run id, the worker and a number. `conftest.py` makes the run id once, before any worker starts, and every worker reads it. The service refuses a second account with the same email, so a scenario that skipped the alias would fail on its second run against the same store.
- **No clean-up after a scenario.** Aliased data cannot collide, so it stays. All the workers of a run share one store: a new data folder, made once before the run starts, and named in the run's header (`todo store: ...`). Set `TODO_DATA_DIR` to share one store between runs as well: the suite still passes on two workers, and one scenario still passes twice in a row.

Todo names are not aliased: a todo belongs to the account of its scenario.

## The layering test

`tests/acceptance/test_layering.py` reads the source of the DSL and of the specifications. It does not run them and needs no running system. Each breach is one line: the file, the line, the rule and what it found, for example:

```
tests/acceptance/dsl.py:53: the DSL makes no check: an assert statement in Todo.complete; the check belongs in the driver
tests/acceptance/test_todos.py:16: every identifier goes through an alias: the email address 'ann@example.com' reaches no DSL parameter that aliases it
tests/acceptance/test_todos.py:18: one DSL call per Given, When or Then line: the line 'Then "Buy milk" is open' (line 13) makes 2 DSL calls, at lines 17, 18
```

| Rule | Fails on |
|---|---|
| the DSL makes no check | an `assert`, a `raise` or a call to the runner's `fail` inside a DSL method, async or not, or inside a module-level function of `dsl.py` |
| every identifier goes through an alias | a string in a specification that matches a pattern in `IDENTIFIER_PATTERNS` (an email address) and is not an argument of a DSL parameter that the method passes to `self._alias(...)` |
| one DSL call per Given, When or Then line | a statement that is not one DSL call, a step line with no call, or a line that makes two. A Given line is matched to a `has` method, a Then line to a `confirm` method, a When line to any other. Within each of these phases, lines and calls are matched by count. It reads module-level `test_*` functions and the `test_*` methods of `Test*` classes |

Two items of the model's checklist are not rules here: DSL and driver method names match, and nothing cleans up after a scenario. The example follows both. The layering test does not check them.

## Adopt it

1. Copy `conftest.py`, `pytest.ini` and `tests/acceptance/` into your project.
2. Replace `todo/` with your system, and `tests/acceptance/system.py` with how your run reaches it.
3. Write your specifications and DSL first. Add your driver names to `DRIVERS`: until the modules exist, each scenario is an error at setup.
4. Write each driver against the interface in `tests/acceptance/drivers/__init__.py`. Put every check in the driver.
5. Set `DSL_FILE`, `SPEC_FILES` and `IDENTIFIER_PATTERNS` in `test_layering.py` for your suite, and run it in CI with the specifications.

Compass does not read this example's code. Its own tests, in `tests/acceptance/atdd_strategy/test_reference_example.py` of the Compass repository, run it and plant each breach. The CI job `atdd-adapter-python` runs it on every pull request.
