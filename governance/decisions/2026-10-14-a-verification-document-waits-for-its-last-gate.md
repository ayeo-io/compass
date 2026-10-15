# a-verification-document-waits-for-its-last-gate

## Decided by

jed72

## Date

2026-10-14

## Supersedes

Nothing. It amends decision 2 of ADR-050 (artifact status is written by stage exits and by a person's approval) for the documents the `verify` stage owns. ADR-050 holds the matching dated amendment section. Merged ledger entries are not edited, so this entry is where the change is recorded.

## Decision

A document the `verify` stage owns, such as the verification report, is approved only when every gate of the issue that the gate catalogue places in the `verify` stage reads `pass`. Until then it reads `draft`.

- A gate of another stage, or one the catalogue does not define, does not count. At least one `verify` gate must exist.
- A document with a human check moves to `awaiting-approval` at the same moment, and not before.
- A `verify` gate pass still moves the `draft` documents of earlier stages on the first pass.
- `compass issue artifact set` approves a `verify` document only when every `verify` gate has already passed. Registered earlier, the document reads `draft` and the last `verify` gate pass moves it.
- No command rewrites a document the earlier rule approved, so no migration runs. No command gains a flag, output key or status word, and no catalogue file or locked check changes.

## Why

Under the earlier rule the first `verify` gate pass approved the verification report with `approved_by: compass gate pass`, even when the report's verdict was FAIL and other gates were pending. A reader of the issue page saw an approved report that no one had agreed was final. Approval now follows the end of the stage, which is the moment the report can be final.

## Evidence

Approved by jed72 on 14 October 2026. The tests in `tests/test_verify_report_approved_when_gates_pass.py` cover the rule and its edges, and a planted fault that restores the first-pass rule fails them.
