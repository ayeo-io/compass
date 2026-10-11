---
id: ADR-051
title: Rendered blocks are derived in place and checked
status: accepted
date: 2026-10-10
supersedes: ''
superseded_by: ''
---

## Context

Issue documents hold hand-kept copies of state the manifest already records: the coverage ledger, the gate table and the Definition of Done ticks. On shipped work the copies are wrong. A reader sees unticked boxes on finished work, and the page that was meant to show the state (`compass issue dashboard render`) exists for a small share of issues.

ADR-008 says derived views are never a source of truth. ADR-046 and ADR-047 apply it to the board, a file Compass owns and writes outside `docs/compass/`. This change writes derived text inside a person's document, in a folder that many projects git-ignore, so a bad write cannot be undone from git. The engine must prove that it changes nothing outside its own markers.

This record covers the engine (grammar, mask, write path), the check, the after-command step, the item records, the pages, the migration and the removal of the old verb and check.

## Decision

1. **Grammar.** A rendered block is the region between a line that, stripped, is exactly `<!-- compass:render KIND -->` and the next line that, stripped, is exactly `<!-- /compass:render -->`. A marker counts only outside a fenced code block and outside a multi-line HTML comment. A line that starts like a marker and is not one, an unknown kind, a closing marker with no opening one, an opening marker inside an open block and an opening marker with no closing one are malformed. The parse names the file and the line, and the render writes nothing.
2. **One leaf module owns the grammar, the mask and the write.** `rendered_blocks.py` imports only `atomic_io`. No other module restates the grammar or writes a rendered document.
3. **Masking.** `masked_text` removes the lines inside every block and keeps the marker lines. A text with no block is returned byte for byte, so no digest recorded before this change moves. A text whose markers do not parse is returned whole, and the function never raises. Every digest of a document (`review_records.file_digest`, which the approval digest, freshness and the inputs of a judged check use; the BDD run record's spec digest) and every reader of a document's text (the BDD lifter, `compass analyze`, the spec-documented check, the scenario line of `compass tdd-red`, `doc_sections` and through it the stage-list tick, the template list renderer and the `dod-evidence-typed` tag rule, and `compass issue decision add --from-ledger`) goes through it. A render therefore never moves an approved document back to draft and never makes a reader take block text as the document's own.
4. **Escaping.** Every line copied from a record or a document goes through `neutralise`, `field` or `cell`. A comment opener or closer becomes an entity, a line that would open a fence or read as a conflict marker gets a backslash, a `|` in a table cell is escaped and a line break becomes a space.
5. **Two post-conditions before any write.** The masked text of the new document must equal the masked text of the old one. A parse of the new document must give the same kinds in the same order, the new interior in the rendered blocks and the old interior in the rest, and no rendered line may hold a comment opener or closer, open a fence or read as a conflict marker. A breach refuses the render with exit 2.
6. **Write safety.** The render holds the issue's lock (`.render.lock` in the work folder) while it reads the records and writes. It reads and parses every registered document before it writes any. Each write goes through `atomic_write_text`, which gains a keyword-only `before_replace` callable; the engine uses it to re-read the file just before the rename and refuse when the file changed since the read. There is no rollback across files: a failure part way leaves the files already written as they are and a second run converges. A small gap remains between the re-read and the rename. Temporary files are named with the prefix `.compass-render-` and a killed render's leftovers are deleted by the next render under the lock.
7. **Write boundary.** The render writes only under `docs/compass/`. A registered path that leaves the project, or that is or sits under a symbolic link, is refused; one outside `docs/compass/` is named and not rendered. The issue page path is built from the manifest's `created` date and the slug by `issue_layout.docs_dir_for` and refused when it would leave `docs/compass/<created>-<slug>/`. The evidence tree id excludes `docs/compass/`, so a render there cannot change it.
8. **Renderers are pure.** `block_renderers.py` renders a block from a snapshot of the records, with no clock, no git configuration and no absolute path, so a second render changes no byte. `render_cmd.plan_issue` plans without writing; the verb applies the plan and `--dry-run` reports it.
9. **The check `rendered-blocks-current` (1.0.0) and its severity.** The check runs the plan without writing and compares. A stale block drawn from the issue's own records fails at `verify`, `ship` and done and is an advisory failure before; a block drawn from other issues or the project (`related`, the governance lines of `decisions`, the issue's index row) is always advisory, because a checkout that holds one issue cannot judge it. The blocking verdict reads the issue's own manifest with `load_manifest` and never the parse cache. jed72 decided the split on 2026-10-10, which departs from "any rendered block" in the requirement. A missing issue page fails at `verify`.
10. **A removed check stays reportable.** An issue runs against the configuration it was assessed under (ADR-036), so a stored generation can list `dashboard-current` after the check is gone. `check_registry.REMOVED` is a framework-owned table of removed check ids. `compass check` reports a listed removed id as nothing to check, naming the release and the replacement, without judging it, and runs the replacement in the same guardrail unless the generation lists it. `compass policy lint` reads the same table to name a removed check in a layer as unknown and to give its replacement. No generation is rewritten, and no alias or no-op check is kept.
11. **One trigger table, one render step.** `record_triggers.py` holds the label sync's table, the further commands that change a record a block shows, and an exempt list with a reason for each command. `github_labels` and `render_after` both read it and neither imports the other. The entry point calls the render step after the label sync. A test walks the call graph from every command to `save_manifest` and names a command in none of the three tables. A failed render never fails the command and prints one line with a count.
12. **Item records.** The Definition of Done (the `verify` exit list) and Ready (the `plan` entry list) are met by records in the manifest: `evidence[].meets`, a `human-approval` record with `check`, `follow_ups[].defers`, and `page_ticks` written only by migration. An agent can no longer tick an item on a page. `dod-evidence-typed` moves to implementation 2.0.0 and reads these records; its verdict on a page with a ticked box and no record changes from pass to fail, so ADR-038 needs a new major. **jed72 approved changing this locked check on 2026-10-10.** Every issue whose stored generation records 1.0.0 is refused until `compass issue migrate` pins a generation that records 2.0.0 (the migration unit). An issue read without a configuration is judged by the shipped default's lists.
13. **The page is not read.** The stage lists and `dod-evidence-typed` no longer import the checklist section reader; only `compass issue migrate` reads page ticks. The templates carry empty `coverage`, `evidence`, `gates`, `decisions-taken`, `dod` and `dor` blocks in place of the state tables and boxes, and `compass issue template show` prints each template as the file. The delivery-approach tables and each template's Gate checklist wait for the artifact catalogue (follow-up FU-1).
14. **The old verb and check are removed.** `compass issue dashboard render`, its alias and `dashboard-current` go in 7.0.0, and `dashboard.py` goes with them. The artifact commands it held (`issue artifact set`, `issue artifact-path`) move to `artifact_cmd.py`. A command line that still types the verb exits 2 with the parse error and one line naming `issue render`. The maintainer (jed72) said go to the removal on 2026-10-11, after the migration was green, as the standing rule asks before a CLI verb is deleted.
15. **One hint row amends ADR-044.** ADR-044 ended every alias and hint row at 7.0.0. A hint row that carries both `released_in` (the first release tag that held the spelling) and `removed_in` stays, because a release did hold that spelling and a person upgrading from it needs the new name. It runs nothing. `aliases.removal_problems` still fails on any alias row and on a hint row without both fields, and `tests/test_cli_renames.py` checks that the tag named in `released_in` holds the spelling. The one row is `issue dashboard` to `issue render`.
16. **Migration only adds.** `compass issue migrate` adds an empty `dod` marker pair after the Definition of Done section of a verification report and moves the registry digest of that report from its old masked digest to the new one, so the report keeps its status. It writes `meets`, `defers` and `page_ticks` records from the boxes, an empty `verification-note.md` for each quick fix closed as completed, and keeps an old generated work-folder page byte for byte as `README.md.v6.bak`. A tag that names an id the manifest does not hold writes no record, and the item stays open and is reported. A page tick is read only by `item_records`: it is not a person's approval (`human-approval-present` never reads it). Migration pins the stored generation of an issue, open or closed, that records an implementation major this CLI lacks, through the `--config` path; a closed issue keeps its configuration and only its versions move.
17. **`dod-evidence-typed` stays at 2.0.0, with one more rule.** A closed issue whose verification report holds neither a Definition of Done heading nor a `dod` block reads nothing to check, because an archived page that never held the list has no record to carry. An issue still in flight is judged, so deleting the section does not clear the check. jed72 approved changing this locked check twice: to move it to 2.0.0 on 2026-10-10, and to add this rule on 2026-10-11. The version does not move again because 2.0.0 has not been released and no stored generation records it. The rule changes no verdict in the check's corpus, so the verdict digest in `tests/fixtures/impls/versions.lock.yml` is unchanged, and for an absent section it restores the 1.0.0 behaviour for a closed issue.
18. **Compatibility contract 3 reads the migrated sample.** The recorded verdicts of `compass check` on the archive sample are compared after `compass issue migrate` and `compass issue render --all`, with an allow-list of exactly three row moves: `dashboard-current` leaves, `rendered-blocks-current` appears, and `dod-evidence-typed` is `pass` or `nothing-to-check` where it was `pass`. Any other move fails. jed72 approved this on 2026-10-11. No baseline was rewritten.

