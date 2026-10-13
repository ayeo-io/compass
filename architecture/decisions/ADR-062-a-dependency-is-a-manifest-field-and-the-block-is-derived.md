---
id: ADR-062
title: A dependency between issues is a manifest field, and the block it causes is derived
status: accepted
date: 2026-10-13
supersedes: ''
superseded_by: ''
---

Accepted by jed72 on 2026-10-13.

## Context

An issue that waits for another issue says so only in prose. One issue's intent, technical design and distribution map each said another issue had to land first, and its product-owner review then found that the other issue did not exist. `compass next`, `compass check` and the board could see none of it, because no field held the wait.

The manifest already links issues in one direction: `repairs`, `follow_ups[].target_task` and `landed_by`. None of them says "this issue cannot be implemented until that one reaches a point". The related block of the issue page (ADR-051) already reads a `depends_on` key as a link, but nothing writes it and nothing gives it a meaning.

Four existing decisions bound the answer:

- ADR-045: an issue's state is derived from its records and never written. The stored `blocked` flag counts only while the issue is in progress or in review.
- ADR-006: a manifest without a new key must read exactly as before.
- ADR-052: a manifest read from the parse cache may feed an advisory part, never a blocking verdict.
- ADR-048: a reader of one checkout judges by that checkout's records, and only `--worktrees` on the board reads other trees.

ADR-003 adds a fifth. It says flow and every cross-issue signal advise and never gate, and its follow-on note says a future dependency graph should be advisory too. A wait that stops implementation is a gate. This record says where the gate lives and why it does not reopen ADR-003.

## Decision

1. **The shape.** An issue records what it waits for in an optional manifest key:

   ```yaml
   depends_on:
     - issue: <slug>        # one path segment, not the issue's own slug
       reason: <text>       # required, not empty
       until: <value>       # one of the nine values below; written on every entry, done when not given
   ```

   An entry has exactly these three keys. `schemas/manifest.schema.json` declares the key with `additionalProperties: false` on an entry, `schemas/manifest.reference.yml` shows one entry, and `docs/issue-dependencies.md` is the owning doc. A test compares the three key names across the three files. `schema_version` stays `3.0`, and no migrate runs. Later readers, such as the technical design's dependencies section, read this shape and no other.

2. **What `until` means.** One function in `lifecycle.py` compares, using `stable_ids.STAGE_IDS` for the order and `lifecycle.state_of` for the state:

   | Value | Met when the depended-on issue, read by the caller's reader, ... |
   |---|---|
   | `done` | is `done` with close reason `completed` |
   | `in-review` | is `in-review`, or `done` with close reason `completed` |
   | `define`, `refine`, `plan`, `breakdown`, `implement`, `verify`, `ship` | is at that stage or a later one, as `compass next` names it, or `done` with close reason `completed` |

   An issue closed as `not-planned` or `duplicate` meets no value. An issue on hold is judged by the same rules: its stage comes from its records and its state is `backlog`.

3. **The block is derived, never written.** The same module holds the one derivation every reader calls. An unmet dependency blocks only while the waiting issue is at the implement stage, as `compass next` names it, and is neither on hold nor done. Earlier stages are not blocked, so a spec and a design can be written while the wait is open. No command stores the dependency block. It is a second source of an issue's blocked reason, beside the stored flag, which keeps its ADR-045 rule. A reader that shows both puts the stored reason first.

4. **A fault never blocks.** A dependency that cannot be judged does not count as unmet. The faults are: no manifest in this checkout, a manifest that cannot be parsed, an unknown `until`, an entry that is not the documented shape, and a dependency that names the waiting issue back (a two-issue cycle). Every reader leaves a fault out of the block. `compass issue lint` reports each fault and fails, so the fault is found by the command that can say why. A reader that cannot run at all, such as a broken install, still refuses in the hook, as every hook reader does.

5. **The blocking read is uncached and reads this checkout only.** The pre-tool hook and `compass next` read each dependency's manifest from this checkout's `.compass/work/<slug>/` with `core.load_manifest`, never through the parse cache. This extends ADR-052 decision 2 to a read of another issue that decides a refusal. The hook runs no git command and lists no other worktree, so this checkout's record decides (ADR-048). It reads another manifest only when the issue's own `depends_on` is non-empty, opens each dependency's manifest once, does not follow a dependency's own dependencies, and starts at most one more python3 process than an edit with no dependencies.

