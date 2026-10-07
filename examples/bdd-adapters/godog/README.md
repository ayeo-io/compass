# godog reference adapter

The same Compass spec as the other three adapters, run by **godog**.

**Only step 3 differs between the four adapters.** That is the point: the spec,
the extract command and the shape of the run are identical, so an adopter picks
the binding idiom for their language and changes nothing else.

## The four steps

### 1. Declare the runner in `compass.yml`

Use `.compass/config.yml` in a project that has no `compass.yml`.

```yaml
project:
  bdd_runner: godog
  bdd_features_dir: features
  bdd_steps_dir: .
  bdd_run_command: "go test ./..."
```

### 2. Extract the Gherkin

```bash
compass bdd extract --issue reset-password --out features/reset-password.feature
```

Reads `docs/compass/2026-08-03-reset-password/acceptance-criteria.md` and writes plain Gherkin,
with each scenario tagged `@TRC-*` so a per-scenario result maps back to
`manifest.yml`. Deterministic: same spec, same bytes.

### 3. Bind the steps  *(the only step that differs)*

```bash
go mod tidy
```

Step definitions live in `reset_password_test.go`.

### 4. Run

```bash
go test ./...
```

```
ok  compass/godog-adapter
```

## Things worth knowing

**Run extract before the tests.** The `.feature` file is derived. Regenerate it
whenever the spec changes - in CI, put `compass bdd extract` immediately before
the run command.

**An unbound step fails with an error**, naming the step text it could not find. That
is the first mistake an adopter makes, and it says what to fix.

**A CI job runs this adapter on every pull request and every push to main.** An example nobody runs is an
example nobody can trust, which is why Compass ships none without one.
