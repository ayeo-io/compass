# Upgrading to 7.0.0

This page says how to move a project from Compass 6.x to 7.0.0. Each section is one change: what breaks, what changes and what to do. The decision records are in `architecture/decisions/`. To go on to 9.0.0, read `docs/upgrade-9-0-0.md`.

Do these steps for every upgrade to 7.0.0:

1. Update the Compass plugin in every checkout. Do not run a 6.x CLI on a 7.0.0 tree.
2. Copy `.compass/work` and `docs/compass` to a folder outside the project.
3. Replace each removed spelling in your scripts, notes and CI (the first section).
4. Run `compass issue migrate`, read the list, then run `compass issue migrate --apply --i-have-a-copy`.
5. Run `compass issue render --all --dry-run`, then `compass issue render --all`.
6. Run `compass policy lint`, and `compass check` on each open issue.

## The released spellings end, and the old readers stay until 9.0.0

7.0.0 removes the command spellings that 6.0.0 renamed. The readers for old words, old approach names, copied 5.x governance and `.compass/config.yml` (when `compass.yml` is absent) stay until 9.0.0. The decision is `governance/decisions/2026-10-25-legacy-readers-readable-until-9-0-0.md`.

### What is removed

Each old spelling exits 2 with the parser's usual error. The error names no new spelling, except for `issue dashboard` and `issue labels sync`.

| Old | New |
|---|---|
| `approach summary` | `approach show` |
| `issue set-status` | `issue status set`, or `issue status remove` for `active` |
| `policy review-rules` | `review-rule list` |
| `issue dashboard` | `issue render` |
| `issue artifact` | `issue artifact set` |
| `migrate` | `issue migrate` |
| `issue subtask update` | `issue subtask set` |
| `run --stage build` | `run --stage implement` |
| `issue labels sync` | `issue github sync` |

### What is kept until 9.0.0

- **Old words** in a manifest, a policy or a flag, such as the stage mode `full` and the size `standard`. `compass policy migrate --words` rewrites a project's `compass.yml`.
- **Old approach names.**
- **Copied 5.x governance** and the generated views `governance/routing-policy.yml` and `governance/guardrails.yml`.
- **`.compass/config.yml`**, when `compass.yml` is absent. `compass policy migrate` moves its settings into `compass.yml`.

### What to do

1. Copy `.compass/work` and `docs/compass` to a folder outside the project. Then replace each removed spelling in your scripts, notes and CI.
2. Run `compass policy migrate --words` and `compass policy migrate` before 9.0.0. 9.0.0 has neither command.

## Artifact status and decisions taken

Stage commands write the status of each registered document. A document that is not accepted does not ship. The decision is `architecture/decisions/ADR-050-artifact-status-is-written-by-stage-exits-and-by-a-persons-approval.md`.

### What changes

- **Stage commands write status.** `compass issue artifact set` with a path, `compass issue subtask add`, `compass tdd-red`, `compass acceptance record`, `compass gate pass` on a `verify` gate and `compass ship-commit` move the `draft` documents of earlier stages. A document with no human check becomes `approved`. A document with a human check becomes `awaiting-approval`.
- **`approved_by` names a person or a command**, such as `compass tdd-red`. `approved_at` holds the time.
- **A person approves with `compass evidence approve --artifact <kind>`.** It needs a terminal and refuses the approver `agent`. It writes an `artifact-approval` record. That is not a `human-approval` record, so it never clears the sign-off of guardrail `G5`. <!-- vocabulary-scan: allow - the 7.0.0 guide records the flag 9.0.0 removed (ADR-091) -->
- **`compass issue artifact set --status approved` refuses a document with a human check.**
- **A changed file moves an approved document back to `draft`** when it is registered again.
- **`compass issue artifact set` records the document's digest on every registration.** The stale-document refusals stay behind the capability `artifact-freshness`.
- **A re-assessment keeps a written document as `superseded`** when the new approach no longer registers it.
- **`compass ship-commit` refuses an unapproved document.** The blocking check `artifacts-approved` fails on a document that reads `draft` or `awaiting-approval`, and on one omitted with no reason. Write the document, or omit it with `compass issue artifact set <kind> --status omitted --reason "<why>"`.
- **`compass quick-fix finish` approves the quick fix's document** after `compass check` passes.
- **A project artifact with no `stage` is owned by ship.** Add `stage: <stage>` to its catalog entry to have an earlier stage approve it.
- **`compass issue migrate` settles the status of done issues.** Each `draft` or `awaiting-approval` document becomes `approved` (close reason `completed`) or `superseded` (`not-planned` or `duplicate`), with the reason "migrated from a 6.0.0 record". Open issues are left as they are.
- **A decision an agent took for the person is shown at the next checkpoint.** `compass issue decision add` (and `--from-ledger`) records it in `decisions_taken`. On `balanced` and `controlled` autonomy, `compass next` waits until a person confirms the set with `compass evidence approve --decisions` or reopens one with `compass issue decision set`. On `autonomous` it lists the decisions and does not wait. The confirmation is an `artifact-approval` record.
- **The retro's `--decisions` flag** reports the share confirmed, changed and never confirmed. 9.0.0 removed the retro (ADR-093).

### What to do

1. Copy the two folders and run `compass issue migrate`, as the steps at the top of this page say.
2. Open issues gain the `artifacts-approved` check at their next `compass approach evaluate --write`.

## Rendered blocks and the issue page

Compass writes the status, ticks and counts in an issue's documents from the manifest and the evidence. `compass check` fails a document that disagrees with them. Each issue gets an issue page, a quick fix gets a verification note, and the project gets an index. The decision is `architecture/decisions/ADR-051-rendered-blocks-are-derived-in-place-and-checked.md`. The facts are in `docs/rendered-blocks.md`.

### What is removed

