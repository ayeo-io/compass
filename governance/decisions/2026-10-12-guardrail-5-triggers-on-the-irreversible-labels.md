# guardrail-5-triggers-on-the-irreversible-labels

## Decided by

jed72

## Date

2026-10-12

## Supersedes

The critical-risk arm that issue `g5-trigger-matches-statement` added to the trigger of guardrail `G5`.

## Decision

Guardrail `G5` ("a human signs off on the irreversible") applies when an issue carries one of the labels `auth`, `payments`, `personal-data` and `migrations`, and only then. Critical risk on its own no longer brings the sign-off. The check `human-approval-present` and its hard lock do not change.

Critical risk still sets the full approach and every other gate. `compass approach evaluate` names the four labels when risk is critical and none is set, so the assessor decides whether the change is one of them.

An issue keeps the trigger stored in its generation. A project that wants the sign-off on every critical-risk change sets `G5.when` back to the four labels or critical risk in its `compass.yml`. The lock allows that because it is stricter, and refuses a trigger that drops a label.

## Why

Irreversibility is carried by the labels. A migration can lose data that cannot be restored, and auth, payments and personal data reach people outside the repository, so the four labels stay. Critical-risk code that carries none of them can be reverted at merge, and CI, review and Compass's own checks gate it, so a sign-off there guards nothing irreversible.

## Evidence

jed72's answer on 2026-10-12, "yes narrow guardrail 5", recorded in ayeo-io/compass-delivery-record#38 (Narrow guardrail 5's trigger to the irreversible labels) and public issue ayeo-io/compass#548 of the same name. `tests/test_g5_irreversible_labels.py` holds the behaviour.
