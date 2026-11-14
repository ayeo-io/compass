# Issue dependencies

An issue can record the issues it waits for. While it is at build (the
implement stage of an older issue) and a dependency has not reached the
agreed point, the pre-tool hook refuses production-code edits. Nothing
stores the block: each reader derives it from the records
([ADR-062](../architecture/decisions/ADR-062-a-dependency-is-a-manifest-field-and-the-block-is-derived.md)).

## The shape

An issue's manifest holds an optional list:

`depends_on: [{issue, reason, until}]`

| Key | Rule |
|---|---|
| `issue` | The slug of the issue waited for: one path segment, not the issue's own slug. Required, not empty. |
| `reason` | Why the issue waits. Required, not empty. |
| `until` | One of the eleven values below. `compass issue depends add` writes `done` when `--until` is not given. A hand-written entry without it reads as `done`. |

- An entry holds these three keys and no other.
- An issue has one entry for each dependency. Adding a listed slug replaces
  that entry's reason and `until` and keeps its place.
- `schema_version` stays `3.0`. A manifest without the key is unchanged.
- `schemas/manifest.schema.json` and `schemas/manifest.reference.yml` state
  the same shape. A test fails until the schema, the reference manifest and
  this page agree.

## The `until` values

The other issue is read in this checkout.

| Value | Met when the depended-on issue ... |
|---|---|
| `done` | is `done` with close reason `completed`. |
| `in-review` | is `in-review`, or `done` with close reason `completed`. |
| `specify`, `build`, `ship` | is at that path stage or a later one, or is `done` with close reason `completed`. |
| `define`, `refine`, `plan`, `breakdown`, `implement`, `verify` | is at that stage or a later one in the legacy order, or is `done` with close reason `completed`. |

The stage of an issue is the stage `compass next` gives it.

- A legacy `until` and a legacy stage are compared in the legacy order.
- When either one is a path stage, both are compared as path stages:
  `define`, `refine` and `plan` map to `specify`; `breakdown` and
  `implement` to `build`; `verify` and `ship` to `ship`.
- A dependency closed as `not-planned` or `duplicate` meets no value. The
  lint finding names `compass issue depends remove`.
- A dependency on hold (state `backlog`) is judged by the same rules.
- `assess`, `backlog`, `ready` and `in-progress` are not values.

## When the block counts

The block counts only while the waiting issue is at build (the implement
stage), is not on hold and is not done. An issue at an earlier stage is not
blocked. The stored `blocked` flag keeps its own rule (ADR-045). Where both
apply, the board shows the stored reason first.

## What the hook reads

On a production-code edit at build, the pre-tool hook judges the
dependencies only when `depends_on` is present and not empty.

- It reads this checkout's `.compass/work/<slug>/` for each dependency,
  once, uncached. It never reads through the parse cache (ADR-052).
- It runs no git command and lists no other worktree (ADR-048).
- It refuses only on a positive read of an unmet dependency, with the code
  `waits-for-issue`.
- It never refuses a spike. A declared acceptance does not clear a wait.

Cost:

- With no `depends_on`, the hook opens no other manifest and starts no more
  python3 processes.
- With dependencies, it starts at most one more python3 process and opens
  each dependency's manifest once.
- The median hook time with 5 dependencies is at most twice the median
  with 0.

### Fail-safe cases

A fault never stops work. Each case below allows the edit with one warning
line on standard error. `compass issue lint` reports the same fault and
exits non-zero.

- A dependency with no manifest in this checkout.
- A manifest that does not parse.
- An `until` that is not one of the eleven values.
- An entry that is not the shape above, or a `depends_on` that is not a
  list.
- A direct cycle between two issues. No reader counts it as an unmet wait.

Two cases still block:

- A reader that cannot run at all (no python3, a broken install) refuses.
- A longer cycle blocks each member at build. Lint reports a cycle that
  passes through the linted issue.

### The worktree rule

A dependency finished only in another worktree still blocks here. The
refusal names the state this checkout reads. There is no override flag. To
clear the block:

- bring that issue's folder (`.compass/work/<slug>/`) into this checkout; or
- run `compass issue depends remove <slug>`.

## The verbs

| Verb | What it does | Refuses with exit 2, writing nothing |
|---|---|---|
| `compass issue depends add <slug> --reason "..." [--until <value>]` | Writes the entry. Exit 0, with a lint finding on standard error for a slug with no manifest in this checkout. | a cycle; the issue's own slug; a slug that is not one path segment; an unknown `until`; an empty reason |
| `compass issue depends remove <slug>` | Removes the entry, and the key with the last entry. The other issue needs no manifest here. | a slug that is not a dependency of the issue |

Both render again the waiting issue's page and the pages of the issues its
manifest links to (`RENDER_TRIGGERS`). `remove` also renders the removed
dependency's page again.

## What each reader shows

| Reader | Shows |
|---|---|
| `compass next` | At build, ` \| blocked: waits for b to reach done` after the usual parts. It never shows a fault; lint does. |
| `compass flow` | `BLOCKED: <reason>` on an in-progress or in-review row, with the wait while the issue is at build. |
| `compass flow --json` | Every row holds `depends_on`: a list of objects with the keys `issue`, `reason`, `until`, `state`, `stage` and `met`, at every stage. A dependency that was not read has `state` and `stage` null and `met` false. |
| `ship-commit` | After a landing, "these issues were waiting for b:" and a line for each open issue that names it. |

## Code

The dependency functions are in `cli/compass_pkg/lifecycle.py`. Every reader
calls them, so `compass next`, the board and `ship-commit` show the same
words.

- `lifecycle.reached` compares an `until` value with a state and stage.
- `lifecycle.judge` judges each well-formed entry; `lifecycle.entries` lists
  them, with a text for each shape fault.
- `lifecycle.dependency_block` and `lifecycle.blocked_text` build the
  derived reason and join it with the stored one.
- `lifecycle.hook_lines` is what the hook's dependency reader prints.

The verbs, the cycle walk and the lint lines are in
`cli/compass_pkg/issue_depends.py`. The board (`flow.board`) reads copies it
already parsed, so a planted parse-cache entry can mislead the board, never
the hook or `compass next`.
