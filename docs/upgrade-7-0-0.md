# Upgrading to 7.0.0

This page lists what 7.0.0 changes and what to do about it. Each section is one change. The decisions behind them are in `architecture/decisions/`.

## Artifact status and decisions taken

Stage commands now write the status of each registered document. A document that is not accepted does not ship. The decision is `architecture/decisions/ADR-050-artifact-status-is-written-by-stage-exits-and-by-a-persons-approval.md`.

### What changes

- **Stage commands write status.** A command that writes the record of a stage moves the `draft` documents of earlier stages that have a path. The commands are `compass issue artifact set` with a path, `compass issue subtask add`, `compass tdd-red`, `compass acceptance record`, `compass gate pass` on a `verify` gate and `compass ship-commit`. A document with no human check becomes `approved`. A document with a human check becomes `awaiting-approval`.
- **`approved_by` names a person or a command.** A person's approval names the person. A stage's approval names the command, such as `compass tdd-red`. `approved_at` holds the time. The receipt and the dashboard show both.
- **A person approves with `compass evidence approve --artifact <kind>`.** It needs a terminal, and it refuses the approver `agent`. It writes a record of the new evidence type `artifact-approval`. That record meets the document's human check. It is not a `human-approval` record, so it never clears the sign-off of guardrail `G5`.
- **`compass issue artifact set --status approved` refuses a document with a human check.** It names the command above.
- **A rewrite moves an approved document back to `draft`.** Registering an approved document again after its file changed moves it to `draft` and records why.
- **Digests are always recorded.** `compass issue artifact set` records the digest of the document on every registration. The stale-document refusals stay behind the capability `artifact-freshness`.
- **A re-assessment keeps a written document as `superseded`.** An entry the new approach no longer registers stays when it has a path, with a reason that names the re-assessment.
- **`compass ship-commit` refuses an unapproved document.** The blocking check `artifacts-approved` fails on a document that reads `draft` or `awaiting-approval`, and on one omitted with no reason. Each failure names the command that fixes it. A document the approach earned and nobody wrote must be written, or omitted with `compass issue artifact set <kind> --status omitted --reason "<why>"`.
- **A quick fix gains no stop.** `compass quick-fix finish` approves the quick fix's document after `compass check` passes.
- **A project artifact with no `stage` is owned by ship.** Add `stage: <stage>` to its catalogue entry to have an earlier stage approve it. `compass ship-commit` approves the ship-owned ones.

### What to do

1. Run `compass issue migrate` for a dry run of the archive changes, then `compass issue migrate --apply --i-have-a-copy` after you copy `.compass/work`.
2. Open issues gain the `artifacts-approved` check at their next `compass approach evaluate --write`. Until then `compass check` and `compass ship-commit` do not run it for them.
3. Do not run a 6.x CLI on a 7.0.0 tree.

### New keys and verbs

| Name | Where | Meaning |
|---|---|---|
| `stage` | an artifact in the catalogue | The stage that owns the artifact |
| `approved_by`, `approved_at` | an artifact entry in `manifest.yml` | Who approved the document, and when |
| `artifact-approval` | the type of an evidence record | A person's approval of a document or of a set of decisions |
| `artifacts-approved` | a check in the default preset | The ship refusal |
| `compass evidence approve --artifact` | a flag | Approve a document that reads `awaiting-approval` |
