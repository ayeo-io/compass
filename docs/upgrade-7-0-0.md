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

1. Run `compass issue migrate` for a dry run of the archive changes, then `compass issue migrate --apply --i-have-a-copy` after you copy `.compass/work` and `docs/compass` to a folder outside the project.
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

`compass issue migrate` (a dry run) lists, for each issue, what it would write. `--apply` writes it, and needs `--i-have-a-copy` where git does not track the work root or `docs/compass`. It only adds lines and records:

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
3. It re-points a registered `design` to `technical-design` and `prd` to `intent`, keeping each entry's id, status and path. It removes the `recommendation` entry and leaves its file. An entry the 6.x migrate registered under a review filename (`review` with no round, `review-2`, `integrated-review-3`) becomes the round its file becomes, keeping its id, status and approval. Where that round is already registered, by an earlier 7.0.0 run, the two entries become one, so each file keeps one entry. The merged entry keeps the later approval and the id of the entry that held it. When only one entry is approved, it keeps that approval and id. When neither is, it keeps the round entry's id and status, the more current record. Two entries whose files both exist are not merged: the report names both files for you to settle. The dry run and the apply name the id and approval kept and the id and approval dropped. An entry whose file is gone and that no document maps to is left, and the report says what to do.
4. It registers each document it moves before it moves it, the delivery-approach record first and then each review round in order. A file named for a kind is registered under that kind, unless the kind is already registered at another file that exists: that path is kept, the file is left where it is, and the report names both. A review round is renamed `review-<n>.md`: a plain `review-<n>` keeps its number, a bare `review` is round 1 when that is free, and the other review names (`verify-*`, `integrated-review-*`, `security-review`, `review-claims`) take the next free numbers.
5. It rewrites each manifest path that named a moved file: evidence, subtasks and gate evidence.
6. It removes the compatibility pointer beside the manifest when the registered record exists. A file there without the pointer's marker line is left and reported.
7. It renames a lightweight distribution map on an issue with fewer than two subtasks to `distribution-map.md.v6.bak`, byte for byte, and marks its entry `superseded` with a reason that names the backup. A map that names two or more subtasks is left. A map that was never registered is adopted with no depth and kept, because nothing says it was written only to meet the regular approach; the report lists it. The migrate writes no delivery-approach record for an issue that never had one.
8. It leaves a name on the not-an-artifact list where it is, and reports a name the mapping table does not know as unmapped, with the issue. Neither is registered.

Then the steps of the rendered-blocks section above run: the Definition of Done records, the status of done issues and the generation pin.

The dry run lists each move, rename, registration, re-point, pointer removal and stub rename, then the totals: documents by target kind, files left on the not-an-artifact list, unmapped files, pointers to remove and maps to rename. It writes nothing. A second `--apply` reports nothing to do. A migrate stopped part way finishes on the next `--apply`, and every issue stays workable in between, because the registry names the new path before the file moves.

**Copy first.** `--apply` renames files in `docs/compass/` as well as `.compass/work/`. Where git does not track a folder, it refuses without `--i-have-a-copy`, naming every folder it cannot restore in one refusal. Nothing a person wrote is deleted: renames and moves keep the bytes, and the three things removed are in your copy: each pointer, the one `recommendation` entry, and a registry entry that merges into another entry for the same file. A merged entry can hold an older approval; the migrate keeps the newer approval and names the dropped entry's id and approval in its report, in the dry run as well as the apply.

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

## Checkpoint outcomes and usage

Compass now records what happened at each stage hand-off and what each issue cost. The decision is `architecture/decisions/ADR-063-checkpoint-outcomes-and-session-usage-are-stored-and-the-autonomy-and-cost-figures-are-derived.md`, and `docs/autonomy-and-cost.md` owns the facts.

### What changes

