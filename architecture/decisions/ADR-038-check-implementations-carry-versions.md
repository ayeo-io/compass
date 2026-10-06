---
id: ADR-038
title: Check implementations carry versions, and a major change refuses rather than reinterprets
status: proposed
date: 2026-10-06
supersedes: ''
superseded_by: ''
---

## Context

The configurable-framework design records, for each issue, the configuration it runs against (ADR-036, an issue runs against a stored generation). A configuration names its deterministic checks by implementation id, and the CLI runs the implementation it ships. Recording the id does not preserve the behaviour: the code behind an id can change in any release.

Today the CLI has 22 built-in check implementations, in the `CHECK_FNS` table at `cli/compass_pkg/check_cmd.py:46-69`. None carries a version. `governance/guardrails.yml` (version 1.26.0) versions the policy file, not the code that runs it. A change to `_check_human_approval` (`cli/compass_pkg/checks.py:740`) would change the verdict for every open issue on its next `compass check`, with nothing to say that it happened.

Each of the 22 implementations already has a mutation proof in `tests/mutation_proofs.yml`: a `fails` test that feeds the check a broken input and a `restores` test that puts it right. These pairs are the only recorded inputs with known verdicts today.

## Decision

Each built-in check implementation is an entry in a registry, a new module, `check_registry.py` in `cli/compass_pkg/`. The entry carries:

- a semantic version;
- a fixture corpus: a directory of cases, each a small manifest and evidence tree with an `expected.yml` that holds the verdict (`pass`, `fail` or `nothing-to-check`).

`expected.yml` holds the verdict only, not the detail text, so a change of wording is not a change of behaviour. Each corpus starts from the check's pair in `tests/mutation_proofs.yml`, so it holds at least two cases from the first release. `CHECK_FNS` is derived from the registry, so every existing caller keeps working.

The build fails on an unannounced change of behaviour:

- A test runs every corpus and computes a digest of the verdicts per implementation.
- A lock file holds, per implementation, the version and the verdict digest.
- The test fails when a verdict digest changed and the major version did not.
- The test fails when an installed major is higher than the locked one and the lock file was not updated in the same change.

`compass check` refuses rather than reinterprets:

- The issue's generation records the version of each implementation it uses.
- When an implementation's installed major differs from the recorded major, that check returns `refused`.
- The refusal names both versions and points to `compass issue migrate-config`.
- Every other check still runs. A refused blocking check counts as a failure.
- `compass issue migrate-config` writes a new generation pinned to the installed versions and marks every result the old implementation produced as invalidated, so each runs again.

The same major rule applies to the configuration schema and to the resolver. A schema or resolver major that differs from the generation's refuses every command for that issue except `compass issue migrate-config`, because a different schema or resolver can change the meaning of every check at once.

The claim is narrow, and every document that states it must keep it narrow:

- Across majors, the CLI refuses.
- Within a major, compatibility is shown on the fixture corpus and nowhere else. A change of behaviour that no corpus case exercises is not detected.

`docs/safety-contract.md` must state this as a deliberate limit. A derived page must list, per implementation, its corpus cases and what each exercises.

## Alternatives considered

- **Record the implementation id only.** Rejected: an id names code, not behaviour, so the stored generation would name a check whose verdicts can change without notice.
- **Record a digest of the implementation's source.** Rejected: any edit, including a comment or a refactor, would refuse every open issue, and the digest says nothing about whether verdicts changed.
- **Ship every past major of each implementation and run the one the generation names.** Rejected: the CLI would carry every old version indefinitely, and old code would run against evidence written for new code.
- **Reinterpret silently on a major change.** Rejected: an issue's verdict would change between two runs with no change to the issue, which breaks the stored-generation guarantee.

## Consequences

- An issue never gets a verdict from an implementation it was not assessed against across a major. It gets a refusal that names the command to move on.
- A person who changes a check's verdict on any corpus case must bump its major and update the lock file in the same change, or the build fails.
- The within-major claim is weak at first: two cases per check, from the mutation proofs. It grows only as cases are added, usually when a defect is found.
- Two new artifacts must be kept: one corpus directory per implementation and one lock file.
- A schema or resolver major bump makes every open issue run `compass issue migrate-config` before its next check. Majors of these two must therefore be rare.

## References

- ADR-006: backward compatibility is non-negotiable; this record keeps a break visible and paid once.
- ADR-036: an issue runs against a stored generation; the generation records the versions this record compares.
- `cli/compass_pkg/check_cmd.py:46-69` (`CHECK_FNS`, 22 implementations).
- `tests/mutation_proofs.yml` (22 proof pairs, the seed of each corpus).
- `docs/safety-contract.md`, "Deliberate limits".
