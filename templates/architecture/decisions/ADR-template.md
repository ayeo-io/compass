---
id: ADR-NNN
title: Short title describing the decision
status: proposed
date: YYYY-MM-DD
supersedes: ''
superseded_by: ''
---

<!-- HOW ASSESS AND THE ARCHITECT PERSPECTIVE USE THIS FILE
     Assess scans architecture/decisions/ADR-*.md and includes a summary of
     each record (id, title, status) in architecture-loaded.yml.  The
     `architect` agent reads these summaries to know which decisions
     are already recorded, so it can cite them in architecture-notes.md
     rather than reopening settled decisions.

     Use `compass adr new <slug>` to create a new ADR from this template -
     it assigns the next sequential number and registers the file in README.md.

     Status lifecycle:
       proposed   - decision is being considered
       accepted   - decision is in effect
       superseded - replaced by a later ADR (set superseded_by: ADR-NNN)

     Frontmatter field guide:
       id             - matches the filename prefix (ADR-NNN)
       title          - short imperative phrase describing the decision
       status         - one of: proposed | accepted | superseded
       date           - ISO date when the decision was recorded
       supersedes     - id of the ADR this decision replaces ('' if none)
       superseded_by  - id of the ADR that replaced this one ('' if active)
-->

## Context

<!-- Describe the situation that needed this decision.  What forces
     were in play?  What changed in the system, team, or requirements that
     made the status quo unsatisfactory? -->

## Decision

<!-- State the decision clearly and concisely.  Lead with the verb:
     "We will use X", "We adopt the pattern Y", "We reject Z". -->

## Alternatives considered

<!-- For each alternative: what it was, why it was evaluated, and why it
     was not chosen.  A decision without alternatives is an assertion, not
     a record. -->

| Alternative | Why considered | Why rejected |
|---|---|---|
| <!-- option --> | <!-- rationale for considering --> | <!-- reason for rejection --> |

## Consequences

<!-- Describe the outcomes of this decision - positive, negative, and
     neutral.  Include: what becomes easier, what becomes harder, what
     is now deprecated or forbidden, and what follow-on decisions are
     implied. -->

**Positive:**
-

**Negative:**
-

**Neutral / follow-on:**
-

## References

<!-- Link to the issues, PRs, RFCs, other ADRs, or external sources that
     informed this decision. -->

-
