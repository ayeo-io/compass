# locks-allow-tightening-and-g5-is-hard

## Decided by

jed72

## Date

2026-10-06

## Supersedes

Nothing.

## Decision

A lock allows a child layer to make the locked entry stricter and refuses any change that loosens it or cannot be compared. The guardrail that a person signs off on the irreversible (`G5`) and its approval check are hard locks, which no unlock lifts.

## Why

An unlock must never grant permission to ship an irreversible change without a person's sign-off.

## Evidence

The maintainer's approval on 6 October 2026 of the recommendations for the open questions of the configurable-framework technical specification, given with the approval to split the configuration work into epics. Question Q-14.
