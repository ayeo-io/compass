---
id: ADR-039
title: "Waivers, locks and unlocks: who may depart from the shipped default"
status: accepted
date: 2026-10-06
supersedes: ''
superseded_by: ''
---

## Context

The maintainer accepted this record on 2026-10-06.

ADR-033 lets a project add and change checks, gates and dimension values as data, and keeps the five guardrails and the shipped core framework-owned and locked. The configurable-framework design makes the rest of the shipped default changeable through layers: the shipped default, an optional parent, the project file `compass.yml` and the issue's `config:`. A layer can loosen what the layer above it set. That needs three rules: who may approve a departure, what a lock protects, and what the CLI can and cannot confirm.

Today a project departs from a floor with a `waived:` entry that has an `id` and a `reason` and nothing else (`cli/compass_pkg/governance.py:166-182`). No one is named as approving it. The one approval the CLI checks is `human-approval` evidence, which must carry `approver`, `role`, `scope`, `timestamp` and `decision: approved` (`cli/compass_pkg/checks.py:740-775`). The CLI checks that the fields are present. It never checks who wrote them.

## Decision

**Three facts, reported apart.** The receipt names each one separately:

- **Conformance**: the effective configuration keeps every framework obligation.
- **Approval**: a permitted person authorised each departure.
- **Enforcement coverage**: what the installed CLI and hooks can block.

**Project waiver.** A waiver sits in the entry it excuses and writes three fields: `reason`, `approved_by` and `approved_on`. The approval is inline and committed with `compass.yml`. `approved_on` must not be later than today.

**Issue waiver.** It writes `reason` and `approved_by`, where `approved_by` is the id of a `human-approval` evidence record in the issue. It has no `approved_on`, because the record already carries a timestamp. The record names the entry and the field values it approved, so one approval cannot excuse a different waiver. An issue waiver expires when the issue lands.

**Derived, never written.** The CLI derives the waived fields from the entry's operation and the scope from the file the waiver sits in. It derives the covered revision too, and there is no `covers` field:

- for a project waiver, the `extends:` pin;
- for an issue waiver, the project revision recorded in the issue's generation.

A waiver is invalidated when the parent value of a waived field changed between the covered revision and the new one. A change anywhere else invalidates nothing. `compass policy update` and reassess run this test. `compass policy update` does not move the pin while a waiver it would invalidate stands unapproved. `compass policy lint` runs the same test when the pin in the working file differs from the pin at git HEAD. Outside git, or in a fresh clone, it prints "pin history unknown".

**Who approves.** Two layer keys name approvers. They are layer keys, not settings keys (ADR-043), so the project file and a parent may both carry them:

- `owner:` names the project's owner;
- `approvers:` names lists of approvers by kind: `issue-waiver` in the project file, and `project-waiver` in a parent.

The layer above the waiving layer names who may approve:

- an issue waiver: a name in the project file's `approvers.issue-waiver`, or the `owner` when the list is absent;
- a project waiver: a name in the parent's `approvers.project-waiver`, or the project's `owner` when the list is absent. The shipped default declares no list, so on the shipped default the owner approves;
- an unlock: the project `owner` only (below).

A waiver with no `owner` declared anywhere fails. A parent's own waivers count as already applied, and `compass policy effective` shows each as "parent waiver, not approved by this project". The adopter's approval is the approval of the `extends:` itself when the parent loosens the shipped default (`governance/decisions/2026-10-06-parent-waivers-count-as-applied.md`).

**Locks.** `locked: true` on an entry protects its footprint, compared with the obligation-field table the change classifier uses (ADR-037, configuration changes are classified by effect), so a lock and the classifier cannot disagree about what counts. The footprint is:

- for a check: its compared fields, its place in each stage list and gate the locking layer attached it to, and the existence of that stage and gate. This covers removing the stage, detaching the check from its gate, changing its `when`, widening `accepts` or `reviewers`, dropping its `approvers` and setting `on_skipped: pass`;
- for a gate: its check set, its accepted evidence types and its stage;
- for a stage: its existence, its order, and its entry and exit lists;
- for a rule: its effects.

