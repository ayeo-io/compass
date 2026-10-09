# Compass

Compass is adaptive spec-driven development for Claude Code. You describe
the work; Compass reads its risk, familiarity, size and goal, and a
deterministic CLI computes how much process it needs. Five guardrails hold
on every route: every change lands with a passing test, acceptance
criteria come before code, code traces to a criterion, evidence is a
recorded command output, and a person approves anything irreversible.

## Start here

- [Five minutes](five-minutes.md) - one small change, from assessment to a reviewable result.
- [Quickstart](quickstart.md) - from an empty machine to a finished first issue.
- [Install check](install-smoke-test.md) - confirm an install works.
- [Configuration](configuration.md) - project settings live in one file, `compass.yml`; `compass policy show` prints the configuration in force.
- [Upgrading to 6.0.0](upgrade-6-0-0.md) - coming from 5.x: the renamed words and commands, and what reads the old form until 7.0.0.

## What Compass guarantees

- [Safety contract](safety-contract.md) - what Compass enforces, and what it does not claim.
- [Refusal codes](refusal-codes.md) - every reason the pre-tool hook can refuse with.
- [Security](security.md) - what Compass runs, and how it guards against tampered dependencies.

## How it works

- [Methodology](methodology.md) - the adaptive, spec-driven method and why it is built this way.
- [Roles](roles-guide.md) - how product, design, engineering, marketing and QA each use Compass.
- [Portability](portability.md) - how Compass maps onto other agent runtimes.

The source, the CLI reference and the issue tracker are on
[GitHub](https://github.com/ayeo-io/compass).
