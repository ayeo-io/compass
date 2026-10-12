# this-repository-names-its-owner

## Decided by

jed72

## Date

2026-10-12

## Supersedes

Nothing. It amends `2026-10-06-this-repository-may-hold-a-settings-only-compass-yml`: where that entry says the file holds settings keys only, it now holds settings keys and `owner`. The rest of that entry stands. Merged ledger entries are not edited, so this entry is where the amendment is recorded. ADR-042 carries the same amendment to its self-application rule.

## Decision

This repository's `compass.yml` may name its owner, `owner: jed72`, as well as settings keys. It still declares no check, gate, rule, route, waiver, unlock, capability or approvers list, and a test enforces this.

## Why

Without an owner, nobody may confirm the decisions agents take for the maintainer or approve an issue's waiver, so `compass evidence approve --decisions` refused in this repository. The owner only names who approves; it changes no check, gate or rule, so this repository's issues still run the shipped default and its delivery record stays evidence for that default.

## Evidence

The maintainer's answer "yes" in the Claude Code chat on 2026-10-12, after `compass evidence approve --decisions` for issue artifact-catalogue-fields refused because the project declared no owner.
