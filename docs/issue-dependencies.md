# Issue dependencies

An issue can record the issues it waits for. While it is at the implement stage and a dependency has not reached the agreed point, the pre-tool hook refuses production-code edits, and `compass next`, the board and the issue page say what it waits for. This document owns the `depends_on` shape, the rule that derives the block, the verbs and what each reader shows. The decision behind it is [ADR-062](../architecture/decisions/ADR-062-a-dependency-is-a-manifest-field-and-the-block-is-derived.md).

Nothing stores the block. Every reader derives it from the records each time it reads.

## The shape

An issue's manifest holds an optional list:

`depends_on: [{issue, reason, until}]`

- Each entry has exactly the three keys `issue`, `reason` and `until`, and no other.
- `issue` is the slug of the issue waited for: one path segment, not the issue's own slug. It is required and not empty.
- `reason` says why the issue waits. It is required and not empty.
- `until` is required in the stored entry. `compass issue depends add` writes it on every entry and writes `done` when `--until` is not given. A hand-written entry without it reads as `done`.
- An issue has one entry for each dependency. Adding a slug that is already listed replaces that entry's reason and `until` and keeps its place.
- `schema_version` stays `3.0`. A manifest without the key reads, renders and behaves as it did.

`schemas/manifest.schema.json` (with `additionalProperties: false` on an entry) and `schemas/manifest.reference.yml` state the same shape. A test compares the key names in the schema, the reference manifest and this document, so a change of shape fails until all three agree.

The technical design's Risks and dependencies section, which a later change renders, reads this shape and no other. A renderer calls `lifecycle.entries` and `lifecycle.judge` rather than reading the key itself, so it shows the same words as the board.

## The `until` values

`until` takes exactly one of nine lower-case words. The other issue is read in this checkout.

| Value | Met when the depended-on issue ... |
|---|---|
| `done` | is `done` with close reason `completed`. |
| `in-review` | is `in-review`, or `done` with close reason `completed`. |
| `define`, `refine`, `plan`, `breakdown`, `implement`, `verify`, `ship` | is at that stage or a later one in that order, or is `done` with close reason `completed`. "At a stage" means the stage `compass next` names for it. |

- A dependency closed as `not-planned` or `duplicate` meets none of the nine values. The lint finding says so and names `compass issue depends remove`.
- A dependency on hold (state `backlog`) is judged by the same rules: its stage comes from its records.
- `assess`, `backlog`, `ready` and `in-progress` are not values.

## When the block counts

The block counts only while the waiting issue is at the implement stage, as `compass next` names it, and is not on hold and not done. An issue at an earlier stage is not blocked, but the board card still says what it waits for. The stored `blocked` flag keeps its own rule (in-progress or in-review only, ADR-045) and is not changed. Where both apply, the board and the issue page show the stored reason first.

## What the hook reads

On a production-code edit at implement, the pre-tool hook judges the issue's dependencies only when its own `depends_on` is present and not an empty list.

- It reads this checkout's `.compass/work/<slug>/` for each dependency, once, uncached, with `load_manifest`. It never reads through the parse cache (ADR-052).
- It runs no git command and lists no other worktree. This checkout's record decides (ADR-048).
- A spike is never refused, and a declared acceptance does not clear a wait.
- It refuses only on a positive read of an unmet dependency, with the code `waits-for-issue`.

### Cost budget

- With no `depends_on`, or an empty list, the hook opens no other issue's manifest and starts no more python3 processes than before.
- With any dependencies it starts at most one extra python3 process and opens each dependency's manifest once.
- The median hook time with 5 dependencies is at most twice the median with 0.

### Fail-safe cases

A fault never stops work. Each case below allows the edit with one warning line on standard error, and `compass issue lint` reports the same fault and exits non-zero:

- a dependency with no manifest in this checkout;
- a manifest that does not parse;
- an `until` that is not one of the nine values;
- an entry that is not the shape above, or a `depends_on` that is not a list;
- a direct cycle between two issues, which no reader counts as an unmet wait.

A reader that cannot run at all (no python3, a broken install) still refuses, as every reader in the hook does. A longer cycle blocks each member at implement; lint reports a cycle that passes through the linted issue.

### The worktree rule

A dependency finished only in another worktree still blocks here, because this checkout decides. The refusal names the state this checkout reads and gives two ways out:

- bring that issue's folder (`.compass/work/<slug>/`) into this checkout;
- run `compass issue depends remove <slug>`.

There is no override flag. `compass board render --worktrees` can show the newer copy, because the board only advises.

## The verbs

| Verb | What it does | Refuses with exit 2, writing nothing |
|---|---|---|
| `compass issue depends add <slug> --reason "..." [--until <value>]` | Writes the entry. Exit 0, and a lint finding on standard error for a slug with no manifest in this checkout. | a cycle; the issue's own slug; a slug that is not one path segment; an unknown `until`; an empty reason |
| `compass issue depends remove <slug>` | Removes the entry, and the key with the last entry. The other issue needs no manifest here. | a slug that is not a dependency of the issue |

Both re-render the waiting issue's page and the pages of the issues its manifest links to (`RENDER_TRIGGERS`). `remove` also re-renders the removed dependency's page, when it has a manifest in this checkout, so that page no longer lists the waiting issue.

## What each reader shows

| Reader | Shows |
|---|---|
| `compass next` | At implement, ` \| blocked: waits for b to reach done` after the usual parts. Only the dependency block, never a fault; lint is where faults show. |
| The board card | The line "waits for b" for an open issue with an unmet dependency whose issue was read, and the blocked flag with the wait while the issue is at implement. |
| The board panel | A Dependencies part: for each entry the slug, the reason, `until <value>`, the state, and one word - `met`, `waiting`, `not found` or `unreadable`. |
| `compass flow --json` | Every row holds `depends_on`: a list of objects with the keys `issue`, `reason`, `until`, `state`, `stage` and `met`. The list is empty for an issue with none. A dependency that was not read has `state` and `stage` null and `met` false. |
| The issue page | The header adds `Blocked: waits for ...` on its own line while the block counts. A `depends on` line in the `related` block ends with ` - met` or the wait. |
| `ship-commit` | After a landing, "these issues were waiting for b:" and a line for each open issue that names it. |

## Code

The dependency functions are in `cli/compass_pkg/lifecycle.py`:

- `lifecycle.reached` is the one comparison of an `until` value with a state and stage;
- `lifecycle.judge` judges every well-formed entry of an issue and returns `Dependency` records;
- `lifecycle.entries` returns the well-formed entries and a text for each shape fault;
- `lifecycle.dependency_block` and `lifecycle.blocked_text` build the derived reason and join it with the stored one;
- `lifecycle.checkout_reader` and `lifecycle.mapping_reader` are the readers: this checkout uncached, or manifests a caller already parsed;
- `lifecycle.hook_lines` is what the hook's dependency reader prints.

The verbs, the cycle walk, the lint lines and the `ship-commit` lines are in `cli/compass_pkg/issue_depends.py`. The board page and the issue page are `board_page.py` and `issue_page.py`; the board rows come from `flow.board`. The board and the page read the copies they already parsed, so a planted parse-cache entry can mislead them but never the hook or `compass next`.
