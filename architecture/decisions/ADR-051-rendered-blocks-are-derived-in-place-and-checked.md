---
id: ADR-051
title: Rendered blocks are derived in place and checked
status: proposed
date: 2026-10-10
supersedes: ''
superseded_by: ''
---

## Context

Issue documents hold hand-kept copies of state the manifest already records: the coverage ledger, the gate table and the Definition of Done ticks. On shipped work the copies are wrong. A reader sees unticked boxes on finished work, and the page that was meant to show the state (`compass issue dashboard render`) exists for a small share of issues.

ADR-008 says derived views are never a source of truth. ADR-046 and ADR-047 apply it to the board, a file Compass owns and writes outside `docs/compass/`. This change writes derived text inside a person's document, in a folder that many projects git-ignore, so a bad write cannot be undone from git. The engine must prove that it changes nothing outside its own markers.

This record covers the engine (grammar, mask, write path). The units that follow add the check, the after-command step, the item records, the pages and the migration, and finish this record.

## Decision

1. **Grammar.** A rendered block is the region between a line that, stripped, is exactly `<!-- compass:render KIND -->` and the next line that, stripped, is exactly `<!-- /compass:render -->`. A marker counts only outside a fenced code block and outside a multi-line HTML comment. A line that starts like a marker and is not one, an unknown kind, a closing marker with no opening one, an opening marker inside an open block and an opening marker with no closing one are malformed. The parse names the file and the line, and the render writes nothing.
2. **One leaf module owns the grammar, the mask and the write.** `rendered_blocks.py` imports only `atomic_io`. No other module restates the grammar or writes a rendered document.
3. **Masking.** `masked_text` removes the lines inside every block and keeps the marker lines. A text with no block is returned byte for byte, so no digest recorded before this change moves. A text whose markers do not parse is returned whole, and the function never raises. Every digest of a document (`review_records.file_digest`, which the approval digest, freshness and the inputs of a judged check use; the BDD run record's spec digest) and every reader of a document's text (the BDD lifter, `compass analyze`, the spec-documented check, the scenario line of `compass tdd-red`, `doc_sections` and through it the stage-list tick, the template list renderer and the `dod-evidence-typed` tag rule, and `compass issue decision add --from-ledger`) goes through it. A render therefore never moves an approved document back to draft and never makes a reader take block text as the document's own.
4. **Escaping.** Every line copied from a record or a document goes through `neutralise`, `field` or `cell`. A comment opener or closer becomes an entity, a line that would open a fence or read as a conflict marker gets a backslash, a `|` in a table cell is escaped and a line break becomes a space.
5. **Two post-conditions before any write.** The masked text of the new document must equal the masked text of the old one. A parse of the new document must give the same kinds in the same order, the new interior in the rendered blocks and the old interior in the rest, and no rendered line may hold a comment opener or closer, open a fence or read as a conflict marker. A breach refuses the render with exit 2.
6. **Write safety.** The render holds the issue's lock (`.render.lock` in the work folder) while it reads the records and writes. It reads and parses every registered document before it writes any. Each write goes through `atomic_write_text`, which gains a keyword-only `before_replace` callable; the engine uses it to re-read the file just before the rename and refuse when the file changed since the read. There is no rollback across files: a failure part way leaves the files already written as they are and a second run converges. A small gap remains between the re-read and the rename. Temporary files are named with the prefix `.compass-render-` and a killed render's leftovers are deleted by the next render under the lock.
7. **Write boundary.** The render writes only under `docs/compass/`. A registered path that leaves the project, or that is or sits under a symbolic link, is refused; one outside `docs/compass/` is named and not rendered. The issue page path is built from the manifest's `created` date and the slug by `issue_layout.docs_dir_for` and refused when it would leave `docs/compass/<created>-<slug>/`. The evidence tree id excludes `docs/compass/`, so a render there cannot change it.
8. **Renderers are pure.** `block_renderers.py` renders a block from a snapshot of the records, with no clock, no git configuration and no absolute path, so a second render changes no byte. `render_cmd.plan_issue` plans without writing; the verb applies the plan and `--dry-run` reports it.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| Extend `dashboard.py` | The old page already has a marker and a check | The module is being removed and also holds the artifact command |
| Mask in each consumer | No shared module | Twelve definitions drift, which is the failure the single function prevents |
| A backup or journal per write | Undo a bad write | More state in untracked folders, and no help for an edit made during the run |
| Fence copied text instead of escaping it | Keeps the text exact | A copied fence escapes the fence, and the ask loses its Markdown |
| A per-block digest sidecar | Cheap staleness check | A second state, the kind ADR-046 rejected |

## Consequences

- Documents with no block keep their digests, so no recorded digest moves at the upgrade.
- A document with a block digests without it, so a person who edits only inside a block is not seen as editing the document.
- A reader that wants block text must read the file itself. None does today.
- Escaped text reads as written on GitHub, with entities for comment markers.
- The check, the after-command step, item records, pages and migration build on this engine and are recorded in the units that add them.

## References

- ADR-008 (derived views), ADR-036 (`atomic_io`), ADR-046 and ADR-047 (the board file).
- `docs/rendered-blocks.md` owns the facts of the engine.
