# Compass

Compass is acceptance-test-driven development for Claude Code, with a record
a reviewer can check. It lets a team under change control hand code changes
to an AI agent and still show a reviewer, or an auditor, that the process
was followed. A person approves each change, and Compass records that
approval. Compass writes the record of a change itself: it runs the tests on
a copy of the commit the change started from, where they must fail, and on
the working tree, where they must pass. For each change, Compass records who
asked, what was agreed, the failing run, the passing run, who approved and
the commit that shipped. Each change leaves one plain file, `trail.md`, with
a SHA-256 digest for each record. A reviewer checks it with `sha256sum -c`,
without Compass installed. The [safety contract](safety-contract.md) states
what each guarantee covers and where it stops.

Five guardrails apply to all work that ships code, whatever the assessment:
a test that fails without the change, acceptance criteria before code, code traced to
a criterion, typed evidence rather than a written claim, and a person's
approval for a change labelled `auth`, `payments`, `personal-data` or
`migrations`. A project can add checks of its own, report failures without
blocking while it tries Compass, or excuse one check on one issue with a
waiver a person approves. The person's approval cannot be waived
([safety contract](safety-contract.md)).

## Start here

- [Five minutes](five-minutes.md) - one small change in two commands, from the request to a commit that holds the code and its record.
- [Quickstart](quickstart.md) - from an empty machine to a finished first issue.
- [Install check](install-smoke-test.md) - confirm an install works.
- [Configuration](configuration.md) - project settings live in one file, `compass.yml`; a setting can only add to the check set, and `compass policy show` prints the check set and its digest.
- [Upgrading to 7.0.0](upgrade-7-0-0.md) - coming from 6.x: each change, what breaks and what to do.
- [Upgrading to 8.0.0](upgrade-8-0-0.md) - coming from 7.x: the delegation change, what breaks and what to do.
- [Upgrading to 6.0.0](upgrade-6-0-0.md) - coming from 5.x: the renamed words and commands, and what reads the old form until 9.0.0.

## What Compass guarantees

- [Safety contract](safety-contract.md) - what Compass enforces, and what it does not claim.
- [Refusal codes](refusal-codes.md) - every reason the pre-tool hook can refuse with.
- [Security](security.md) - what Compass runs, and how it guards against tampered dependencies.

## How it works

- [Methodology](methodology.md) - the adaptive, spec-driven method and why it is built this way.
- [Portability](portability.md) - how Compass maps onto other agent runtimes.

The source, the CLI reference and the issue tracker are on
[GitHub](https://github.com/ayeo-io/compass).
