---
id: ADR-055
title: Every approach records its delivery approach, with a justification for each assessed value
status: proposed
date: 2026-10-12
supersedes: ''
superseded_by: ''
---

## Context

The delivery-approach record was written beside the manifest, and only the quick fix and, later, the
spike named it in the catalogue. The reasons for an assessment lived in a table inside the record, so a
reader of the manifest had no reason for a value. The quick-fix writer filled a missing reason with
"(no reason given)", and defaulted `--goal` and `--role` to `delivery` and `engineer` as if they were
assessed.

## Decision

1. **A catalogue flag owes the record on every approach.** An entry with `every_approach: true` joins
   every approach that does not name it. Its depth is the approach's mode for the kind's own stage when
   that mode is an artifact depth, else `lightweight`. `evaluate_route` reads the flag through
   `view.evaluator_policy()`. The classifier's policy comes from `obligations.policy_adapter`, which
   does not carry the key, so a stored generation owes nothing new.
2. **`evaluate --write` registers a depth and no path.** The writer sets the path with `compass issue
   artifact set` once the file exists, at the home `compass issue artifact-path delivery-approach` prints.
3. **The manifest holds `justifications` beside `assessment`, never inside it.** One line for each
   dimension of type `enum` or `ordered-enum`.
4. **A new or changed value needs a justification.** `compass approach evaluate --write --justify
   DIM=TEXT` merges the flags over the stored key and refuses, naming each dimension, when a value is new
   or differs from `evaluated_assessment` and has no non-blank line. It writes nothing on refusal. An
   unchanged value keeps its line, or none on an issue that predates the key, so a repeated write and a
   re-run on an archived issue are not refused.
5. **An omitted `--goal` or `--role` records no value.** `compass quick-fix start` refuses a value given
   without a reason, and writes no default. The readers (the receipt, the board, the flow rows) show an
   absent dimension as "not assessed". "(no reason given)" leaves the code.
6. **The receipt reads `justifications`, and keeps its reader of the record's table for an issue with no
   such key.**

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| List `delivery-approach` in every approach's `artifacts` | No new field | It cannot follow a layer that changes an approach's assess stage |
| Demand a justification on every write | Simple rule | It refuses a repeated write that records no new judgement, and every re-run on an archived issue |
| A fixed reason for the defaulted goal and role | No flag change | It is "(no reason given)" in other words, and records a judgement nobody made |

## Consequences

**Positive:**
- A manifest carries the reason for every assessed value.
- The record is a registered document on every approach, found through the registry.

**Negative:**
- Every first `evaluate --write` in a script or test gains `--justify` flags.
- `compass issue configure --commit` takes `--justify` too, because it runs the same evaluation.

## References

- ADR-001: the assessment is judgement.
- ADR-022: the artifact registry.
- ADR-036, ADR-037: stored generations and the classifier.
- ADR-053: the catalogue entry.
