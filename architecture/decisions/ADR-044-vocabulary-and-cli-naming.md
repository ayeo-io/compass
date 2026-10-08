---
id: ADR-044
title: Vocabulary and CLI naming, amending ADR-012 and ADR-024
status: accepted
date: 2026-10-08
supersedes: ''
superseded_by: ''
---

## Context

The maintainer agreed the nine naming decisions below on 2026-10-08. They must land before 6.0.0, because that release makes ids and `--json` shapes a public contract, and a rename afterwards costs a major version.

This record amends ADR-012 and ADR-024 without changing them:

- ADR-012 freezes the vocabulary and asks for a decision record for any change of meaning, new ban or un-banning. This record is that record for the words below.
- ADR-024 says what Compass owes an unobserved adopter: a migration path, and no redirects. This record adds one narrow case, an alias for a renamed CLI verb that a release tag holds. It adds no redirect for any other name.

Today several words mean more than one thing, and the CLI verbs follow no single convention:

- `full` names a delivery approach, the top stage mode and the top artifact depth. `light` sits on the same depth ladder.
- `full-plus-backfill` uses "backfill", which the vocabulary retired for "follow-up".
- The size `standard` is also a retired delivery-approach name.
- The vocabulary defines one lifecycle (`backlog`, `ready`, `in-progress`, `in-review`, `done`) and the CLI enforces another (`queued`, `active`, `parked`, `landed`, `abandoned`).
- The `issue-type` entry lists three delivery approaches as types and describes a field that does not exist.
- "Route" is used as a verb and as a noun, and `epic` is recorded as dropped.
- `compass run --stage build` and `issue friction --phase` use retired stage words.
- Verbs mix shapes: an adjective as a verb, nouns as verbs, and verb-noun pairs inside a group.

Adopters of v5.6.0 hold manifests, copies of `governance/routing-policy.yml` and `.compass/config.yml`, and scripts that call released verbs, all in the old words. The layered configuration (`compass.yml`, git parents pinned by sha, policy-test fixtures and stored generations) is in no release. Only the maintainer's own repositories hold those in old words.

## Decision

**The nine decisions.**

1. Depth words: `full` becomes `thorough`, `light` becomes `lightweight` and `full-plus-backfill` becomes `thorough-with-follow-up`, as stage modes and artifact depths only. `full` stays the name of a delivery approach. `collapsed`, `skipped` and the special modes keep their names.
2. The size `standard` becomes `medium`, as a size only. In `delivery_approach` it stays a retired approach name that maps to `regular`.
3. The `issue-type` entry lists `feature`, `bug` and `task`. `quick-fix`, `hotfix` and `spike` are defined only as delivery approaches. The ban on "task" narrows to "task" meaning an issue.
4. The workflow states are `backlog`, `ready`, `in-progress`, `in-review` and `done`. The close reasons are `completed`, `not-planned` and `duplicate`. `blocked` is a flag, not a state. They replace `queued`, `active`, `parked`, `landed` and `abandoned`. How the states are stored is in ADR-045.
5. "Route" is a verb only in prose. No new machine name uses it.
6. `epic` is restored, with `initiative` and `milestone`, as work levels. This record adds the entries and changes no behaviour.
7. The CLI follows `compass <noun> <verb>`.
8. Each renamed verb that a release tag holds keeps an alias until 7.0.0.
9. `compass run --stage build` becomes `implement`, and `issue friction --phase` becomes `--stage`.

**The CLI convention.** A leaf verb is one of `show`, `list`, `add`, `remove`, `set`, `render`, `lint`, `test`, `diff`, `update`, `migrate`, `sync` or `init`. The allowed top-level verbs are `init`, `check`, `ci`, `run`, `next`, `retro`, `flow` and `analyze`. Every other verb the parser registers is a named exception in the CLI rename test, with a reason for each. The maintainer's list of exceptions names `approve`, `review`, `next`, `replan`, `package`, `artifact-path`, `raised-by`, `receipt`, `tdd-red`, `tdd-green`, `ship-commit` and `rework-scan`. The table also holds the other registered verbs that this change does not rename, so that a new verb outside both lists fails the test.

## Aliases

An alias is kept only for a renamed CLI verb, and only when a release tag holds the old spelling. A spelling counts as released only when `git show <tag>:cli/compass` and the registering modules at that tag hold it. The alias ends at 7.0.0.

