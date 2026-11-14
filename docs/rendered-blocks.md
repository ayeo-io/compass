# Rendered blocks

A rendered block is text in an issue's document that Compass wrote from the
issue's records until 9.0.0 (ADR-051). This page records the blocks a
document written before 9.0.0 holds, and how 9.0.0 reads such a document.

## What 9.0.0 does

- It renders no block, issue page or project index (ADR-091). `compass
  issue render` is removed.
- The check `rendered-blocks-current` is removed. A stored generation that
  lists it reports nothing to check.
- No shipped template holds a marker.
- Every reader of a document leaves the block lines out (see
  [Masked text](#masked-text)).
- Each kind below stays a known kind, so an older document still parses.

## What a block looks like

```text
<!-- compass:render gates -->
Gates: 7 of 9 pass
...
<!-- /compass:render -->
```

- The opening marker is a line that, without leading and trailing space, is
  exactly `<!-- compass:render KIND -->`. The closing marker is exactly
  `<!-- /compass:render -->`.
- A marker counts only on a line of its own, outside a fenced code block
  and outside a multi-line HTML comment.
- Malformed: a line that starts like a marker and is not one, an unknown
  kind, a closing marker with no opening one, an opening marker inside an
  open block, and an opening marker with no closing one.
- A block holds no clock, no absolute path and no name from git. The same
  records give the same text.
- The one fence a block body can hold is the Mermaid chart, opened by
  ```` ```mermaid ```` and closed by ```` ``` ````.

## Block kinds

| Kind | What it shows |
|---|---|
| `coverage` | Each scenario with its tests, red, green and acceptance records and the result (`passed`, `failing test only` or `no test record`), then the de-scoped failure modes. A design with a `## Verification plan` heading adds a Kind column: `unit`, `integration`, `acceptance`, `judged review`, `manual`, `not planned` or `unknown (<word>)` |
| `gates` | `Gates: n of m pass`, then each gate with its status and evidence ids |
| `dod`, `dor` | `Definition of Done: n of m met`, then each item: met by an evidence id, ticked by a person, carried to a follow-up, ticked on the page before 7.0.0, or open |
| `plan-exit`, `breakdown-exit` | The `plan` or `breakdown` exit list, read like `dod` |
| `artifacts` | The registered documents with status and approver. A document with no file reads `not written yet` |
| `evidence` | Each evidence entry's id, type and path |
| `follow-ups` | Each follow-up's id, status, summary, target issue and the check it defers |
| `decisions-taken` | The decisions an agent took for the person, then the reassessments |
| `header` | The issue, its approach, state, stage, gates, owner and dates, and a `Blocked: waits for ...` line while a dependency holds the issue |
| `ask` | The Problem, Desired outcome, Success signals and Non-goals sections of `intent.md`, or `No statement of the ask is recorded.` |
| `decision-required` | The document that waits for a person's approval, or that nothing waits |
| `acceptance` | `Acceptance: n of m scenarios passed`, then each scenario |
| `related` | The issues this one links to and the issues that link to it, each with its state. A missing issue reads `not found` |
| `decisions` | The `DD-n` headings of `technical-design.md` with scope and ADR links, the decisions taken, and the governance decisions that name this slug |
| `traceability` | A Mermaid flowchart from intent to scenario to test to evidence. The arrows are `==>`, because a rendered line cannot hold `-->` |
| `deliberately-omitted` | The documents omitted on purpose, with the reason |
| `verification-note` | A quick fix's scenario, test, red and green records, gates, changed files and release line |
| `document-header` | Six lines at the top of a document. See [below](#the-document-header-block) |
| `dependencies` | One line for each `depends_on` entry. See [below](#the-dependencies-block) |
| `assessment` | Each assessed dimension with its value and justification, then `Labels:` |
| `policy-rules` | The policy line, the generation and each rule that fired, or `No policy rule fired.` |
| `stage-weights` | Each stage with the mode the manifest records |
| `gate-set` | The gates in the manifest's order, with the policy rules that added a gate |
| `model-tiers` | Each seat in the manifest's `models:` key. 9.0.0 writes no `models:` (ADR-090) |
| `acceptance-strategy` | Whether the four-layer acceptance strategy (`S17`) applies, the reason, and its routing |
| `readiness` | `Repository readiness: 9 of 11 signals, floor met`, or `not measured`. Nothing writes the manifest key now (ADR-093) |
| `release-line` | The manifest's `release_note`, or `No release line recorded yet.` ([release line](release-line.md)) |
| `index` | The row of the project index |

- A document written before a block existed has no marker for it, and keeps
  its tables.
- `compass quick-fix start` writes the marker pairs of the quick-fix record
  (`document-header`, `assessment`, `policy-rules` and
  `acceptance-strategy`) and no block text. In 9.0.0 the pairs stay empty.

## The `document-header` block

Each line is read from a record, none from a file or the clock:

| Line | Source |
|---|---|
| `Issue` and `Approach` | The manifest: the slug and `delivery_approach` |
| `Stage` and `Owner` | The kind's catalog entry |
| `Status` | The document's registry entry, or `not registered` |
| `Date` | The day of `approved_at` when the document is approved, else the manifest's `created` |
| `Reads` | The registered documents whose kind's stage comes before this kind's stage, ordered by stage and then file name. An entry with a path is listed. An entry with status `superseded` or `omitted` is skipped |
| `Audience` | The kind's catalog entry |

`verification-note` has no header block.

## The `dependencies` block

One line for each `depends_on` entry
([issue dependencies](issue-dependencies.md)):

```text
- <slug> - <reason> - until <until> - <word>
```

- The word is `met`, `waiting`, `not found` or `unreadable`, from
  `lifecycle.judge`.
- `not judged` replaces the word when the render read no project scan.
- `None` means the issue has no entries.
- A malformed entry takes the line `compass issue lint` prints for it.

## Sections that blocks and checks read by name

| Section | Read by |
|---|---|
| Verification plan (design) | The `coverage` block, which adds the Kind column |
| Risks and dependencies (design) | The `dependencies` block under its risk table |
| Non-functional requirements (spec) | The check `nfr-rows-resolved` |
| Data and interfaces (design) | The check `contracts-declared`, removed in 9.0.0 |

`nfr-rows-resolved` reads the masked text, so a table inside a comment or a
fence does not count (`governance/guardrails.md`).

## Masked text

`rendered_blocks.masked_text` is a document's text with the lines inside
every block removed and the marker lines kept. A text with no block comes
back byte for byte. A text whose markers do not parse comes back whole.

Every digest of a document and every reader of its text uses it:

| Consumer | Why |
|---|---|
| `review_records.file_digest` (approval digest, judged-check inputs) | A render must not move an approved document back to draft |
| `checks._spec_sha256` (the BDD run record) | A render must not read as an edit to the spec |
| `bdd.cmd_bdd_extract`, `analyze`, `checks._scenario_documented_in_spec` | Block text is not a scenario |
| `tdd._scenario_line` | The line number is the line in the file, so removed lines stay as empty lines |
| `doc_sections.comment_mask` (stage-list tick, template list renderer, `dod-evidence-typed` tag rule) | A heading or box inside a block is not a checklist |
| `decisions_taken._review_text` | A `decisions-taken` block repeats the ledger |

## Text copied into a block

A line copied from a record went through `rendered_blocks.neutralise`,
`field` or `cell`:

- `<!--` is written `&lt;!--` and `-->` is written `--&gt;`;
- a line that opens a code fence (three backticks or `~~~`) or starts with a
  git conflict marker (`<<<<<<<`, `=======`, `>>>>>>>`, `|||||||`) gets a
  backslash before its first character;
- a `|` in a table cell is written `\|`, and a line break in a one-line
  field becomes a space.

## Item records

The `dod` and `dor` blocks, `dod-evidence-typed` and the stage lists read
the Definition of Done and the Definition of Ready from records in the
manifest, never from the page
([entry and exit evaluation](entry-exit-evaluation.md), "Item records").

A quick fix completed before 9.0.0 holds `verification-note.md`. `compass
quick-fix finish` writes none: its records are in the manifest and the trail
([delivery record](delivery-record.md)).

## Migration

`compass issue migrate [root]` is a dry run and writes nothing. `--apply`
makes the changes. Where git cannot restore an issue folder, it also needs
`--i-have-a-copy` (`docs/upgrade-7-0-0.md`, "Copy first"). For an issue
written before rendered blocks it only adds lines and records (ADR-020). The
code is `cli/compass_pkg/migrate_blocks.py` and `cli/compass_pkg/migrate.py`.

| What | Rule |
|---|---|
| Marker | 9.0.0 adds no `dod` marker pair and no verification note. |
| Boxes to items | A box is the item whose statement it reads. When the report has as many boxes as the list has items, an unmatched box is the item at its place. A box that reads no item is reported. A box also reads an item through its statement from before 7.0.0 (`FORMER_STATEMENTS` in `migrate_blocks.py`). |
| Records | `meets` on the evidence an `(evidence: ...)` tag names, `defers` on the follow-up a `(follow-up: ...)` tag names (an older tag word and the `BF-` id prefix are read too), and a `page_ticks` entry for each ticked box. |
| Records not written | A tag that names an id the manifest does not hold, evidence of a type the list does not accept, or a follow-up that already defers another item. The item stays open, and the report names the issue, the item and the id. |
| Page ticks | Only `item_records` reads one. `human-approval-present` and the approval readers never do: a ticked box is not a person's approval. |
| Missing heading | A report with no "Definition of Done" heading gets no record, and the report says so. A closed issue with neither that heading nor a `dod` block reads "nothing to check" for `dod-evidence-typed`. An issue in flight is judged, so every item is open. |
| Old page | A work-folder `README.md` whose first line is the old generated marker is renamed to `README.md.v6.bak`. Another `README.md` is not touched. |
| Stored generation | An issue whose generation records an implementation major this CLI lacks (`dod-evidence-typed` 1.x) is pinned to the installed versions through the `--config` path. A closed issue keeps its configuration. When the next generation folder holds a file a generation commit does not write, the issue is not pinned and the file is named for a person. |
| Open items | Printed on every run, after the changes, because they need a person. A second `--apply` changes no file. |

## Limit

Block text is derived from the records. Edit the record, not the block.
