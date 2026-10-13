# Upgrading to 7.0.0

This page lists what 7.0.0 changes and what to do about it. Each section is one change. The decisions behind them are in `architecture/decisions/`.

## Artifact status and decisions taken

Stage commands now write the status of each registered document. A document that is not accepted does not ship. The decision is `architecture/decisions/ADR-050-artifact-status-is-written-by-stage-exits-and-by-a-persons-approval.md`.

### What changes

- **Stage commands write status.** A command that writes the record of a stage moves the `draft` documents of earlier stages that have a path. The commands are `compass issue artifact set` with a path, `compass issue subtask add`, `compass tdd-red`, `compass acceptance record`, `compass gate pass` on a `verify` gate and `compass ship-commit`. A document with no human check becomes `approved`. A document with a human check becomes `awaiting-approval`.
- **`approved_by` names a person or a command.** A person's approval names the person. A stage's approval names the command, such as `compass tdd-red`. `approved_at` holds the time. The receipt and the dashboard show both.
- **A person approves with `compass evidence approve --artifact <kind>`.** It needs a terminal, and it refuses the approver `agent`. It writes a record of the new evidence type `artifact-approval`. That record meets the document's human check. It is not a `human-approval` record, so it never clears the sign-off of guardrail `G5`.
- **`compass issue artifact set --status approved` refuses a document with a human check.** It names the command above.
- **A rewrite moves an approved document back to `draft`.** Registering an approved document again after its file changed moves it to `draft` and records why.
- **Digests are always recorded.** `compass issue artifact set` records the digest of the document on every registration. The stale-document refusals stay behind the capability `artifact-freshness`.
- **A re-assessment keeps a written document as `superseded`.** An entry the new approach no longer registers stays when it has a path, with a reason that names the re-assessment.
- **`compass ship-commit` refuses an unapproved document.** The blocking check `artifacts-approved` fails on a document that reads `draft` or `awaiting-approval`, and on one omitted with no reason. Each failure names the command that fixes it. A document the approach earned and nobody wrote must be written, or omitted with `compass issue artifact set <kind> --status omitted --reason "<why>"`.
- **A quick fix gains no stop.** `compass quick-fix finish` approves the quick fix's document after `compass check` passes.
- **A project artifact with no `stage` is owned by ship.** Add `stage: <stage>` to its catalogue entry to have an earlier stage approve it. `compass ship-commit` approves the ship-owned ones.
- **`compass issue migrate` settles the status of done issues.** On a done issue, each `draft` or `awaiting-approval` document becomes `approved` (close reason `completed`, `approved_by: compass issue migrate`) or `superseded` (`not-planned` or `duplicate`), with the reason "migrated from a 6.0.0 record". Documents in any other status and open issues are left as they are. The dry run reports the counts, and a second run changes nothing.
- **A decision an agent took for the person is shown at the next checkpoint.** `compass issue decision add` (and `--from-ledger`) records it in `decisions_taken`. On `balanced` and `controlled` autonomy, `compass next` reports `Waiting at the <stage> checkpoint` until a person confirms the set with `compass evidence approve --decisions` or reopens a decision with `compass issue decision set`. On `autonomous` it lists the decisions and does not wait. The approver is a name in the project file's `approvers:` lists, or its `owner` when there are none. The confirmation is an `artifact-approval` record, never a `human-approval` record.
- **`compass retro --decisions` reports how those decisions were settled.** It gives the share confirmed, changed and never confirmed on a done issue.

### What to do

1. Run `compass issue migrate` for a dry run of the archive changes, then `compass issue migrate --apply --i-have-a-copy` after you copy `.compass/work`.
2. Open issues gain the `artifacts-approved` check at their next `compass approach evaluate --write`. Until then `compass check` and `compass ship-commit` do not run it for them.
3. Do not run a 6.x CLI on a 7.0.0 tree.

### New keys and verbs

| Name | Where | Meaning |
|---|---|---|
| `stage` | an artifact in the catalogue | The stage that owns the artifact |
| `approved_by`, `approved_at` | an artifact entry in `manifest.yml` | Who approved the document, and when |
| `artifact-approval` | the type of an evidence record | A person's approval of a document or of a set of decisions |
| `artifacts-approved` | a check in the default preset | The ship refusal |
| `compass evidence approve --artifact` | a flag | Approve a document that reads `awaiting-approval` |
| `decisions_taken` | `manifest.yml` | The decisions an agent took for the person, with their status |
| `compass evidence approve --decisions` | a flag | Confirm the decisions taken for the person |
| `compass issue decision add`, `compass issue decision set` | verbs | Record a decision taken for the person, or reopen one |
| `compass retro --decisions` | a flag | Report how decisions taken for the person were settled |

