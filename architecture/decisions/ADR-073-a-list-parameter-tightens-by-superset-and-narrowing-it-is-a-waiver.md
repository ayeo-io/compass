---
id: ADR-073
title: A list parameter tightens by superset; narrowing it is a waiver
status: accepted
date: 2026-10-19
supersedes: ''
superseded_by: ''
---

Accepted by the architect for list-parameter-superset-tightens on 2026-10-19.

## Context

A trigger path makes a check run on a change. A project that adds an entry to a trigger list makes the check run on more changes. A project that removes an entry makes it run on fewer.

The classifier gave every edit to a trigger list the verdict `incomparable`, because the check registry declared `tighter: none` for `trigger_paths` and `trigger_contents` of `contracts-declared`. A project that wanted a stricter check paid the cost of a waiver, the same as a project that wanted a looser one.

Three earlier decisions bound the answer:

- ADR-037: a configuration change is classified by its effect, and the check registry owns the direction of a check parameter. Its table row for a parameter gives `none` where no direction is declared.
- ADR-064: the document set gains the section checks. It states that a project sets the whole trigger list with a waiver.
- ADR-039: a loosening needs a signed waiver. The waiver process does not change.

## Decision

The rule covers `trigger_paths` and `trigger_contents` of `contracts-declared` only. It amends ADR-037 and ADR-064 for those two keys and supersedes neither.

1. **A new direction `superset`.** A list parameter can declare it in the check registry. The classifier compares each side as a set of exact entries.
2. **The verdicts.** A project list that holds every shipped entry and at least one more is `tighter`. A list that lacks a shipped entry and adds none is `looser`. A list that lacks a shipped entry and adds another is `incomparable`. Reordering a list and repeating an entry leave the set unchanged, so the change is `equal`.
3. **Entries are compared whole.** A `trigger_contents` entry is the pair of path glob and text. The classifier does not judge how broad a glob is, so replacing `schemas/*` with `schemas/**` is a replaced entry and needs a waiver.
4. **A list that cannot be read is incomparable.** A missing list, a value that is not a list and a malformed entry give `incomparable` and raise no error. Only an unknown direction string raises.
5. **The registry refuses `superset` on a parameter that is not a list.** No other key declares it. `command-passes.args` stays `none`.
6. **The classifier version is 11.** An added path was `incomparable` and is now `tighter`, so a stored verdict from version 10 must not be served.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| Narrowing a list is free | The issue text asked for it | Narrowing is a loosening, because a trigger path makes a check run, so fewer entries check fewer changes |
| Test the key name in the classifier | One branch, no registry change | It hides the rule from the registry that ADR-037 names as the owner of a check parameter's direction |
| Judge whether one glob covers another | A wider glob is stricter | It is unsound in general and out of scope |
| Treat a missing list as empty | Simple | The classifier fills in no default |
| Raise on a malformed list | Loud failure | A typo in a layer file would stop the whole classification |

## Consequences

**Positive:**
- A project that adds a trigger path needs no waiver.
- A loosening still needs one.

**Negative:**
- A project that replaces a glob with a wider one files a waiver.
- Stored classifications are computed again once.

**Neutral / follow-on:**
- A future list parameter takes the rule by declaring `superset`.

## References

- ADR-037, ADR-039, ADR-064.
- `governance/guardrails.md` and `governance/routing-policy.md` state the rule.