- **The verb `compass issue dashboard render` and its alias.** It exits 2 with the parse error and one line: `'issue dashboard' is now 'issue render'`.
- **The check `dashboard-current`.** `rendered-blocks-current` replaces it. `compass check` reports the removed check in a stored generation, or in a copied 5.6.0 governance folder, as "nothing to check" and runs the replacement.
- **The reminder to run the old verb.** The documents are rendered after each command that changes a record.
- **The generated `README.md` beside the manifest** in `.compass/work/<issue>/`. Migration keeps each one as `README.md.v6.bak`. The issue page is `docs/compass/<created>-<issue>/README.md`.

### What changes

- **Ticks move from the page to the manifest.** The Definition of Done is the `verify` exit list and the Definition of Ready is the `plan` entry list. A box ticked by hand counts for nothing. A record meets an item:
  - `compass gate pass ... --meets CHECK` and `compass evidence add ... --meets CHECK` meet an item with evidence of an accepted type.
  - `compass evidence approve --check <item>` records a person's tick. It needs a terminal.
  - `compass follow-up add FU-ID --defers CHECK --summary TEXT` carries an item to a follow-up.
- **`dod-evidence-typed` is implementation 2.0.0** and reads these records. A closed issue whose verification report has no Definition of Done heading and no `dod` block reads "nothing to check".
- **Cross-issue blocks are advisory:** the `related` block, the governance lines of `decisions` and the index row never fail `rendered-blocks-current`.
- **A stale block drawn from the issue's own records fails at `verify`, `ship` and done.** Before that it is advisory. The fix is `compass issue render`.
- **`compass ship-commit` renders the done state before it commits.** `compass quick-fix finish` writes the verification note.
- **`dod-every-scenario-passes`, `dod-suite-green` and `dod-coverage-floor` name the report sections** "Scenario acceptance results" and "Test suite evidence", not `§1` and `§2`. A stored generation keeps its wording.

### What `compass issue migrate` does

`compass issue migrate` is a dry run. `--apply` writes, and needs `--i-have-a-copy` where git could not restore an issue folder (see **Copy first** below). It only adds lines and records:

1. It inserts an empty `dod` marker pair after the Definition of Done section of the verification report.
2. It writes `meets`, `defers` and `page_ticks` records from the boxes of that section. A ticked box becomes a page tick. A page tick counts as met on the page and is never a person's approval for `G5`. A tag that names an unknown id, or evidence of a type the list does not accept, writes no record: the item stays open and the report names it.
3. It writes an empty verification note for each quick fix closed as completed.
4. It renames each generated `README.md` beside a manifest to `README.md.v6.bak`, byte for byte. A `README.md` you wrote is not touched.
5. It pins the stored generation of an issue that records an implementation major this CLI lacks (`dod-evidence-typed` 1.x), so the check runs. When the next generation folder holds a file that a generation commit does not write, the issue is not pinned and the report names the file.
6. It reports a verification report with no Definition of Done heading. That report gets no marker and no record.

It prints the items it could not record on every run. A second `--apply` changes no file.

### What to do

1. Do steps 2, 4 and 5 at the top of this page.
2. Record each open item the migration printed, with the commands above.
3. To go back, restore both folders from the copy.

### New verbs, flags and keys

- `compass issue render [--issue SLUG] [--all] [--dry-run]` rewrites the rendered blocks, the issue page and the project index.
- `compass follow-up add FU-ID [--defers CHECK] --summary TEXT [--target SLUG]` records a follow-up.
- `rendered-blocks-current` is a check in `G4`.
- `evidence[].meets`, `follow_ups[].defers` and `page_ticks` are the manifest records that meet an item. Only migration writes `page_ticks`.
- `<!-- compass:render KIND -->` starts a block Compass writes. Do not edit between the markers.

## The artifact catalog, the delivery-approach record and the archive

The artifact catalog describes each document: who writes it, who reads it, its traditional name and its sections. The delivery-approach record is in the documents folder on every approach. Each assessed value carries a justification. A review round is a file of its own. `compass issue migrate` moves and renames the archive's documents to match. The decisions are ADR-053 to ADR-056 in `architecture/decisions/`. The facts are in `docs/artifact-catalog.md`.

### What breaks

- **An added artifact kind needs five more fields.** A project that declares a kind the shipped default does not declare stops resolving with `M-ADD-PARTIAL`. The entry needs `stage`, `owner`, `audience`, `stands_for` and `sections` beside `file`. There is no flag and no alias.
- **`compass approach evaluate --write` refuses a value with no justification.** A new or changed value of risk, familiarity, size, goal, role or urgency needs `--justify DIM=TEXT`. An unchanged assessment, and an archived issue with no `justifications` key, are not refused.
- **`compass quick-fix start --goal` and `--role` need a reason:** `--goal VALUE - REASON`. Leave the flag out and the dimension is recorded as not assessed.
- **`compass issue artifact set --path` refuses a path outside the kind's home**, `docs/compass/<created>-<issue>/<file>`.
- **The spike conclusion's flag is `--next-issue`:** `compass issue artifact set spike-conclusion --decision graduate-to-delivery --next-issue <slug>`. It has no alias.
- **The migrate renames and moves documents.** Review rounds become `review-<n>.md`, the delivery-approach record moves into the documents folder, and a one-subtask stub map becomes `distribution-map.md.v6.bak`. Change each script or note that names an old filename.
- **The migrate removes the compatibility pointer.** A `pre-tool.sh` hook installed before 5.0.0 then blocks every edit. Update the plugin before you migrate.
- **Two new blocking checks can fail a new issue at `verify`.** Both report `nothing to check` on an issue stored before they existed, on a closed issue, and when the document is not registered. The shipped preset places neither on a gate, a stage or an artifact. The rules are in `governance/guardrails.md`.
  - `nfr-rows-resolved` fails when a row of the spec's Non-functional requirements table names no scenario and gives no reason.
  - `contracts-declared` fails when a changed file is a trigger path and the design's Data and interfaces section declares no contract. To add trigger paths, set the whole `trigger_paths` list in the project layer. Removing or replacing an entry needs a project waiver where the check is placed.
- **A heading carries no number.** Templates and section lists name headings without `1.` or `4a.`. A numbered document written earlier is still read.

