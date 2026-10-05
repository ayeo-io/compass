---
id: ADR-033
title: Projects add checks, gates and assessment-dimension values as data; the five guardrails and the shipped core stay framework-owned and locked
status: accepted
date: 2026-10-05
supersedes: 'ADR-002'
superseded_by: ''
---

## Context

ADR-002 fixed what may grow. The framework added artifacts and roles, never
a guardrail or an assessment dimension, and a project could not define its
own rules. Two invariants restated it: five guardrails, not more (`Inv-2`),
and no new delivery approaches or dimensions (`Inv-3`).

ADR-002 rejected project-defined rules for one reason. A project rule that
blocks the same CLI as a framework rule creates a compatibility surface: when
Compass upgrades it must not break the project's rule, and in May 2026 the
framework could not promise that.

Since then three things have changed:

- Projects already add checks. ADR-009 made architecture fitness functions
  project guardrails, run through the generic `command-passes` check and
  scoped by `applies_when` and `blocking_when` (`governance/guardrails.yml`).
  The rule ADR-002 states is no longer the rule the code runs.
- Adopters change one rule by copying every governance file and then drifting
  from the shipped copy. ADR-010 records the cost and proposes layering.
- The maintainer has approved a configurable framework: the stages, checks,
  gates, dimensions and vocabulary become data with shipped defaults, and a
  project or a single issue declares only its differences.

## Decision

The line moves from "what may be added" to "who owns it".

**The framework owns the core, and locks it.** These stay framework
decisions, changed only by a framework release with its own issue and ADR:

- the five guardrails `G1` to `G5` and their check sets;
- the shipped stages, delivery approaches and assessment dimensions;
- the gates no delivery approach can remove;
- typed evidence, and the pre-tool hook.

A project can unlock a locked entry only with a waiver its owner approves.
The project is then reported as not conforming to Compass on every run. No
unlock lets an irreversible change ship without `G5`'s human sign-off.

**A project adds the rest as data.** A project can add checks, gates,
assessment-dimension values and assessment dimensions in its configuration,
and an issue can adjust its own configuration. A project check is not a
guardrail and gets no G number.

**This holds only with four mechanisms in place.** They answer the
compatibility obligation ADR-002 could not meet:

1. Each issue runs against a stored copy of its resolved configuration, so an
   upgrade or a project change never changes an open issue.
2. Each built-in check implementation carries a version and a fixture corpus.
   A major change refuses to run an old issue's check rather than give a
   different verdict.
3. A classifier compares a project's configuration with its parent over every
   assessment. A change that loosens an obligation, or both loosens and
   tightens, needs an approved waiver.
4. Locks protect every field that changes how a locked check passes, using
   the same field list the classifier compares.

Until these ship, nothing changes for adopters. The project-rule surface opens
with them, not before.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| Keep ADR-002 and add exceptions case by case | No record changes; each exception is small | ADR-009 is already such an exception, and a rule with standing exceptions no longer tells a reader what is allowed. |
| Let projects add checks, but keep dimensions and gates fixed | Smaller change; checks are where the demand is | A check is scoped by assessment and attached to a gate. Without project gates and dimension values a project still copies files to scope its own check. |
| Let projects edit the core freely, reported by lint | Most flexible; lint already reports drift | Detection relies on someone reading the report. ADR-010 records a project that lost two gates while lint passed. |

## Consequences

**Positive:**

- A project that adds one check writes its difference, not a copy of every
  governance file.
- The records match the code: ADR-009's project guardrails are allowed by the
  rule, not by an exception to it.
- The guarantees `docs/safety-contract.md` makes stay framework-owned and
  locked.

**Negative:**

- The rule surface adopters can see grows. A reader must be able to see the
  resolved configuration and where each value came from.
- The framework takes on a versioning obligation for its check
  implementations, enforced by the fixture corpus.

**Neutral / follow-on:**

- The two invariants on guardrails and routing (`Inv-2`, `Inv-3`) in
  `architecture/decisions/README.md`, and boundary condition 4 in
  `architecture/system-context.md`, change in the same commit.
- ADR-010 is accepted in the same commit. Its three prerequisites are met by
  this design: a migration that keeps a copied `governance/` working, locks
  and the classifier for weakening, and a command that prints the resolved
  configuration with each value's source.

## References

- ADR-002 - the decision this replaces.
- ADR-009 - architecture fitness functions are project guardrails.
- ADR-010 - project governance layers over the framework defaults.
- ADR-006 - backward compatibility within a major version.
- `docs/safety-contract.md` - the guarantees the framework locks.
- `governance/decisions/2026-10-05-guardrails-merge-routing-policy-replaces.md`
  - the earlier plan for issue #105, in which guardrails merged first and the
  routing policy stayed replaced whole. Issue #105 is now part of the
  configurable framework, so both merge together when layering ships.