## Rendered blocks and the issue page

Compass now writes the status, ticks and counts in an issue's documents from the manifest and the evidence, and `compass check` fails a document that disagrees with them. Each issue gets an issue page, a quick fix gets a verification note, and the project gets an index. The decision is `architecture/decisions/ADR-051-rendered-blocks-are-derived-in-place-and-checked.md`. The facts are in `docs/rendered-blocks.md`.

### What is removed

- **The verb `compass issue dashboard render` and its alias.** A command line that still types it exits 2 with the parse error and one line: `'issue dashboard' is now 'issue render'`. The line runs nothing. It is the one hint row that stays at 7.0.0, because 5.6.0 held the spelling.
- **The check `dashboard-current`.** `rendered-blocks-current` replaces it. An issue stored before 7.0.0 can still list the removed check in its generation. `compass check` reports it as "nothing to check", names the release and the replacement, and runs `rendered-blocks-current` in its place.
- **The reminder after a command.** The line that told you to run the old verb is gone. The documents are rendered for you after each command that changes a record.
- **The generated `README.md` beside the manifest** in `.compass/work/<issue>/`. Migration keeps each one as `README.md.v6.bak` (see below). The issue page is `docs/compass/<created>-<issue>/README.md`.
- **A copied 5.6.0 governance folder still works.** A copied folder that names `dashboard-current` still lints, and `compass check` reports it as above.

### What changes

- **Ticks move from the page to the manifest.** The Definition of Done is the `verify` exit list and the Definition of Ready is the `plan` entry list. An item is met by a record, never by a box on a page. A box ticked by hand counts for nothing.
  - `compass gate pass ... --meets CHECK` and `compass evidence add ... --meets CHECK` meet an item with evidence of an accepted type.
  - `compass evidence approve --check <item>` records a person's tick. It needs a terminal, as the other approvals do.
  - `compass follow-up add FU-ID --defers CHECK --summary TEXT` carries an item to a follow-up.
  - `dod-evidence-typed` is now implementation 2.0.0 and reads these records. A closed issue whose verification report holds neither a Definition of Done heading nor a `dod` block reads "nothing to check". An issue still in flight is judged.
- **Cross-issue blocks are advisory.** The `related` block, the governance lines of `decisions` and the index row never fail `rendered-blocks-current`, because a checkout may not hold the other issues.
- **A stale block drawn from the issue's own records fails at `verify`, `ship` and done.** Before that it is advisory. The fix is `compass issue render`.
- **`ship-commit` renders the done state before it commits.** `compass quick-fix finish` writes the verification note.

### What `compass issue migrate` does

`compass issue migrate` (a dry run) lists, for each issue, what it would write. `--apply` writes it, and needs `--i-have-a-copy` where git does not track the work root. It only adds lines and records:

1. It inserts an empty `dod` marker pair after the Definition of Done section of the verification report, and moves the report's registry digest so it keeps its status.
2. It writes `meets`, `defers` and `page_ticks` records from the boxes of that section. A tag naming an id the manifest does not hold, or evidence of a type the list does not accept, writes no record. The item stays open and the report names the issue, the item and the id. A ticked box becomes a page tick, which counts as met on the page and is never a person's approval for `G5`.
3. It writes an empty verification note for each quick fix closed as completed.
4. It renames each generated `README.md` beside a manifest to `README.md.v6.bak`, byte for byte, with any text you added under it. A `README.md` you wrote is not touched.
5. It pins the stored generation of an issue, open or closed, that records an implementation major this CLI lacks (`dod-evidence-typed` 1.x), so the check runs instead of being refused. The configuration does not change.
6. It carries issues in flight the same way as done ones.
7. It reports a verification report with no Definition of Done heading. That report gets no marker and no record.

The items it could not record are printed after the changes, on every run. A second `--apply` changes no file.

After `--apply`, run `compass issue render --all --dry-run` to see the files and block kinds that would change, then `compass issue render --all`.

### What to do

1. Copy `.compass/work` and `docs/compass` to a folder outside the project.
2. Run `compass issue migrate`, read the list, then `compass issue migrate --apply --i-have-a-copy`.
3. Run `compass issue render --all --dry-run`, then `compass issue render --all`.
4. Record each open item the migration printed, with the commands above.
5. To go back, restore both folders from the copy (the rollback plan of the issue that added rendered blocks).

### New verbs, flags and keys