### What changes

- **`compass issue template show <kind>` prints a skeleton** built from the catalog, at `--depth lightweight` or `thorough`. It opens with a `document-header` block.
- **Four sections are new:** Non-functional requirements (the spec), and Data and interfaces, Verification plan and Risks and dependencies (the design). The role block `How each role reads this file` is gone from every template.
- **Two new block kinds:** `document-header` opens every document written from a template. `dependencies` lists the design's `depends_on` entries.
- **The `coverage` block gains a Kind column** when the technical design has a `## Verification plan` heading. It shows the planned kind of test: `unit`, `integration`, `acceptance`, `judged review` or `manual`, else `not planned` or `unknown (<word>)`. `compass issue lint` prints a note for an unknown kind.
- **`compass quick-fix start` renders the record,** with `document-header`, `assessment` and `policy-rules` blocks. The `**Approach:**` line is gone.
- **The delivery-approach record is in the documents folder on every approach.** The hooks still find a record beside the manifest.
- **The distribution map is owed from two subtasks.** With fewer, `compass check` does not judge it.
- **Review rounds are `review-<n>.md`,** registered under the kind `review` with a `round`. `compass issue artifact set` and `compass issue artifact-path` take `--round`. The default is the latest round.
- **A spike owes its delivery-approach record and its conclusion.** `compass issue artifact set spike-conclusion --decision <discard|graduate-to-delivery|defer>` also writes the evidence record that `spike-conclusion-present` reads.
- **Six new kinds:** `architecture-notes`, `bug-report`, `positioning`, `product-owner-review`, `review` and `spike-conclusion`.
- **Six new block kinds:** `assessment`, `policy-rules`, `stage-weights`, `gate-set`, `plan-exit` and `breakdown-exit`.
- **`compass issue lint` reports a file in the documents folder whose name matches no kind.** It does not change the exit code. A name on the not-an-artifact list, such as `devlog.md`, is not reported.

### What `compass issue migrate` does

For each issue, in this order:

1. It plans every move first. Two plain review files that claim one round stop that issue. It is left byte for byte, and the report names it.
2. It keeps the generated page as a backup, renames the filenames earlier releases retired and brings the manifest keys up to date.
3. It re-points a registered `design` to `technical-design` and `prd` to `intent`, and keeps each entry's id, status and path. It removes the `recommendation` entry and leaves its file.
4. It gives an entry registered under a review filename the round its file becomes. Where that round is already registered, the two entries become one. The merged entry keeps the later approval and its id, and the report names what was kept and dropped. Two entries whose files both exist are not merged: the pair is left as it is, entries and files, until a person settles it.
5. It registers each document before it moves it. A review round is renamed `review-<n>.md`: a plain `review-<n>` keeps its number, a bare `review` is round 1 when that is free, and the other review names take the next free numbers. A file whose kind is already registered at another file that exists is left where it is, and the report names both.
6. It rewrites each manifest path that named a moved file.
7. It removes the compatibility pointer beside the manifest when the registered record exists.
8. It renames a lightweight distribution map on an issue with fewer than two subtasks to `distribution-map.md.v6.bak`, and marks its entry `superseded`. It leaves a map that names two or more subtasks, declares `units: 1`, was never registered, or has a path outside the project.
9. It reports a name the mapping table does not know as unmapped. It leaves a name on the not-an-artifact list.

Then the steps of the rendered-blocks section run.

The dry run lists each change and the totals, and writes nothing. A dry run after `--apply` reports what a second `--apply` would do: nothing, on a migrated archive. A document in both places, beside the manifest and in `docs/compass`, is an item for you until you delete one copy. A migrate stopped part way finishes on the next `--apply`.

**Copy first.** `--apply` renames files in `docs/compass/` as well as `.compass/work/`.

- Without `--i-have-a-copy`, the check judges each issue folder under both. It needs every file in it that the migrate can change committed and unchanged. A staged file, or a committed file edited since, does not count.
- The check refuses in one refusal, naming each root it cannot restore, with a count and the first five folders. It also refuses a root whose real path is outside the git repository, and a git call that fails. Outside a git repository it passes.
- The copy command the refusal names, `cp -RH`, follows a root that is a symbolic link.
- To undo an apply with git, run `git reset --hard`, then `git clean -fd -- .compass/work docs/compass`. `git clean` removes every untracked file in those folders, including a file you wrote and never committed. Run `git clean -n -d -- .compass/work docs/compass` first: it lists what would be removed and removes nothing.
- Renames and moves keep the bytes. The migrate removes only each pointer, the one `recommendation` entry, and a registry entry that merges into another. Each is in your copy.

### What to do

1. Copy both folders to a folder outside the project: `.compass/work` and `docs/compass`.
2. Run `compass issue migrate` and read the per-issue lines and the totals. The totals alone do not show a wrong round number.
3. Run `compass issue migrate --apply --i-have-a-copy`. Its totals must equal the dry run's.
4. Run `compass issue lint` on every issue. No file should be reported outside the issues step 3 named.
5. Run `compass issue render --all --dry-run`, then `compass issue render --all`.
6. To go back, restore both folders from the copy, together.

### New flags and keys

| Name | Where | Meaning |
|---|---|---|
| `owner`, `audience`, `stands_for`, `sections` | an artifact in the catalog | Who writes the document, who reads it, its traditional name, and its headings per depth |
| `required_when: {subtasks: {min: N}}` | an artifact in the catalog | The document is owed only with at least N subtasks |
| `every_approach: true` | an artifact in the catalog | Every approach owes the document |
| `<n>` in `file` | an artifact in the catalog | The kind repeats, one file per round |
| `justifications` | `manifest.yml`, beside `assessment` | One line per assessed dimension |
| `round` | an artifact entry in `manifest.yml` | The round of a kind that repeats |

## Checkpoint outcomes and usage

