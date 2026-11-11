# Rendered blocks

A rendered block is text in an issue's document that Compass wrote from the
issue's records until 9.0.0 (ADR-051, ADR-091). 9.0.0 renders no block, issue
page or project index, and the check `rendered-blocks-current` is removed: a
stored generation that lists it reports nothing to check. No shipped template
holds a marker: 9.0.0 deleted fourteen templates and took the markers out of
the six it kept. A document written before 9.0.0 holds the marker pairs this
page describes, so every reader of a document leaves the block lines out (see
"Masked text" below). The rest of this page records the blocks an older
document holds.

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
`plan-exit`, `breakdown-exit`, `readiness`, `document-header`, `dependencies`, `release-line`,
`model-tiers` and `acceptance-strategy`. All are rendered.

| Kind | What it shows |
|---|---|
| `coverage` | One row for each scenario: tests, red, green and acceptance records, and the result (`passed`, `failing test only` or `no test record`). Then the de-scoped failure modes with their reasons. When the technical design holds a `## Verification plan` heading, a Kind column sits between Title and Tests: see "The Kind column" below. A design with no such heading gets the columns it had before |
| `gates` | `Gates: n of m pass`, then one line for each gate with its status and evidence ids |
| `dod`, `dor` | `Definition of Done: n of m met`, then one line for each item of the configured `verify` exit list or `plan` entry list: met by an evidence id, ticked by a person, carried to a follow-up, ticked on the page before 7.0.0, or open |
| `artifacts` | The registered documents that are not omitted, each with status, approver, the name or meaning the entry records (`traditional_name`, `stands_for`) and why it exists. A document is a relative link under `docs/compass/` when its file exists; otherwise its status reads `not written yet` and it has no link |
| `evidence` | Each evidence entry's id, type and path. A path under `docs/compass/` is a relative link; a path in the work folder is plain text, because that folder is untracked in many projects |
| `follow-ups` | Each follow-up's id, status, summary, target issue and the check it defers |
| `decisions-taken` | The decisions an agent took for the person with their state, then the reassessments with their reasons |
| `header` | The issue, its approach, state (`done (completed)` for a closed issue), stage and gates, then the owner and the created and completed dates, then, while a dependency holds the issue at implement, a second `Blocked: waits for ...` line with the wait (see below), then a line naming the board command, which 9.0.0 removed (ADR-093) |
| `ask` | The Problem, Desired outcome, Success signals and Non-goals sections of `intent.md`. Without them, the issue line of `delivery-approach.md` and the scenario titles; without those, `No statement of the ask is recorded.` |
| `decision-required` | The document that waits for a person's approval, with the command that approves it, or that nothing waits |
| `acceptance` | `Acceptance: n of m scenarios passed`, then each scenario with its title and `passed` or `not yet passed` |
| `related` | The issues this one links to and the issues that link to it, each with its state and a link to its page: `depends on`, `depended on by`, `parent`, `child`, `repairs`, `repaired by`, `follow-up target`, `follow-up from`, `delivered by`, `raised from` and `raised here`. A field that is absent gives no line; an issue with no links reads `None`; a link to an issue that does not exist reads `not found` with no link. A `depends on` line for an issue that was read ends with ` - met`, or with ` - ` and the wait (`waits for b to reach done`); a dependency that is not found, unreadable or in a fault keeps its plain text |
| `decisions` | The `DD-n` headings of `technical-design.md` with their scope and a link to each ADR record that exists, the decisions taken, and the governance decisions whose Evidence section names this exact slug (`- governance:` lines). An issue with none reads `None` |
| `traceability` | The Mermaid flowchart from intent to scenario to test to evidence, with an unproven scenario drawn open. Past 25 scenarios it draws one summary node for each intent. The arrows are `==>` because a rendered line may not hold `-->` |
| `deliberately-omitted` | The documents omitted on purpose, with the reason |
| `verification-note` | A quick fix's scenario, test, red and green records, gates, changed files outside `docs/compass/` and the release line when the manifest records a `release_note` |
| `document-header` | The header of every document written from a template, and of the quick-fix record: six lines, each read from a record, none from a file or the clock. See "The `document-header` block" below |
| `dependencies` | The design's Risks and dependencies list: one line for each `depends_on` entry. See "The `dependencies` block" below |
| `assessment` | In `delivery-approach.md` under The assessment, and in the quick-fix record under Assessment. One row for each assessed dimension with its value and the justification the manifest's `justifications` key records (`no justification recorded` on an issue assessed before the key), then `Labels:` |
| `policy-rules` | In `delivery-approach.md` under Policy rules that fired, and in the quick-fix record under Policy rules fired. The policy line, the generation, and one row for each rule that fired (type, id, what it changed, rationale), or `No policy rule fired.` |
| `stage-weights` | In `delivery-approach.md` under Per-stage weight. One row for each stage in stage order, with the mode the manifest records |
| `gate-set` | In `delivery-approach.md` under Gate set. The gates in the manifest's order, and beside a gate a policy rule added, the ids of those rules |
| `model-tiers` | In the `delivery-approach.md` of an issue assessed before 9.0.0, under Model tiers. One row for each seat the manifest's `models:` key records. 9.0.0 writes no `models:` and its template has no such block (ADR-090); the block still renders a stored key, so an older document stays current |
| `plan-exit`, `breakdown-exit` | The configured `plan` or `breakdown` exit list under `## Gate` in `technical-design.md` and `distribution-map.md`, read like `dod`. Empty (the shipped default): `No exit checks are configured for the plan stage.` (or `breakdown`) |
| `acceptance-strategy` | In `delivery-approach.md` under The assessment. One line from the manifest's `acceptance_strategy` block: whether the four-layer acceptance strategy (`S17`) applies, the reason, and its routing on the issue's approach, as in `Four-layer acceptance strategy (`S17`): applies - client-observable behavior. Routing on the regular approach: on.` An issue with no block shows a line that says the strategy does not apply to it: in a project whose `compass.yml` extends the shipped default at major 6 or 7 the line names that `extends:` value, and otherwise it says the issue was assessed before the strategy shipped. That line draws on the project, so a stale one is only advisory. The quick-fix record holds the block under Acceptance strategy. A delivery approach written before the block existed has no marker, so the render leaves it alone |
| `readiness` | The one line `Repository readiness: 9 of 11 signals, floor met`, or `Repository readiness: not measured (<why>: <how to fix>)`, from the manifest's `readiness:` summary. The marker was in the delivery-approach template, under The assessment. A delivery approach written before the block existed has no marker, so the render leaves it alone. Since 9.0.0 nothing prints the line and nothing writes the manifest key: the `readiness` verb and the readiness floor are gone (ADR-093), and `compass flow` and `issue_detail` no longer carry a readiness line. The marker stays a known kind, so an older document still parses |
| `release-line` | In the `## Release line` section of the verification report template, after "Decisions taken for the user" and before `## Gate`. The manifest's `release_note` on one line, or `No release line recorded yet.` with the command `compass ship-commit --release-note "<text written for a user>"`. The manifest is the only copy of the line (`docs/release-line.md`). A report written before the block existed has no marker, so the render leaves it alone |