## Now reads as

The earlier records stay as written. From 7.0.0 they read as follows (the style of ADR-044).

- ADR-003: cross-issue blocks are advisory in `rendered-blocks-current`. A cross-task signal still never fails a check.
- ADR-020: `compass issue migrate` adds markers, records, notes and generation pins and changes no line.
- ADR-022: the manifest also holds `evidence[].meets`, `follow_ups[].defers`, `follow_ups[].target_task` and `page_ticks`.
- ADR-026: `ship-commit` renders the done state before it commits.
- ADR-044: `issue render` and `follow-up add` are leaf verbs and `issue dashboard` is gone. At 7.0.0 a removed verb that a release held may keep one hint row that runs nothing.
- ADR-046: the board's detail values come from `issue_detail`, shared with the issue page. The `--json` keys are unchanged.
- ADR-047: the board file is still never written under `docs/compass/`. The issue page names the command and does not link the file.
- ADR-050: the digest of a document excludes block interiors. `artifacts-approved` is unchanged. `compass quick-fix finish` approves `verification-note.md`.
- ADR-012: the terms `rendered-block`, `issue-page`, `verification-note`, `project-index`, `item-record` and `page-tick` are added to the frozen vocabulary.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| Extend `dashboard.py` | The old page already has a marker and a check | The module is being removed and also holds the artifact command |
| Mask in each consumer | No shared module | Twelve definitions drift, which is the failure the single function prevents |
| A backup or journal per write | Undo a bad write | More state in untracked folders, and no help for an edit made during the run |
| Fence copied text instead of escaping it | Keeps the text exact | A copied fence escapes the fence, and the ask loses its Markdown |
| A per-block digest sidecar | Cheap staleness check | A second state, the kind ADR-046 rejected |
| Keep `dashboard-current` as a no-op check | A stored generation still lists it | An alias in all but name; the removed-check table reports it without keeping code |
| Render on every `save_manifest` | One hook, no table | It would render mid-command and after a failed command, and an implicit hook cannot be tested for completeness |

## Consequences

- Documents with no block keep their digests, so no recorded digest moves at the upgrade.
- A document with a block digests without it, so a person who edits only inside a block is not seen as editing the document.
- A reader that wants block text must read the file itself. None does today.
- Escaped text reads as written on GitHub, with entities for comment markers.
- The check, the after-command step, item records, pages and migration build on this engine; `docs/rendered-blocks.md` owns their facts.

## References

- ADR-008 (derived views), ADR-036 (`atomic_io`), ADR-046 and ADR-047 (the board file).
- `docs/rendered-blocks.md` owns the facts of the engine.