Compass records what happened at each stage hand-off and what each issue cost. The decision is `architecture/decisions/ADR-063-checkpoint-outcomes-and-session-usage-are-stored-and-the-autonomy-and-cost-figures-are-derived.md`. `docs/checkpoints.md` owns the facts that 9.0.0 kept. 9.0.0 removed the session record, the usage record, the retro and the cost section of `compass issue diagnose` (ADR-093).

### What changes

- **A person's answer to a hand-off is a record.** `compass evidence approve --checkpoint <stage>` writes a `checkpoint-approval` record and a `waited` outcome. It never clears the sign-off of guardrail `G5` or a human check.
- **An agent records a hand-off that autonomy passed** with `compass issue checkpoint add <stage> --outcome skipped --by <agent>`.
- **`compass ship-commit` refuses an unanswered listed checkpoint** with the code `checkpoint-no-outcome`. An issue assessed before this change is never refused.
- **The pre-tool hook records each session** in `usage.sessions`. Every issue folder gains an empty `.manifest.lock` file.
- **`compass ship-commit` records usage on every approach but the quick fix.** It keeps numbers only. Above 1 GiB of transcript it reads none and records the reason `too-large`.
- **The retro's `--impact` view gains four rows.** With `--json` it prints one object.
- **`compass issue diagnose` gains a Checkpoints and cost section.**

### What to do

1. Nothing for issues already assessed.
2. Answer each listed hand-off of a new issue with `compass evidence approve --checkpoint <stage>` at a terminal before you ship it.
3. Add `.manifest.lock` to the `.gitignore` of a project that tracks its issue folders.

## Repository readiness and autonomous work

A project on `autonomy: autonomous` must meet the readiness floor before an issue can be assessed. The decision is `architecture/decisions/ADR-058-the-readiness-floor-caps-autonomous-work.md`. 9.0.0 removed the floor, the `readiness` verb and its page (ADR-093).

### What breaks

`compass approach evaluate --write` exits 2 and writes nothing for an autonomous project that:

- is below the readiness floor. The message names each absent readiness signal and the change that makes it present.
- has no fresh readiness record. The message says whether the record is missing, stale or unreadable.
- is run by an untrusted CI contribution. No setting changes this.

### What changes

- **The floor is four required signals:** `agent-instructions-present`, `build-declared-and-succeeds`, `tests-declared-and-under-two-minutes` and `lint-declared-and-clean`.
- **The `readiness` verb** measures the repository against eleven readiness signals and writes `.compass/readiness.yml`. Its `--fix-list` lists the absent ones with the change for each.
- **The readiness record is per checkout and never committed.** Add `/.compass/readiness.yml` to `.gitignore`. It goes stale when the settings file changes, when a signal's implementation version changes, after seven days, or once HEAD is more than 25 commits past the commit it measured.
- **The verb runs a project command only when `allow_project_commands: true` is set and the contribution is trusted.** Each command runs in a clean checkout of HEAD, in a temporary worktree. The test command must pass within two minutes.
- **Six optional project keys** in `compass.yml`: `project.lint_command`, `project.format_check_command`, `project.build_command`, `project.typecheck_command`, `project.secret_scan` and `project.structured_logging`.
- **The floor is not a guardrail.** No gate, routing rule or `compass check` result names a readiness signal.

### Who is never refused

`balanced` and `controlled` are never refused:

- a project on `balanced` or `controlled`;
- a project with no settings file, because `autonomy` defaults to `balanced`;
- an issue whose own `config:` sets `autonomy: balanced` or `controlled`.

### What to do

On an autonomous project, run the `readiness` verb. A CI job that assesses autonomous work must run it before assess. If the floor is not met, do one of these, then run the verb again and assess:

1. **Change `autonomy`** to `balanced` or `controlled` in `compass.yml`.
2. **Make the absent signals present.** `--fix-list` names the change for each. For a long suite, set the test signal's `command` parameter to `test_micro_command` in a project layer, and declare a micro suite that passes within two minutes.
3. **Set `required_for_autonomous: false`** on a readiness signal in a project layer. This needs the owner's waiver in the same entry:

   ```yaml
   readiness:
     tests-declared-and-under-two-minutes:
       set: {required_for_autonomous: false}
       waiver:
         reason: our suite runs in a merge queue, not before each change
         approved_by: <owner>
         approved_on: 2026-10-13
   ```

## The issue page on GitHub

Compass can post an issue's README to the linked GitHub issue. The decision is `architecture/decisions/ADR-057-derived-views-go-to-github-one-way-behind-a-refusal-check.md`. 9.0.0 removed the label sync, the issue page and `compass issue github sync` (ADR-093). `docs/github-links.md` owns `compass issue link set`, which stays.

### What is removed

- **The verb `compass issue labels sync`.** It exits 2, runs nothing and prints one line: `'issue labels sync' is now 'issue github sync'`.

### What changes

- **`compass issue github sync` replaces it.** It writes the labels and, when `page` is on, the issue page. It exits non-zero when either failed or was refused.
- **A new switch, `github_labels.page`, is off by default.** With it on, Compass posts the issue's README as one comment and, once, the ask into an empty issue body. The readers of the GitHub issue then see the issue's documents. Two checks refuse a post that holds a private path or a credential shape.
- **`github-sync.yml` holds two sections.** A record written by a 6.x CLI reads as the `labels` section.

### What to do

1. Replace `compass issue labels sync` with `compass issue github sync` in your scripts, notes and CI.
2. Leave `page` off unless the readers of your GitHub issues may see your issue documents. To turn it on, set `github_labels: {page: true}` in `compass.yml`.

### New keys

| Name | Where | Meaning |
|---|---|---|
| `checkpoint_outcomes` | `manifest.yml` | One outcome, `waited` or `skipped`, for each checkpoint stage |
| `usage.sessions`, `usage.total`, `usage.unattributed` | `manifest.yml` | The sessions that worked on the issue, and what they cost |
| `too-large`, `no-window` | reasons in a `usage` block | Transcripts over the read limit, and a stage no record ends |

## Guardrail `G5` counts only its own sign-off