- A lock allows a change that tightens the entry.
- A lock refuses a change that loosens it or cannot be compared.
- A waiver does not excuse a lock refusal.
- The guardrail that a human signs off on the irreversible (`G5`) and its check `human-approval-present` are `locked: hard`. No unlock lifts a hard lock.

**What the shipped default locks.**

| Entries | Lock |
|---|---|
| stage `assess`: its existence, and its place first | `true` |
| stages `verify` and `ship`, and `verify` before `ship` | `true` |
| gates `verify.correctness`, `verify.governance` and `verify.traceability`, and the rules that add them to every approach that ships | `true` |
| guardrails `G1` to `G4` and the checks in their sets | `true` |
| guardrail `G5` and check `human-approval-present` | `hard` |
| gate `spike.conclude`, the spike guardrails, and the spike approach's `ships: false` | `true` |
| evidence types and every gate's accepted types | fixed data, outside every layer |

Nothing else is locked. Floors, caps, loop ceilings and advisory rules are not, so a project departs from them with an approved waiver, as it waives a floor today.

This narrows ADR-033's list in two places. A shipped delivery approach and an assessment dimension stay framework-owned: only a framework release changes the shipped entry. But a project may depart from them in its own layer with an approved waiver, as the classifier allows (ADR-037); only the entries above need an unlock. And the pre-tool hook is not a configuration entry, so no layer can name it, lock it or unlock it (below).

**Unlocks.** Only the project layer can write `unlock:`, and only with a waiver its `owner` approves, as ADR-033 says. An issue, a parent or a preset that carries `unlock:` fails lint. An unlocked project is reported non-conformant by `compass check`, `compass issue receipt` and `compass approach summary` on every run.

**The hook is enforcement coverage.** The pre-tool hook is a shell script that reads the manifest, not a catalogue entry, so no layer can lock it or switch it off. The receipt reports the CLI and resolver versions it can confirm. For the hook it says "not verifiable from the CLI", because the CLI cannot see a user-scope install.

**The authentication limit.** The CLI checks that a name is in a list and that a date is not in the future. It never authenticates the person. Anyone who can edit `compass.yml` can write any name, and an edited `approved_on` clears a waiver without anyone reading the new parent value.

## Alternatives considered

- **A `covers` digest written in each waiver.** Rejected: the pin already sits in the same file, so a digest repeats it. A whole-revision digest also invalidates every waiver on any parent change, including one that does not touch the waived field.
- **A separate approvals directory.** Rejected: a committed file that names a person proves no more than a field that names a person, and it adds a file to keep in step with the waiver.
- **A lock refuses every change, stricter or looser.** Rejected: a project could not raise a locked check from advisory to blocking, which the framework has no reason to stop.
- **An `approvers.unlock` list, so a project names who may unlock.** Rejected: ADR-033 gives the decision to leave conformance to the owner, and a list would let a project widen it in the same file that carries the unlock.
- **Let any layer unlock.** Rejected: a published parent could switch off a framework guarantee for every project that extends it.

## Consequences

- A departure from the shipped default always carries a name and a reason, where today's `waived:` carries a reason only.
- A parent patch that does not touch a waived field asks for no re-approval. A list-valued field compares as a whole list, so adding one item to a waived list invalidates the waiver.
- Migrated `waived:` entries have no approval. They are read as `approved_by: LEGACY` and reported as "no approval recorded" until 7.0.0.
- `docs/safety-contract.md` does not yet state that `human-approval` evidence is not authenticated. It must state that, and that the same limit applies to waivers.
- A pin moved by a pulled commit already matches HEAD, so lint does not re-check its waivers.

## References

- ADR-033: projects add checks, gates and dimension values as data; the five guardrails stay locked.
- ADR-036: an issue runs against a stored generation.
- ADR-037: configuration changes are classified by effect.
- `cli/compass_pkg/governance.py:166-182` (today's `waived:`); `cli/compass_pkg/checks.py:740-775` (`human-approval-present`); `governance/guardrails.yml:268-273` (G5).
- Ledger: `governance/decisions/2026-10-06-locks-allow-tightening-and-g5-is-hard.md`, `2026-10-06-hook-coverage-is-not-verifiable.md`, `2026-10-06-lint-rechecks-a-hand-edited-pin.md`, `2026-10-06-legacy-waivers-readable-until-7-0-0.md`.
