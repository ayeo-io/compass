# set-on-a-map-is-key-by-key

## Decided by

jed72

## Date

2026-10-06

## Supersedes

Nothing.

## Decision

Inside `set:`, a map-valued field is changed key by key, with explicit `set` and `remove`. A plain map replaces the whole field.

## Why

An explicit form changes nothing by accident through a deep merge.

## Evidence

The maintainer's approval on 6 October 2026 of the recommendations for the open questions of the configurable-framework technical specification, given with the approval to split the configuration work into epics. Question Q-16.