`human-approval-present`, the check of guardrail `G5` ("a human signs off on the irreversible"), counts only a `human-approval` record given for guardrail `G5`. The decision is `architecture/decisions/ADR-066-an-approval-names-its-subject-and-guardrail-5-counts-only-an-approval-given-for-it.md`.

### What breaks

- **An in-flight issue whose only approval names another subject fails.** A `human-approval` record that holds a `check`, `waiver`, `checkpoint`, `artifact` or `decisions` key, or a `guardrail` other than exactly `G5`, is set aside. For example, `compass evidence approve --check dod-reviewed` no longer clears the payments sign-off.

### What changes

- **A person records the sign-off with `compass evidence approve --guardrail` and the value `G5`.** It needs a terminal and refuses the approver `agent`, `--decision rejected` and any guardrail but `G5`.
- **A sign-off recorded the earlier way still counts.** A `human-approval` record with no subject key is a sign-off given for guardrail `G5`.
- **A landed issue is reported, never failed.**
- **The check is version 1.1.0.** `compass check` still judges an issue whose generation recorded 1.0.0.

### What to do

1. Run `compass check` on each open issue that guardrail `G5` applies to. Where `human-approval-present` fails with "no approval was given for guardrail `G5`", a person runs this before the issue lands:

   ```
   compass evidence approve --guardrail G5 --approver <name> --role <role> --scope <text>
   ```

2. Update scripts that write `human-approval` records for the sign-off: set the `guardrail` key to `G5`, or write no subject key.

## The lightweight intent and the release line

A regular issue opens with a short intent, and every issue that ships records one release line for the release notes. The decision is `architecture/decisions/ADR-065-regular-issues-owe-an-intent-and-shipping-issues-record-a-release-line.md`. `docs/release-line.md` and `docs/release-notes.md` own the facts.

### What changes

- **The regular approach owes `intent` at depth `lightweight`**, with four headings: Problem, Desired outcome, Success signals and Non-goals. `compass ship-commit` refuses a regular issue while the intent is unwritten, through the check `artifacts-approved`.
- **A new approach field, `release_line`.** Quick fix, regular, hotfix and full set it `true`. The spike has no such field. Setting it `false` needs a waiver.
- **A new manifest key, `release_note`.** `compass acceptance record`, `compass ship-commit` and `compass quick-fix finish` write it with `--release-note "<text>"`. The latest write wins. A blank line is refused, and a line that starts with `#` is refused with `release-line-heading`.
- **Every landing refuses an issue that owes a line and has none**, with the code `release-line-missing`.
- **The verification report gains a `## Release line` section** with the rendered block `release-line`.
- **A new verb, `compass release notes --since <ref>`**, prints the release line of each shipping issue completed after a git reference. It writes nothing.

### What to do

1. Nothing for issues already assessed. An open issue owes an intent and a release line only after `compass approach evaluate --write` commits a generation from the new default.
2. Give each new shipping issue its line before it lands: `compass ship-commit --issue <slug> --release-note "<text written for a user>"`, or the same flag on `quick-fix finish` or `acceptance record`.
3. Update agent instructions and scripts that run a quick fix to `compass quick-fix finish -m "<message>" --release-note "<one sentence for a user>" --no-commit -- <test command>`.
4. If `compass.yml` has replaced a shipping approach (an entry with `replace: true`), add the new fields to that entry. Without them `compass policy lint` fails the entry with `C-LOOSENING`. A project waiver on the entry is the alternative (`docs/policy-lint.md`).

   | Replaced entry | Needs |
   |---|---|
   | regular | `release_line: true` and `intent: lightweight` or deeper |
   | full | `release_line: true` and `intent: thorough` |
   | quick fix, hotfix | `release_line: true` |

   ```yaml
   approaches:
     regular:
       replace: true
       release_line: true
       artifacts: {intent: lightweight, acceptance-criteria: thorough, technical-design: thorough, distribution-map: lightweight, verification-report: thorough}
   ```

## Word limits and low-level designs

The catalog gives a document kind a word limit per depth. The full approach gains one low-level design per work unit. The decision is `architecture/decisions/ADR-067-word-limits-are-catalogue-obligations-and-a-low-level-design-is-one-document-per-work-unit.md`. `docs/artifact-catalog.md` owns the facts.  <!-- us-english-scan: allow - a file name, a variable or a stored key, not prose -->

### What breaks

- **A new blocking check, `design-within-word-ceiling`, can fail an issue after plan.** It fails a technical design over 1.5 times its limit: 6,000 words at thorough and 1,800 at lightweight. It sits in no gate, and an issue waiver can make it advisory.
- **`compass policy migrate` reports an unedited copy of the 5.x governance files as `incomparable`.** This is expected. The migrate is not blocked.

### What changes

- **A new catalog field, `word_ceiling`**, a map from depth to a number of words. The default is 4,000 (thorough) and 1,200 (lightweight) for `technical-design`, and 5,000 and 1,500 for `acceptance-criteria`. A layer that changes a shipped kind's limit needs a waiver.
- **A word is a whitespace-separated token of the visible text.** Rendered block interiors, marker lines and HTML comments do not count.
- **`compass issue lint` prints two new notes:** a registered document over its limit, and a work unit of the full approach with no registered low-level design.
- **A new kind, `low-level-design`**, with the file `low-level-design/<unit>.md`, where a unit is `U` and a whole number from 1. No approach owes it.
- **`compass issue artifact set` and `compass issue artifact-path` take `--unit U<n>`.** `artifact-path` with no `--unit` refuses when two or more units are registered.
- **`scripts/measure-artifact-catalogue.py --design-size --json`** reports the median design size per approach on a copy of an archive.  <!-- us-english-scan: allow - a file name, a variable or a stored key, not prose -->

### What to do

1. Nothing for issues already assessed. An issue adopts the word limits at its next `compass approach evaluate --write`.
2. On the full approach, write `low-level-design/U<n>.md` for each unit at plan and register it with `compass issue artifact set low-level-design --unit U<n> --status draft --path <file>`.
3. Keep a thorough technical design within 4,000 words. `compass issue lint` notes a design over 4,000, and `compass check` refuses one over 6,000.

