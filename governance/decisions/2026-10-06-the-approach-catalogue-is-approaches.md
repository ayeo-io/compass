# the-approach-catalogue-is-approaches

## Decided by

jed72

## Date

2026-10-06

## Supersedes

Nothing.

## Decision

The configuration catalogue of delivery approaches is named `approaches`. With it, the issue-layer key is `approach:`, the floor effect is `force_minimum_approach` and vocabulary ids use the prefix `approaches.`. `routing-policy.yml` and the `router` agent keep their names. The legacy keys `route_shapes` and `force_minimum_route` stay readable through 6.x.

## Why

The rest of the product already calls these approaches: the `compass approach` verbs, the `approaches/` documents and the manifest's `delivery_approach`. `routes:` would bring back the word the vocabulary bans for this thing, and `delivery_approaches:` is long and repeats in every nested id.

## Evidence

The maintainer's approval on 6 October 2026 of the recommendation for question Q-4(a) of the configurable-framework technical specification.
