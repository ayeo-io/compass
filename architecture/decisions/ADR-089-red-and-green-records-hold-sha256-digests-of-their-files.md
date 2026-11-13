---
id: ADR-089
title: Red and green records hold SHA-256 digests of their files
status: accepted
date: 2026-11-03
supersedes: ''
superseded_by: ''
---

## Context

A reviewer must be able to check an issue's test records without Compass. Two fields stop that today (ayeo-io/compass-delivery#348):

- `content_digest` is the SHA-256 of the record re-serialized as sorted JSON (`red_first.content_digest`), not of the file. `sha256sum` on the record file does not give it, so a reviewer needs Python and Compass's serializer.
- `changes_id` is a git tree id of the issue's files (`changed_files` and the test files the scenarios declare). No commit reaches that tree, so `git gc` can remove it. `ship-commit` reads that tree to name the files that changed after a green (`manifest._stale_paths`), and a landed issue is judged by comparing it with a tree built from `land_commit` (`binding._check_landed`).

Two rules depend on `content_digest` and must keep their strength:

- ADR-086 counts a record only when the registry entry's `record_id` is the file's and the file's `content_digest` matches what it holds (`evidence_identity.py`, `strategy_records.counts`). The red verdict that unlocks code edits (`red_first._record_verdict`) uses the same digest.
- ADR-088 needs `first_timestamp` on a green to be covered by `content_digest`, so an edit to it is seen.

## Decision

1. **The digests in a record.** Each red, green and acceptance record, and each isolation and layering record, that names its tree carries `file_sha256`: an object that maps the project-relative path of each of the issue's files to the SHA-256 of its bytes on disk, in lowercase hexadecimal, as `sha256sum` prints it. The digests are taken before the command runs, as `tree_id` is. The issue's files are the files `changes_id` covered (`binding.changes_paths`): the paths in `changed_files` and the test files the scenarios declare, without `.compass/` and `docs/compass/`. A file is left out, as `changes_id` left it out, when it is absent, a symlink, outside the repository, or untracked and ignored by git. Beside it, `file_modes` maps each of those paths to the mode git would record, `100755` or `100644`, so a change to the executable bit alone shows, as it did in the tree ids. Where `core.fileMode` is false, a tracked file's mode is read from the git index, as git reads it. Outside a git repository a record carries neither `tree_id` nor `file_sha256`.
2. **What a test file is.** A test file is the part before `::` of each test id in a scenario's `tests:` list (`binding.declared_test_paths`). The record lists those of its paths in `test_files`. The CLI does not read test files from the command line: a command can name a folder, a `-k` filter or a runner Compass does not know, and the declared tests are the list the checks already trust.
3. **The digest of the record file.** A record cannot hold the digest of its own bytes. The CLI writes `evidence/SHA256SUMS` in the issue folder, in `sha256sum` format (`<digest>  <path>`), with each path relative to the project root. Each time the CLI writes a record through its evidence writer (`tdd._write_evidence`), it rewrites the file with:
   - one line for each record file it wrote, with the digest of the bytes it wrote. A line stays until the record is written again or its file is removed.
   - one line for each path in the `file_sha256` of the record written last, with its digest. A record with no `file_sha256` (outside git, or the older format) keeps the file lines already there. Write order, not `timestamp`, decides, because records carry the time only to the second. A file deleted or renamed since an earlier record is not listed, so `sha256sum -c` does not fail on a file the issue removed.

   `sha256sum -c` checks bytes only, not `file_modes`; `compass check` and `ship-commit` compare the modes. A reviewer runs `sha256sum -c .compass/work/<slug>/evidence/SHA256SUMS` from the project root (`shasum -a 256 -c` on macOS). A name that holds a newline or a backslash is written with `sha256sum`'s escape: a leading `\` and the character escaped.
4. **A test file that changed between red and green.** The red record keeps the digest the file had at red. `SHA256SUMS` lists each path once, from the record written last, so a test corrected between red and green does not fail `sha256sum -c`, and a normal red, then code, then green issue passes it. It is not a finding: a test is often corrected after its first run. A reader who wants the red-time digest reads it from the red record.
5. **`content_digest` stays.** It stays the identity check of ADR-086, beside `record_id`, and covers `file_sha256`, `file_modes`, `test_files` and `first_timestamp`. The record file's digest in `SHA256SUMS` is added for a reader without Compass; Compass does not read `SHA256SUMS`. So every check that read `content_digest` reads it as before. The landed check and `ship-commit` compare the bytes a checkout writes and the mode, so they see every change to a file that `changes_id` saw, and no check is weaker.
6. **`changes_id` is dropped.** The CLI no longer writes `changes_id`. Where it was read:
   - `evidence-matches-tree`, for a landed issue, compares each path in `file_sha256` and in `changes_paths` with the file in `land_commit`: the SHA-256 of the bytes git's checkout conversion gives (`git cat-file --filters`), so line endings set by `.gitattributes` or `core.autocrlf`, and smudge filters, read as on disk, and the mode `git ls-tree` gives, compared with `file_modes`. A path missing on one side differs. The detail names the paths that differ, and marks a mode-only change. The check moves to 1.1.0.
   - `ship-commit` compares the same digests and modes, read the same way, with the commit or staged tree it is about to land, and names the paths that differ. It no longer reads a tree that no commit reaches.
   - `compass tdd-green`'s rerun test and `quick-fix finish`'s reuse of a green compare `file_sha256` and `file_modes` where they compared `changes_id`.
   - `governance/guardrails.yml`, the `default` preset's `checks.yml`, `docs/safety-contract.md` and the tests name `file_sha256`. The frozen presets `default@6` and `default@7` keep their text, as they describe those releases.