6. **The refusal names its way out.** The hook's refusal names the dependency, its `until`, its state as this checkout reads it and two ways out: bring the dependency's issue folder into this checkout, or run `compass issue depends remove <slug>`. No override flag is added. A dependency finished only in another worktree keeps refusing here until one of the two is done.

7. **Advisory readers may read the cache.** The board, `compass flow --json` and the issue page only advise, so they judge dependencies from the manifests they already read, which may come from the parse cache. The issue page shows the wait in the `related` block and on a header line that opens `Blocked: waits for`. That header line is a cross-issue part, so ADR-052 decision 3's list of parts a cached read may feed gains it. With `--worktrees`, the board judges a dependency by the copy of that issue it shows.

8. **Where this stands against ADR-003.** Flow, the board and every view of a dependency stay advisory and write nothing. The gate is the waiting issue's own: the person recorded the wait in that issue's manifest, and the per-issue hook enforces that issue's own record, as it enforces its own red. The hook does not walk the dependency graph and acts on no other issue. ADR-003's follow-on note, that a dependency graph should be advisory, now has one exception: an issue's own declared wait, at implement. Every other use of the graph stays advisory.

9. **Writing a dependency.** `compass issue depends add <slug> --reason <text> [--until <value>]` and `compass issue depends remove <slug>` are the only writers. `add` refuses a cycle with exit 2. It finds one by following `depends_on` through the readable manifests of this checkout, with a visited set. It writes an entry for a slug that has no manifest yet, prints the lint finding and exits 0, because the issue may live in another worktree or be about to be assessed.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| Write the stored `blocked` flag when `depends add` runs | One flag, one reader | A stored copy of a derived fact goes out of date when the other issue moves, and needs a writer at every place that issue's records change (ADR-045) |
| Keep dependencies advisory, as ADR-003's follow-on note says | No new gate | The waiting issue cannot be stopped at the one point the wait matters, so the wait returns to prose |
| Block at every stage | Simpler rule | A spec and a design can be written while the other issue is open; blocking them delays the work the wait does not touch |
| Refuse when a dependency cannot be read | A stricter wait | A missing or renamed manifest would stop every edit on every dependent issue, and a false block teaches people to bypass the hook |
| Read dependencies through the parse cache in the hook | Faster | A planted entry could clear or impose a refusal (ADR-052) |
| Read other worktrees in the hook | Sees a dependency finished elsewhere | A git call and a worktree listing on every edit, and a stale copy in another tree could clear a wait |
| Walk the whole graph in the hook | Catches a long hand-written cycle | Opens issues the edit did not name and breaks the cost bound; lint reports such a cycle instead |
| A separate record for the uncached, this-checkout-only read | One decision per record | The read rule exists only for this block and is short, so it is decisions 4 to 6 here |

## Consequences

**Positive:**
- A wait between issues is one field that `compass next`, the hook, lint, the board, `compass flow --json`, the issue page and `ship-commit` read through one function, so they cannot disagree.
- A manifest without the key reads and behaves as before, and the hook opens no other manifest for it.
- A missing or broken dependency never stops work; lint names it.

**Negative:**
- A dependency finished only in another worktree keeps the hook refusing in this checkout until the folder is brought in or the dependency is removed.
- A hand-written cycle of three or more issues, each at implement, refuses all of them until someone removes one dependency. `depends add` cannot create one, and lint reports it.
- An edit on an issue with dependencies costs one more python3 process and one manifest read per dependency.

**Neutral / follow-on:**
- `compass flow --json` rows gain a `depends_on` key, which ADR-046 allows within a major version.
- The issue page header can hold two `Blocked:` lines: the stored flag, then the dependency line.

## References

- ADR-003: flow advises and never gates. Decision 8 above states the one exception.
- ADR-006: backward compatibility.
- ADR-045: the lifecycle is derived from records; the stored blocked flag.
- ADR-046: the board data set; `--json` is additive.
- ADR-048: reading issue state across worktrees.
- ADR-051 and ADR-052: rendered blocks, and the parse cache's trust boundary.
- `docs/issue-dependencies.md` owns the facts of the dependency verbs and the derivation.
