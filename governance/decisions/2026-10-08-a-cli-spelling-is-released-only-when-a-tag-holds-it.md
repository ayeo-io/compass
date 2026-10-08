# a-cli-spelling-is-released-only-when-a-tag-holds-it

## Decided by

jed72

## Date

2026-10-08

## Supersedes

Nothing.

## Decision

A CLI spelling counts as released only when a release tag holds it. A renamed spelling that a release tag holds keeps an alias until 7.0.0. A renamed spelling that no tag holds gets no alias, and its unknown-command message names the new spelling.

## Why

An alias exists for an adopter who may call the old spelling in a script. An adopter can only hold a spelling that a release shipped, and an installed copy of the plugin can differ from its tag. The tag is the one record that stays fixed.

## Evidence

The maintainer's rule that aliases are owed only for spellings a release holds, applied on 8 October 2026 to the issue `vocabulary-and-cli-renames`, and recorded in `architecture/decisions/ADR-044-vocabulary-and-cli-naming.md`.
