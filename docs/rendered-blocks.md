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
`verification-note` and `index`. The first eight are rendered now. A block of
another kind is left as it is until its renderer exists.

| Kind | What it shows |
|---|---|
| `coverage` | One row for each scenario: tests, red, green and acceptance records, and the result (`passed`, `failing test only` or `no test record`). Then the de-scoped failure modes with their reasons |
| `gates` | `Gates: n of m pass`, then one line for each gate with its status and evidence ids |
| `dod`, `dor` | `Definition of Done: n of m met`, then one line for each item of the configured `verify` exit list or `plan` entry list: met by an evidence id, ticked by a person, carried to a follow-up, ticked on the page before 7.0.0, or open |
| `artifacts` | The registered documents with status, approver and reason, each a relative link under `docs/compass/` |
| `evidence` | Each evidence entry's id, type and path. A path under `docs/compass/` is a relative link; a path in the work folder is plain text, because that folder is untracked in many projects |
| `follow-ups` | Each follow-up's id, status, summary, target issue and the check it defers |
| `decisions-taken` | The decisions an agent took for the person with their state, then the reassessments with their reasons |

A block holds no clock, no absolute path and no name taken from git. The same
records give the same text, so a second render changes no byte.

## `compass issue render`

```text
compass issue render [--issue SLUG] [--dry-run]
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
`--all` is not built yet and exits 2.

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
- A render that fails never fails the command and never stops the other
  renders. One line on standard error gives the count and the first failure:
  `compass: 2 of 3 renders failed - first: <issue>: <file>:<line>: <fault>`.
  The label sync prints its own line when it fails.
- The step prints no reminder. `compass issue dashboard render` and the
  reminder that named it are gone.

## The check `rendered-blocks-current`

`rendered-blocks-current` (implementation 1.0.0, in guardrail `G4`) runs the
render of `compass issue render` without writing and compares, so there is one
definition of current. It reads the issue's own manifest with `load_manifest`,
never through the parse cache.

| Block | Draws on | At `verify`, `ship` and done | Before `verify` |
|---|---|---|---|
| `coverage`, `gates`, `dod`, `dor`, `artifacts`, `evidence`, `follow-ups`, `decisions-taken`, the issue page | the issue's own records | fails | advisory |
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
