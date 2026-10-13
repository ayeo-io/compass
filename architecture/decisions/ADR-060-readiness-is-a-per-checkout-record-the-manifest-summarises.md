---
id: ADR-060
title: Readiness is a per-checkout record that the manifest summarises
status: proposed
date: 2026-10-13
supersedes: ''
superseded_by: ''
---

## Context

A measurement can take minutes and runs project commands, so the readiness floor (ADR-058) must read a stored result rather than measure at assess. The result describes one checkout at one commit. ADR-036 stores an issue's configuration as immutable generations and commits nothing when the configuration and the computed outcome are unchanged. Six readers need the result: `approach evaluate --write`, the session-start hook, `/compass:init`, `compass retro`, the receipt and the board, and the delivery-approach document.

## Decision

1. **The readiness record is `.compass/readiness.yml`.** `compass readiness` writes it. It holds each signal's id, implementation, version, weight, `required_for_autonomous`, result and reason, why a command signal's command did not run (`not_run`) and, for an absent signal, the one change that makes it present and the file it touches; `measured_at`; the HEAD commit; the path and digest of the settings file; the digest of the shipped readiness catalogue; and, for the test signal, the command timed and `duration_seconds`. `schemas/readiness-record.schema.json` describes it.
2. **It is per-checkout state.** Compass never commits it, and the upgrade guide tells a project to ignore it. It is a plain file a person can edit, like the project commands themselves.
3. **Fresh means all of these hold:**
   - the settings-file digest equals the digest of the settings file now;
   - the shipped catalogue digest and every recorded implementation version equal what this CLI ships;
   - `measured_at` is at most seven days before now, and not after now;
   - the recorded commit exists, and HEAD is at most 25 commits past it, counted as `git rev-list --count <recorded>..HEAD`.
   Without Git history only the first three apply; a record with no commit, read where history now exists, is stale. Otherwise the record is stale, and the reason names the first rule that failed. A missing record is "not measured"; one that cannot be read or parsed is "unreadable".
4. **One module reads it.** `readiness_record.py` parses the record, tests freshness, builds the summary and writes the one readiness line. Every reader calls it, so no two readers can disagree. It imports only the standard library, the YAML reader and atomic writer (`atomic_io`), `project_settings` and `readiness_registry`, so the session-start hook can import it cheaply.
5. **The manifest holds a summary, outside every generation digest.** Every `approach evaluate --write` writes the manifest key `readiness:`: `status: measured` with `score`, `signals`, `floor_met`, `absent` and `measured_at`, or `status: not-measured` with `reason` (`missing`, `stale` or `unreadable`) and `detail`. The key is not one of the generation outcome keys, so a new measurement with an unchanged configuration commits no generation; the manifest is still rewritten, as it is today when nothing changed. A manifest with no key reads as "not measured".
6. **The line reads "Repository readiness: N of M signals, floor met"**, "floor not met", or "not measured" followed by the reason in brackets.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| Store the summary in the generation | The generation records what the issue ran under | Every measurement would force a new generation and change every digest (ADR-036) |
| Commit the record | One record for every clone | A record describes one checkout; a committed one goes stale silently and can be forged by a contribution |
| Stale only on a settings or version change | No surprise refusals | A deleted instructions file or a broken build would keep the floor met indefinitely |
| Stale on every commit | Always current | An autonomous project would be refused after every change |
| Each reader parses the record | No shared module | Six freshness tests would disagree |

## Consequences

**Positive:**
- The delivery approach, receipt, board and retro show what the repository looked like when each issue was assessed.
- A new measurement never forces a new generation.

**Negative:**
- A fresh clone or CI checkout has no record, so an autonomous project runs `compass readiness` first. The limits of seven days and 25 commits are fixed in 7.0.0; making them settable needs a classifier rule for each.

**Neutral / follow-on:**
- The manifest schema gains an optional key; an issue assessed before 7.0.0 is unchanged.

## References

- ADR-005: state lives on disk.
- ADR-036: generations, and "nothing changed" commits nothing.
- ADR-058: the readiness floor.
- ADR-059: the catalogue and implementation versions.
- `docs/readiness.md` owns the record and its freshness rules.
