# this-repository-may-hold-a-settings-only-compass-yml

## Decided by

jed72

## Date

2026-10-06

## Supersedes

`governance/decisions/2026-10-05-no-project-guardrails-in-this-repository.md`

## Decision

This repository still declares no project guardrails, and the check that every shipped check has a mutation proof stays a test in `tests/`. Once the configurable framework lands, this repository may hold a root `compass.yml`, but only with settings keys (such as `autonomy`), never a check, a gate or another change to the shipped default. A test enforces this, so this repository's own issues keep running the shipped default unchanged and its delivery record stays evidence for it.

## Why

Chosen from the recommendation of 6 October. The earlier reason, that this repository's `governance/` files reach every adopter, does not apply to a root `compass.yml`, which only this repository reads. The stricter rule is kept so that the framework is measured on the default it ships.

## Evidence

The maintainer's answer to question Q-21 of the configurable-framework technical specification, 6 October 2026.