## Role is not an assessment dimension

The assessment no longer reads a role. The decision is `architecture/decisions/ADR-070-role-is-not-an-assessment-dimension-and-documents-on-disk-bring-the-claims-gate-and-the-intent-block.md`. `governance/routing-policy.md` owns the rules. 9.0.0 removed the role entry points and the role templates (ADR-093).

### What breaks

- **The shipped default has no `role` dimension, no role rules and no role default.** RP-ROLE-001, RP-ROLE-002 and RP-SROLE-001 are gone. `governance/routing-policy.yml` moves to version 3.0.0. `retired_rules` in `governance/legacy-views.yml` lists each retired rule id and its replacement.
- **The full approach no longer carries `verify.claims`.** An issue owes the gate only when it has a `positioning.md`.
- **A `compass.yml` that edits a retired entry is refused:** a `set`, `replace` or `remove` of `dimensions.role`, `rules.role_rules` or `rules.role_defaults`.
- **A project rule, check or gate whose `when` reads `role` fails `compass policy lint`** with `M-WHEN-RETIRED`. A check or gate whose `when` reads `artifacts_any` fails with `M-WHEN-DOCUMENTS`.
- **`compass policy migrate` blocks on a copied role rule the project edited**, with `M-RETIRED`.
- **The bias that was RP-BIAS-003 is now RP-BIAS-002.** A `compass.yml` that edited one of the two ids now edits a different bias text.

### What changes

- **Two artifact rules replace the role rules.** They read the issue's documents on disk with the condition `artifacts_any`:
  - RP-ART-001: with `positioning.md`, the issue gains `verify.claims`, owes `launch-readiness.md`, and the ship stage is blocked until every claim traces to a passing scenario.
  - RP-ART-002: with `intent.md`, the plan stage is blocked until the spec is checked against it.
- **A recorded role is not read.** `compass issue migrate` lists each recorded `assessment.role` and leaves it in place.
- **An issue with a stored 6.x generation keeps its role rules** until it is re-assessed. A project on copied 6.x governance keeps them until it runs `compass policy migrate`.
- **An issue with no stored generation, in a project with a `compass.yml`, takes the new default at once.**
- **`--justify role=` and `compass quick-fix start --role` are accepted and ignored until 9.0.0.** Each prints a notice on standard error. <!-- vocabulary-scan: allow - the 7.0.0 guide records the flag 9.0.0 removed (ADR-098) -->
- **A landing refuses an artifact rule the approach does not hold**, with `artifact-rule-not-applied`. This happens when a document such as `positioning.md` is written after assess. Run `compass approach evaluate --issue <slug> --write`.

### What to do

1. Check the open issues that have no `generation:` key. An issue that relied on a product-owner or marketer role needs its `intent.md` or `positioning.md` on disk, and a re-assessment.
2. Stop passing `--justify role=` and `--role`.
3. If `compass policy lint` reports `M-WHEN-RETIRED`, key the rule on a document with `artifacts_any: [<kind>]`, or on a label. Key a check or gate on a label.
4. If a merge or `compass policy migrate` names a retired rule, make the same edit to its replacement (RP-ART-001 or RP-ART-002) in `compass.yml`.
5. On an issue already assessed, re-assess after you write `positioning.md`.

## Approving inside Claude Code, and delegated approvals

A person approves or rejects by typing `/compass:approve` or `/compass:reject` in the Claude Code session. A person can also let one named agent approve for them, for at most 24 hours and a stated scope. The decisions are `architecture/decisions/ADR-068-a-person-approves-inside-claude-code-through-an-event-the-model-cannot-raise.md` and `architecture/decisions/ADR-069-a-person-can-delegate-approvals-to-a-named-agent-for-a-stated-time-and-scope.md`.

### What breaks

- **`compass evidence add --type human-approval` is refused.** The refusal names the three approval paths.
- **An in-flight issue whose only guardrail `G5` sign-off is withdrawn fails.** `human-approval-present` is version 1.2.0 and skips a record that an `approval-withdrawal` names.
- **The plugin registers two new hooks:** `hooks/prompt-approval.sh` on `UserPromptExpansion` and `hooks/approval-summary.sh` on `UserPromptSubmit`. A Claude Code version without `UserPromptExpansion` falls back to the terminal command.

### What changes

- **The agent asks and the person answers.** The agent runs `compass evidence request`. Compass shows the request at the end of the turn. The person types `/compass:approve` or `/compass:reject <reason>`, and the record holds `via: prompt`.
- **`compass evidence approve` at a terminal still works.** Its records hold `via: terminal`.
- **A rejected document stays in draft until its file changes.**
- **Delegation.** `/compass:delegate <agent> until <time>` lets one named agent approve with `compass evidence approve ... --delegated --as <agent>`. `g5` is covered only when typed, after the person types back a code shown to them. `/compass:revoke` ends it. The person sees a summary of each delegated approval, and `/compass:reject <record id>` overrules one.

### What to do

1. Update the Compass plugin, so the new hooks and commands are registered.
2. Put `owner: <your id>` in `compass.yml`, or set `COMPASS_APPROVER` before you start Claude Code. The prompt hook names the approver from them.
3. Replace scripts that ran `compass evidence add --type human-approval` with `compass evidence request` and the person's `/compass:approve`, or `compass evidence approve` at a terminal.

### New keys

| Name | Where | Meaning |
|---|---|---|
| `via` | an approval record | `prompt`, `terminal` or `delegation` |
| `approval-withdrawal` | an evidence type | Withdraws a delegated guardrail `G5` sign-off |
| `.compass/delegations/DL-<n>.yml` | a file | One delegation |
| `approval-requests/` | the issue's folder under `.compass/work/` | Pending and closed requests |

## Shell writes through a variable, and `tee`, `cp` and `mv` targets

The pre-tool hook reads more exactly which files a Bash command writes. `docs/safety-contract.md` describes the behavior, under "Shell-write detection is best-effort".

