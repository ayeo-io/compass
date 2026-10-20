# Ownership

<!-- HOW ASSESS USES THIS FILE
     Assess reads this file and includes it in architecture-loaded.yml as a
     narrative artifact.  The `architect` agent uses ownership data to
     flag when a proposed change crosses team boundaries - a common source of
     undetected coupling and rework.

     Keep this file current.  Stale ownership is worse than no ownership file:
     the agent will flag risks against the wrong team, creating noise and
     eroding trust in the mechanism.
-->

## Service / module ownership table

<!-- One row per service, module, or significant library. -->

| Surface | Owning team | Primary contact | Notes |
|---|---|---|---|
| <!-- name --> | <!-- team name --> | <!-- person or alias --> | <!-- e.g. "on-call rotation" --> |

## Ownership rules

<!-- State any rules that govern how ownership can change or how cross-team
     changes must be coordinated.  These rules can also live in
     architecture/invariants.yml, an optional freeform YAML file the assess
     stage already reads into architecture-loaded.yml - no schema constrains
     its shape yet. -->
<!-- absorbed: "architecture/invariants.yml once the schema is finalized. --\>" -->

- <!-- example: a change to a service's public API must be approved by that service's
       owning team before it can land. -->

## Cross-team dependencies

<!-- Enumerate dependencies where the caller is owned by a different team
     than the callee.  These are highest-priority for the `architect` agent. -->

| Caller (team) | Callee (team) | Contract | Review required |
|---|---|---|---|
| <!-- name (team) --> | <!-- name (team) --> | <!-- contract name --> | <!-- yes / no --> |
