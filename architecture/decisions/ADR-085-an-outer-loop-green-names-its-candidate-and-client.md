---
id: ADR-085
title: An outer-loop green names its candidate and client
status: accepted
date: 2026-11-02
supersedes: ''
superseded_by: ''
---

## Context

A reviewer cannot tell an acceptance green from a unit-test green when no record says what was tested or through which interface. Strategy `S17`, the four-layer acceptance strategy, drives the outer loop through a client interface against a named candidate (PRD-2026-002, the four-layer acceptance strategy, requirement FR-09). The product owner decided that a local build can be the candidate, named by its tree id, and that a record missing either the candidate or the client is refused. Every green already names its tree (`tree_id`, `binding.ids_for`).

## Decision

1. **Three flat fields.** An outer-loop green record can hold `candidate`, `candidate_kind` (`local` or `deployed`) and `client` (`api`, `web` or `cli`). `compass tdd-green --loop outer` takes `--candidate <build id>|local` and `--client api|web|cli`, and `compass quick-fix finish` takes the same flags. Any build id is a deployed candidate. `local` stores the record's own `tree_id` as the candidate, with kind `local`; outside git there is no tree id, so `local` is refused.
2. **The client list is fixed.** Another client is refused with exit 2, and the message lists the three. A project cannot add a client.
3. **Refused at write.** On an issue the strategy applies to (`acceptance_strategy.in_scope`), an outer-loop green that names no candidate, no client or neither is refused with exit 2 before the command runs, and nothing is written. `compass quick-fix finish` refuses before it traces a file. The message names what is missing and the two flags.
4. **Refused at registration.** `compass evidence add --type test-run` refuses to register an outer-loop green that lacks either, on an in-scope issue.
5. **Checked at verify.** `outer-loop-recorded` fails each registered outer-loop green that lacks either, or names another client or candidate kind, on an in-scope issue. This finds a record registered another way, such as by editing the manifest.
6. **A unit-test green names neither.** `compass tdd-green --loop inner` refuses `--candidate` and `--client`, so the fields mark an acceptance green only. `compass quick-fix finish` chooses its loop itself, so a session cannot always tell which one it records: on the inner loop it takes the two flags and does not write them. It still refuses an unknown client. `commands/quick-fix.md` therefore gives the two flags in every finish command.
7. **Out of scope.** Where the strategy does not apply, an outer-loop green needs neither field, and the fields are written when given.
8. **One run, several scenarios.** With `--loop outer`, `compass tdd-green` takes `--scenario` more than once, or `--every-scenario`, as `compass tdd-red` does (ADR-081). One run writes one green per scenario, each with the same `run_id`, `scenarios_in_run`, candidate and client. Every scenario needs its red before the command runs.
9. **The retrospective.** `compass retro --acceptance` lists, for each counted issue, the clients its outer-loop greens name, and reports how many counted issues have a deployed candidate and which have a local candidate only.
10. **The quick-fix reuse.** `compass quick-fix finish` reuses a green already on record only when it is of the loop the finish records and names the same candidate and client. Before, it took the newest registry entry of the scenario whatever its loop, so an inner-loop green on the same tree stood in for the outer-loop green, and every later finish reused it again.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| A nested `candidate: {id, kind}` | Groups the candidate's two parts | The spec and the retrospective read three scalar fields, and nesting adds a shape check |
| Extend the record of which scenarios the BDD runner ran | That record already names the run | A project without `project.bdd_runner` would get no field |
| Default `--candidate local` on `quick-fix finish` | A quick fix runs on the working tree, so fewer flags | The record would claim a client and candidate nobody named; the client has no default, so a flag is still needed |
| Write the flags on an inner-loop green | A finish could always pass them, and they would be kept | A unit-test green would then look like an acceptance green, which is what the fields exist to prevent |
| Refuse the flags on an inner-loop `quick-fix finish` too | One rule for both commands | A session would have to know which loop finish records before it runs; the teaching would need one command per case |
| A new corpus case and major version 2.0.0 for `outer-loop-recorded` | The corpus would show the new rule | The check has not shipped in a release; a major bump would refuse the check on every issue assessed on this branch. The `restored` case now holds both fields, and the scenario tests cover the rule |

## Consequences

- On an in-scope issue, `compass tdd-green --loop outer` and `compass quick-fix finish` need `--candidate` and `--client`. An in-scope quick fix records the outer loop by default (ADR-080), so its finish needs them too.
- A record written before this decision is read as it is. An in-scope outer-loop green with no candidate or client fails `outer-loop-recorded` until it is recorded again.
- `compass tdd-green` moved from `cli/compass_pkg/tdd.py` to `cli/compass_pkg/tdd_green.py`.

## References

- ADR-080 (the `loop` field), ADR-081 (one red run for several scenarios), ADR-082 (the outer-loop file and registry entry), ADR-084 (one run count per loop).
- `cli/compass_pkg/candidate_client.py`, `cli/compass_pkg/tdd_green.py`, `cli/compass_pkg/outer_loop.py`, `cli/compass_pkg/quick_fix_cmd.py`, `cli/compass_pkg/acceptance_strategy.py`.
- `tests/acceptance/atdd_strategy/test_candidate_client.py`.
