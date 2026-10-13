---
id: ADR-059
title: Readiness signals are a versioned catalogue
status: proposed
date: 2026-10-13
supersedes: ''
superseded_by: ''
---

## Context

A readiness signal is one binary fact about a repository, such as "a lint command is declared and exits 0". Projects differ in which facts matter, so the set must be configuration, changed by a project layer under the same rules as every other catalogue (ADR-033, ADR-035, ADR-037, ADR-039). The code behind a signal can change between releases, which is the problem ADR-038 solved for checks with versioned implementations.

"Signal" already names the cross-issue patterns in `governance/signals.yml`, and "floor" already names the routing rules that raise a minimum approach.

## Decision

1. **A new catalogue, `readiness`.** The shipped default preset gains `readiness.yml` with eleven signals. Each entry has `statement`, `impl`, `weight`, optional `params` and `required_for_autonomous`. The catalogue joins `catalogue_spec.CATALOGUES`, so merge, lint, the classifier, `policy diff`, `policy show` and the generated schema read it from the same field table.
2. **The floor is a field of each entry.** `required_for_autonomous: true` marks a signal the readiness floor needs (ADR-058). It compares as an ordered field where `true` is stricter, so turning it off is a loosening that needs the owner's waiver, written in the entry it excuses, as making a blocking check advisory does.
3. **Implementations are registered with versions.** A leaf module, `readiness_registry.py`, holds one entry per implementation: name, semantic version, parameter types, allowed values, the stricter direction of each parameter (as for check parameters, ADR-038: `none` makes any change incomparable), and whether it runs a project command. `check_registry.READINESS` exposes the same table, so implementations are looked up in one place. `compass check` never runs one: `REGISTRY` and `CHECK_FNS` do not hold them.
4. **Every result is binary.** An implementation returns `present` or `absent` with a one-line reason. No other result exists, and a signal that cannot run is absent with the reason.
5. **The score counts signals.** "N of M signals" counts present signals against all signals. `weight` orders the fix list within the required and the other signals; it never scales the score, because the score is a count and not a grade.
6. **Lint refuses an unregistered implementation**, naming the signal and the implementation, and a parameter the implementation does not take, of the wrong type or outside the registered choices. Lint reads the resolved entry, so a layer that only sets `params` on a shipped signal is judged against that signal's implementation (`M-READINESS-IMPL`, `M-READINESS-PARAM`).
7. **The words are "readiness signal" and "readiness floor"** in printed output and documentation, so neither reads as a `signals.yml` pattern or a routing floor.
8. **The classifier compares one fact, `readiness`.** For each signal it holds `impl`, `params` and whether `required_for_autonomous` is true (false when absent). A signal that only one side has is off the floor on the other side, so removing a floor signal is a loosening and adding one to the floor is a tightening. `weight` and `statement` are not compared. The classifier version is 3.
9. **The catalogue is resolved like the others and stored in each generation.** A project with a `compass.yml` reads it through the layer chain, including this repository, whose own `compass.yml` the effective view otherwise skips. A project with no `compass.yml` reads the shipped catalogue. The legacy governance views carry no readiness entry, and the legacy adapter takes the readiness catalogue and its display names from the shipped preset, so the views still adapt back to the preset. The preset's `vocabulary.yml` gives each signal a display name (`readiness.<id>`).

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| A top-level `required_for_autonomous` list | Matches the first wording of the requirement | A waiver is written in the entry it excuses (ADR-039); a list has no entry to hold it, and the merge machinery treats a catalogue as a map of entries |
| Register implementations in `REGISTRY` beside checks | One table | `compass check` would be able to run a readiness signal, and the floor would read as a check |
| Weighted score | Lets a project rank signals | A grade is a non-goal; a count is the one number a person can check by reading the list |
| Readiness kept out of the generation | A catalogue change would not commit a new generation | It adds a special case to the resolver for one catalogue, and the stored generation would no longer describe the configuration in force |

## Consequences

**Positive:**
- A project adds, changes or removes a signal with the operations it already uses for checks, and `policy diff` classifies the change.
- A changed implementation cannot keep an old result fresh: its version is in the record (ADR-060).

**Negative:**
- Adding a catalogue changes the resolved configuration of every issue, so each issue's next `evaluate --write` after the 7.0.0 upgrade commits a new generation, as any preset change does.
- This repository's `compass.yml` held settings only (governance decision `2026-10-06-this-repository-may-hold-a-settings-only-compass-yml`), so its one readiness override, which times its micro suite, needed a new decision: `2026-10-13-this-repository-declares-readiness-commands`.

**Neutral / follow-on:**
- Reading host settings, such as branch protection, through an API is not a signal in 7.0.0.

## References

- ADR-033, ADR-035: projects add catalogue entries as data.
- ADR-037: classification by effect.
- ADR-038: implementations carry versions.
- ADR-039: waivers, locks and unlocks.
- ADR-041, ADR-044: the vocabulary.
- `docs/readiness.md` lists the eleven signals and their implementations.
