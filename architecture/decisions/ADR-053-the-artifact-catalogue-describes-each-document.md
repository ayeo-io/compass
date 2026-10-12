---
id: ADR-053
title: The artifact catalogue describes each document
status: proposed
date: 2026-10-12
supersedes: ''
superseded_by: ''
---

## Context

A document kind's stage, owner, reader and headings sit in template comments that no tool reads.
`legacy_adapter.ARTIFACT_STAGES` holds a second copy of the stage. ADR-035 sets the field table of the
catalogues, and ADR-050 decision 1 made `stage` optional, so a kind with no stage waited for the ship
commit. The issue `artifact-catalogue-fields` needs each kind to carry the facts a skeleton, a glossary
entry and the readers of the registry draw on.

## Decision

1. **Five required fields.** An entry in the artifacts catalogue holds `file`, `stage`, `owner`,
   `audience`, `stands_for` and `sections`. `depends_on` stays optional and reads as an empty list.
   `stage` was optional under ADR-050 decision 1 and is now required.
2. **Three optional fields.** `required_when` says when an owed document is owed. `every_approach` marks
   a document every delivery approach owes. `checks` and `bookkeeping` are as before.
3. **`sections` maps a depth to its headings.** The keys are artifact depths and each value is a list
   of heading texts in order. A list may be empty only for a document whose template is one rendered block
   and has no `## ` heading.
4. **Where the checks sit.** The merge refuses an added kind that lacks a required field with
   `M-ADD-PARTIAL`, naming each field. `compass policy lint` reports, in one run and in the `resolved`
   group, a malformed `sections`, `file` or `required_when`, a blank `audience`, `owner` or
   `stands_for`, and an `owner` that is neither an agent nor a value of the `role` dimension.
5. **Reading an old generation.** `artifact_kinds.entry` returns a stored entry with each absent
   descriptive field filled from the shipped default, for a kind the shipped default declares. It never
   fills `required_when` or `every_approach`, so a stored generation keeps the obligations it was stored
   with (ADR-036).
6. **The legacy adapter.** The adapter takes the descriptive fields and `required_when` of a shipped
   kind from the shipped catalogue and no longer holds a stage table. It does not copy `every_approach`.
7. **The classifier.** `artifacts.required_when` is an obligation field compared by identity, for the
   kinds an approach owes. A layer that only adds a kind is `equivalent` and needs no waiver; the
   classifier keeps its four results. `compass policy diff` names an added kind on a line of its own.
8. **A project layer that adds a kind with only `file:` no longer resolves.** There is no flag and no
   alias. The release notes name the break.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| A front-matter block in each template | Keeps the facts beside the prose | A preset cannot change it, and a project kind with no template cannot have it |
| Keep `stage` optional | Fewer breaks for a layer | The owning stage is needed by every reader of the registry |
| Check the shape of each field in `catalogue_check.check_layer` | One place for every check | The layer group stops the lint at its first fault, so a bad stage and a bad `sections` would not both be reported in one run |
| A fifth classifier result, `additive` | Names the case | It changes the JSON shape, the cache key and every consumer of `result` |

## Consequences

**Positive:**
- One entry holds who reads a document, who writes it, its traditional name and its headings.
- A preset or a project adds a kind with the same fields, and the classifier needs no waiver for it.

**Negative:**
- A project layer that adds a kind with only `file:` stops resolving at 7.0.0.
- The legacy adapter now reads the shipped catalogue from disk.

**Neutral / follow-on:**
- One function, `artifact_owed.owed()`, answers whether an issue owes a kind whose entry holds
  `required_when`. `compass check`, `compass next`, the issue page, the board panel and the receipt all
  ask it, so they agree. The subtask count is the length of the manifest's `subtasks:` list, and an
  absent list counts as zero. A person's `omitted` record wins over the condition.
- A kind whose condition is false is left out of `artifacts-approved` (this reads ADR-050 decision 2).
  A distribution map that was written or omitted still marks breakdown done, because a person's record
  wins over the condition (ADR-045 is unchanged).
  A full issue capped to one worktree with one subtask no longer owes the map.
- The skeleton, the generated glossary entries and the stored-generation fallback for the readers are
  built in later units of the issue. They finish this record.

## References

- ADR-035: the field table of the catalogues.
- ADR-036: an issue runs against a stored generation.
- ADR-037: the classifier.
- ADR-050: artifact status, decision 1 on `stage`.
- `docs/policy-lint.md` owns the lint findings.