| Name | Where | Meaning |
|---|---|---|
| `compass issue render [--issue SLUG] [--all] [--dry-run]` | verb | Rewrite the rendered blocks, the issue page and the project index |
| `compass follow-up add FU-ID [--defers CHECK] --summary TEXT [--target SLUG]` | verb | Record a follow-up, and carry an item to it |
| `--meets CHECK` | flag of `compass gate pass` and `compass evidence add` | Meet a Definition of Done or Ready item |
| `compass evidence approve --check <item>` | flag | A person's tick of an item |
| `rendered-blocks-current` | check in `G4` | Fails a block that disagrees with the records |
| `evidence[].meets`, `follow_ups[].defers`, `page_ticks` | `manifest.yml` | The records that meet an item. Only migration writes `page_ticks` |
| `<!-- compass:render KIND -->` | marker in a document | The start of a block Compass writes. Do not edit between the markers |

## The artifact catalogue, the delivery-approach record and the archive

The artifact catalogue now describes each document: who writes it, who reads it, its traditional name and its sections. The delivery-approach record lives in the documents folder on every approach, each assessed value carries a justification, and a review round is a file of its own. `compass issue migrate` moves and renames the archive's documents to match. The decisions are ADR-053 to ADR-056 in `architecture/decisions/`. The facts are in `docs/artifact-catalogue.md`.

### What breaks

- **An added artifact kind needs five more fields.** A project layer, or a project that keeps its own copy of the 5.x governance files, that declares a kind the shipped default does not declare stops resolving with `M-ADD-PARTIAL`. The entry needs `stage`, `owner`, `audience`, `stands_for` and `sections` beside `file`. The error names each missing field. There is no flag and no alias, and the legacy adapter does not write placeholder values for a copied 5.x file.
- **`compass approach evaluate --write` refuses a value with no justification.** A value of an ordered or enumerated dimension (risk, familiarity, size, goal, role or urgency) that is new or changed since the last evaluation needs `--justify DIM=TEXT`. The refusal names every such dimension and writes nothing. A second write with an unchanged assessment, and an archived issue with no `justifications` key, are not refused.
- **`compass quick-fix start --goal` and `--role` need a reason.** Give `--goal VALUE - REASON`. A value with no reason is refused, naming the dimension, before anything is written. Leave the flag out and the dimension is recorded as not assessed.
- **`compass issue artifact set --path` refuses a path outside the kind's home.** Each kind has one home, `docs/compass/<created>-<issue>/<file>`. The refusal names it.
- **The spike conclusion's flag is `--next-issue`.** `compass issue artifact set spike-conclusion --decision graduate-to-delivery --next-issue <slug>` names the delivery issue. The flag is new in 7.0.0 and has no alias. A pre-release build spelled it with the retired word, so only a script written against that build is affected.
- **The migrate renames and moves documents.** Review rounds become `review-<n>.md`, the delivery-approach record moves into the documents folder, and a one-subtask stub map becomes `distribution-map.md.v6.bak`. A script or note that names an old filename must use the new one. Each registry entry's reason names the old filename.
- **The migrate removes the compatibility pointer.** A `pre-tool.sh` hook installed before 5.0.0 looks for the record beside the manifest only, so it blocks every edit once the pointer is gone. Update the plugin before you migrate.

### What changes

- **`compass issue template show <kind>` prints a skeleton** built from the catalogue, at `--depth lightweight` or `thorough`. A template that is not a kind is printed as the file.
- **The delivery-approach record is in the documents folder on every approach.** `compass approach evaluate --write` registers its depth and no path. The hooks still find a record beside the manifest, so an issue the migrate has not reached keeps working.
- **The distribution map is owed from two subtasks.** With fewer, `compass check` does not judge it, `compass next` does not name it, and the issue page, the board and the receipt say "not needed: one subtask". A map recorded as `omitted` keeps its meaning.
- **Review rounds are `review-<n>.md`,** registered under the kind `review` with a `round`. `compass issue artifact set` and `compass issue artifact-path` take `--round`; with none they read the latest round.
- **A spike owes its delivery-approach record and its conclusion.** `compass issue artifact set spike-conclusion --decision <discard|graduate-to-delivery|defer>` also writes the evidence record that `spike-conclusion-present` reads.
- **Six new kinds:** `architecture-notes`, `bug-report`, `positioning`, `product-owner-review`, `review` and `spike-conclusion`. A kind no approach owes can still be registered.
- **Six new block kinds:** `assessment`, `policy-rules`, `stage-weights` and `gate-set` in the delivery-approach record, and `plan-exit` and `breakdown-exit` in the Gate sections of the technical design and the distribution map.
- **`compass issue lint` reports a file in the documents folder whose name matches no kind.** It is one line per file and does not change the exit code. A name on the not-an-artifact list, such as `devlog.md`, a review brief or a builder's `result.md`, is not reported.
- **Two read-only fallbacks stay for the archive.** An issue stored on an earlier generation reads each missing descriptive field of a shipped kind from the shipped default. The receipt reads the assessment table of a record written before `justifications` existed.

