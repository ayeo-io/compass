# guardrails-merge-folds-into-prd-22

## Decided by

jed72

## Date

2026-10-05

## Supersedes

`governance/decisions/2026-10-05-guardrails-merge-routing-policy-replaces.md`

## Decision

A project's own guardrails are not merged with the shipped defaults as a separate feature. The configurable framework covers it: a project's `compass.yml` adds checks and changes defaults through its layers and merge operations. When its first slice lands, issue #105 is checked against it before it is closed.

## Why

Chosen from the recommendation of 5 October. Building a guardrails-only merge first would add a second merge mechanism that the configurable framework then replaces.

## Evidence

The maintainer's answer on 5 October 2026, to fold it in and check it is still relevant once the configurable framework is implemented. Issue #105.