A block holds no clock, no absolute path and no name taken from git. The same
records give the same text, so a second render changes no byte. The one fence a
rendered body may hold is the Mermaid chart, opened and closed by the exact
lines ```` ```mermaid ```` and ```` ``` ````.

## The `document-header` block

Every template in the artifact catalogue opens with a title and one `document-header` block, except
`verification-note`, which has no header block. The block has six lines. Each is read from a record,
so a render on another day changes nothing.

| Line | Source |
|---|---|
| `Issue` and `Approach` | The manifest: the slug and `delivery_approach` |
| `Stage` and `Owner` | The kind's catalogue entry |
| `Status` | The document's registry entry, or `not registered` |
| `Date` | The day of `approved_at` when the document is approved, else the manifest's `created` |
| `Reads` | The registered documents whose kind's stage comes before this kind's stage, ordered by stage and then file name. A document is listed when its entry holds a path, not when the file exists. An entry with status `superseded` or `omitted` is skipped |
| `Audience` | The kind's catalogue entry |

Status and Date are separate lines, so an approval changes two lines. The renderer reads no file and no clock.
It is an own-record block: `rendered-blocks-current` fails at `verify` and in a done issue when the block is
stale, and treats it as advisory before. `compass issue template show` prints the same six lines with the
kind's real stage, owner and audience and a `{{...}}` placeholder for each fact only an issue's records give.
A document already written keeps its own prose: an archived document with no marker pair is never rewritten.

## The `dependencies` block

The technical design's Risks and dependencies section holds a `dependencies` block under its risk table. It
lists the issue's `depends_on` entries, one line each:

```text
- <slug> - <reason> - until <until> - <word>
```

The word is the one the board panel shows: `met`, `waiting`, `not found` or `unreadable`. It comes from the same
judgement as the panel (`lifecycle.judge`), so the two cannot disagree. A malformed entry takes the line
`compass issue lint` prints for it. `None` means the issue has no entries. `not judged` replaces the word when
the render read no project scan, so no other issue could be judged.

The block reads other issues' manifests, so it is a cross-issue block: a stale block is an advisory failure of
`rendered-blocks-current` and never blocks the issue. `compass issue depends add` and `compass issue depends
remove` render it again. The shape of `depends_on` is in `docs/issue-dependencies.md`.

## The Kind column

When the technical design holds a `## Verification plan` heading, the `coverage` block adds a Kind column
between Title and Tests. Before 9.0.0 a reader of the plan read it as follows (ADR-091 removed it):

- The first table under the heading whose header holds Group and Kind is the plan. A row that still holds a
  `{{...}}` placeholder is skipped. A heading counts under the section-number rule of the catalogue, and a
  heading inside a fence or a comment does not count.
