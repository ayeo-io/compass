# Four-layer acceptance tests - the TypeScript reference example

A small project to copy from when a TypeScript project adopts the four-layer acceptance test model. It has the same layers and the same rules as the Python example in `../python/`. The model gives each kind of knowledge one place to live:

| Layer | Here | Holds |
|---|---|---|
| Executable specification | `tests/acceptance/todos.spec.ts`, `tests/acceptance/accounts.spec.ts` | the scenario in a comment at the top of each test, and one DSL call for each Given, When or Then line |
| Domain-specific language (DSL) | `tests/acceptance/dsl.ts` | the words the specifications use; defaults; aliases for every account email. No check |
| Protocol driver | `tests/acceptance/drivers/` | every check, and how one real client talks to the system: `api.ts` through the HTTP API, `cli.ts` through the command line |
| System under test | `src/` | a todo service with an HTTP API (`src/server.ts`) and a CLI (`src/cli.ts`) over one store (`src/service.ts`) |

The support code the first specification needs:

| File | What it does |
|---|---|
| `tests/acceptance/alias.ts` | the alias helper: one run id for the whole run, a counter for each worker (each worker's numbers kept apart by its process id) and a map per scenario |
| `tests/acceptance/drivers/index.ts` | the driver interface, and `DRIVERS`, the names the factory knows |
| `tests/acceptance/driverFactory.ts` | the driver factory: one DSL per specification file, and a new driver for each scenario |
| `tests/acceptance/run.ts` | the runner adapter: chooses the driver, makes the run id and the store, starts `node --test`, and writes the JUnit report |
| `tests/acceptance/junitReporter.ts` | the JUnit reporter `run.ts` gives node: it names each test's file as the testcase's classname |
| `tests/acceptance/system.ts` | the API server, started on first use and stopped when the worker's scenarios end |
| `tests/acceptance/layering.test.ts` | the layering test |

The example needs Node 22.13 or later. It runs its TypeScript with Node's own `--experimental-strip-types`, its tests with `node:test` and its store with `node:sqlite`, so the suite itself needs no package. The type check and the layering test need the packages in `package.json`, each pinned to one exact version, with every package they bring in pinned by `package-lock.json`.

## Run it

From this folder:

```
npm ci
npm run typecheck
npm run acceptance -- --driver api --workers 2
npm run acceptance -- --driver cli --workers 2
npm run layering
```

Do not run a tool through an unpinned `npx`: the npm scripts call the pinned tools in `node_modules/.bin`.

The driver is chosen once, when the run starts: `--driver api|cli`, or the `ACCEPTANCE_DRIVER` environment variable when the option is not given, or `api`. The run's header names it (`acceptance driver: cli`). A name that is not in `DRIVERS` stops the run before any scenario, with a message that names the drivers there are.

A test to run is a file, or `<file>::<test name>` for one scenario, for example `npm run acceptance -- "tests/acceptance/todos.spec.ts::a completed todo can be archived"`. `--workers 2` runs the two specification files at once, each in its own process.

The `beforeEach` hook in `tests/acceptance/driverFactory.ts` imports the chosen driver's module. The import is inside the hook on purpose. While you write the specifications and the DSL, before the driver exists, each scenario fails in its hook (`failed running beforeEach hook`, with `ERR_MODULE_NOT_FOUND` for the driver's file), and node:test still runs every scenario and writes its JUnit report.

## The JUnit report

`tests/acceptance/run.ts` writes the JUnit report to `--junit PATH`, or to the path in the environment variable `COMPASS_JUNIT_REPORT`. `compass tdd-red` and `compass layering record` set that variable on every command they run. Compass reads the report, not the terminal output:

- `compass tdd-red --loop outer` records the stage 1 red from the report: a scenario whose hook failed because a module of this project is missing is an import red, with the missing file in `missing_modules`. A missing package, one that is not a file of this project, is refused.
- A scenario's declared test is `<file>::<test name>`, for example `tests/acceptance/todos.spec.ts::a new todo is open`. Compass matches it by the file and the name. node's own JUnit reporter names no file, so `run.ts` uses `tests/acceptance/junitReporter.ts`, which writes the file as each testcase's classname.
- A specification file that does not load, and a test its describe block cancelled, are not a red: no scenario of theirs ran.
- `compass layering record -- npm run layering` takes the number of tests that ran from the report.

