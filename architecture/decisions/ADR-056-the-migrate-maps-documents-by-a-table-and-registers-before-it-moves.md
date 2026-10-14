---
id: ADR-056
title: The migrate maps documents by a table, renames reviews by a round rule, and registers a document before it moves it
status: proposed
date: 2026-10-12
supersedes: ''
superseded_by: ''
---

## Context

Before 7.0.0 the migrate moved every document it found beside a manifest into the issue's documents
folder and registered it under its own filename stem. The archive therefore holds kind names that no
catalogue declares: the 29 names that carry a review round (`review-1`, `verify-security-2`,
`integrated-review-3`), `design` and `prd`, and names that are not documents of a kind at all (a review
brief, an assignment, an architect's ruling). The migrate also moved the delivery-approach record first and
registered it second, which left a moment when `hooks/pre-tool.sh` found no record and blocked every code
edit. It left a pointer file at the old name, and it checked only `.compass/work/` for a Git copy although
it also moves files under `docs/compass/`.

## Decision

1. **A table says what each name becomes.** `migrate_kinds.KIND_RULES` is ordered and the first matching
   row wins:
   - a name on `stable_ids.NOT_AN_ARTIFACT` stays where it is and is not registered;
   - a name the catalogue declares is that kind, unless the kind is already registered at another file
     that exists: the registered path is kept, the file stays where it is and the report names both, so
     no later step edits a copy the person did not register;
   - `design` and `prd` are `technical-design` and `intent`; when both the old and the new kind are
     registered or present, both stay and the report names the issue;
   - `review.md` and `review-<n>.md` are rounds of `review`;
   - `review-claims`, `security-review`, `integrated-review-<n>` and `verify-<word>` are rounds of
     `review`;
   - any other name is unmapped: it is reported with the issue slug and left where it is.
2. **A round keeps its number when its name holds one.** `review.md` is round 1 and `review-<n>.md` is
   round n. Every other family takes the next free round after the highest of those, in ascending order of
   the number in its old name (1 when it has none), then the old name. Each entry's `reason` is "migrated
   from <old filename>". Two plain files that claim one round raise `RoundCollision` before anything is
   written, so that issue is byte-identical afterwards and the others are migrated.
3. **A document is registered before it moves.** For each issue the migrate does these steps in order,
   the delivery-approach record first and then by ascending round: re-point `design` and `prd`; register
   the new path; move the file; rewrite the manifest paths that named it; remove a compatibility pointer;
   rename a stub distribution map. The resolver falls back to the file beside the manifest until the move,
   so the hook finds the record at every stop. `migrate_kinds.STEP_HOOK(slug, step)` runs after each step,
   so a test can stop the migrate there and run the hooks. The hooks do not change.
4. **The migrate leaves no pointer.** It removes an earlier run's pointer only when its marker line is
   present and the registered file exists. A file beside the manifest without the marker is left and
   reported.
5. **Nothing a person wrote is deleted.** A stub distribution map (a lightweight map on an issue with fewer
   than two subtasks) is renamed to `distribution-map.md.v6.bak` and its entry becomes `superseded` with no
   path. A map that was never registered is adopted with no depth, so the rule does not judge it: it is
   kept as a person's map and the report lists it. The `recommendation` entry leaves the registry, and its
   file stays. The migrate adds no rendered
   block to an archived document (ADR-051 decision 3).
6. **Paths follow the files.** The paths that named a moved file are rewritten from the registry's
   "migrated from" reasons, so a run stopped after the move rewrites the same paths as one that was not.
   The slots include a gate's evidence when it holds a path.
7. **The copy check covers both folders.** `--apply` without `--i-have-a-copy` refuses when `.compass/work/`
   or `docs/compass/` is not tracked by Git.
8. **The report ends with the counts.** Per target kind, files left on the not-an-artifact list, unmapped
   files, pointers removed and stub maps renamed. The dry run writes nothing and a second `--apply` reports
   nothing to do.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| Stop on every round collision | No guess about which file wins | It leaves dozens of issues for hand work, and the round numbers are still not unique |
| A kind for each review brief | Every filename becomes a kind | Nothing reads the instances, and it works against "review rounds are review-n and nothing else" |
| Keep the pointer | Protects a hook installed before 5.0.0 | The registry has served the hook since 5.0.0, and the pointer is generated text that names a path |
| A second resolver in the hooks | The hooks look in the documents folder too | It is a second resolver in bash, the drift the hook's own comment warns against |

## Consequences

**Positive:**
- Every review round is `review-<n>.md`, and every ad-hoc kind name is mapped or ruled out.
- A migrate that stops at any step leaves the hook and `stop.sh` content with the record.
- A run that is resumed reaches the same rounds and the same bytes as one that is not stopped.

**Negative:**
- Round numbers of the non-plain families show order, not time.
- A project layer's own kind has no row, so its files are reported as unmapped and left where they are.
- An install of the hook from before 5.0.0 blocks once the pointer is gone (ADR-024: the release notes
  name it).

## Amendment, 14 October 2026: entries registered under a filename stem merge into their round

The 6.x migrate registered each document under its filename stem, such as a `review` entry with no
round or a `review-2` entry. Decisions 3 and 5 are extended, not changed:

- **Decision 3 gains a step.** Before a file moves, an entry registered under a stem is re-kinded to
  the kind and round the table gives it. When another entry already names that file, the two merge
  into one: the entry with the later approval keeps its id and approval; if only one is approved, that
  one is kept; if neither is, the round entry is kept, because stage exits write status and the
  round entry holds the more current one. Two entries whose files both exist are not merged; the
  report names both files for a person. The dry run prints the same merge line as the apply.
- **Decision 5 gains a removal.** A merged entry is the third thing the migrate removes, beside each
  pointer and the `recommendation` entry. The report names the dropped entry's id and approval, and
  the copy taken before `--apply` holds it.

A re-run repairs a tree an earlier 7.0.0 migrate left with stale stem entries.

## References

- ADR-006, ADR-020: the migrate and its rewrites.
- ADR-022: the artifact registry.
- ADR-024: an unobserved adopter is owed a migration path.
- ADR-040: framework constants live in one place.
- ADR-051: decisions 3 and 16, the archived document and `README.md.v6.bak`.
- ADR-054: a kind that repeats, keyed by round.
