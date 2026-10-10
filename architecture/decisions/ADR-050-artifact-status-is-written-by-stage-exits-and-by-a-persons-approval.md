---
id: ADR-050
title: Artifact status is written by stage exits and by a person's approval
status: accepted
date: 2026-10-10
supersedes: ''
superseded_by: ''
---

## Context

The artifact registry in `manifest.yml` gives each document a status: `draft`, `awaiting-approval`, `approved`, `superseded` or `omitted`. Before this record no stage command moved it. Every registration wrote `draft`, and only a hand-run `compass issue artifact set --status` wrote another status. On the maintainer's archive, most entries on done issues still read `draft`, so the status told a reader nothing about whether anyone had accepted the document.

Define, refine, plan and breakdown have no command that records the end of the stage. ADR-045 derives the stage an issue is in from its records, because a missed writer hides state with no error. A decision an agent takes for the person, such as an answer to a requirement question, reaches the person only in the verification report, after the code exists.

## Decision

1. **Owning stage.** The artifact catalogue gains an optional `stage` key, validated against the stage catalogue. A kind with no `stage` is owned by ship. An issue stored before the key existed reads the shipped default preset's value for a shipped kind.
2. **The stage exit is the next record written.** A command that writes a record of stage S moves every `draft` entry that has a `path` and an owning stage earlier than S. With no human check on the artifact it becomes `approved`, and `approved_by` names the command. With a human check it becomes `awaiting-approval`. An entry with no `path` never moves, because no document has been written.
   - The writers are `compass issue artifact set` with a path (the kind's own stage), `compass issue subtask add` (breakdown), `compass tdd-red` and `compass acceptance record` (implement), `compass gate pass` on a `verify` gate (the `verify` stage, which also moves its own entries), and `compass ship-commit` (ship's own entries only).
   - A `verify` document registered after a `verify` gate has passed is approved by that registration, because the gate pass was the stage's record. `commands/verify.md` passes the gates before it registers the report.
   - `awaiting-approval` and `approved` are refused for an entry with no path, since no document has been written. The refusal names `--status omitted --reason`.
   - A quick fix has one document and no stage hand-offs, so a stage command leaves it alone and `compass quick-fix finish` approves it after `compass check` passes.
   - On the shipped default preset, `approved` means the pipeline moved past the document, and `approved_by` names the command. A person's approval names the person.
   - Statuses do not depend on the order of two later records once each document is registered at its own stage. `approved_by` names the first later record, so it can differ when two different later records arrive in a different order.
