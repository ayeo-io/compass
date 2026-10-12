---
id: ADR-052
title: The parse cache serves the render as well as flow
status: accepted
date: 2026-10-10
supersedes: ''
superseded_by: ''
---

## Context

ADR-049 lets one reader, the board in `compass flow`, read manifests through the parse cache. It
justifies the cache by ADR-003: flow advises and never gates, so "a fault in the cache can only
mislead an advisory view". It adds that widening the list of readers is a reviewed change, and a
test (`test_trc_a14_only_the_named_readers_use_the_parse_cache`) fails when another module names the
cache.

The rendered blocks of ADR-051 need the same speed. A block that draws on other issues (`related`,
the governance lines of `decisions`, the issue's row of the project index) needs every manifest,
and `compass issue render --all` needs them for 490 issues inside five seconds (DCJ-61). The
ADR-049 argument stops holding for a committed document and for a check that can block, because
the cache keys an entry on the source digest and does not check the payload against it. A corrupted
or planted entry with the right key is used.

## Decision

1. **Readers.** Two modules may name the cache: `flow.py`, the board, and `project_scan.py`, the
   one read of every manifest that serves `compass issue render` (one issue and `--all`), the
   project index and the after-command render. `render_skip.py` and the renderers receive the
   scan and never name the cache. `test_trc_a14_only_the_named_readers_use_the_parse_cache` lists
   the two names, and `test_dcj_77_cache_cannot_decide_blocking_verdict` plants a third module and
   expects the list to fail.
2. **The blocking read is uncached.** `render_cmd.plan_issue` reads the issue's own manifest with
   `load_manifest`, and substitutes it for the scan's copy before any block is rendered.
   `rendered-blocks-current` therefore judges the own-record blocks from the file. It never reads
   the cache. `compass issue render --all` is the exception: it plans each issue from the scan's
   copy, because an uncached read of every manifest breaks the DCJ-61 time bound.
3. **Cached reads feed only advisory parts.** A manifest read from the cache can reach a
   `related` block, the governance lines of a `decisions` block, an index row, the index and the
   skip key. Each is a cross-issue part, and `rendered-blocks-current` reports a stale one as an
   advisory failure at every stage (ADR-051, decision 9).
4. **No saving path reads the cache.** The render saves no manifest. The command that triggered
   it saved earlier, in a separate step, and `plan_issue` does not read the cache for the issue the
   command changed. A command that reads, changes and saves a manifest still uses `core.load_yaml`.
5. **A planted payload is accepted for writes and advisory parts only.** A payload with a valid
   key can mislead a rendered cross-issue block or an index row, and `compass issue render` writes
   what it is given. Through `--all` it can also write a wrong own-record block, which makes
   `rendered-blocks-current` fail, because the check reads the file. It cannot clear a gate, pass a
   check that blocks, or make an approval. The next single-issue render, or a render with the cache
   folder deleted, replaces what it wrote.
6. **A dry run stores nothing.** `compass issue render --all --dry-run` reads the cache and never
   writes an entry, so a dry run changes no byte in the project.

ADR-049 stays as written. This record names the readers its section 5 left to a reviewed change.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| Check the payload digest on every read | Detects a planted entry | A digest stored beside the payload is planted with it, and a second parse defeats the cache |
| Read every manifest uncached in the render | No new reader | About 2.3 s for 484 manifests before the render does any work; DCJ-61 has five seconds for all of it |
| Let the check read the cache too | One read path | A planted entry could clear or fail a blocking check, which ADR-003 forbids for a signal from another issue |
| Add the cache to `core.load_yaml` | Every command faster | Every save and the locked re-read of `generation.py` would depend on it (ADR-049 rejected this) |
| A render-only parse cache | Keeps flow's list unchanged | A second store of the same parse with the same fault, and two folders to prune |

## Consequences

**Positive:**
- `compass issue render --all` renders 490 issues with distinct manifests in 0.8 s with a warm
  cache and 2.9 s with a cold one (median of three, skip state deleted). A record-changing
  command, with the render of its issue and the project index, takes 0.3 s on the same
  project, and `compass check` on one issue takes 0.4 s.
- A cache fault cannot decide a blocking verdict or a gate.

**Negative:**
- A planted entry can put a wrong line in an advisory block and in the project index, until the
  next render.
- The render reads every manifest to build the reverse links, so a render in a large project costs a
  scan even for one issue.

**Neutral / follow-on:**
- The skip state (`render-skip.json` in the cache folder under `.compass`) is derived. It is safe to delete, and its
  absence makes the next `--all` render every issue and change no byte.

## References

- ADR-049: the cache and its section 5 on who may read through it.
- ADR-051: rendered blocks, the severity split and the advisory parts.
- ADR-003: flow advises and never gates.
- `docs/rendered-blocks.md` owns the facts of the render modules.
