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

## The issue page on GitHub

Compass can now post an issue's README to the linked GitHub issue, and the verb that wrote labels on demand has a new spelling. The decision is `architecture/decisions/ADR-057-derived-views-go-to-github-one-way-behind-a-refusal-check.md`. The facts are in `docs/github-labels.md`.

### What is removed

- **The verb `compass issue labels sync`.** A command line that still types it exits 2, runs nothing and makes no `gh` call. It prints one line: `'issue labels sync' is now 'issue github sync'`. The hint row names release 6.0.0 and removal at 7.0.0.

### What changes

- **`compass issue github sync` replaces it.** It writes the labels and, when `page` is on, the issue page, each whatever the other's result. It exits non-zero when either failed or was refused. The sync failure line and the notes of `compass issue lint` name the new verb.
- **A new switch, `github_labels.page`, is off by default.** With it on, Compass posts the issue's README as one comment and, once, the ask into an empty issue body. It widens the audience of the issue's documents to the readers of the GitHub issue. Three checks refuse a post that holds a rival product name, a private path or a credential shape.
- **`github-sync.yml` holds two sections.** A record written by a 6.x CLI reads as the `labels` section. No migration is needed.

### What to do

1. Replace `compass issue labels sync` with `compass issue github sync` in your scripts, notes and CI.
2. Leave `page` off unless the readers of your GitHub issues may see your issue documents. To turn it on, set `github_labels: {page: true}` in `compass.yml`.
3. To have the name check run, set `record.names_key` before you turn `page` on. Without it the first post says so on standard error and posts.

### New keys and verbs

| Name | Where | Meaning |
|---|---|---|
| `github_labels.page` | `compass.yml` | Post the issue page to the linked GitHub issue |
| `compass issue github sync` | verb | Write the labels and the issue page on demand |