- **A person's answer to a hand-off is a record.** `compass evidence approve --checkpoint <stage>` writes a `checkpoint-approval` record and a `waited` outcome. The record is not a `human-approval` record, so it never clears the sign-off of guardrail `G5` or a human check.
- **An agent records a hand-off that autonomy passed.** `compass issue checkpoint add <stage> --outcome skipped --by <agent>` replaces the devlog line the stage commands asked for.
- **`compass ship-commit` refuses an unanswered listed checkpoint.** It refuses a judged issue that lists a checkpoint with no outcome, before it writes anything, with the code `checkpoint-no-outcome`. A judged issue is one whose first assessment wrote `checkpoint_outcomes`. An issue assessed before this change is never refused, and no migrate adds the key.
- **The pre-tool hook records each session.** The first time it judges a tool call for an issue, it appends the session id to `usage.sessions`. It never refuses an edit because of it. Every issue folder gains an empty `.manifest.lock` file.
- **`compass ship-commit` records usage on every approach but the quick fix.** It reads the full transcripts of the recorded sessions and keeps numbers only. Above 1 GiB of transcript it reads none and records the reason `too-large`.
- **`compass retro --impact` gains four rows**, the autonomy ratio, the band split, the cost per change and the decisions confirmed, each withheld below its floor. `compass retro --impact --json` and `compass retro --impact --format json` print one object. Before, `--json` printed the report's lines under an `output` key.
- **`compass issue diagnose` gains a Checkpoints and cost section**, and its last line of what the records cannot show now reads "token use of a session the hook did not record".

### What to do

1. Nothing for issues already assessed. They read, lint and land as before.
2. Answer each listed hand-off of a new issue with `compass evidence approve --checkpoint <stage>` at a terminal before you ship it.
3. Add `.manifest.lock` to the `.gitignore` of a project that tracks its issue folders.

## Repository readiness and autonomous work

From 7.0.0 a project on `autonomy: autonomous` must meet the readiness floor before an issue can be assessed. An autonomous project below the floor, or with no fresh readiness record, is refused at `compass approach evaluate --write`, which every assess and reassess runs. The decision is `architecture/decisions/ADR-058-the-readiness-floor-caps-autonomous-work.md`. The facts are in `docs/readiness.md`.

### What breaks

- **An autonomous project below the readiness floor is refused at assess.** `approach evaluate --write` exits 2 and writes nothing. The message names each absent readiness signal with the change that makes it present, and names `autonomy` as the setting to change.
- **An autonomous project with no fresh readiness record is refused.** The message says whether the record is missing, stale or unreadable, and names `compass readiness`.
- **An untrusted CI contribution cannot run an autonomous project.** Trust is read from the CI runner's environment before the record, so a record committed with the contribution does not count. No setting changes this. Measuring again does not help, so the message does not ask for it.

### What changes

- **The four required signals** form the floor: `agent-instructions-present`, `build-declared-and-succeeds`, `tests-declared-and-under-two-minutes` and `lint-declared-and-clean`. The floor is met when each is present.
- **`compass readiness`** measures the repository against eleven readiness signals and writes `.compass/readiness.yml`. `compass readiness --fix-list` lists the absent ones, those on the floor first, with the change for each.
- **Six optional project keys** in `compass.yml`: `project.lint_command`, `project.format_check_command`, `project.build_command` and `project.typecheck_command`, which `compass readiness` runs, and `project.secret_scan` and `project.structured_logging`, which it only reads.
- **The readiness line.** Every `approach evaluate --write` records the repository's readiness in the manifest's `readiness:` key, outside the generation, so a new measurement never forces a new generation. On an autonomous project below the floor, or with no fresh record, a session starts with one warning line. The session is never blocked.
- **The floor is not a guardrail.** No gate, routing rule or `compass check` result names a readiness signal.

### Who is never refused

- A project on `balanced` or `controlled`. Its manifest records the readiness summary, or "not measured", and nothing else changes.
- A project with no settings file, because `autonomy` defaults to `balanced`.
- An issue whose own `config:` sets `autonomy: balanced` or `controlled`, even on an autonomous project.

`balanced` and `controlled` are never refused.

### The readiness record

- It is per checkout and never committed. A fresh clone has none. Add `/.compass/readiness.yml` to `.gitignore`.
- It goes stale when the settings file changes, when a readiness signal's implementation version changes, after seven days, or once HEAD is more than 25 commits past the commit it measured.
- It is a plain file a person can edit, as the project commands themselves are. The floor is a guard against an unready repository, not against a person who edits the record.

### The commands

- `compass readiness` runs a project command only when `allow_project_commands: true` is set and the contribution is trusted.
- Every project command runs in a clean checkout of HEAD, in a temporary worktree, so a command that needs installed dependencies must set them up itself.
- One run finishes within five minutes. The test command must pass within two minutes.
- A CI job that assesses autonomous work runs `compass readiness` as a step before assess, because the CI checkout has no record.

### What to do

On an autonomous project, run `compass readiness`. If it reports the floor as not met, take one of three ways to carry on:

1. **Change `autonomy`** to `balanced` or `controlled` in `compass.yml`. The stage hand-offs that value lists then wait for a person.
2. **Make the absent signals present.** `compass readiness --fix-list` names the change for each, such as declaring `project.build_command`. For a long suite, set the test signal's `command` parameter to `test_micro_command` in a project layer, and declare a micro suite that passes within two minutes.
3. **Set `required_for_autonomous: false`** on a readiness signal in a project layer. That takes the signal off the floor, so it needs the owner's waiver in the same entry:

   ```yaml
   readiness:
     tests-declared-and-under-two-minutes:
       set: {required_for_autonomous: false}
       waiver:
         reason: our suite runs in a merge queue, not before each change
         approved_by: <owner>
         approved_on: 2026-10-13
   ```

Then run `compass readiness` again and assess.

### New verbs, flags and keys

| Name | Where | Meaning |
|---|---|---|
| `compass readiness [--json] [--fix-list]` | verb | Measure the repository and write the readiness record, or list the absent signals from a fresh record |
| `project.lint_command`, `project.format_check_command`, `project.build_command`, `project.typecheck_command` | `compass.yml` | The project commands `compass readiness` runs |
| `project.secret_scan`, `project.structured_logging` | `compass.yml` | Declarations; a non-empty string makes the signal present |
| `readiness` | catalogue in a preset or project layer | The readiness signals |
| `required_for_autonomous` | field of a readiness signal | `true` puts the signal on the floor |
| `.compass/readiness.yml` | per checkout, never committed | The readiness record |
| `readiness` | `manifest.yml` | The repository's readiness when the issue was assessed |

## The issue page on GitHub

Compass can now post an issue's README to the linked GitHub issue, and the verb that wrote labels on demand has a new spelling. The decision is `architecture/decisions/ADR-057-derived-views-go-to-github-one-way-behind-a-refusal-check.md`. The facts are in `docs/github-labels.md`.

### What is removed

- **The verb `compass issue labels sync`.** A command line that still types it exits 2, runs nothing and makes no `gh` call. It prints one line: `'issue labels sync' is now 'issue github sync'`. The hint row names release 6.0.0 and removal at 7.0.0.

### What changes

- **`compass issue github sync` replaces it.** It writes the labels and, when `page` is on, the issue page, each whatever the other's result. It exits non-zero when either failed or was refused. The sync failure line and the notes of `compass issue lint` name the new verb.
- **A new switch, `github_labels.page`, is off by default.** With it on, Compass posts the issue's README as one comment and, once, the ask into an empty issue body. It widens the audience of the issue's documents to the readers of the GitHub issue. Two checks refuse a post that holds a private path or a credential shape.
- **`github-sync.yml` holds two sections.** A record written by a 6.x CLI reads as the `labels` section. No migration is needed.

### What to do

1. Replace `compass issue labels sync` with `compass issue github sync` in your scripts, notes and CI.
2. Leave `page` off unless the readers of your GitHub issues may see your issue documents. To turn it on, set `github_labels: {page: true}` in `compass.yml`.

### New keys and verbs

| Name | Where | Meaning |
|---|---|---|
| `checkpoint_outcomes` | `manifest.yml` | One outcome, `waited` or `skipped`, for each checkpoint stage |
| `checkpoint-approval` | the type of an evidence record | A person's answer to one checkpoint hand-off |
| `usage.sessions`, `usage.total`, `usage.unattributed` | `manifest.yml` | The sessions that worked on the issue, and what they cost |
| `too-large`, `no-window` | reasons in a `usage` block | Transcripts over the read limit, and a stage no record ends |
| `checkpoint-no-outcome` | a refusal code | The landing refusal |
| `compass evidence approve --checkpoint` | a flag | Answer a hand-off |
| `compass issue checkpoint add` | a verb | Record a hand-off that autonomy passed |
| `github_labels.page` | `compass.yml` | Post the issue page to the linked GitHub issue |
| `compass issue github sync` | verb | Write the labels and the issue page on demand |

## Guardrail `G5` counts only its own sign-off

`human-approval-present`, the check of guardrail `G5` ("a human signs off on the irreversible"), counts only a `human-approval` record given for guardrail `G5`. An approval given for another human check no longer clears the sign-off on an irreversible change. The decision is `architecture/decisions/ADR-066-an-approval-names-its-subject-and-guardrail-5-counts-only-an-approval-given-for-it.md`.

### What breaks

- **An in-flight issue whose only approval names another subject now fails.** A `human-approval` record that holds a `check`, `waiver`, `checkpoint`, `artifact` or `decisions` key, or a `guardrail` other than exactly `G5`, is set aside. So `compass evidence approve --check dod-reviewed` no longer clears the payments sign-off. The failure names the record, the subject it was given for and the command below.