### What `compass issue migrate` does

For each issue, in this order:

1. It plans every move first. Two plain review files that claim one round stop that issue: it is left byte for byte as it was, and the report names it. The other issues go on.
2. It sets the generated page aside, renames the filenames earlier releases retired and brings the manifest keys up to date, as before.
3. It re-points a registered `design` to `technical-design` and `prd` to `intent`, keeping each entry's id, status and path. It removes the `recommendation` entry and leaves its file.
4. It registers each document it moves before it moves it, the delivery-approach record first and then each review round in order. A file named for a kind is registered under that kind, unless the kind is already registered at another file that exists: that path is kept, the file is left where it is, and the report names both. A review round is renamed `review-<n>.md`: a plain `review-<n>` keeps its number, a bare `review` is round 1 when that is free, and the other review names (`verify-*`, `integrated-review-*`, `security-review`, `review-claims`) take the next free numbers.
5. It rewrites each manifest path that named a moved file: evidence, subtasks and gate evidence.
6. It removes the compatibility pointer beside the manifest when the registered record exists. A file there without the pointer's marker line is left and reported.
7. It renames a lightweight distribution map on an issue with fewer than two subtasks to `distribution-map.md.v6.bak`, byte for byte, and marks its entry `superseded` with a reason that names the backup. A map that names two or more subtasks is left. A map that was never registered is adopted with no depth and kept, because nothing says it was written only to meet the regular approach; the report lists it. The migrate writes no delivery-approach record for an issue that never had one.
8. It leaves a name on the not-an-artifact list where it is, and reports a name the mapping table does not know as unmapped, with the issue. Neither is registered.

Then the steps of the rendered-blocks section above run: the Definition of Done records, the status of done issues and the generation pin.

The dry run lists each move, rename, registration, re-point, pointer removal and stub rename, then the totals: documents by target kind, files left on the not-an-artifact list, unmapped files, pointers to remove and maps to rename. It writes nothing. A second `--apply` reports nothing to do. A migrate stopped part way finishes on the next `--apply`, and every issue stays workable in between, because the registry names the new path before the file moves.

**Copy first.** `--apply` renames files in `docs/compass/` as well as `.compass/work/`. Where git does not track either folder, it refuses without `--i-have-a-copy`, naming the folder. Nothing a person wrote is deleted: renames and moves keep the bytes, and the two things removed (each pointer and the one `recommendation` entry) are in your copy.

### What to do

1. Copy both folders to a folder outside the project: `.compass/work` and `docs/compass`.
2. Run `compass issue migrate` and read the per-issue lines and the totals. The totals alone do not show a wrong round number.
3. Run `compass issue migrate --apply --i-have-a-copy`. Its totals should equal the dry run's.
4. Run `compass issue lint` on every issue. No file should be reported outside the issues step 3 named.
5. Run `compass issue render --all --dry-run`, then `compass issue render --all`.
6. To go back, restore both folders from the copy, together. The rollback plan of the issue that added the catalogue fields gives the commands.

### New flags and keys

| Name | Where | Meaning |
|---|---|---|
| `owner`, `audience`, `stands_for`, `sections` | an artifact in the catalogue | Who writes the document, who reads it, its traditional name, and its headings per depth. Required with `file` and `stage` |
| `required_when: {subtasks: {min: N}}` | an artifact in the catalogue | The document is owed only with at least N subtasks |
| `every_approach: true` | an artifact in the catalogue | Every approach owes the document |
| `<n>` in `file` | an artifact in the catalogue | The kind repeats, one file per round |
| `--justify DIM=TEXT` | flag of `compass approach evaluate --write` | The justification of an assessed value |
| `justifications` | `manifest.yml`, beside `assessment` | One line per assessed dimension |
| `round` | an artifact entry in `manifest.yml` | The round of a kind that repeats |
| `--round N` | flag of `compass issue artifact set` and `compass issue artifact-path` | Name one round; the default is the latest |
| `--depth` | flag of `compass issue template show` | Print the lightweight or thorough skeleton |
| `--decision`, `--next-issue` | flags of `compass issue artifact set spike-conclusion` | Record how a spike closes |
| `distribution-map.md.v6.bak` | the documents folder | A stub map the migrate set aside |
