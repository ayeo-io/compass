---
id: ADR-058
title: The readiness floor caps autonomous work
status: proposed
date: 2026-10-13
supersedes: ''
superseded_by: ''
---

## Context

Compass sizes the process a change gets from four dimensions of the change. Nothing measures whether the repository itself is fit for unattended agent work. `autonomy: autonomous` means "never wait for a person", and until 7.0.0 nothing conditions it: a project with no lint command, no reproducible build and a forty-minute suite can run a full-approach issue with no stop.

ADR-006 says every new mechanism no-ops on a project that has not adopted it, and that mandatory adoption is a breaking change that needs a major version and a migration guide. ADR-003 says cross-issue signals advise and never gate. The session-start hook never blocks a session.

## Decision

1. **A readiness floor exists.** It is met when every readiness signal marked `required_for_autonomous` in the effective readiness catalogue is present in a fresh readiness record (ADR-059, ADR-060). The shipped floor is four signals: agent instructions present, build declared and succeeds, tests declared and under two minutes, lint declared and clean.
2. **Only `autonomous` is refused.** `compass approach evaluate --write` refuses, with exit 2 and before it prints or writes anything, when the effective autonomy of the issue is `autonomous` and the floor is not met. The effective autonomy is the issue's own `autonomy` when its configuration sets one, else the project's. `balanced` and `controlled` are never refused. A project with no settings file defaults to `balanced`.
3. **Missing, stale and unreadable records refuse like a measured failure** on `autonomous`, and the message names `compass readiness`. So does a record measured for an untrusted contribution, in which a command signal holds `not_run: untrusted`; that message asks for a trusted run. `evaluate --write` never measures anything itself.
4. **An untrusted contribution is refused on its own terms.** The contribution trust decision (`trust.py`) is read from the environment before the record is read. When it refuses, `evaluate --write` on `autonomous` refuses with a message that says readiness cannot be measured for an untrusted contribution, that no setting lets one run unattended, and that `balanced` and `controlled` run. The refusal does not depend on the record, so a record committed by the contribution cannot clear the floor.
5. **`evaluate` without `--write` reports** whether a write would be refused, and why: a concern line in the default view, and a `readiness` key in `--json` holding the readiness summary and `would_refuse`, the refusal message or null.
6. **The session-start hook warns and never blocks.** It adds one line when the project is on `autonomous` and below the floor, or its record is missing, stale or unreadable. Every failure of the readiness code inside the hook loses the line, never the session.
7. **The floor is not a guardrail.** No guardrail, gate, check or routing rule names a readiness signal. `compass check` never reads readiness. The floor conditions how much a session may run without a person; it does not decide whether work lands. ADR-003 is unchanged: readiness is a property of the repository, not a cross-issue signal, and `compass readiness` and `compass retro` stay advisory.
8. **This is mandatory adoption at a major version.** It lands in 7.0.0 under ADR-006's major-version provision, with a section of the 7.0.0 upgrade guide as the migration guide. It must not ship in a 6.x release.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| Refuse in the session-start hook | Stops the session at the earliest point | The hook never blocks, and a refusal there would block a person's session as well as unattended work |
| Refuse in the pre-tool hook | Stops every code edit below the floor | It reaches every edit of every issue, including issues assessed before 7.0.0, and duplicates a decision the evaluator already makes per assessment |
| Make the floor a guardrail or a gate | Reuses the gate machinery | A gate decides whether work lands; the floor decides whether work runs unattended. A gate would also refuse `balanced` projects |
| Warn only, as ADR-006 prefers | No break for adopters | A warning on every session is the noise ADR-006 itself rejects, and the point is that unattended work on an unfit repository stops |
| Let a setting override the untrusted-contribution refusal | A way through for every CI run | The setting would be a file the contribution can edit |

## Consequences

**Positive:**
- An autonomous project below the floor is stopped at assess, with the absent signals and the setting to change named.
- `balanced` and `controlled` projects, and projects with no settings file, see only a new readiness line.

**Negative:**
- Every adopter on `autonomous` must run `compass readiness` in each checkout, weekly or every 25 commits, and in CI as a step before assess.
- `quick-fix start` computes its approach without `evaluate --write`, so this decision does not reach it. A separate decision is owed if quick fixes on `autonomous` are to be capped too.

**Neutral / follow-on:**
- The four required signals are catalogue data. A project layer can change the set, and loosening it needs the owner's waiver (ADR-039).

## References

- ADR-003: flow advises but never gates.
- ADR-006: backward compatibility; mandatory adoption needs a major version and a migration guide.
- ADR-036: an issue runs against a stored generation.
- ADR-059, ADR-060, ADR-061: the catalogue, the record and how commands run.
- `docs/upgrade-7-0-0.md`, section "Repository readiness and autonomous work".
- `docs/readiness.md` owns the readiness verb, the record and the floor.
