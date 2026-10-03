---
id: ADR-030
title: compass run is the one verb that starts a host session
status: accepted
date: 2026-10-03
supersedes: ''
superseded_by: ''
---

## Context

ADR-025 made the printed plan and the recorded run the multiagent
interface: Compass provisions, prints and records, and the host launches
the agents. Compass itself started no model session.

Issue #302 asks for a stage of an issue to run with nobody in
the session: one fresh `claude -p` session per cycle, with Compass deciding
between cycles from the files on disk. That needs something to start the
sessions. The eval harness (`evals/harness.py`) already starts `claude -p`
for its comparison runs, but it is a development tool, not a verb.

The maintainer was offline when this was written, so it was proposed: the
compass:architect agent ruled on their behalf that the runner could be
built and tested against a stub, and left accepting the exception to them.
The maintainer accepted it on 2026-10-03.

## Decision

`compass run` is the one Compass verb that starts a model session, as a
bounded exception to ADR-025. It is a new top-level verb: the tests that
pin the verb list, which record that Compass grows by documents and checks
rather than verbs, each name this decision as the reason for the addition.

- It starts `claude -p` and nothing else, through one launcher,
  `cli/compass_pkg/host_launch.py`, which the eval harness also uses.
- No hook and no other verb starts a session. The orchestrator still
  launches nothing, and the multiagent interface of ADR-025 is unchanged.
- A run is bounded: cycle and minute ceilings from the `loop_ceilings`
  rules in `governance/routing-policy.yml` (RP-LOOP-006, RP-LOOP-007), a
  stop file that must be named, and a stop after cycles that change
  nothing (RP-LOOP-005).
- A run never lands an issue. Landing stays a person's act.
- The runner reads no credential. It passes the caller's environment on
  as it is, and redacts credentials from everything it records or prints.

## Alternatives considered

- **Keep ADR-025 whole, and leave unattended runs to the host's own
  scripting.** Every adopter would write the loop, and none would have the
  ceilings or the stop file. The failures this guards against - a session
  that runs out of context, a stop file nobody checks, a credential in an
  error message - are the ones unattended loops are known for.
- **Embed a model client.** Compass would carry an SDK and a credential
  path. Starting the host's own `claude` keeps Compass a guest in it.
- **A daemon or scheduler.** Scheduling belongs to the host: cron or a CI
  workflow starts `compass run`.

## Consequences

- An adopter can run the build or verify stage unattended, and every run
  leaves a record and a `runs:` entry in the manifest.
- Every run costs money. The reference workflow `ci/headless-verify.yml`
  runs only when started by hand, and nothing in `.github/workflows/` runs
  it.
- The live acceptance in issue #302, a quick-fix example run assess-to-ship
  in CI, is not met until the maintainer approves a secret and a spend
  limit.

## References

- ADR-025, the multiagent interface this makes an exception to.
- Issue #302; the loop ceilings from #301.
- `docs/headless-runner.md`, the owning doc.
