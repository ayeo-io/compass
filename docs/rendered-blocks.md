# Rendered blocks

A rendered block is text in an issue's document that Compass writes from the
issue's records. `compass issue render` rewrites every block and leaves every
other byte of the document as it is. Architecture decision: ADR-051.

## What a block looks like

```text
<!-- compass:render gates -->
Gates: 7 of 9 pass
...
<!-- /compass:render -->
```

- The opening marker is a line that, with leading and trailing space removed,
  is exactly `<!-- compass:render KIND -->`. The closing marker is exactly
  `<!-- /compass:render -->`.
- A marker counts only on a line of its own, outside a fenced code block and
  outside a multi-line HTML comment. A marker quoted in a fence, in a comment or
  in inline code is text.
- A line that starts like a marker and is not exactly one is malformed. So are
  an unknown kind, a closing marker with no opening one, an opening marker
  inside an open block, and an opening marker with no closing one. The render
  names the file and the line and writes nothing.
- A document with no block is never read for rendering and never written.

## Block kinds

The kinds are `coverage`, `gates`, `dod`, `dor`, `artifacts`, `evidence`,
`follow-ups`, `decisions-taken`, `header`, `ask`, `decision-required`,
`acceptance`, `related`, `decisions`, `traceability`, `deliberately-omitted`,
`verification-note`, `index`, `assessment`, `policy-rules`, `stage-weights`, `gate-set`,
`plan-exit` and `breakdown-exit`. All are rendered.

| Kind | What it shows |
|---|---|
| `coverage` | One row for each scenario: tests, red, green and acceptance records, and the result (`passed`, `failing test only` or `no test record`). Then the de-scoped failure modes with their reasons |
| `gates` | `Gates: n of m pass`, then one line for each gate with its status and evidence ids |
| `dod`, `dor` | `Definition of Done: n of m met`, then one line for each item of the configured `verify` exit list or `plan` entry list: met by an evidence id, ticked by a person, carried to a follow-up, ticked on the page before 7.0.0, or open |
| `artifacts` | The registered documents that are not omitted, each with status, approver, the name or meaning the entry records (`traditional_name`, `stands_for`) and why it exists. A document is a relative link under `docs/compass/` when its file exists; otherwise its status reads `not written yet` and it has no link |
| `evidence` | Each evidence entry's id, type and path. A path under `docs/compass/` is a relative link; a path in the work folder is plain text, because that folder is untracked in many projects |
| `follow-ups` | Each follow-up's id, status, summary, target issue and the check it defers |
| `decisions-taken` | The decisions an agent took for the person with their state, then the reassessments with their reasons |
| `header` | The issue, its approach, state (`done (completed)` for a closed issue), stage and gates, then the owner and the created and completed dates, then the command `compass board render` |
| `ask` | The Problem, Desired outcome, Success signals and Non-goals sections of `intent.md`. Without them, the issue line of `delivery-approach.md` and the scenario titles; without those, `No statement of the ask is recorded.` |
| `decision-required` | The document that waits for a person's approval, with the command that approves it, or that nothing waits |
| `acceptance` | `Acceptance: n of m scenarios passed`, then each scenario with its title and `passed` or `not yet passed` |
| `related` | The issues this one links to and the issues that link to it, each with its state and a link to its page: `depends on`, `depended on by`, `parent`, `child`, `repairs`, `repaired by`, `follow-up target`, `follow-up from`, `delivered by`, `raised from` and `raised here`. A field that is absent gives no line; an issue with no links reads `None`; a link to an issue that does not exist reads `not found` with no link |
| `decisions` | The `DD-n` headings of `technical-design.md` with their scope and a link to each ADR record that exists, the decisions taken, and the governance decisions whose Evidence section names this exact slug (`- governance:` lines). An issue with none reads `None` |
| `traceability` | The Mermaid flowchart from intent to scenario to test to evidence, with an unproven scenario drawn open. Past 25 scenarios it draws one summary node for each intent. The arrows are `==>` because a rendered line may not hold `-->` |
| `deliberately-omitted` | The documents omitted on purpose, with the reason |
| `verification-note` | A quick fix's scenario, test, red and green records, gates, changed files outside `docs/compass/` and the release line when the manifest records a `release_note` |
| `index` | The project index: see below |
| `assessment` | In `delivery-approach.md` section 1. One row for each assessed dimension with its value and the justification the manifest's `justifications` key records (`no justification recorded` on an issue assessed before the key), then `Labels:` |
| `policy-rules` | In section 3. The policy line, the generation, and one row for each rule that fired (type, id, what it changed, rationale), or `No policy rule fired.` |
| `stage-weights` | In section 4a. One row for each stage in stage order, with the mode the manifest records |
| `gate-set` | In section 4b. The gates in the manifest's order, and beside a gate a policy rule added, the ids of those rules |
| `plan-exit`, `breakdown-exit` | The configured `plan` or `breakdown` exit list under `## Gate` in `technical-design.md` and `distribution-map.md`, read like `dod`. Empty (the shipped default): `No exit checks are configured for the plan stage.` (or `breakdown`) |