## Isolation

The suite runs against a real system, so the scenarios must not share data:

- **Functional:** each scenario starts by creating its own account and works only in it.
- **Temporal:** each account email goes through the alias helper, so `ann@example.com` reaches the system as `ann@example.com-3f9a1c2e-w4711-7`: the run id, the worker and a number. `run.ts` makes the run id once, before any worker starts, and every worker reads it. The service refuses a second account with the same email, so a scenario that skipped the alias would fail on its second run against the same store.
- **No clean-up after a scenario.** Aliased data cannot collide, so it stays. All the workers of a run share one store: a new data folder, made once before the run starts, and named in the run's header (`todo store: ...`). Set `TODO_DATA_DIR` to share one store between runs as well.

Todo names are not aliased: a todo belongs to the account of its scenario.

## The layering test

`tests/acceptance/layering.test.ts` reads the source of the DSL and of the specifications with the TypeScript compiler's parser. It does not run them and needs no running system. Each breach is one line: the file, the line, the rule and what it found, for example:

```
tests/acceptance/dsl.ts:58: the DSL makes no check: a call to assert.ok in Todo.complete; the check belongs in the driver
tests/acceptance/todos.spec.ts:20: every identifier goes through an alias: the email address 'ann@example.com' reaches no DSL parameter that aliases it
tests/acceptance/todos.spec.ts:22: one DSL call per Given, When or Then line: the line 'Then "Buy milk" is open' (line 17) makes 2 DSL calls, at lines 21, 22
```

| Rule | Fails on |
|---|---|
| the DSL makes no check | a `throw`, a call to `assert` or `expect`, or a call to a `fail` anywhere in `dsl.ts` |
| every identifier goes through an alias | a string in a specification that matches a pattern in `IDENTIFIER_PATTERNS` (an email address) and is not an argument of a DSL parameter that the method passes to `this.alias(...)` |
| one DSL call per Given, When or Then line | a statement that is not one DSL call, a step line with no call, or a line that makes two. A Given line is matched to a `has` method, a Then line to a `confirm` method, a When line to any other. Within each of these phases, lines and calls are matched by count. It reads each top-level `test(...)` call of a specification file |
| a DSL method name uses no banned term | a DSL method whose name holds a term of the `banned` list in the project's `governance/terminology.yml`, the first one found in the example's root or a folder above it. Without that file the rule skips and says why |

As in the Python example, two items of the model's checklist are not rules here: DSL and driver method names match, and nothing cleans up after a scenario.

## Adopt it

1. Copy `package.json`, `package-lock.json`, `tsconfig.json` and `tests/acceptance/` into your project, and run `npm ci`.
2. Replace `src/` with your system, and `tests/acceptance/system.ts` with how your run reaches it.
3. Write your specifications and DSL first. Add your driver names to `DRIVERS`: until the modules exist, each scenario fails in its hook.
4. Write each driver against the interface in `tests/acceptance/drivers/index.ts`. Put every check in the driver.
5. Set `DSL_FILE`, `SPEC_FILES`, `IDENTIFIER_PATTERNS` and, if your banned list is elsewhere, `TERMINOLOGY_FILE` in `layering.test.ts` for your suite. Run it in CI with the specifications.
6. Name each piece of support code in your `compass.yml`, so `compass readiness` can report the pieces that are missing, and give Compass the commands that write its records:

   ```yaml
   project:
     acceptance_support:
       alias_helper: tests/acceptance/alias.ts
       driver_factory: tests/acceptance/driverFactory.ts
       dsl_root: tests/acceptance/dsl.ts
       layering_test: tests/acceptance/layering.test.ts
     layering_command: npm run --silent layering
   ```

Compass does not read this example's code. Its own tests, in `tests/acceptance/atdd_strategy/test_reference_example.py`, `test_stage1_red.py` and `test_cross_cutting.py` of the Compass repository, run it. They skip on a machine without Node 22.13 or the example's packages, and say which is missing. The CI job `atdd-adapter-typescript` runs the example and those tests.
