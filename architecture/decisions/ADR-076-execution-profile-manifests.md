---
id: ADR-076
title: Execution profiles are committed in a top-level profiles folder, with two new terms
status: proposed
date: 2026-10-22
supersedes: ''
superseded_by: ''
---

Decided for the issue `execution-profile-manifests` on 22 October 2026. jed72, the product owner, agreed the folder, the noun and the verbs. This record holds the design decision on where the store lives (`DD-1`) and the one on the terms (`DD-6`) of that issue. Both have project scope.

## Context

An execution profile fixes one way of working as a versioned file. The profile commands (`compass profile lint`, `add` and `show`) need a place for the stored versions and a place for the component registry, which says which skill, prompt fragment and tool guidance revisions exist and are approved. Later work reads the same paths, for example to record the profile a run used and to select one.

The new nouns need names. The word "catalog" already means one of the nine maps of configuration entries in `governance/terminology.yml`, so a second meaning would break ADR-012 rule 1 (one word, one meaning).

## Decision

**Where the store and the registry live (`DD-1`).**

1. Both are committed with the project, in a top-level `profiles` folder. They are outside `.compass/`, `governance/`, `.compass/work/` and `compass.yml`.
2. A stored version is the flat file `profiles/<id>.<version>.yml`. An id has no dot, so the first dot ends it.
3. The component registry is the file `component-registry.yml` in `profiles/`. It holds one key, `components`, a list. The profile commands read it and never write it.
4. The layout is flat, not `profiles/<id>/<version>.yml`. The pre-tool hook treats a path with some folder names as production code, and a project cannot remove such a pattern. A flat name avoids a path that an agent could not edit until a failing test is on record.
5. The commands build exact file names, list nothing and ignore other files in `profiles/`.

**The terms and the record (`DD-6`).**

1. `governance/terminology.yml` gains the terms `execution-profile` and `component-registry`, written as meaning only. New text says "profile" and "profile file".
2. The vocabulary version moves from `2.0.0-pre23` to `2.0.0-pre24` in the same change. Two new terms fill a gap, change no meaning and no ban, and ADR-012 rule 4 allows that with a version bump and a decision record.
3. The component registry keeps "registry" as the noun and `registry-duplicate` as the reason code. The word "catalog" keeps its meaning.
4. This file is the record. It adds no entry to `governance/decisions/`.

## Alternatives considered

- **`profiles/<id>/<version>.yml`.** The pre-tool hook blocks edits to a path with some folder names until a failing test is on record. Rejected.
- **A folder in `.compass/`.** The first proposal. The product owner moved the files out so a reviewer reads them as project data. Rejected.
- **`governance/`.** It holds rule files, and the commands must not change anything there. Rejected.
- **`compass.yml`.** It holds settings, not versioned content. Rejected.
- **Keep "component catalog".** It would give a frozen term a second meaning. Rejected.
- **A `governance/decisions/` entry.** That folder records a product decision by a named person. Rule 4 of ADR-012 allows this record instead. Rejected.

## Consequences

- Later items that record or select a profile read the same paths.
- `CLAUDE.md` says to stage each file by its path and never `.compass/`. Profile files are outside `.compass/`, so that rule does not touch them.
- A registry entry marked approved is text in a committed file. It is a recorded fact and not a checked one. `docs/execution-profiles.md` says so.
- The glossary gains two entries, and the count of terms moves from 99 to 101.

## References

- `docs/execution-profiles.md`, the owning document.
- ADR-012, the vocabulary rules.
- ADR-072, the refusal that asks for this record when a project-scope decision lands.
- `schemas/execution-profile.schema.json`.
