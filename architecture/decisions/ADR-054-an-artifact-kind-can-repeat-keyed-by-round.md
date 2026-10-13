---
id: ADR-054
title: An artifact kind can repeat, keyed by round
status: proposed
date: 2026-10-12
supersedes: ''
superseded_by: ''
---

## Context

Every reader of the artifact registry took the first entry of a kind. A review has several rounds, and
the archive reached 25 kind names (`review-claims`, `integrated-review-3`, `verify-security-2`) because
the registry could hold one `review` only. ADR-022 gives each entry an id, a status and a path, and
ADR-050 judges each entry by its status. Neither says what an issue with two reviews looks like.

## Decision

1. **The filename marks a kind that repeats.** A kind repeats when its catalogue `file` holds `<n>`, as
   `review-<n>.md` does. There is no separate flag, so the two cannot disagree.
2. **One entry per round, with a `round`.** Each entry has its own id, status and path.
   The round is read from the filename and stored as an integer from 1. A filename that does not match
   the pattern, or that carries a leading zero, is refused with the pattern named.
3. **The latest round is the default.** `compass issue artifact-path <kind>`, `resolve_artifact` and
   `artifact_path` answer with the highest round when no round is named. `--round N` names one.
   Registering the same round again updates its entry and adds no new one.
4. **Every reader lists every round.** `artifacts-approved`, the issue page, the board panel and the
   receipt each show one line per round with the entry id and path. A finding names the entry id and the
   round it is about.
5. **A kind that no approach, rule or `every_approach` flag names is voluntary.** Today these are
   `review`, `bug-report`, `architecture-notes`, `product-owner-review` and `positioning`.
   `compass issue artifact set` accepts any kind the issue's catalogue declares, and a reassessment never
   marks a voluntary entry `superseded`. `approach evaluate --write` keys its merge by kind and round.
6. **One home for every kind.** `compass issue artifact set --path` accepts only
   `docs/compass/<created>-<slug>/<file>`, with the round in `<file>` for a repeating kind. The rule
   holds for every kind, read from the catalogue's `file`, with no list of exceptions in the code.
7. **`compass issue lint` reports a stray file.** A top-level `.md` file in the documents folder that
   matches no kind's `file` and is not on `stable_ids.NOT_AN_ARTIFACT` is one line of the report. The
   finding does not change the exit code.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| A separate `repeats: true` field | Names the behaviour | It can disagree with `file`, and a kind would then both repeat and name one file |
| A kind per round (`review-1`) | No registry change | It is how the archive reached 25 kind names; no catalogue can declare them |
| A list of the six new kinds that have a home | Smaller change | ADR-040 forbids a list of ids in code, and the rule has no exception |
| Make `review` owed on every approach | No voluntary kinds | Every issue would owe a review document and fail `artifacts-approved` without one |

## Consequences

**Positive:**
- A review round is a registered document, and no reader hides a later round behind the first.
- A reassessment keeps a review a person registered.

**Negative:**
- Every reader of the registry took one entry per kind. Each changed in the same commit.
- `artifact set --path` refuses a path outside the documents folder, so a fixture that registered a
  document elsewhere changed.

**Neutral / follow-on:**
- The migrate (a later unit of the issue) maps the ad-hoc review names onto `review-<n>.md`.

## References

- ADR-022: the issue record is a manifest, with an artifact registry.
- ADR-040: stable ids are constants.
- ADR-050: artifact status.
- `docs/artifact-catalogue.md` owns the catalogue fields, the rounds and the home rule.