- The alias table is `cli/aliases.yml`, a data file beside the CLI entry point. Its `aliases:` rows list each alias with the first release tag that holds the old spelling. Its `hints:` rows list the old spellings no release holds. A test fails when a row has no tag, or when the tag does not hold the old spelling.
- A second test fails when the package version is 7.0.0 or later and the table is not empty.
- A renamed spelling that no release tag holds gets no alias. It is an unknown command whose error message names the new spelling.
- An alias prints one notice on standard error naming the new spelling. Standard output and the exit code are those of the new command.

Vocabulary values are not redirected. An old value in a file is read through the rename tables (below), and a writer emits only the new word. The mapping of layers, policy-test fixtures and stored generations serves state that no release holds. It does not contradict ADR-024, because it is not a redirect for a released name.

## The value tables

- **One table per field.** Each old word is mapped only in the fields the table lists, in `cli/migrate-map.yml`. `standard` is a size only, `full` is a depth only, and a check parameter that happens to be called `size` is not a size field.
- **Two entry points.** Manifests are mapped as they load. Configuration layers are mapped before they are checked and again before they merge, so a layer written in old words classifies and merges as it did.
- **Raw digests.** A layer's digest is taken from the file as written, before mapping, so the rename alone reports no change. Stored generation files are read through the mapping and never rewritten (ADR-036).
- **Rewrite on save, with a backup.** A manifest is rewritten in new words only when a command saves it. The first rewrite that changes a mapped value copies the original to `manifest.yml.v5.bak`, only if that file does not exist. Issue state is untracked in this repository, so git cannot restore it.
- **The list of retired values** in `governance/terminology.yml` holds the same triples (field, old word, new word) as the mapping table. A test keeps the two equal.
- **Removal.** The tables end at 7.0.0, when an old word is rejected by the same check as any unknown value.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| Keep the old words and document the clashes | No migration cost. | After 6.0.0 the clashes become public contract, and a rename then needs a major version. |
| Replace each old word everywhere as text | Smallest change. | The same word has two meanings (`standard`, `full`, `active`), so a text replace changes meanings and fails silently. |
| Alias every renamed spelling, released or not | One simple rule. | It would add machinery for spellings no adopter holds, which ADR-024 rejects. |
| Redirect old values at read time without a table | Less data. | Nothing would force the redirect to end at 7.0.0. |
| Hidden argparse aliases for verbs | Native to the parser. | `issue artifact` cannot be both a leaf and a group, help would list hidden parsers, and there is no one table to test for removal. |
| One record for naming and the lifecycle | Fewer records. | The lifecycle changes what `status` means for every reader and needs its own record (ADR-045). |

## Consequences

**Positive:**
- Each word and verb has one meaning and one shape before 6.0.0 freezes them.
- A script that calls a released verb keeps working until 7.0.0 and says what to change.
- The alias table and the value tables each end by a failing test, not by memory.

**Negative:**
- A script that reads `compass flow --json` changes once, at 6.0.0.
- A file written by 6.0.0 in new words is not read by v5.6.0.
- Later branches that compare a status with an old word fail the source guard after they merge this change.

**Neutral / follow-on:**
- ADR-008, ADR-026 and ADR-034 say `landed` for the issues that feed the living spec. They now read as `done` with close reason `completed`.
- ADR-036 and ADR-038 say `migrate-config`. They now read as `issue migrate --config`.
- ADR-012 and ADR-024 stay as written.
- The issue `type` field, the work-level field and `policy explain` are later work and are not decided here.

## References

- ADR-006: backward compatibility is non-negotiable.
- ADR-012: the v2 vocabulary is frozen. Amended by this record.
- ADR-014: retired names go at the next major version.
- ADR-017: an identifier is a key, not jargon. The machine names `landed_by`, `land_commit`, `land_timestamp` and `landed-by-resolves` keep their names.
- ADR-020: the archive is migrated on read.
- ADR-024: what Compass owes an unobserved adopter. Amended by this record.
- ADR-036: an issue runs against a stored generation.
- ADR-040: stable ids live in one module.
- ADR-041: the configuration vocabulary.
- ADR-045: the issue lifecycle is derived from records.
- `governance/decisions/2026-10-08-a-cli-spelling-is-released-only-when-a-tag-holds-it.md`
