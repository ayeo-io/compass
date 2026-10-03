---
id: ADR-031
title: The delivery record is kept in a second, private repository, synced at every landing
status: accepted
date: 2026-10-03
supersedes: ''
superseded_by: ''
---

## Context

A project keeps its issue records out of its own git history:
`.compass/work/` and `docs/compass/<created>-<slug>/` are ignored, so a
public repository does not publish working notes. For Compass itself the
planning documents (`docs/analysis/`, `docs/proposals/`) and the backlog
command are ignored too. So the record that justifies every landing existed
on one machine, and a lost disk would erase it.

## Decision

The record is kept in a second repository, named under `record:` in
`.compass/config.yml` with the paths it holds. For Compass that is
`ayeo-io/compass-delivery-record`, private, chosen by the maintainer on
2026-10-03.

- `compass record sync` copies the paths into a clone of that repository,
  removes what the project no longer has, redacts credentials in text, and
  commits and pushes, naming the project's commit.
- `ship-commit` runs it after every landing. A failed sync fails ship
  loudly; the commit stands, and `compass record sync` is the fix.
- `compass record restore` copies the record back into a project, such as a
  fresh clone, and refuses to overwrite a file that differs unless told to.
- The clone lives in the user's cache folder, never inside the project.

## Alternatives considered

- **A private branch in the same repository.** One push to the wrong
  remote, or one public fork, would publish it.
- **A tracked, scrubbed archive in the project.** Scrubbing for publication
  removes what makes the record useful, such as the planning documents,
  and a public repository is the wrong place for them.

## Consequences

- The record survives the machine. The restore drill, run once from a fresh
  clone, is recorded in the issue that built this.
- A project that names no record is unchanged.
- The record repository must stay private; Compass cannot check that.

## References

- ADR-006, backward compatibility: a project that names no record is unchanged.
- `docs/delivery-record.md`, the owning doc.
