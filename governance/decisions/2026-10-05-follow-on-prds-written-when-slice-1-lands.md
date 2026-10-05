# follow-on-prds-written-when-slice-1-lands

## Decided by

jed72

## Date

2026-10-05

## Supersedes

Nothing.

## Decision

The configurable framework (ADR-033) defers four pieces of work to their own product requirement documents: custom stages with declared exit outcomes, external waits, concurrency control, and lighter presets. These documents are written when the framework's first slice lands, not numbered and stubbed now. Until then, the first slice cites each one by its title.

## Why

Chosen from the recommendation of 5 October, with the timing changed. The four topics need execution semantics that the first slice will make concrete, so writing them earlier would mean writing them twice.

## Evidence

The design review of the configurable framework on 5 October 2026, recorded with ADR-033 in the same pull request.
