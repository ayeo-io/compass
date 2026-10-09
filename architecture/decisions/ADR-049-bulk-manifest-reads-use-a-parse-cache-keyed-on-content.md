---
id: ADR-049
title: Manifests read in bulk use a parse cache keyed on content
status: accepted
date: 2026-10-09
supersedes: ''
superseded_by: ''
---

## Context

ADR-013 bundles one pure-Python PyYAML and accepts that it is slow on large files. On this repository's 485 manifests, parsing was about 98.6% of `compass flow`'s time, and the command took 2.33 s (median of three), over its 2.0 s target.

Commands that save a manifest depend on reading the file as it is now. `core.load_yaml` has 77 call sites. Some read, change and save, and `generation.py` re-reads the manifest under a lock to refuse a change made by another process. The archive under `.compass/work/` is not in git in this repository, so a lost update cannot be restored.

## Decision

1. **Who may use the cache.** A command that reads many manifests and saves none of them may read them through `parse_cache.ParseCache`. The cache stores the result of `yaml.safe_load` under the bundled PyYAML for each file's exact bytes. Today only the board in `compass flow` does.
2. **The parity rule.** A read through the cache returns a value equal to `yaml.safe_load` of the file's current bytes under the bundled PyYAML. Equal means the same type at every position and identical `safe_dump` text with `sort_keys=False`. The cache stores results of the one parser. It is not a second parser, and no machine reads differently from another.
3. **Freshness.** Every read reads the file's bytes. The key is their SHA-256. An entry is used only when its recorded source digest, format and PyYAML version all match. Any doubt parses.
4. **Safety.**
   - Entries are tagged JSON over a closed set of types, read with `json.loads` only. The module imports no `pickle`, `marshal` or `shelve`.
   - The cache lives in `<project>/.compass/cache/parsed_yaml/`. It refuses links, refuses a path that resolves outside `.compass`, and holds its own `.gitignore` so `git status` does not change.
   - A write failure is ignored, and the cache never prints.
5. **Scope.** `core.load_yaml` and `core.load_manifest` do not use the cache. No path that saves a manifest reads through it. A test fails if any module other than `flow.py` names it. Widening that list is a reviewed change against this record.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| libyaml's `CSafeLoader` when installed | A compiled parser, much faster (not measured here) | Parsing differs between machines, which ADR-013's unconditional precedence rules out |
| A bundled compiled libyaml | Fast everywhere | Platform binaries; ADR-013 bundles the pure-Python sdist |
| Parse fewer manifests | Most issues are done | Every state is counted in printed output, so skipping a parse changes the output or needs a second reader of the format |
| A cache keyed on path, modification time and size | Cheap check, no read | A copy that keeps both values (`cp -p`, `rsync -a`) serves stale data |
| The cache inside `core.load_yaml` | Every command faster | Every save and the locked re-read would depend on the cache, and data in `.compass/work/` may not be in git |
| A pickle or marshal store | Exact types for free | Runs or crashes on a planted file |
| SQLite | One file | A binary store that ADR-005 turned down for issue state, and more than a folder of content-named files needs |
| Parallel parsing in worker processes | Stores nothing | Speed depends on the core count, and a CLI command pays process start-up. It is the next option if the cache is not fast enough |

## Consequences

**Positive:**
- `compass flow` finishes in about 0.3 s once its parses are stored, against 2.33 s before, on this repository.
- No output changes. The parser and its precedence are unchanged.

**Negative:**
- A project gains a derived folder, safe to delete at any time.
- The first run after many manifests change is slower, by about 5% on the 484-manifest measurement. A test bounds it at 10%.
- Other commands that read many manifests stay slow until they opt in through their own reviewed change.
- ADR-013 still says "slower on large files" and does not point here, because merged records do not change.

**Neutral / follow-on:**
- An update of the bundled PyYAML makes every entry miss once, by design.
- A value outside the closed type set, such as a `!!binary` or `!!set` value, is parsed every time.

## References

- ADR-013: vendored third-party code. This record works within it.
- ADR-003: flow advises and never gates, so a fault in the cache can only mislead an advisory view.
- ADR-005: state lives on disk. The cache is derived data, never state.
- The `manifest-parse-speed` issue's acceptance criteria: the read contract, speed, parity, freshness, the stored cache and unchanged output.