### What breaks

The hook now refuses these Bash writes to production code when no failing test is on record:

| Shape | Example |
|---|---|
| `cp` or `mv` whose target is not the last word of the line | `sudo cp a.ts src/app.ts`, `(cp a.ts src/app.ts)`, `cp a.ts src/app.ts 2>&1`, `cp a.ts src/app.ts; echo done` |
| a quoted target | `echo x > "src/app.ts"`, `tee 'src/app.ts'` |
| a path spelled to look outside the project | `/tmp/../<project>/src/app.ts`, `//<project>/src/app.ts`, a path that differs only in letter case |
| a write inside a substitution, after `>\|`, or split by a line continuation | `x=$(cp a.ts src/app.ts)`, `echo x >\| src/app.ts` |
| a destination after a substitution that holds a quoted bracket | `cp "$(echo '(')" src/app.ts` |
| a test or `.compass/` directory named before a `..` after an unknown part | `echo x > $X/../tests/../src/app.ts`, `echo x > $X/../.compass/notes.ts` |

A test file name, such as `$X/../src/test_app.ts`, and a document are still exempt.

### What is newly allowed

| Shape | Example |
|---|---|
| a temporary file named through a variable the command sets | `S=/tmp/scratch && cat > $S/plant.ts` |
| the input of `tee` | `node src/cmp.ts \| tee out.txt` is not a write to `src/cmp.ts` |
| a file read after `cp` or `mv` | `cp a b && grep x src/app.ts` is not a write to `src/app.ts` |
| a path that resolves outside the project, or to a test or a document | `<project>/../elsewhere/app.ts`, `src/../tests/test_app.ts` |

A variable whose value the command does not state for certain is judged inside the project, as before.

### What to do

Nothing. A command that is now refused needs a failing test on record, as an Edit of the same file does.

## Rewriting your configuration in the 6.0.0 words

`compass policy migrate --words` rewrites a project's `compass.yml`, a team preset and its policy-test fixtures in the 6.0.0 words. 9.0.0 removed the command (ADR-094).

### What breaks

Nothing. The command writes only when you pass `--apply`.

### What changes

- **`compass policy migrate --words [DIR]` rewrites `compass.yml` and the fixtures under `compass-fixtures/`.** A word changes only in the field that holds it. Comments, order and quoting stay.
- **Without `--apply` it prints a diff and writes nothing.**
- **`--apply` refuses a write git cannot undo:** an uncommitted file, or a project in no git repository, unless you pass `--i-have-a-copy`. It writes every file or none.
- **A condition that reads `role` is listed, not rewritten.** The command exits 1 until you change it.

### What to do

1. Commit your configuration, then run `compass policy migrate --words` and read the diff.
2. Run `compass policy migrate --words --apply`.
3. If it lists a hand edit, key the rule on a document with `artifacts_any`, or on a label.
4. For a team preset in another repository, run the same two commands there, then the preset test.

## Guardrail 5 triggers on the irreversible labels

Guardrail 5 (`G5`) asks for a person's sign-off only when an issue carries `auth`, `payments`, `personal-data` or `migrations`. Critical risk on its own no longer asks for one. The decision is `governance/decisions/2026-10-12-guardrail-5-triggers-on-the-irreversible-labels.md`.

### What breaks

- **A critical-risk issue with none of the four labels ships without a sign-off.** `compass check` reports `G5` as not applicable for it.

### What changes

- **The trigger.** `G5`'s `when` in the default preset is `labels_any: [auth, payments, personal-data, migrations]`. `governance/guardrails.yml` moves to version 1.33.0.
- **Assess names the labels.** When risk is critical and the trigger does not match, `compass approach evaluate` adds a line under "Pay attention to".
- **Stored issues keep their trigger** until they are re-assessed. A project that copied `governance/` keeps its trigger, and `compass policy migrate` carries it into `compass.yml` as a `set` on `G5`.

### What to do

1. Check open critical-risk issues for a change to auth, payments, personal data or a migration, and add the label to any that are.
2. To keep the sign-off on every critical-risk change, add this to `compass.yml`. A trigger that drops a label is refused.

   ```yaml
   gates:
     G5:
       set:
         when:
           any_of:
           - labels_any: [auth, payments, personal-data, migrations]
           - {risk: critical}
   ```

3. Run `compass policy lint` to check the file.

## A copied `waived:` entry migrates to a `LEGACY` waiver

`compass policy migrate` keeps the reason a 5.x project recorded under `routing_guardrails.waived:` in its copied routing policy. 9.0.0 removed the command (ADR-094).

### What changes

- **A removal the copy recorded gets a `LEGACY` waiver**, with `approved_by: LEGACY` and no `approved_on`. Lint reads it as the warning `W-LEGACY`, so it does not block `--apply`.
- **A lock refusal still blocks.** Removing a guardrail the framework locks, such as `G1`, stays blocked with `K-LOCK-REFUSED`.
- **These keep the `UNAPPROVED` stub and still block:** an entry that also loosens something no record names, and a `waived:` entry with no `id` or a blank `reason`.
- **The JSON report's `waiver` field can be `LEGACY`.**

### What to do

Nothing. To clear the warning, the project's `owner` replaces `LEGACY` with an approver's name and adds `approved_on`.

## A waived stage mode holds on a floor-raised approach

A floor that raises an issue's approach keeps the issue's lower mode for a stage the floor does not name, when that stage's entry in the issue's `config:` carries an approved issue waiver. The decision is `governance/decisions/2026-10-17-a-waived-stage-mode-holds-on-a-floor-raised-approach.md`.

### What changes

- **A generation stored by 6.0.1 for an issue with an approved breakdown waiver reads as `breakdown: skipped`.** The manifest's `stages:` keeps `multiagent` until the next `compass approach evaluate --write`.
- **The classifier is version 10.** The lint refuses a waived breakdown from `multiagent` to `skipped` on a floor-raised approach unless the waiver's approval is valid.

### What to do

