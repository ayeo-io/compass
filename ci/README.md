# CI integration

Wiring Compass into CI is small, because the Compass CLI already does the
work. The whole integration is:

> **Run `compass ci`. Honour the exit code.**

`compass ci` is the full mechanical gate suite - it runs `compass policy lint`,
then `compass issue lint` and `compass check` for every issue under
`.compass/work/`, and exits non-zero if anything fails. That is the one command
a CI job needs; everything else is just the platform's way of running it.

`compass ci --since <ref>` still lints every issue, but fully checks only those
in flight or landed after `<ref>`, a git tag or commit. Use it where the
archive is large and older issues were checked when they landed.

## Compass CI does not replace your project CI

Compass CI is a **process-integrity lane**, not a substitute for the rest of
your pipeline. It does *not* re-run your test suite, your linter, your type
checker, your security scanner, your build, or your deployment checks. What it
checks is whether the issue state is coherent and backed by evidence: the
issue was assessed, scenarios have tests, changed files trace to scenarios,
gates carry evidence of the right type, approvals are recorded where they
must be. Your project's own CI keeps running everything else.

The two are designed to run alongside each other. The recommended pattern is
two jobs in the same workflow - `project-ci` for the application checks,
`compass-ci` gated on `project-ci` so a failing test suite stops the
pipeline before Compass even runs. `compass tdd-green` records that the
test passed *during implement*, and `compass check` then reads that record at
verify time - it does not re-run the test. The two pipelines together cover
*both* code correctness and process integrity, and neither substitutes for
the other; this is "Compass CI checks process integrity" in
`docs/safety-contract.md`.

## What `compass ci` catches on a pull request

- **Governance drift** - `routing-policy.yml` or `guardrails.yml` is malformed,
  or a guardrail names a check the CLI does not implement (the integrity rule).
- **A malformed issue manifest** - a `manifest.yml` that does not match the schema.
- **An unmet guardrail** - an issue whose `compass check` fails: a scenario with
  no test, a changed file with no traced scenario, a gate marked `pass` with
  missing or wrongly-typed evidence, an outstanding follow-up.

It does **not** re-run your test suite - that is `compass tdd-green`'s job
during implement, and its result is the green record that `compass check`
reads. CI checks that the *issue state is coherent and backed by evidence*, fast.

## GitHub Actions

Copy `ci/github-actions.yml` to `.github/workflows/compass.yml` in your
project. It checks out the repo, sets up Python and runs `compass ci`.

The recommended pattern is to put `compass-ci` in the same workflow as your
project's own tests, gated on them so a red test suite halts the pipeline
before Compass runs:

```yaml
name: CI

on:
  pull_request:
  push:
    branches: [main]

jobs:
  project-ci:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5 # v4.3.1
      # your normal pipeline: tests, lint, type-check, build, etc.
      - run: make test
      - run: make lint

  compass-ci:
    runs-on: ubuntu-latest
    needs: project-ci             # only run Compass once code is green
    env:
      COMPASS_CLI: cli/compass    # adjust to wherever Compass lives in your repo
    steps:
      - uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5 # v4.3.1
      - uses: actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065 # v5.6.0
        with:
          python-version: "3.11"
      - run: python3 "$COMPASS_CLI" ci
```

Pin the Compass copy that `COMPASS_CLI` points at to a specific commit SHA,
not a branch - see `docs/security.md` for the supply-chain stance.

## Piloting Compass without blocking delivery - `mode: advisory`

When a team is first adopting Compass, you may want `compass ci` to *report*
failures without exiting non-zero, so it does not block PRs while the team
is still learning the model. Set the adoption mode in `compass.yml` (the key is `mode` in `.compass/config.yml`
for a project without a `compass.yml`):

```yaml
adoption: advisory     # report failures, exit 0 - non-blocking
# adoption: enforced   # the default - fail the CI job on any failure
```

In `advisory` mode every failure is still printed (with the structured
`what / why / fix` blocks) under a clear `[mode: advisory]` banner - an
advisory run is never mistaken for an enforced one. Change to `mode:
enforced` when the team is ready and the gates start blocking landings.
Teams can adopt Compass in steps - see "Compass enforces nothing in a
project that has not opted in" in `docs/safety-contract.md`.

## Any other CI

The pattern ports unchanged - it is two lines on any platform:

```sh
python3 path/to/compass ci
# the job fails if compass ci exits non-zero
```

PyYAML travels inside the plugin, so there is no install step. If you want full JSON Schema validation in the lint commands, `pip install jsonschema` is optional - the built-in linter runs without it.

GitLab CI, CircleCI, Buildkite, a git pre-push hook - all the same. There is
no Compass-specific CI plugin to install. The CLI exits non-zero on failure,
which is all a CI system needs.

## A note on where the CLI lives

`compass ci` resolves `governance/` and the issue working directory by walking
up from the working directory, and finds `schemas/` relative to the CLI
script. In a project that has Compass installed, point the CI step at wherever
`cli/compass` is (vendored, a submodule, or a pinned checkout). In the Compass
framework repo itself, it is just `cli/compass`.
