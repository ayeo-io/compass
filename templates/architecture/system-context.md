# System Context

<!-- HOW ASSESS USES THIS FILE
     Assess reads this file at the start of every issue and includes it (with
     its SHA-256 fingerprint) in .compass/work/<issue>/architecture-loaded.yml.
     Downstream agents - `spec-author`, `planner`, and `architect` - read
     architecture-loaded.yml to get persistent architectural context that
     survives session boundaries and context compaction.

     Keep this file factual and concise.  It is machine-read as well as
     human-read.
-->

## What this system does

<!-- One paragraph: the primary purpose of this system and the problem it
     solves.  Avoid implementation detail; focus on the outcome it delivers
     to its users or dependents. -->

## Bounded context

<!-- Name this service/application and draw the boundary.  What is inside
     this context?  What is deliberately outside? -->

## Primary users and dependents

<!-- Who or what calls this system?  Who or what does this system call? -->

| Actor | Relationship | Notes |
|---|---|---|
| <!-- name --> | <!-- caller / callee / operator --> | <!-- one line --> |

## Non-goals

<!-- What this system explicitly does NOT do.  Non-goals are important:
     they prevent scope creep and help the `architect` agent flag when a
     proposed change would cross the stated boundary. -->

## Quality attributes

<!-- The two or three attributes that are non-negotiable for this system
     (e.g. availability, consistency, latency, throughput, auditability). -->

| Attribute | Target | How enforced |
|---|---|---|
| <!-- name --> | <!-- measure --> | <!-- test / monitor / contract --> |