3. **A person's approval is a new evidence type.** `compass evidence approve` takes exactly one of `--check`, `--artifact <kind>` and `--decisions`. `--check` writes `human-approval`, as before. `--artifact` and `--decisions` write `artifact-approval`. `approval_records` counts an `artifact-approval` record that carries `check` for that human check. `human-approval-present`, the check of guardrail `G5`, reads only `human-approval`, so a document or decision approval never clears a sign-off. No form writes a `human-approval` record. A waiver's approval needs a `human-approval` record, so the new type cannot approve a waiver either. The terminal requirement and the refusal of the approver `agent` apply to all three forms.
4. **Rewrites are found by the document's own digest, recorded always.** On every registration, `compass issue artifact set` records the digest of the document and of each artifact it depends on. An `approved` entry whose recorded digest differs from the file goes back to `draft`, with `approved_by` and `approved_at` removed and a reason. The stale-document refusals stay behind the capability `artifact-freshness`. The governance decision `2026-10-10-artifact-freshness-records-digests-always` amends `2026-10-05-artifact-freshness-stays-opt-in` for the recording half.
5. **A re-assessment supersedes.** An entry the new approach no longer registers stays as `superseded` when it has a path, with a reason that names the re-assessment. An entry with no path is dropped, as before.
6. **The ship refusal is a check.** `artifacts-approved` 1.0.0 is a deterministic, blocking, unlocked check in the default preset, in no gate. It declines until every gate has passed, then judges a copy of the issue with the ship exit applied, which is the state `compass ship-commit` would leave. It fails on a document that reads `draft` or `awaiting-approval`, and on an `omitted` document with no reason, and each failure names the command that moves it. `compass check` runs it in its own block, and `compass ship-commit` runs it before the commit, so a refusal leaves no commit. An issue waiver can make it advisory. An issue stored on an earlier generation gains the check at its next `compass approach evaluate --write`.
7. **Decisions an agent took for the person.** The manifest gains `decisions_taken`, a list of `{id, question, resolution, by, stage, status, reason}` with status `open`, `confirmed` or `reopened`. `compass issue decision add --from-ledger` reads the requirements review's ambiguity ledger, and `compass issue decision add` records one by hand. `compass next` reads the manifest's `checkpoints:` for the first time and, at a checkpoint with unconfirmed decisions, reports the wait and lists them. `compass evidence approve --decisions` confirms them as a set. `compass retro --decisions` counts how they were settled.
8. **Migration.** `compass issue migrate` marks each `draft` or `awaiting-approval` entry on a done issue `approved` (close reason `completed`) or `superseded` (any other), with the reason "migrated from a 6.0.0 record". It is a dry run until `--apply`, which needs a copy of the work folder.
9. **Delivery.** All of this is the shipped default of 7.0.0, with no capability flag, no alias and no end date.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| A stage-exit verb for each of define, refine, plan and breakdown | One obvious writer per stage | ADR-045 gives the reason: a missed writer hides state with no error |
| Derive the status on read, as ADR-045 derives the stage | No stored state to go out of date | A person's approval and a rewrite back to `draft` are facts that must be stored, and a stored and a derived status would share one field |
| Record document and decision approvals as `human-approval` and change `human-approval-present` to ignore them | No new type | It changes a check that is locked hard. It was rejected by the maintainer |
| `human-approval` records with `G5` left alone | No change to the check | A decision confirmed at define would clear the sign-off on a critical issue |
| A new top-level `approve` verb | The words of the requirement | ADR-044 does not allow a top-level verb here, and `evidence approve` is already a named exception |
| The ship refusal hard-coded in `ship-commit` | Simpler | It cannot be waived |
| The refusal as a check in `G4` | An existing gate | ADR-039 locks `G1` to `G4`, so an issue waiver could not apply to it |
| Parse the ledger on every read | No second record | `confirmed` and `reopened` have no home in prose |

## Consequences

**Positive:**
- A landed issue reads `approved` on every document, with who or which command and when.
- An issue with an unapproved document cannot land.
- A requirement decision an agent took reaches the person at the next checkpoint, before the plan stage.

**Negative:**
- A document the approach earned and nobody wrote stops ship until it is written or omitted with a reason.
- A project kind with no `stage` waits for `ship-commit`, whose approval says little.
- The decision is recorded twice, in the ledger and in the manifest. The ledger id keys them, and `--from-ledger` reconciles them.
- `compass decision check` (the governance ledger) and `compass issue decision` (one issue's agent decisions) share a noun. Each means a recorded choice and who took it, with a different scope.

**Neutral / follow-on:**
- ADR-045's "No stage command writes `status`" now reads as the issue's workflow status. Stage commands write artifact status.
- ADR-044's `evidence approve` now takes `--artifact` and `--decisions`, and `issue decision` is a group with the leaf verbs `add` and `set`.
- ADR-026's `ship-commit` also runs `artifacts-approved` and approves the documents ship owns.
- ADR-022's manifest also holds `decisions_taken` and the approver fields.
- ADR-012 gains the term `decision-taken` in `governance/terminology.yml`, as ADR-041 and ADR-044 added terms.
- ADR-045, ADR-044, ADR-026 and ADR-022 stay as written.
- Any `--check` approval clears `G5` today, whatever it approves. That gap predates this record and is a separate item.

## References

- ADR-006: a project's added artifact kinds keep working.
- ADR-035: the catalogue is data, so the owning stage is a key and not a table in code.
- ADR-036: an issue runs against a stored generation, so an older issue gains the check at its next evaluation.
- ADR-038: a new check implementation carries a version and a fixture corpus.
- ADR-039: locks and waivers. `human-approval-present` stays locked hard and unchanged.
- ADR-044: noun-verb rule for the new verbs.
- ADR-045: the stage is derived from records, which the exit rule follows.
- `2026-10-06-evidence-types-stay-framework-owned`: the framework adds `artifact-approval` in a release.
- `2026-10-10-artifact-freshness-records-digests-always`: the recording half of artifact freshness.