### What changes

- **A person records the sign-off with `compass evidence approve --guardrail` and the value `G5`.** The full command is below. It needs a terminal and refuses the approver `agent`. It writes a `human-approval` record whose `guardrail` key holds `G5`, with no `check` key. It records an approval only, so it refuses `--decision rejected`, and it refuses any guardrail but `G5`.
- **A sign-off recorded the earlier way still counts.** A `human-approval` record with no subject key is a sign-off given for guardrail `G5`. No stored record is rewritten.
- **An in-flight issue can now pass where it failed.** The check cites the first approved record given for guardrail `G5`. An incomplete approval of another subject recorded first no longer hides a complete sign-off, so that issue moves from fail to pass.
- **A landed issue is reported, never failed.** When the new rule fails a landed issue and the earlier rule passes it, the check passes and says it is reported only.
- **The check is version 1.1.0.** Its fixture corpus verdicts did not change, so it keeps major version 1, and `compass check` judges an issue whose generation recorded 1.0.0.

### What to do

1. Run `compass check` on each open issue that guardrail `G5` applies to. Where `human-approval-present` fails with "no approval was given for guardrail `G5`", a person runs this before the issue lands:

   ```
   compass evidence approve --guardrail G5 --approver <name> --role <role> --scope <text>
   ```

2. Update scripts that write `human-approval` records for the sign-off: set the `guardrail` key to `G5`, or write no subject key.

### New keys and verbs

| Name | Where | Meaning |
|---|---|---|
| `compass evidence approve --guardrail` | a flag, whose only value is `G5` | Record the sign-off of guardrail `G5` |
| `guardrail` | an evidence record of type `human-approval` | The guardrail the sign-off is for; only `G5` is read |

## The lightweight intent and the release line

A regular issue now opens with a short intent, and every issue that ships records one release line for the release notes. The decision is `architecture/decisions/ADR-065-regular-issues-owe-an-intent-and-shipping-issues-record-a-release-line.md`. `docs/release-line.md` owns the facts of the release line, and `docs/release-notes.md` those of the release notes.

### What changes

- **The regular approach owes `intent` at depth `lightweight`.** It has four headings: Problem, Desired outcome, Success signals and Non-goals. The router drafts it at assess from the issue description, and the spec author corrects it at define. `compass analyze` checks each scenario's intent id against it, and `compass ship-commit` refuses a regular issue while the intent is unwritten, through the check `artifacts-approved`.
- **A new approach field, `release_line`.** Quick fix, regular, hotfix and full set it `true` in the shipped default. The spike has no such field. Setting it `false` on an approach that has it is a loosening and needs a waiver.
- **A new manifest key, `release_note`.** `compass acceptance record`, `compass ship-commit` and `compass quick-fix finish` write it with `--release-note "<text>"`. The latest write wins. A blank line, a line that starts with `#`, and a line the living spec's title rules refuse are refused before anything is written.
- **Every landing refuses an issue that owes a line and has none**, with the code `release-line-missing`. An issue owes one only when its stored generation sets `release_line: true` on its approach and the issue is neither completed nor closed.
- **The verification report gains a `## Release line` section** with the rendered block `release-line`. A report written before this change has no marker and is left as it is.
- **A new verb, `compass release notes --since <ref>`**, prints the release line of each shipping issue completed after a git reference. It writes nothing.

### What to do

1. Nothing for issues already assessed. An open issue owes an intent and a release line only after `compass approach evaluate --write` commits a generation from the new default. A completed or closed issue never does.
2. Give each new shipping issue its line before it lands: `compass ship-commit --issue <slug> --release-note "<text written for a user>"`, or the same flag on `quick-fix finish` or `acceptance record`.

### New keys and verbs

| Name | Where | Meaning |
|---|---|---|
| `release_line` | an approach in the catalogue | Whether an issue on the approach owes a release line |
| `release_note` | `manifest.yml` | The issue's release line |
| `--release-note` | a flag of `compass ship-commit`, `compass acceptance record` and `compass quick-fix finish` | Write the release line |
| `release-line-missing`, `release-line-heading` | refusal codes | A landing of an issue that owes a line and has none, and a line that starts with `#` |
| `release-line` | a rendered block kind | The release line in the verification report |
| `compass release notes --since <ref>` | a verb | Print the release lines since a git reference |