A block holds no clock, no absolute path and no name taken from git. The same
records give the same text, so a second render changes no byte. The one fence a
rendered body may hold is the Mermaid chart, opened and closed by the exact
lines ```` ```mermaid ```` and ```` ``` ````.

## The issue page

`docs/compass/<created>-<slug>/README.md` holds the page. `compass issue render`
creates it with ten blocks, in this order: `header`, `ask`, `decision-required`,
`acceptance`, `related`, `decisions`, `artifacts`, `traceability`,
`deliberately-omitted`, `follow-ups`. The ask opens within the first 20 lines and the
header takes at most 12.

The header takes the issue's approach, state, stage and gate count from
`issue_detail.detail`, the function that `compass flow` calls for the same
facts, so the board panel and the page cannot disagree. The board can read an
issue from another worktree (`--worktrees`) while the page reads this checkout.
The page names the command `compass board render` and does not link the board file,
which lives in the system temp folder.

A page a person wrote, with no block, is left alone. The render says it is
hand-written and was not rendered, and `rendered-blocks-current` fails at
`verify` because the page holds no rendered block.

## The verification note

A quick fix registers `verification-note` at lightweight depth.
`compass quick-fix finish` writes `verification-note.md` once the three gates
have passed, registers it, approves it, traces it to the scenarios and fills its
block. The file is at most 40 lines. A test that fails gets no note. Prose above
the block is kept by every render.

## The project index

The README.md directly in the folder `docs/compass` holds one `index` block: a table for each of Backlog,
Ready, In progress, In review, Done in the last 30 days and Closed, then
Unreadable (a manifest that cannot be read, by slug) and Other documents (the
Markdown files directly in `docs/compass/`). Each readable issue is in one table,
as its slug linked to its page. The window of the "Done in the last 30 days"
table ends at the newest completion the project holds, so the file does not
change as the days pass. Every line of the block depends on the whole project, so
it is a cross-issue block. This repository ignores the file, because it ignores
the issue folders.

A render of one issue also refreshes the index, under
`.compass/cache/render-index.lock`. `rendered-blocks-current` judges an issue by
its own row only.

## `compass issue render`

```text
compass issue render [--issue SLUG | --all] [--dry-run]
```

It renders the blocks of every registered document under `docs/compass/` and of
the issue page, `docs/compass/<created>-<slug>/README.md`, which it creates when
it is absent. It does this in order:

1. Take the issue's lock, `.compass/work/<slug>/.render.lock`.
2. Read the manifest and the evidence listing once.
3. Read and parse every registered document. Check each registered path again: a
   path that leaves the project, or that is or sits under a symbolic link, is
   refused. A path outside `docs/compass/` is named and not rendered. A path with
   no file is named as not on disk.
4. Render every block and check two things before any write: the text outside the
   markers is unchanged, and a parse of the new text gives the blocks that were
   meant. No rendered line may hold a comment opener or closer, open a code fence
   or read as a git conflict marker.
5. Delete temporary files a killed render left, then write each changed document
   with `atomic_write_text`. Just before each rename the render reads the file
   again and refuses when it changed since step 3.

| Outcome | Exit code |
|---|---|
| Done | 0 |
| A malformed marker, a document that is not UTF-8, a registered path that is a link or leaves the project, a breach of a post-condition, a file that changed during the render, or a write failure | 2 |

`--dry-run` lists the documents and kinds that would change and writes nothing.

### `--all`

`compass issue render --all` renders every readable issue and then the project
index. It reads the project once (`project_scan.ProjectScan`), skips an issue whose
inputs are unchanged, and names each issue it could not render: an unreadable
manifest or a refused document. It renders the others.

