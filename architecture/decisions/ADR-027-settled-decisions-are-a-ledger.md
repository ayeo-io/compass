---
id: ADR-027
title: Settled product decisions are a ledger of immutable entries, recorded by the person who made them
status: accepted
date: 2026-10-02
supersedes: ''
superseded_by: ''
---

## Context

Compass records design decisions as ADRs and freezes its vocabulary in
`governance/terminology.yml`. Neither holds the small product decisions a
review keeps colliding with: a command's name, a refusal's wording, the
choice of version number, which file owns a fact. Those were settled in
conversation or in a pull request, and nothing a reviewer reads says so.

On 2026-10-02 a review point was implemented on trust although the routing
policy contradicted it, and the result shipped as a defect (#242). The
same day, reviews raised points the maintainer had already settled.

## Decision

- Product decisions live in `governance/decisions/`, one file per decision,
  named `YYYY-MM-DD-<slug>.md` by the day it was recorded. Each holds
  `Decided by`, `Date`, `Supersedes`, `Decision`, `Why` and `Evidence`, in
  under 200 words.
- An entry never changes. A change of mind is a new entry whose `Supersedes`
  names the old one. `compass decision check` fails when an entry that
  exists at a base ref is changed or removed; `compass ci --since <ref>`
  runs it.
- `Decided by` comes from `git config compass.decidedBy`, else `user.name`,
  so a person can be recorded by a handle. The CLI offers no way to
  set it, because in a session the one passing an option is the model, and
  an agent never decides; it records what a person decided.
- Reviewers read the ledger before recommending a rename, a wording change
  or a reversal, and report a collision as "settled by <path>".

## Alternatives considered

- **No verb: entries written by hand from a template.** Smallest surface, and
  ADR-002 prefers growth by artifacts and lenses. Rejected because the
  decider would then be typed by whoever writes the file, which in a session
  is the model; `compass decision record` reads it from git instead.
- **A subcommand of an existing group,** as the `bdd` group holds its own
  subcommands. No existing group fits: `adr` records design decisions with
  their reasoning, and `policy` checks the governance YAML. A ledger entry
  is neither.
- **Extend `terminology.yml` or the ADRs.** Rejected: the vocabulary file
  must stay the authority for words only, and ADRs argue a design, where an
  entry records an outcome.

## Consequences

- The history check departs from the letter of ADR-002, which says any new
  check registers as a `CHECK_FN` entry under an existing guardrail. The
  guardrails judge an issue's work; this check judges the repository's own
  ledger, as `policy lint` judges the governance YAML. So it runs as a group
  of `compass ci`, as `policy lint` does, and adds no guardrail.
- ADRs stay the record of design decisions with their reasoning. The ledger
  records outcomes and does not argue them.
- `terminology.yml` stays the vocabulary authority. An entry may cite a
  term; it may not define one.
- The ledger only helps if it stays small and is read. The 200-word cap and
  one outcome per entry keep it small; the reviewer and governance-check
  wording make it read.
- Adds the `decision` verb to the public surface, a minor change under
  ADR-006.

## References

- ADR-002, the framework grows by adding artifacts and lenses, not by adding
  guardrails or routing dimensions.
- ADR-006, backward compatibility within a major.
- `governance/decisions/`, the ledger.
- `cli/compass_pkg/decisions.py`, the verb and the history check.
