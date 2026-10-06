# dimensions-keep-tighter

## Decided by

jed72

## Date

2026-10-06

## Supersedes

Nothing.

## Decision

An ordered assessment dimension keeps its `tighter:` field, although no parameter reads it yet.

## Why

The configurable framework needs it, and a check parameter whose value is a dimension value will compare by it.

## Evidence

The maintainer's approval on 6 October 2026 of the recommendations for the open questions of the configurable-framework technical specification, given with the approval to split the configuration work into epics. Question Q-15.