| Outcome | Exit code |
|---|---|
| Every issue rendered or skipped | 0 |
| Some issue failed; each is named, and its documents are as they were | 1 |
| `--all` with `--issue` | 2 |

`--all --dry-run` lists each file a render would write with its block kinds and
the issues it would skip. It writes nothing: not a document, not the skip state
and not an entry of the parse cache. With `--json` the keys are `rendered`,
`skipped`, `failed`, `dry_run` and `would_write`.

The skip state, `render-skip.json` in the cache folder under `.compass`, maps each issue to a digest of
what its render reads: the CLI version, the manifest, the folder and evidence
listings, the stored generations, every registered document and the page, the
manifests it links to in either direction, the listings of `governance/decisions/`
and `architecture/decisions/`, and `compass.yml`. It is derived. Delete it and
the next run renders every issue and changes no byte. With it, a second `--all`
does not read an issue whose inputs have not changed.

### The parse cache

`project_scan.py` reads the manifests through the parse cache, as the board does
(ADR-049, widened by ADR-052). The check and the single-issue render read the
issue's own manifest without it, so a planted cache entry cannot clear
`rendered-blocks-current`. `--all` plans each issue from the scan's copy to stay
inside its time bound, so a planted entry can make it write a wrong own-record
block. The check then fails, and `compass issue render --issue <slug>` repairs the
page.

## When an issue lands

`compass ship-commit` and `compass quick-fix finish` render the issue's documents, its
page and the project index as the issue will read once it is done, before they make
the commit (`manifest._render_landing`). They stage the files the project does not
ignore. The commit holds the done state, and the render that follows the landing
changes no byte. The landing does this only when every gate has passed, and a failure
of the render never stops it.

There is no rollback across documents. When the third write of three fails, the
first two stay written and a second run finishes the job.

## After each command that changes a record

The entry point calls `render_after.after_command` after the label sync. It
renders the documents of the issue a command named and of every issue the
manifest links to, in either direction (`raised_by`, `parent`, `depends_on`,
`landed_by`, `delivered` and the `target_task` of a follow-up). An issue the
manifest does not link to is not read for writing and keeps its bytes and its
modification time.

- The commands are `RENDER_TRIGGERS` in `cli/compass_pkg/record_triggers.py`:
  the label sync's table (`LABEL_TRIGGERS`) plus `RENDER_FURTHER`. `EXEMPT`
  names the commands that save a manifest and render nothing, each with its
  reason. A test walks the call graph from every command to `save_manifest` and
  fails, naming a command in none of the three.
- A command that exits non-zero renders nothing.
- The environment variable `COMPASS_RENDER_AFTER=0` switches the step off; any
  other value, or none, leaves it on. It exists so a test suite does not pay for
  rendering after every command. `compass issue render` ignores it. A command
  outside `RENDER_TRIGGERS` does not load `render_after` or the render modules.
- A render that fails never fails the command and never stops the other
  renders. One line on standard error gives the count and the first failure:
  `compass: 2 of 3 renders failed - first: <issue>: <file>:<line>: <fault>`.
  The label sync prints its own line when it fails.
- The step prints no reminder. The old review page verb and the reminder that
  named it are gone.

## The check `rendered-blocks-current`

`rendered-blocks-current` (implementation 1.0.0, in guardrail `G4`) runs the
render of `compass issue render` without writing and compares, so there is one
definition of current. It reads the issue's own manifest with `load_manifest`,
never through the parse cache.

| Block | Draws on | At `verify`, `ship` and done | Before `verify` |
|---|---|---|---|
| `coverage`, `gates`, `dod`, `dor`, `artifacts`, `evidence`, `follow-ups`, `decisions-taken`, `assessment`, `policy-rules`, `stage-weights`, `gate-set`, `plan-exit`, `breakdown-exit`, the issue page | the issue's own records | fails | advisory |
| `related`, the governance lines of `decisions`, the issue's row of the index | other issues or the project | advisory | advisory |

A missing issue page fails at `verify` and is advisory before. The message names
the file, the block kind and `compass issue render`. A checkout that holds only
one issue's folders (a CI clone) reports the cross-issue blocks as advisory
failures and passes the rest.

A stored generation can still list `dashboard-current`, because an issue runs
against the configuration it was assessed under. `compass check` reports that id
as `nothing to check`, says it was removed in 7.0.0 and names
`rendered-blocks-current`, and runs the replacement in the same guardrail
unless the generation lists it already. The table is `REMOVED` in
`cli/compass_pkg/check_registry.py`; it is framework-owned and not
configurable. `compass policy lint` names a removed check in a layer as an
unknown check and gives its replacement.

