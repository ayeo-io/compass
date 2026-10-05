# guardrails-merge-routing-policy-replaces

## Decided by

jed72

## Date

2026-10-05

## Supersedes

Nothing.

## Decision

A project's `governance/guardrails.yml` will add its `project:` entries to the shipped defaults instead of replacing the whole folder, so adding one guardrail no longer means copying every governance file. `routing-policy.yml` is still replaced whole. An architecture decision record comes first, then the feature; defaults stay as they are, so existing projects are not affected. Answers issue #105.

## Why

Chosen from the recommendation of 5 October. Merging routing rules would need precedence rules nobody has asked for; merging guardrails removes the cost the field report described.

## Evidence

Issue #105, reproduced on 3.1.1. The silent-ignore half was fixed in f9372f3.
