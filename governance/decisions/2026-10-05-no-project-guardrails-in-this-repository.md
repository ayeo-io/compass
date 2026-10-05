# no-project-guardrails-in-this-repository

## Decided by

jed72

## Date

2026-10-05

## Supersedes

Nothing.

## Decision

This repository declares no project guardrails. Its `governance/guardrails.yml` is the default set every adopter gets, so a project guardrail declared here would apply to every adopter's project. The check that every check this repository adds has a mutation proof on record runs as a test in `tests/`, not as a guardrail. Answers issue #100.

## Why

Chosen from the recommendation of 5 October. The empty `project:` list is deliberate, and the proof check keeps its value as a test without reaching adopters.

## Evidence

Issue #100, and the comment beside `project:` in `governance/guardrails.yml`.
