---
id: ADR-032
title: Rival product names are held in an off-GitHub key and kept out by hashed matching
status: proposed
date: 2026-10-04
supersedes: ''
superseded_by: ''
---

## Context

The maintainer ruled on 2026-10-04 that no rival product's name, alias,
organisation, repository slug or URL is committed to GitHub
(`governance/decisions/2026-10-04-rival-names-never-committed.md`). That
covers the public repository, the private delivery record (ADR-031), commit
messages and pull request text. Compass compares itself with rival
frameworks, so its eval harness, tests and published runs named them in
365 places.

## Decision

- Committed text names a rival by its code, R1 to R9.
- The key that maps codes to names lives under `.compass/private/`,
  untracked and ignored. It also holds each rival eval condition's clone
  address, commit pin and any runtime path that contains a name.
- A gate, `scripts/rival-name-gate.py`, finds names from
  `scripts/rival-name-hashes.txt`: SHA-256 hashes of each entry's
  alphanumeric tokens. It needs no key, so CI runs it over tracked files and
  paths, commit messages and pull request text, and it reports places, never
  names.
- `compass record sync` replaces names with codes when `record.names_key` is
  set, and refuses to sync when that key is missing.

## Alternatives considered

- **A plaintext deny list in the repository.** It would commit the names it
  exists to keep out.
- **Substring matching.** It flags a name inside an unrelated word and misses
  a name split by a different separator; token n-grams do neither.
- **Rewriting git history.** It needs a force-push that breaks every clone
  and fork. Left to the maintainer.

## Consequences

- Past commits still carry names; only new history is clean.
- Short names can be recovered from their hashes by brute force. The codes
  already say a rival exists, so the hashes add little.
- An eval run of a rival condition needs the key; without it the harness
  skips that condition and says so.

## References

- ADR-031, the delivery record this keeps clean.
- `governance/decisions/2026-10-04-rival-names-never-committed.md`.
