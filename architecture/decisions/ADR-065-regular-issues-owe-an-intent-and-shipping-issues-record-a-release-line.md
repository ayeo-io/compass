---
id: ADR-065
title: Regular issues owe a lightweight intent, and every shipping issue records a release line its landing needs
status: proposed
date: 2026-10-14
supersedes: ''
superseded_by: ''
---

Proposed by the architect for intent-and-release-line on 2026-10-14. compass:architect accepts or revises it for jed72 at verify.

## Context

PRD 35 asks for two records a software team expects from each change (DS-8, DS-9). Only 1 of 40 regular issues has an intent, so a regular spec has nothing written to be checked against. No issue records a sentence for release notes, though `release_note:` is already read by the verification note and the project index.

Four earlier decisions bound the answer:

- ADR-036: an issue runs against its stored generation, and a CLI upgrade never changes an open issue.
- ADR-063: a landing refusal judges only an issue that its first assessment marked.
- ADR-034: issue records are not committed, and a squash merge leaves `land_commit` off main.
- ADR-051: rendered blocks are derived in place from the records.

Most archived manifests hold no `generation` key and read the live configuration.

## Decision

1. **Intent on regular.** The shipped regular approach registers `intent` at depth `lightweight`: Problem, Desired outcome, Success signals and Non-goals. The router drafts it at assess. The spec author corrects it at define. `compass analyze` checks scenario intent ids against it, advisory unless the issue holds `verify.analyze`. `artifacts-approved` refuses a landing while it is unwritten. Full keeps the thorough intent; quick fix, hotfix and spike register none.
2. **One release line per shipping issue, in the manifest only.** `release_note:` is an optional string. `compass acceptance record`, `compass ship-commit` and `compass quick-fix finish` write it with `--release-note`, and only when given. The latest write wins. Each write is a locked re-read and write of the one key. A text that is blank, starts with `#`, or fails the living spec's title rules is refused before anything is written. The verification report, the verification note and the living spec show it through rendered output; no document holds a second copy.
3. **The refusal is scoped by the stored generation.** A new approach field, `release_line: true`, marks the approaches that owe a line: quick-fix, regular, hotfix and full in the shipped default. Every landing judges the issue it lands, and refuses when the issue owes a line and neither the manifest nor the flag gives one. An issue owes a line only when all of these hold: it is named, it is not completed and not closed, it has a `generation` key, and its stored configuration declares `release_line: true` for its approach. An issue at an earlier generation owes nothing until a reassess commits a generation that declares it. Setting the field to false on a shipping approach is a loosening and needs a waiver (ADR-039).
4. **Release notes are a derived view.** `compass release notes --since <ref>` lists each completed shipping issue placed after the ref, with its release line, ordered by landing time and slug. An issue is placed after the ref when its `land_commit` is reachable from HEAD and not from the ref, or when the living spec committed at HEAD names it and the spec at the ref does not. An issue the ref reaches, or the ref's spec names, is left out. An issue that cannot be placed is counted, not listed. The verb writes nothing and redacts rival names through the names key as the derivation does.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| Refuse every open issue on a shipping approach | Simplest rule | Changes open issues on a CLI upgrade, against ADR-036, and refuses a completed issue landed again at HEAD |
| Decide by the CLI version in `versions.yml` | No new field | Couples a rule to version numbers; a reassess that changes nothing commits no generation, so some open issues would never gain the rule |
| A check in `compass check` | One place for rules | Judges the archive, most of which reads the live configuration |
| Keep the line in the verification report | DS-9 names the report | Two copies drift; the quick-fix note already renders the manifest value |
| Place issues by `land_commit` reachability alone | One git call per issue | Drops every squash-merged issue, as ADR-034 found |

## Consequences

**Positive:**
- Every issue that lands under a new generation leaves one release line, and a release's notes are one command.
- No archived or in-flight issue is refused or judged by the new rules until it is reassessed.

**Negative:**
- The configuration gains a field, with its schema, vocabulary and classification.
- Hotfixes need one sentence before they land.

**Neutral / follow-on:**
- Changing the regular default is a 7.0.0 change under `governance/decisions/2026-10-06-default-6-x-never-changes-a-6-0-value.md`.
- `compass release notes` is a named exception to ADR-044's verb list.

## References

- ADR-006, ADR-034, ADR-036, ADR-037, ADR-039, ADR-044, ADR-049, ADR-051, ADR-053, ADR-063, ADR-064.
- `docs/generation-store.md`, `docs/rendered-blocks.md` and the owning doc of `ship-commit` own the facts.
