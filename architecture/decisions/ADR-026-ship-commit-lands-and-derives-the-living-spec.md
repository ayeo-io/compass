---
id: ADR-026
title: ship-commit lands every issue and derives the living spec
status: accepted
date: 2026-09-25
supersedes: ''
superseded_by: ''
---

> **Amended by ADR-034 (2026-10-06, proposed):** `ship-commit`'s derive
> includes only the landed issues on the branch, and `compass issue refresh-spec`
> clears a conflict confined to the derived spec.

> **Supersession rule:** the derive archives a scenario only when its
> manifest records `superseded_by`, which names a scenario in the same issue.
> A shared intent id supersedes nothing. Intent ids are local to an issue, and
> most issues use INT-1, so keying on the id archived other issues' scenarios
> and the issue's own sibling scenarios.
>
> **Layout, with no size cap:** `docs/system-spec.md` keeps every current
> scenario. It shows one `### <slug> (landed <date>)` heading per issue and one
> line per scenario, `` - `<id>` <title> ``. The earlier cap of 4000 words came
> from the split into spec and archive, which assumed the spec was mostly
> superseded scenarios. That was the intent-id defect above, not real
> supersession, so the cap is removed. The archive file holds only scenarios
> that record `superseded_by`.

## Context

ADR-008 made the living system spec a derived file, and put its derivation
at "the final step of `scripts/integrate.sh`, after combined-regression
green". When it was written, `integrate.sh` was the step that landed a
multiagent issue, and `integrate.sh` also wrote `status: landed` into the
manifest.

Two things have changed since:

- `ship-commit` lands every issue. It commits the issue's files, marks the
  issue landed once every gate has passed, and records `land_commit`, which
  the landed checks compare against. Nothing derived the spec for an issue
  that did not run `integrate.sh`, so every solo issue left the spec out of
  date until someone re-derived it by hand.
- The multiagent protocol (ADR-025) integrates a staged run one wave at a
  time. Under ADR-008's rule, the first green wave marked the whole issue
  landed and derived the spec, before `/compass:verify` and before the
  later waves.

## Decision

`ship-commit` is the one step that lands an issue and derives the spec.

- After a successful commit with every gate passed, `ship-commit` marks the
  issue landed and records `land_commit`, as before, then runs the
  derivation. If `docs/system-spec.md` changed, it commits that file alone.
- `integrate.sh` merges the subtasks and runs the combined regression. It
  does not write `status`, and it does not derive the spec.

This amends ADR-008's first rule only: where the derivation runs. Its other
three rules stand - the spec is reconstructible from landed issues alone,
idempotent, and never a source of truth.

## Alternatives considered

- **Keep ADR-008, and land only on the last wave.** `integrate.sh` would land
  the issue when the map's last subtask merged. Rejected: solo issues would
  still need a manual re-derivation, and two different steps would mark
  issues landed depending on how they were built.
- **Derive in the land commit itself.** `ship-commit` would mark the issue
  landed and derive the spec before committing, so one commit holds both.
  Rejected for now: the commit id is not known until after the commit, so
  `land_commit` would have to be written in a second step anyway.

## Consequences

- Every issue that lands updates the living spec, in a commit of its own
  after the land commit.
- A staged multiagent run can integrate each wave without landing the issue.
- An issue shipped with a gate not passed is not marked landed, and the spec
  is not re-derived, as before.

## References

- ADR-008 - cross-issue derived artifacts; this record amends its first rule.
- ADR-025 - the multiagent interface, whose staged waves made the change
  necessary.
- `cli/compass_pkg/manifest.py` - `ship-commit`.
- `scripts/integrate.sh` - the multiagent integration step.
