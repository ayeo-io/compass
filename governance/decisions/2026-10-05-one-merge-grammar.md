# one-merge-grammar

## Decided by

jed72

## Date

2026-10-05

## Supersedes

Nothing.

## Decision

There is one merge grammar for a configuration layer: `set:` to update named fields, `replace: true`, `remove: true`, and `add:` and `remove:` on list fields inside `set:`. Routing policy as configuration is built with this grammar from the start, so no adopter ever sees two.

## Why

Two grammars would need two merge engines and would show adopters two ways to write the same change.

## Evidence

The maintainer's answer to question Q-3 of the configurable-framework technical specification, 5 October 2026.
