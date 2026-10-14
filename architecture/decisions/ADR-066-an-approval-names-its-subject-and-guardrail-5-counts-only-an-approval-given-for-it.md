---
id: ADR-066
title: An approval names its subject, and guardrail 5 counts only an approval given for it
status: proposed
date: 2026-10-14
supersedes: ''
superseded_by: ''
---

## Context

Guardrail `G5` ("a human signs off on the irreversible") has one check, `human-approval-present`, which the default preset locks `hard`. Version 1.0.0 of its implementation judged the first approved `human-approval` record in the evidence registry, whatever that record was given for. So `compass evidence approve --check dod-reviewed` on an issue that touches payments also cleared the payments sign-off. jed72 approved counting only approvals given for `G5` on 2026-10-14.

Four facts bound the answer:

- **Earlier sign-offs name no subject.** A `G5` sign-off has been a `human-approval` record with `approver`, `role`, `scope`, `decision` and `timestamp`, and often extra keys such as `path` or `conditions`. `EV-HUMAN-APPROVAL` in the archived issue `vocabulary-and-cli-renames` is one. Rewriting them would be a migration.
- **Other approvals already name a subject.** `compass evidence approve --check` writes `check`; a waiver's approval holds a `waiver` map; `--checkpoint` writes `checkpoint`; `--artifact` and `--decisions` write `artifact` and `decisions`. ADR-039 and ADR-063 already keep each of those approvals to its own subject.
- **ADR-006: a landed issue never moves from pass to fail.** Skipping records that do not count can newly fail a landed issue: with an approval of `check: dod-reviewed` first and an incomplete sign-off second, 1.0.0 judged the complete first record and passed.
- **ADR-038 ties a major version to a change of corpus verdicts, and `compass check` refuses a check across a major.** `impl_versions.refusals` exempts no status, so a major bump refuses the check on every issue whose generation recorded 1.0.0, landed issues included.

ADR-063's context says the check "accepts any approved `human-approval` record". That was true when it was written; this record changes that premise and leaves ADR-063's text as it is.

## Decision

1. **An approval names its subject.** The keys that name a subject are `approval_records.SUBJECT_KEYS`: `check`, `waiver`, `checkpoint`, `artifact` and `decisions`. A record holds a key when the key is present, whatever its value. A record that holds any of them was given for that subject. The list is a deny-list, so earlier sign-offs with extra keys keep counting. Every CLI writer of a `human-approval` record that holds a decision sets one of these keys or sets `guardrail` to `G5`, and a test enumerates the writers.
2. **Guardrail 5 counts only an approval given for it.** `approval_records.gives_g5(record)` is true when the record holds no subject key and its `guardrail` key is absent or the exact string `G5`. `g5`, `5`, `guardrail-5` and a list holding `G5` are set aside, and the failure detail shows the value. `human-approval-present` judges the first approved record, in registry order, for which `gives_g5` holds, and the missing-field rule applies to that record only. `compass evidence approve` imports the same predicate.
3. **A record with no subject key is the guardrail 5 sign-off**, for backward compatibility. No stored record is rewritten.
4. **`compass evidence approve --guardrail` records the sign-off**, given the value `G5`. It sets `guardrail` to `G5` and writes no `check`, needs a terminal and a scope, refuses the approver `agent`, refuses any value but `G5`, and refuses `--decision rejected`, because a rejected record would not withdraw an earlier sign-off.
5. **The landed floor.** On an issue that is not in flight, when the rule above fails and the 1.0.0 rule passes (the first approved `human-approval` record, whatever it names, holds all four fields), the check passes and says it is reported only. The floor holds by construction for every adopter, not only for the archives a sweep can read.
6. **The version reading.** A verdict change outside the fixture corpus stays within the major when a major would refuse landed issues. Both corpus cases (`broken`: no evidence; `restored`: one complete record with no subject key) keep their verdicts, so the implementation moves to **1.1.0**, the lock keeps its digest, and an issue whose generation recorded 1.0.0 is still judged. A minor version, a governance decision entry and the upgrade note announce the change.

The change is a re-scoping, not a tightening only. An in-flight issue whose only approval names another subject now fails. An in-flight issue whose incomplete approval of another subject was recorded before a complete sign-off now moves from fail to pass, which is the correct verdict, because the incomplete record was never the sign-off.

This record extends ADR-038 and ADR-063 and changes neither. The catalogue entry `checks.human-approval-present` and the gate entry of guardrail `G5` do not change.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| An allow-list of the fields a sign-off may hold | It would reject any unknown subject key | Earlier sign-offs hold extra keys such as `path` and `conditions`; an allow-list could fail them |
| Make every sign-off set `guardrail` to `G5` | It would make the subject explicit | Every earlier sign-off has no subject key, so in-flight issues would fail and stored records would need rewriting |
| Major version 2 | ADR-038 ties a major to a verdict change | It refuses the check on every issue whose generation recorded 1.0.0, landed issues included, which breaks ADR-006 |
| Stay at version 1.0.0 | No version machinery moves | `docs/check-implementations.md` would not show that the behaviour changed |
| Rely on a sweep of the archive instead of the landed floor | A sweep shows no landed issue newly fails here | It covers only this repository's archive; an adopter's landed issue could still newly fail |
| `compass evidence approve --check human-approval-present` | It reuses an existing form | It writes a `check` key, which the subject rule sets aside, and routes the record to the human-check reader |
| Amend ADR-063 | Its context states the old behaviour | Merged decision records do not change; a new rule is a new record |

## Consequences

- An approval of a human check, a waiver, a checkpoint, a document or a set of decisions never clears the sign-off on an irreversible change.
- A new subject key on any approval writer must be added to `SUBJECT_KEYS`; the writer test fails until it is.
- In-flight issues that relied on an unrelated approval must record a sign-off with `compass evidence approve --guardrail` and the value `G5` before they land. The failure detail names the record set aside, its subject and the command.
- A hand-written `human-approval` record with a decision and no subject still counts. An approver's name is not authenticated, the same limit as before.
- The fixture corpus still cannot grow within a major, because a new case changes the locked digest. That gap needs its own decision.

## References

- ADR-006 (backward compatibility), ADR-033 (locked guardrails), ADR-038 (implementation versions), ADR-039 and ADR-063 (one approval meets one subject).
- `cli/compass_pkg/approval_records.py` (`SUBJECT_KEYS`, `G5`, `subject_of`, `gives_g5`), `cli/compass_pkg/checks.py` (`_check_human_approval`), `cli/compass_pkg/approve_cmd.py` (`--guardrail`).
- `governance/decisions/2026-10-14-guardrail-5-counts-only-an-approval-given-for-it.md`.
- `tests/test_approval_scoped_to_guardrail_5.py`.