- The kinds are `unit`, `integration`, `acceptance`, `judged review` and `manual`.
- A row names a scenario group letter, or scenario ids, in its Group cell. A scenario takes the kind of the
  row that names its id, else the row that names its group. Between rows of one precedence, the first wins.
  The group of a scenario is the letter of the `## Scenario group <L>` heading above its traceability line.
- `not planned` means no row covers the scenario. `unknown (<word>)` means the row names a kind outside the
  five. `compass issue lint` prints a note for each row with an unknown kind.
- A design without the heading gets the columns it had before. Archived coverage blocks keep their bytes.

No check parses the plan. It reaches `compass check` only as staleness of the `coverage` block in
`rendered-blocks-current`, which is why an edited plan fails there until the block is rendered again.

## Sections that blocks and checks read by name

Four sections are read by name, whatever number an older document gave their heading. Two feed blocks and two
feed checks:

| Section | Read by |
|---|---|
| Verification plan (design) | The `coverage` block, which adds the Kind column |
| Risks and dependencies (design) | The `dependencies` block under its risk table |
| Non-functional requirements (spec) | The check `nfr-rows-resolved`, which is not a block |
| Data and interfaces (design) | The check `contracts-declared`, which is not a block |

The two checks read the document through the masked text of this page's "Masked text" section, so a table inside a
comment or a fence does not count. `governance/guardrails.md` holds their rules.

## The quick-fix record

`compass quick-fix start` writes the delivery-approach record with its own short headings. The record holds a
`document-header` block after the title, an `assessment` block under Assessment, a `policy-rules` block under
Policy rules fired and an `acceptance-strategy` block under Acceptance strategy, and no `**Approach:**` line. The command writes the marker pairs and no block text of its
own. 9.0.0 renders nothing, so the pairs stay empty (ADR-091). A record written before the blocks existed
keeps its tables.

## The verification note

A quick fix completed before 9.0.0 holds `verification-note.md`. `compass quick-fix finish`
writes none: the red and green records, the changed files and the approvals are in the
manifest and the trail (`docs/delivery-record.md`).

## Item records

The `dod` and `dor` blocks, `dod-evidence-typed` (implementation 2.0.0) and the
stage lists read the Definition of Done and Ready from records in the manifest,
never from the page (`docs/entry-exit-evaluation.md`, "Item records").

## Migration

`compass issue migrate [root]` is a dry run; `--apply` makes the changes, and where git
could not restore an issue folder it also needs `--i-have-a-copy` (`docs/upgrade-7-0-0.md`,
"Copy first"). For an issue written before
rendered blocks it only adds lines and records (ADR-020, through ADR-051). The code is
`cli/compass_pkg/migrate_blocks.py`; the rename of the old page and the report are in
`cli/compass_pkg/migrate.py`.

| What | Rule |
|---|---|
| Marker | Before 9.0.0, an empty `dod` pair went at the end of the "Definition of Done" section of the verification report. 9.0.0 adds none. |
| Boxes to items | A box is the item whose statement it reads; when the report has as many boxes as the list has items, an unmatched box is the item at its place. A box that reads no item is reported. A box also reads an item through its earlier statement: reports written before 7.0.0 cite the report's sections by number (`§1`, `§2`), and `FORMER_STATEMENTS` in `migrate_blocks.py` holds that wording for the three items that now name the sections. |
| Records | `meets` on the evidence an `(evidence: ...)` tag names, `defers` on the follow-up a `(follow-up: ...)` tag names (an older tag word and the `BF-` id prefix are read too), and a `page_ticks` entry for each ticked box. A tag naming an id the manifest does not hold, evidence of a type the list does not accept, or a follow-up that already defers another item writes no record. The item stays open and the report names the issue, the item and the id. |
| Page ticks | Only `item_records` reads one. `human-approval-present` and the approval readers never do, so a ticked box is not a person's approval. |
| Missing heading | A report with no "Definition of Done" heading gets no marker and no record, and the report says so. A closed issue with neither that heading nor a `dod` block then reads "nothing to check" for `dod-evidence-typed`; an issue still in flight is judged, so every item is open. |
| Verification note | Before 9.0.0, an empty note, registered, for each quick fix closed as completed. 9.0.0 adds none. |
| Old page | A work-folder `README.md` whose first line is the old generated marker is renamed to `README.md.v6.bak`, with any text a person added under it. A `README.md` without that line is not touched. The page is not generated again. |
| Stored generation | An issue, open or closed, whose generation records an implementation major this CLI lacks (`dod-evidence-typed` 1.x) is pinned to the installed versions through the `--config` path. A closed issue keeps its configuration; only the versions change. When the next generation folder holds a file a generation commit does not write, the issue is not pinned and the file is named among the items left for a person. |
| Open items | The ones above are printed on every run, after the changes, because they need a person. A second `--apply` changes no file. |

Before 9.0.0 a render filled the blocks after `--apply`. The dry run writes nothing.

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
| `review_records.file_digest` (approval digest, judged-check inputs) | A render must not move an approved document back to draft |
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