## Item records

The `dod` and `dor` blocks, `dod-evidence-typed` (implementation 2.0.0) and the
stage lists read the Definition of Done and Ready from records in the manifest,
never from the page (`docs/entry-exit-evaluation.md`, "Item records").

## Migration

`compass issue migrate [root]` is a dry run; `--apply` makes the changes, and on a work
root that git does not track it also needs `--i-have-a-copy`. For an issue written before
rendered blocks it only adds lines and records (ADR-020, through ADR-051). The code is
`cli/compass_pkg/migrate_blocks.py`; the rename of the old page and the report are in
`cli/compass_pkg/migrate.py`.

| What | Rule |
|---|---|
| Marker | An empty `dod` pair goes at the end of the "Definition of Done" section of the verification report. The registry digest of the report, and the `upstream` digest of a document that names it, move from the old masked digest to the new one, so the report keeps its status. A digest that was already stale stays stale. |
| Boxes to items | A box is the item whose statement it reads; when the report has as many boxes as the list has items, an unmatched box is the item at its place. A box that reads no item is reported. |
| Records | `meets` on the evidence an `(evidence: ...)` tag names, `defers` on the follow-up a `(follow-up: ...)` tag names (an older tag word and the `BF-` id prefix are read too), and a `page_ticks` entry for each ticked box. A tag naming an id the manifest does not hold, evidence of a type the list does not accept, or a follow-up that already defers another item writes no record. The item stays open and the report names the issue, the item and the id. |
| Page ticks | Only `item_records` reads one. `human-approval-present` and the approval readers never do, so a ticked box is not a person's approval. |
| Missing heading | A report with no "Definition of Done" heading gets no marker and no record, and the report says so. A closed issue with neither that heading nor a `dod` block then reads "nothing to check" for `dod-evidence-typed`; an issue still in flight is judged, so every item is open. |
| Verification note | An empty note, registered, for each quick fix closed as completed. |
| Old page | A work-folder `README.md` whose first line is the old generated marker is renamed to `README.md.v6.bak`, with any text a person added under it. A `README.md` without that line is not touched. The page is not generated again. |
| Stored generation | An issue, open or closed, whose generation records an implementation major this CLI lacks (`dod-evidence-typed` 1.x) is pinned to the installed versions through the `--config` path. A closed issue keeps its configuration; only the versions change. |
| Open items | The ones above are printed on every run, after the changes, because they need a person. A second `--apply` changes no file. |

After `--apply`, `compass issue render --all` fills the blocks. `--dry-run` of that verb,
and the dry run of this one, write nothing.

## Text copied into a block

A line copied from a record or a document goes through
`rendered_blocks.neutralise`, `field` or `cell`:

- `<!--` is written `&lt;!--` and `-->` is written `--&gt;`;
- a line that opens a code fence (three backticks or `~~~`) or starts with a git
  conflict marker (`<<<<<<<`, `=======`, `>>>>>>>`, `|||||||`) gets a backslash
  before its first character;
- a `|` in a table cell is written `\|`, and a line break in a one-line field
  becomes a space.

## Masked text

`rendered_blocks.masked_text` is a document's text with the lines inside every
block removed and the marker lines kept. A text with no block comes back byte for
byte, and a text whose markers do not parse comes back whole.

Every digest of a document and every reader of its text uses it:

| Consumer | Why |
|---|---|
| `review_records.file_digest` (approval digest, freshness, judged-check inputs) | A render must not move an approved document back to draft |
| `checks._spec_sha256` (the BDD run record) | A render must not read as an edit to the spec |
| `bdd.cmd_bdd_extract`, `analyze`, `checks._scenario_documented_in_spec` | Block text is not a scenario |
| `tdd._scenario_line` | The line number is the line in the file, so removed lines stay as empty lines |
| `doc_sections.comment_mask` (stage-list tick, template list renderer, `dod-evidence-typed` tag rule) | A heading or box inside a block is not a checklist |
| `decisions_taken._review_text` | A `decisions-taken` block repeats the ledger |

## Limits

- Between the second read and the rename there is a short gap. A change made in
  that gap is lost. The render holds the issue's lock, but a person's editor
  does not.
- Block text is derived from the records. Edit the record, not the block.
