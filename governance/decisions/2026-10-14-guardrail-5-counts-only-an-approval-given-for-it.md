# guardrail-5-counts-only-an-approval-given-for-it

## Decided by

jed72

## Date

2026-10-14

## Supersedes

Nothing.

## Decision

The locked check `human-approval-present`, the check of guardrail `G5` ("a human signs off on the irreversible"), counts only a `human-approval` record given for guardrail `G5`. A record given for guardrail `G5` is approved, holds no `check`, `waiver`, `checkpoint`, `artifact` or `decisions` key, and has a `guardrail` key that is absent or exactly `G5`. Any other approval was given for its own subject and is set aside. A person records the sign-off with `compass evidence approve --guardrail` and the value `G5`.

A sign-off with no subject key, the form every earlier sign-off uses, still counts. A landed issue that the earlier rule passes is reported, never failed.

The implementation moves to version 1.1.0 and keeps major version 1. The fixture corpus verdicts do not change, and a major bump would make `compass check` refuse the check on every issue whose generation recorded 1.0.0, landed issues included. The catalogue entry `checks.human-approval-present` and the gate entry of guardrail `G5` do not change.

The change is a re-scoping, not a tightening only. An in-flight issue whose only approval names another subject now fails. One in-flight case moves from fail to pass: an incomplete approval of another subject recorded before a complete sign-off no longer hides the sign-off.

## Why

An approval given for an unrelated human check cleared the sign-off on an irreversible change, so `compass evidence approve --check dod-reviewed` on an issue that touches payments also cleared the payments sign-off.

## Evidence

jed72 approved the change to the locked check on 2026-10-14 ("agreed on all recommendations"), in the issue `approval-scoped-to-guardrail-5`. ADR-066 records the structure. `tests/test_approval_scoped_to_guardrail_5.py` holds the behaviour.