Nothing for an issue with no stage waiver. Reassess an issue that has one, so that its manifest records the waived mode.

## Design-decision scope, the regular requirements review and the hotfix bug report

A project-scoped design decision cannot land without a decision record. A regular issue owes a short requirements review, and a hotfix owes a bug report. The decision is `architecture/decisions/ADR-072-a-project-scoped-design-decision-needs-a-record-and-regular-and-hotfix-owe-a-review-and-a-bug-report.md`. `docs/artifact-catalog.md` owns the facts.

### What breaks

- **A landing refuses an open issue whose technical design holds a `Scope: project` decision that no record in `architecture/decisions/` names**, with the code `project-decision-unrecorded`. A decision with no `Scope:` line is not judged.
- **A new regular issue cannot land until its `requirements-review.md` is approved, and a new hotfix until its `bug-report.md` is approved**, through the check `artifacts-approved`.
- **A project with `entry-exit-evaluation` on owes the seven Definition of Ready records at plan entry on each new regular issue.** `compass next` names each missing one as `entry not met:`.

### What changes

- **Each design decision of the technical design template has a `Scope:` line**, `issue` or `project`. A reason can follow, as in `Scope: Project - later issues follow it`. A line such as `Scope: project and more` counts as unscoped, and `compass issue lint` prints a note.
- **The regular approach owes `requirements-review` at depth `lightweight`**, with three headings: Self-QA of the spec, Ambiguity ledger and Gate.
- **The hotfix approach owes `bug-report` at depth `thorough`.** It keeps `acceptance-criteria` at `lightweight`.
- **The routing policy view is version 3.2.0.**

### What to do

1. Nothing for issues already assessed. An open issue owes the two documents only after `compass approach evaluate --write` commits a generation from the new default.
2. Give each design decision a `Scope:` line. For a `project` decision, run `compass adr new <slug>`, write the record, and cite its ADR id in the decision's block.
3. On a regular issue, register the requirements review at refine with `compass issue artifact set requirements-review --status draft --path <file>`. On a hotfix, write and register `bug-report.md` at assess.

## Renamed names

Compass spells its own names in US English from 7.0.0. Each old name below is still read until 9.0.0, and the new name is the one written. The table is checked against the table the CLI reads (`old_names:` in `cli/migrate-map.yml`).

| Kind | Old name | New name | Read until |
|---|---|---|---|
| kind | `judgement` | `judgment` | 9.0.0 |  <!-- us-english-scan: allow - old name, read until 9.0.0 -->
| check | `dor-behaviour-is-gwt` | `dor-behavior-is-gwt` | 9.0.0 |  <!-- us-english-scan: allow - old name, read until 9.0.0 -->
| skill | `behaviour-mapping` | `behavior-mapping` | 9.0.0 |  <!-- us-english-scan: allow - old name, read until 9.0.0 -->
| refusal code | `not-initialised` | `not-initialized` | 9.0.0 |  <!-- us-english-scan: allow - old name, read until 9.0.0 -->
| state key | `initialised` | `initialized` | 9.0.0 |  <!-- us-english-scan: allow - old name, read until 9.0.0 -->
| readiness key | `catalogue_digest` | `catalog_digest` | 9.0.0 |
| JSON key | `behaviour` | `behavior` | 9.0.0 |  <!-- us-english-scan: allow - old name, read until 9.0.0 -->
| JSON key | `behaviours` | `behaviors` | 9.0.0 |  <!-- us-english-scan: allow - old name, read until 9.0.0 -->
| heading | `Current Behaviour` | `Current Behavior` | 9.0.0 |  <!-- us-english-scan: allow - old name, read until 9.0.0 -->
| heading | `Archived Behaviour` | `Archived Behavior` | 9.0.0 |  <!-- us-english-scan: allow - old name, read until 9.0.0 -->
| term | `catalogue` | `catalog` | 9.0.0 |  <!-- us-english-scan: allow - old name, read until 9.0.0 -->

What to do:

- The session-start hook prints only the new refusal code. Change a script or a rule that matches the old code to match `not-initialized`.
- A script that reads the refusal code or the `behaviour` JSON keys should move to the new names before 9.0.0.  <!-- us-english-scan: allow - old name, read until 9.0.0 -->
- A project that names `compass:behaviour-mapping` or `dor-behaviour-is-gwt` keeps working until 9.0.0.  <!-- us-english-scan: allow - old name, read until 9.0.0 -->
- No manifest, state file or readiness record needs a change by hand. A manifest that holds an old name is rewritten on its next save, with a `.v5.bak` copy.

### The `language` setting

7.0.0 adds the optional setting `language` to `compass.yml`: a BCP 47 tag such as `en-US` or `de`. When it is set, the session-start hook tells the agent to write prose in that language. `compass policy lint` refuses a malformed value. `docs/configuration.md` has the tag table.

## `compass policy migrate --undo` goes back to the old files

`compass policy migrate --undo` puts a migrated project back as it was before `compass policy migrate --apply`. 9.0.0 removed the command (ADR-094). The decision is `governance/decisions/2026-10-19-the-migration-marker-records-what-an-undo-needs.md`.

### What changes

- **`--undo` is a dry run until you add `--apply`.** `--apply` restores the old settings file, and any deleted governance file, from `.compass/legacy/`, byte for byte. It removes `compass.yml`, then `.compass/state.yml` when the migration made it, then the marker, `migration.yml` in `.compass`. `.compass/legacy/` stays.
- **The undo refuses, and writes nothing, when it would lose work:** a file the migration wrote or kept has changed, a legacy copy is missing or differs, or a signed record exists from after the migration. There is no override.
- **The marker holds a `written` digest for each file the migration wrote, and a `migrated_at` time.** `--undo` refuses a marker from an earlier run, which has neither, and prints the steps to go back by hand.
- **`--undo` refuses `--words`, `--i-have-a-copy` and a folder argument.**

### What to do

Nothing, unless you want to go back. Run `compass policy migrate --undo`, read the list, then run `compass policy migrate --undo --apply`.
