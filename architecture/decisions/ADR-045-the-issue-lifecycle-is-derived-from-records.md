---
id: ADR-045
title: The issue lifecycle is derived from records
status: accepted
date: 2026-10-08
supersedes: ''
superseded_by: ''
---

## Context

The maintainer agreed on 2026-10-08 that the issue workflow has five states: `backlog`, `ready`, `in-progress`, `in-review` and `done` (ADR-044). This record decides how a manifest stores them.

The CLI stores five other words in `status`: `queued`, `active`, `parked`, `landed` and `abandoned`. Three facts shape the choice:

- No stage command records that a stage started or ended. `compass next` already works out the stage from records: the acceptance criteria, the requirements review, the technical design, the distribution map, subtasks and test records. No event marks "plan starts" or "review starts".
- Only `ship-commit`, the quick-fix start and the status command write `status`. Assess writes none, and an absent status reads as in flight (ADR-006).
- ADR-005 says state is reconstructible from disk.

A stored in-flight state needs a writer at every place a record is written. A writer that is missed leaves the issue on the wrong board column with no error.

## Decision

**A manifest stores only a hold or a close.** `status` holds `backlog` (a hold a person set) or `done` (closed). With no stored status the issue is in flight.

- `done` carries `close_reason`: `completed`, `not-planned` or `duplicate`. A `duplicate` also carries `duplicate_of`, the slug of the other issue.
- A `blocked` mapping with `reason` and `at` is a flag. It is allowed only while the state is `in-progress` or `in-review`, and closing the issue or putting it in `backlog` clears it.
- `parked_reason`, `parked_at`, `status_reason`, `land_timestamp` and `land_commit` keep their meaning.

**The other three states are derived on read, from records.** One accessor, `state_of`, decides them in this order:

1. `done` gives `done`.
2. `backlog` gives `backlog`, whatever the records say.
3. A gate with a status other than `pending`, or a registered verification report, gives `in-review`.
4. A top-level `current_phase` key wins next, as it does in `compass next`.
5. A registered technical design or distribution map, any subtask, or any test record gives `in-progress`.
6. Acceptance defined and the requirements review finished, collapsed or skipped gives `ready`.
7. Otherwise `backlog`.

No stage command writes `status`. A person cannot set `ready`, `in-progress` or `in-review`: the command refuses and says the records move those states. `issue status remove` ends a hold. It also reopens a closed issue, because v5.6.0 `issue set-status active` reopened one and that spelling keeps working until 7.0.0. A reopening deletes `status`, `close_reason` and `duplicate_of`, keeps the land time as history, and records a reason (`--reason`, or a default).

**Only `done` with close reason `completed` is completed work.** The living spec takes its issues from completed work on an approach that ships. Its heading reads `### <slug> (completed <date>)`, and the reader accepts the older `landed` heading.

**The manifest's `schema_version` becomes `3.0`.** The stored `status` values and three new keys (`close_reason`, `duplicate_of`, `blocked`) change what every reader may assume, and v5.6.0 does not read a file in new words. That is a major version of the manifest. Commands accept schema versions 1, 2 and 3 and refuse 4 with the existing message to update Compass.

**Old values are read, not stored.** `queued` and `parked` read as `backlog`. `active` reads as in flight. `landed` reads as `done` with `completed`, and `abandoned` as `done` with `not-planned`, unless a close reason is already stored. The mapping rules are in ADR-044.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| Store all five states, with a writer at each stage | The manifest shows the state without the CLI. | It needs a writer at about six places, and a missed writer hides the issue with no error. |
| Recompute the state and store it on every save | One writer. | A hold still needs its own rule, and the stored copy goes stale between saves. |
| Keep `active` and add `ready` and `in-review` | Smaller change to the readers. | Two vocabularies would stay in use, which ADR-044 removes. |
| Add a field that records the lossy mapping | The report would be in the manifest. | A field is public contract after 6.0.0 and would record a one-time event. A notice and a backup file carry the same information. |

## Consequences

**Positive:**
- A stage command that forgets to write a state cannot hide an issue.
- The old `active` needs no mapping, because nothing is stored.
- Twenty readers compare through one accessor instead of five status words.

**Negative:**
- A manifest file does not show its in-flight state without the CLI.
- The board's `--json` keys change: the keys `held`, `next_up`, `landed_this_week` and `abandoned` go, and the board lists `backlog`, `ready`, `in_progress`, `in_review`, `done_this_week` and `closed`.
- An older release refuses or misreads a 3.0 manifest, so a rollback needs the backup file or a forward fix.

**Neutral / follow-on:**
- A rule that compares a status with an old word never matches. A source guard fails on such a comparison in the CLI package.
- ADR-008, ADR-026 and ADR-034 now read as "done with close reason completed".

## References

- ADR-005: state is reconstructible from disk.
- ADR-006: backward compatibility is non-negotiable.
- ADR-008, ADR-026, ADR-034: the living spec and the issues that feed it.
- ADR-044: vocabulary and CLI naming.
- `governance/decisions/2026-10-08-the-living-spec-heading-word-is-completed.md`