7. **Old records.** The fields pick the format. A record with `file_sha256` is read by its digests. A record with `changes_id` and no `file_sha256` is read as before: the landed check builds the tree from `land_commit` and compares tree ids, and `ship-commit` compares the same tree ids. A record with neither is not judged, as before. A date rule in the style of `RED_PER_SCENARIO_FROM` is not used: both formats are covered by `content_digest`, so a field cannot be removed without the identity check seeing it, and a date would fail a record an older CLI writes after the date on an issue in flight across the upgrade.
8. **The version.** `evidence-matches-tree` moves to 1.1.0. No archived record carries `file_sha256`, so every archived issue is judged by `changes_id` as before, the corpus verdicts do not change and the major stays at 1.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| Make `content_digest` the SHA-256 of the record file | One digest, checkable with `sha256sum` | A file cannot hold the digest of its own bytes, so the field would have to be left out of the hashed bytes, which `sha256sum` cannot do |
| Replace `content_digest` with the line in `SHA256SUMS` as the identity check | One identity, checkable without Compass | `SHA256SUMS` sits next to the record and is rewritten with it, so it adds no strength; the change would touch every reader of ADR-086 and the hook's red verdict |
| Store the record file's digest in the registry entry in `manifest.yml` | The manifest already holds `content_digest` | `sha256sum -c` cannot read YAML, and a reader would need the manifest's layout |
| Keep `changes_id` and make a commit reach its tree | Keeps one id for the landed check | The commit would be written into the user's repository, and `sha256sum` still could not check a tree id |
| Take the test files from the command line | Covers a test the scenarios do not declare | A command can name a folder, a filter or an unknown runner; the declared tests are the list the checks already use |
| List each path from the newest record that names it, by `timestamp` | Keeps a file only an older record names | A file deleted or renamed since then keeps a line that `sha256sum -c` fails, and two records in one second tie |
| Hash the raw git blob on the commit side | One `git cat-file` call with no attributes | With `eol=crlf`, `core.autocrlf` or a smudge filter the blob is not the bytes on disk, so correct work would fail |
| Leave the mode out | `sha256sum` does not check modes | A change to the executable bit alone would pass, where the tree ids caught it |
| List the red-time digest of each test file in `SHA256SUMS` too | Shows the file at red | A test corrected after its red would fail `sha256sum -c` on an issue that did nothing wrong |
| Pick the format by the record's date, as `RED_PER_SCENARIO_FROM` does | One pattern for each cutoff | A record an older CLI writes after the date would fail the landed check; the fields already tell the formats apart |
| Make `compass check` read `SHA256SUMS` | Catches a byte edit that leaves the JSON the same | The file is rewritten with the record, so it adds no strength over `content_digest`; it stays a reader's tool |

## Consequences

- A reviewer can check an issue's records and its declared tests and changed files with `sha256sum -c`, with no Compass installed. An edit to a record, or to one of the files after its newest record, fails it.
- `ship-commit` names the changed files from the record alone, so `git gc` cannot remove what it reads.
- A record written by an older CLI keeps its verdict.
- The first `compass tdd-green` after the upgrade on an issue in flight is compared with a run that held `changes_id`, so it is not counted as a rerun of an unchanged tree.

## Open questions

1. Should old-format records stop counting from a date, such as the 9.0.0 release date? The default is no date: the fields pick the reader.
2. Should `suite-passed` say in its detail when a declared test changed between its red and its first green? The default is no: the red record keeps the red-time digest, and the check does not read it.
3. Should `evidence-identity-matches` also compare a cited record file with its line in `SHA256SUMS`? The default is no, as decision 5 says.

## References

- ayeo-io/compass-delivery#348, the issue that asks for digests `sha256sum` can check.
- ADR-038 (implementation versions), ADR-086 (records written only by their commands), ADR-088 (`first_timestamp`).
- `cli/compass_pkg/binding.py` (`ids_for`, `file_sha256`, `_check_landed`), `cli/compass_pkg/evidence_sums.py`, `cli/compass_pkg/manifest.py` (`_stale_paths`).
- `tests/test_evidence_sha256sums.py`.
