# Compass

Compass is adaptive spec-driven development for Claude Code. You describe
the work; Compass scores the risk, familiarity and size of each piece of
work, new or existing, and a deterministic CLI computes how much process it
needs from that assessment, the project's configuration and the issue's
documents. Five guardrails apply to all work that ships code, whatever the
assessment: a recorded passing test run, acceptance criteria before code,
code traced to a criterion, typed evidence rather than a written claim, and a
person's approval for a change labelled `auth`, `payments`, `personal-data`
or `migrations`. They are defaults: a project can add its own, report
failures without blocking while it tries Compass, or loosen one with the
owner's recorded waiver. The person's approval cannot be loosened. The
[safety contract](safety-contract.md) states what each guarantee covers and
where it stops.

## Start here

- [Five minutes](five-minutes.md) - one small change, from assessment to a reviewable result.
- [Quickstart](quickstart.md) - from an empty machine to a finished first issue.
- [Install check](install-smoke-test.md) - confirm an install works.
- [Configuration](configuration.md) - project settings live in one file, `compass.yml`; `compass policy show` prints the configuration in force.
- [Upgrading to 7.0.0](upgrade-7-0-0.md) - coming from 6.x: each change, what breaks and what to do.
- [Upgrading to 8.0.0](upgrade-8-0-0.md) - coming from 7.x: the delegation change, what breaks and what to do.
- [Upgrading to 6.0.0](upgrade-6-0-0.md) - coming from 5.x: the renamed words and commands, and what reads the old form until 9.0.0.

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
