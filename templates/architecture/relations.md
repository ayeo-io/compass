# Service Relations

<!-- HOW ASSESS USES THIS FILE
     Assess reads this file and includes it in architecture-loaded.yml as a
     narrative artifact.  The `architect` agent reads it to determine
     which labels in the manifest map to known service names, so it
     fires automatically when acceptance criteria are defined and a
     manifest label matches a service named here.

     Format: keep service names consistent with the labels you use in the
     manifest (the `labels:` field) so the agent can match them.
-->
<!-- absorbed: "(see TRC-B2)." -->

## Service map

<!-- List every service / application / external dependency this context
     interacts with.  One row per relation.  Direction: A -> B means A calls B
     (A is the caller, B is the callee).
-->

| From | To | Protocol | Purpose | Criticality |
|---|---|---|---|---|
| <!-- name --> | <!-- name --> | <!-- HTTP / gRPC / event / DB / etc. --> | <!-- one line --> | <!-- high / medium / low --> |

## Ownership

<!-- Cross-reference to ownership.md when the caller and callee have
     different owners - those relations are highest-risk for architectural
     drift. -->

## Known interface contracts

<!-- List any stable contracts (OpenAPI specs, proto files, event schemas)
     that this service publishes or consumes.  Changing a contract must
     create or update an ADR. -->
<!-- absorbed: "A change that modifies a" -->

| Contract | Location | Owned by |
|---|---|---|
| <!-- name --> | <!-- path or URL --> | <!-- team / person --> |

## Prohibited relations

<!-- Relations that must NEVER be created - typically because they would
     create a cycle, violate ownership, or cross a data-classification
     boundary.  These can also live in architecture/invariants.yml, an
     optional freeform YAML file the assess stage already reads into
     architecture-loaded.yml. -->
<!-- absorbed: "is populated. --\>" -->

- <!-- example: service-A must not call service-B directly (use the event bus) -->
