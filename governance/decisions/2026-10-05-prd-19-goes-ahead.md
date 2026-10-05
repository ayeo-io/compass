# prd-19-goes-ahead

## Decided by

jed72

## Date

2026-10-05

## Supersedes

Nothing.

## Decision

Routing policy as configuration goes ahead: stages, modes and routes become data with `extends:`, after the route rename lands and after a decision record for the format change. It ships together with the first slice of the configurable framework as 6.0.0.

## Why

Chosen from the recommendation of 5 October. The configurable framework needs it, and its compatibility requirement keeps existing project policies working; a major release is where any break is allowed.

## Evidence

The maintainer's answer to the routing-model questions on 5 October 2026.
