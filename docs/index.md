# Compass

Compass is acceptance-test-driven development for Claude Code, with a record
a reviewer can check. It lets a team under change control give code changes
to an AI agent and still show a reviewer or an auditor what happened. The
agent proves each change with acceptance tests. A person approves each
change. Compass keeps a record of both.

Each change leaves one plain file, `trail.md`. It says who asked, what was
agreed, the failing run, the passing run, who approved and what shipped,
with a SHA-256 digest for each record. A reviewer checks it with
`sha256sum -c`, without Compass installed.

Five guardrails apply to all work that ships code:

1. A test that fails without the change.
2. Acceptance criteria before code.
3. Code traced to a criterion.
4. Typed evidence, not a written claim.
5. A person's approval for a change with the label `auth`, `payments`,
   `personal-data` or `migrations`.

A project can add its own checks, report failures without blocking while it
tries Compass, or excuse one check on one issue with a waiver a person
approves. The person's approval cannot be waived. The
[safety contract](safety-contract.md) states what each guarantee covers and
where it stops.

## Start here

- [Five minutes](five-minutes.md) - one small change, from the request to a commit that holds the code and its record.
- [Quickstart](quickstart.md) - install and the first issue.
- [Install check](install-smoke-test.md) - check that an install works.
- [Configuration](configuration.md) - the project settings in `compass.yml`.
- Upgrading: [to 9.0.0](upgrade-9-0-0.md), [to 8.0.0](upgrade-8-0-0.md), [to 7.0.0](upgrade-7-0-0.md), [to 6.0.0](upgrade-6-0-0.md).

## What Compass guarantees

- [Safety contract](safety-contract.md) - what Compass enforces, and what it does not claim.
- [Refusal codes](refusal-codes.md) - each reason the pre-tool hook can refuse with.
- [Security](security.md) - what Compass runs, and how it guards against tampered dependencies.

## How it works

- [Methodology](methodology.md) - the method and why it is built this way.
- [Portability](portability.md) - how Compass maps onto other agent runtimes.

The source, the CLI reference and the issue tracker are on
[GitHub](https://github.com/ayeo-io/compass).
