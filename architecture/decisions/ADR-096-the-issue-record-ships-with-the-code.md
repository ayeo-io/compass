---
id: ADR-096
title: The issue record ships with the code
status: proposed
date: 2026-11-07
supersedes: ''
superseded_by: ''
---

## Context

Compass 9.0.0 is an ATDD framework with a proof trail (ayeo-io/compass-delivery#356 [Commit the issue record with the code and add trail.md], under #345 [Reposition Compass 9.0.0 as an ATDD framework with a proof trail]). The issue asks:

> Make the issue record readable and checkable beside the code.
> - Commit `.compass/work/<slug>/` and the acceptance criteria in the same PR as the code, by default. Generation snapshots and lock files stay out. `compass record sync` stays as an option.
> - Require a request link and a requester at Assess (`compass issue link set`).
> - Write one file per issue, `trail.md`, with these in order: who asked, what was agreed, the red for each scenario, the green, who approved and by what authority, and what shipped. Each line names its evidence file and that file's `sha256sum` digest.

The #345 proposal names two defects this fixes. E1: no issue records who asked or links the request. E6: `land_commit` is wrong after a squash merge. Two archived issues name a commit that is not on `main`.

Earlier records hand parts of this to #356:

- ADR-094 decision 4: generation folders stay out of the commit, so the manifest's `policy:` block is the copy a reviewer reads. Rebuilding a policy from that block when the folder is missing is left to #356.
- ADR-095 open question 16: #355 writes the post-merge fields (the ship approval, `merged_at`, the merge commit) into the manifest. #356 decides how a committed record gets them.
- ADR-089: `evidence/SHA256SUMS` holds `sha256sum` lines for the red and green records. `trail.md` uses the same line format and the same digests.

What is in place before this change:

- **The record is kept out.** Nothing in the CLI decides whether the issue folder is committed. This repository ignores `/.compass/work/` and `/docs/compass/*/` in its `.gitignore`. `docs/delivery-record.md` says Compass keeps each issue's records out of the project's git history. `compass record sync` copies the record into a separate repository.
- **The land commit is written after the commit.** `compass ship-commit` (`manifest.cmd_land_commit`) commits, then writes `land_commit`, status `completed` and `land_timestamp`. So the manifest is changed and not committed after every landing, and a squash merge leaves `land_commit` naming a commit that is not on the default branch. `compass issue link set --pr` moves it to the merge commit only when someone runs it.
- **A missing generation is broken.** `effective.effective_for` loads the stored generation whenever the manifest names one. `generation.load` raises "generation N of <slug> is broken" when its folder is missing. So `compass check` on a fresh clone of a committed record would fail for every issue.
- **No request is recorded.** `compass issue link set --github` writes `github: {repo, number}` for a GitHub issue only. There is no requester field and no link for a request held elsewhere.

No archived issue may change its `compass check` verdict. None of the 622 archived manifests in the main checkout holds `evidence_required`, `policy:` or `landed_with_record`, and no archived folder holds `trail.md`.

## Decision

1. **A record mode decides whether the record ships in the commit.** A new module of the CLI package, the `record_mode` module, returns "committed" or "kept out" with the reason. In order:

   | Condition | Mode |
   |---|---|
   | `record.commit: false` | kept out |
   | `record.commit: true` | committed |
   | `record.remote` set, `record.commit` not set | kept out |
   | neither set | committed |
   | committed, but git ignores the issue folder | kept out, with one line naming the ignore rule |
   | not inside a git work tree | kept out |

   `schemas/compass.schema.json` gains `record.commit` (boolean), and `compass policy lint` refuses another value. A project can write `record: {commit: false}` with no remote. `compass record sync` runs after a landing whenever `record.remote` is set, in either mode.

2. **In committed mode `compass ship-commit` stages the record itself.** When every gate passes, it writes status `completed`, `land_timestamp` and `landed_with_record: true` in one save, and does not write `land_commit`. It writes `trail.md`, then stages `.compass/work/<slug>/` and the documents folder, then commits. After the commit it compares each sum line of the committed `trail.md` with the blob in the new commit, and names any file a git hook changed. When a check after the commit fails, it restores the working manifest and says how to remove the commit. The "nothing staged" path makes a commit that holds only the record. The agent still never stages `.compass/` by hand. In kept-out mode the landing is as before, and `trail.md` is written after the `land_commit` write.

3. **The land commit of a committed record is read from git.** A new module, the `landing` module, gives every reader the land commit:
   - a stored `land_commit` wins (every archived issue, and kept-out mode);
   - else, when the issue is completed and the manifest holds `landed_with_record: true`, it is the newest commit that added the manifest's current `land_timestamp` line;
   - else none.

   After a squash merge that commit is the squash commit on the default branch, so the E6 defect cannot happen. A rebase finds the rebased commit, a merge commit finds the branch commit, and a shallow clone that does not hold the commit gives none, as now. Every reader of `land_commit` calls it.

4. **An ignore file keeps per-checkout files out.** `compass init` writes `.compass/work/.gitignore` in every project and adds any missing line on each later run. It lists `*/generations/`, the lock files (`*/.*.lock`), the `.red` and `.acceptance` markers, `start-state.json`, `evidence/.tdd-state.json` and `approval-requests/pending/`. A pending request holds a live single-use nonce, so it stays out. Closed requests are committed, because `checkpoint_outcomes` reads them. In committed mode only, `compass init` also adds `delegations/`, `cache/`, `private/`, `current-task` and `interruptions.log` to `.compass/.gitignore`.

5. **A fresh clone rebuilds a missing generation from `policy:`.** When the manifest names generation n, the folder `generations/<n>/` does not exist at all, and the manifest holds `policy:`, the rebuild:
   - takes the check set `policy.check_set` names, and refuses when this Compass does not hold it or its `sha256sum` differs from `policy.check_set_sha256`;
   - resolves it with `policy.autonomy` and applies `policy.tightened` with the function that applies `compass.yml` settings, not the current `compass.yml`, so a later settings change does not stop the rebuild;
   - uses the result only when its digest equals `policy.resolved`, and otherwise refuses with both digests;
   - writes the folder under the generation lock, with `provenance.yml` naming `restored_from: policy`.

   The `policy:` block gains `autonomy`, because the resolution reads it and the block did not record it (see "The rebuild measurement"). A block without the key, written on `v9` before this change, is rebuilt with each of the three autonomy values, and only a digest match is used. A folder that exists but is not whole is still refused, as now.

6. **The request is a token and a check, not a stop.** `evidence_required.TOKENS` gains `request`, first, for every delivery issue. A spike owes nothing. `governance/check-set.yml` gains the check `request-recorded` (deterministic, blocking, `on_skipped: not-applicable`), outside every gate and not in `never_waived`. It fails until the manifest holds a request link and a requester, and names which is missing. `compass check` skips it with no row when the stored `evidence_required` does not list `request`. `next:` asks for it first on a new delivery issue. Nothing refuses: not `compass quick-fix start`, not a landing, not the hook.

7. **The request record.** `compass issue link set` and `compass quick-fix start` gain `--request <url>` and `--requester <name>`. They write:

   ```yaml
   request:
     link: https://github.com/acme/widgets/issues/42
     requester: Dana Smith
     recorded_at: 2026-11-07T10:00:00Z
   ```

   `--request` takes an `https://` URL, or `owner/repo#N`, which also writes `github`. `--github` alone counts as the link. The requester is free text, one line, at most 100 characters. It is a claim the session records, not an approval. No `gh` call is made.

8. **`trail.md` is written beside the manifest.** The path is `.compass/work/<slug>/trail.md`. A new module, the `trail` module, writes it in full from the manifest and the files, and never edits it in place. It has six sections, in the order of the issue:

   | Section | Statement | Sum lines |
   |---|---|---|
   | 1. Who asked | the requester and the link, labelled as recorded by the session | `manifest.yml` |
   | 2. What was agreed | the scenarios, the freeze, and the sign-off where it is owed | the spec file, or `manifest.yml` for a quick fix |
   | 3. Red, for each scenario | when it failed, the exit code and the command, or "no red on record" | the red record and its log |
   | 4. Green | the newest green of each scenario, then the files as that green tested them | the green record and its log, then each `file_sha256` entry, with the digest from the record |
   | 5. Who approved, and by what authority | each approval record: approver, role, time, record id, and how it was given (terminal, `/compass:approve`, a delegation, or a pull request review) | `manifest.yml` |
   | 6. What shipped | the landing, the pull request, the merge commit and the release line | `manifest.yml`, `evidence/SHA256SUMS` |

   A sum line is `<64 hex>  <path>`, with the path relative to the repository root. A statement with no evidence says so and has no sum line. From the repository root, `grep -E '^[0-9a-f]{64}  ' <trail> | sha256sum -c -` checks it. The `-` is needed: the macOS `sha256sum` reads the standard input only with it. Plain `sha256sum -c <trail>` passes with a warning about the prose lines, and `shasum -a 256 -c` reads the same lines.

   `compass ship-commit`, `compass issue link set --pr`, `compass record commit` and `compass trail` write it. `compass trail --check` writes nothing and exits 1 when the file differs from what `compass trail` would write. `compass check` prints one line, not a row, when the file is out of date.

9. **The post-merge fields reach a committed record by a follow-up commit.** In committed mode `compass issue link set --pr <n>` writes the pull request and the `pr-approval` records, does not write `land_commit`, writes `trail.md` again, and prints `next: compass record commit --issue <slug>`. The new verb `compass record commit` commits only the issue's record. It refuses when anything else is staged, in kept-out mode, or when the record has no change. It calls no network. Until that commit exists, the merged `trail.md` says the ship approval is read from the pull request after the merge, and `compass check` reports `ship-approval-present` as nothing to check.

10. **No approval path is added.** `trail.md` and `compass trail` only read records. `request.requester` is not a `human-approval` record and no gate or checkpoint reads it. `compass record commit` stages and commits files only. Pending approval requests and `.compass/delegations/` are never staged.

## The rebuild measurement

Decision 5 depends on a rebuild giving the same digest as the generation it replaces. This was measured before the decision, on 7 Nov 2026, against `v9` at `3cd82017`.

Method: for each case, a scratch git project with the case's `compass.yml`, a path issue made with `compass quick-fix start` (a re-assess with `compass approach evaluate --write` for generation 2), then the generation folder deleted and `compass.yml` changed to an unrelated setting. `resolved.yml` was rebuilt from `policy:` alone: the shipped check set, checked against `policy.check_set_sha256`, resolved and then tightened with `policy.tightened`. Its digest was compared with `policy.resolved`.

| Case | Generation | Digest with the default autonomy | Same bytes as the original |
|---|---|---|---|
| No `compass.yml` | 1 | matches | yes |
| `compass.yml` with no setting | 1 | matches | yes |
| `signoff_labels` | 1 | matches | yes |
| `require_evidence` | 1 | matches | yes |
| `agent_review` | 1 | matches | yes |
| `project_checks` | 1 | matches | yes |
| `capabilities` | 1 | matches | yes |
| `signoff_labels` and `require_evidence`, issue labelled with the new label | 1 | matches | yes |
| All five settings | 1 | matches | yes |
| Shipped label `auth`, no settings | 1 | matches | yes |
| Re-assess to generation 2 after a settings change | 2 | matches | yes |
| `autonomy: controlled` | 1 | differs; matches with `controlled` | yes, with `controlled` |
| `autonomy: autonomous` | 1 | differs; matches with `autonomous` | yes, with `autonomous` |

In every case the `complete` marker's digest of `resolved.yml` equalled `policy.resolved`.

The two differences have one cause. `effective.resolve_live` passes the project's `autonomy` to `check_set.resolved`, and `resolved.yml` holds it, but the `policy:` block does not record it. With the recorded value the rebuild matches. So question 6 goes to the rebuild, and the block gains `autonomy` (decision 5). The generation folder is not committed.

## As built

#356 was built in ten steps on `v9`, from commit 4e2a80dc (this record) to commit ee2cdecc. The decisions above hold. Each point says how the build differs from, or adds to, the first text of this record.

- **Decision 1** is built in the `record_mode` module (commit 84058748). `record.settings` accepts `record: {commit: false}` with no remote, and `compass policy lint` refuses a `record.commit` that is not a boolean. When a git ignore rule keeps the issue folder out, the reason names the rule; nothing is force-added and nothing refuses.
- **Decision 2** is built in a new module, `committed_landing` (commit 824a4391). The commit also stages `.compass/work/.gitignore`. When no commit is made, the manifest and `trail.md` are put back and the record paths are unstaged. In kept-out mode the scope check of a ship commit refuses the issue folder and both ignore files, so a record path staged by hand is refused. `compass quick-fix finish` no longer names `.compass/work/<slug>` to stage.
- **Decision 3** is built in the `landing` module (commits 913b8df0 and bb417fd7). It reads the manifest's file name with `core.manifest_path`, as every other reader does, so a project that still holds the retired `task.yml` is read too. `landing` runs `git` with the person's environment, like every other git read of the CLI.
- **Decision 4**: `compass init` and `compass quick-fix start` write `.compass/work/.gitignore` in every project and keep a person's own lines. `session_lease` adds its ignore lines with the same helper.
- **Decision 5** is built as written (commit 688794be). The rebuild looks for the check set in the shipped file, then in `governance/check-sets/<id>@<version>.yml`, and checks its `sha256sum`. The folder is written to disk, not kept in memory, because `results.yml`, `compass ci` and `compass record restore` read it. `provenance.yml` names `restored_from: policy`. The `policy:` block gains `autonomy` at each generation commit, and the schema keeps it optional (VD-032). A refusal names why the rebuild failed.
- **Decision 6** adds one exception (commit 2e61d7c7, VD-033). `compass quick-fix finish` runs `compass check` and refused on any failing check, so a missing request stopped every landing through `finish`. It now lands when `request-recorded` is the only failing check, and adds a `request` line that names the `compass issue link set` command. Any other failing check still refuses. The check stays blocking, so `compass check` and `compass ci` exit 1 until the request is recorded or a person approves a waiver.
- **Decision 6** also keeps the check set at `compass-checks@9.0.0`; `tests/fixtures/check-set-digests.yml` is repinned. `governance/guardrails.yml` is frozen byte for byte (ADR-094), so the tests that compare the check set with it leave `request-recorded` out by name, as they do for `ship-approval-present`.
- **Decision 7**: `--github` alone gives `request.link` only when none is held. Fixtures that model a complete issue now record a request (commit a6686a9b).
- **Decision 8** is built in the `trail` module (commit 9b289f1a), with two changes (VD-034):
  - The header prints `sha256sum -c -`. On this Mac, `/sbin/sha256sum` prints its usage and reads nothing when it is given `-c` and no file; GNU `sha256sum` and `shasum -a 256` accept `-` too. Decision 8 above now says so.
  - Section 6 names no commit id for a landing whose record is committed with the code. It says the issue landed with this record in the commit that added this `land_timestamp`, and gives the `git log -G` command that finds it. A stored `land_commit` is named as it is. So the same record gives the same bytes, and `compass trail --check` stays true after the commit and after a squash merge.

  A spike gets no trail. `compass trail` has its own `--help` text, and the verb lists of the guards name it (commit 6a5f791e).
- **Decision 9** is built as written (commit ee2cdecc). `compass issue link set --pr` writes `trail.md` again in both modes. On a manifest with `landed_with_record: true` and no stored `land_commit`, it does not write `land_commit`, because a stored value would win over the one `landing` reads from git. An issue with a stored `land_commit` still has it moved, as before. `compass next` names `compass record commit` while a landed committed issue's folder holds a change git has not committed. After the merge, section 4 of the trail names the recorded merge commit as the commit to check the code lines at.
- **Decision 19**: `governance/terminology.yml` gains `trail`, `request-link`, `record-mode` and `landed-with-record`, at version `2.0.0-pre29`.
- The archive comparison over 622 issue folders shows no verdict that moves after steps 3 and 8 (commits 913b8df0 and 688794be).
- This repository stays kept out (VD-031). Its `compass.yml` and `CLAUDE.md` are unchanged.

## Limits

- `trail.md` proves that the files match the digests it names. It does not prove that its prose is true. A process running as the same operating system user can edit the manifest and write `trail.md` again, as ADR-095 states for `pr-approval` records.
- A code file named in section 4 matches only at the commit that holds that version of `trail.md`. A later change to the same file makes that line fail at a later commit. The header says where to run the check.
- A pre-commit formatter that rewrites a record file changes its digest. `compass ship-commit` writes `trail.md` again after the hooks run and warns when a hook changes a file during the commit.
- A shallow clone that does not hold the land commit gives no land commit, as now.
- A rebuild needs the check set the issue was assessed under. A later Compass that changed the check set holds each earlier released one. Before such a release, a rebuild on another release refuses with the reason.
- The requester is what the session recorded. Compass does not check who it is.

What this change does not do:

- It does not commit generation folders, lock files, markers or pending approval requests.
- It does not refuse `compass quick-fix start`, a landing or a tool call for a missing request.
- It does not let an agent record a person's approval.
- It does not change `compass-contract.md`. "Stage each file by its path, never `.compass/`" stays true, because `compass ship-commit` and `compass record commit` stage the record, not the agent.
- It does not change this repository's files. Its `compass.yml` names `record.remote`, so it is kept out.
- It does not change the gate ids, `generation.RESOLVER_VERSION`, `tests/fixtures/frozen-digests.yml` or any compatibility corpus.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| Commit the generation folders too | No rebuild is needed | The issue keeps them out, and the measurement shows the rebuild is exact |
| Keep writing `land_commit` after the commit | No new module | The manifest stays changed and not committed after every landing, and the squash-merge defect stays |
| Refuse `quick-fix start` without a request | The issue asks for a request link at Assess | It breaks the frozen contract 4 entry `quick-fix-start-valid`, and #345 rules out a stop in the session |
| Refuse a landing without a request | The rule would hold at ship | About 25 to 45 test files that land a path issue would change, and the issue does not ask for it |
| Read the requester from the GitHub issue author with `gh` | A checked identity | It needs the network at assess, and many requests are not GitHub issues |
| Write `trail.md` after every manifest save | Always up to date | It adds a write to every command; `compass check` says when it is out of date |
| Put `trail.md` in the documents folder | A reviewer opens it more often | It is away from the evidence it hashes, and this repository ignores that folder |
| Hash only the records, not the code | Always passes | It proves less: the code lines prove the committed code is the code that was tested |
| Read the approvals before the merge and commit them to the branch | No follow-up commit | A commit after the approval can dismiss it where "dismiss stale approvals" is on |
| Commit the record for every project unless `record.commit: false` | One rule | A project that set up a private record repository would start publishing its records on upgrade |

## Consequences

What changes for a user:

- A project with no `record:` setting commits each issue's record with its code. `compass ship-commit` stages it, and a fresh clone can run `compass check` and `sha256sum -c`.
- Every delivery issue assessed after this change shows a `request-recorded` row until the request is recorded.
- Each landed issue has a `trail.md` that a reviewer checks with `sha256sum -c`, without Compass installed.
- After a merge, a committed record gets the post-merge fields with `compass record commit`.

What old issues keep:

- Each verdict. No archived manifest holds `evidence_required`, `landed_with_record` or `policy:`, and no archived folder holds `trail.md`. The archive comparison over 622 issue folders must show no change.
- Contracts 1 to 5. The new flags are optional, so `quick-fix-start-valid` still exits 0.

For this repository:

- It stays kept out, because its `compass.yml` names `record.remote`. `trail.md` is written into its ignored issue folders, and `compass record sync` carries it.
- `CLAUDE.md` does not change. To switch to committed records later, the owner changes the `CLAUDE.md` rule that keeps issue state untracked, sets `record.commit: true`, and removes the `.gitignore` patterns for the issue folders.

## Open questions

Each question has the decision this change builds. The owner confirms questions 1, 3, 4, 6, 14 and 18 when accepting this record, because each changes what a user sees.

1. **What is the default mode for a project that syncs a record and does not say?** Decided: kept out when `record.remote` is set and `record.commit` is not. Such a project chose a separate record store, so the default does not move its files.
2. **What happens when git ignores the issue folder in committed mode?** Decided: kept out, with one line at ship naming the ignore rule and `record.commit: false`. Force-adding would override the project's own choice.
3. **Is the request a stop?** Decided: no. It is a token, a failing `request-recorded` check and a `next:` line (decision 6).
4. **What does a change with no request to link do?** Decided: a waiver of `request-recorded` that a person approves (ADR-094 waivers).
5. **What is a requester?** Decided: free text, one line, at most 100 characters, recorded by the session and labelled as a claim.
6. **How does a fresh clone get a generation?** Decided: rebuilt from the manifest's `policy:` block when the digest matches, with `autonomy` added to the block (decision 5). The measurement shows the rebuild is exact. Reversing it means committing `generations/<n>/` and removing it from the ignore file.
7. **Does each release keep the earlier check sets?** Decided: yes, from the first release after 9.0.0 that changes the check set. Nothing is copied now.
8. **How is the land commit found?** Decided: from git, by the commit that added the current `land_timestamp`, only when the manifest holds `landed_with_record: true` (decision 3).
9. **Where is `trail.md`?** Decided: `.compass/work/<slug>/trail.md`, beside what it hashes.
10. **Is `trail.md` written in kept-out mode?** Decided: yes. `compass record sync` carries it.
11. **What is the path base?** Decided: the repository root, as the issue asks.
12. **Does section 4 hash the code and tests?** Decided: yes, with the digests of the newest green's `file_sha256`.
13. **When is `trail.md` written?** Decided: by `compass ship-commit`, `compass issue link set --pr`, `compass record commit` and `compass trail`; `compass check` prints a line when it is out of date.
14. **How do the post-merge fields reach a committed record?** Decided: a follow-up commit made by `compass record commit`, named by `next:` after `compass issue link set --pr` (decision 9).
15. **What stays out of the commit?** Decided: the list in decision 4.
16. **Does `compass init` write ignore rules?** Decided: yes (decision 4).
17. **Does the contract change?** Decided: no.
18. **What does this repository do?** Decided: it stays kept out, because it names `record.remote`. Its `CLAUDE.md` does not change now. Writing `record: {commit: false}` into its `compass.yml` is the owner's choice.
19. **Names.** Decided: the token `request`, the check `request-recorded`, the key `landed_with_record`, the verbs `compass trail` and `compass record commit`, and the setting `record.commit`. `governance/terminology.yml` gains `trail`, `request link` and `record mode`.

## References

- ayeo-io/compass-delivery#356 [Commit the issue record with the code and add trail.md] and its parent, #345 [Reposition Compass 9.0.0 as an ATDD framework with a proof trail], defects E1 and E6.
- Related issues:
  - #348 [Make evidence digests checkable with sha256sum], which added `evidence/SHA256SUMS` (ADR-089);
  - #355 [Read the ship approval from the merged PR review], which writes the post-merge fields (ADR-095);
  - #357 [Replace configuration layers and presets with one fixed check set], which added the `policy:` block (ADR-094).
- ADR-089 (the `sha256sum` digests of red and green records), ADR-094 (the check set and the `policy:` block, decision 4), ADR-095 (the ship approval, open question 16).
- `cli/compass_pkg/manifest.py`, `cli/compass_pkg/generation.py`, `cli/compass_pkg/effective.py`, `cli/compass_pkg/record.py`, `cli/compass_pkg/issue_link.py`, `cli/compass_pkg/pull_request_link.py`, `cli/compass_pkg/evidence_required.py`, `cli/compass_pkg/evidence_sums.py`, `cli/compass_pkg/init_cmd.py`, `cli/compass_pkg/quick_fix_cmd.py`, `governance/check-set.yml`, `docs/delivery-record.md`.
