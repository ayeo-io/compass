---
id: ADR-095
title: Compass reads the ship approval from the merged pull request
status: proposed
date: 2026-11-07
supersedes: ''
superseded_by: ''
---

## Context

Compass 9.0.0 is an ATDD framework with a proof trail (ayeo-io/compass-delivery#355 [Read the ship approval from the merged PR review], under #345 [Reposition Compass 9.0.0 as an ATDD framework with a proof trail]). The answer of #345 to its open question 2 binds this change:

> Every change gets one person's approval, at ship. Compass reads it from the merged PR's review, not from a stop in the session. Sign-off on the scenarios before code is required only when assess says so: a label (auth, payments, personal-data or migrations) or critical risk.

Three earlier records hand parts of this to #355:

- ADR-092 open question 6: #351 added the `scenario-approval` token and the `specify` checkpoint for it, and #355 adds the PR approval and the scenario digest freeze;
- ADR-092 open question 8: the delegation audit line in `devlog.md` moves with #355;
- ADR-094: #355 owns the ship approval, and ADR-094 added only the waiver subject.

What is in place before this change:

- **Scenario sign-off.** `RP-EVID-SIGNOFF` adds `scenario-approval` for a `G5` label or critical risk (`evidence_required.ADDITIONS`). The answer is a `checkpoint-approval` record at the `specify` checkpoint. Nothing refuses a red or a code edit before the answer; only the landing refuses (`checkpoint_outcomes.landing_refusal`).
- **The red record.** `compass tdd-red` writes `evidence/red-<scenario>.json` and the `.red` marker that unlocks code edits. The tree id leaves out `docs/compass/`, so no red covers the spec.
- **The one read of GitHub.** `compass issue link set --pr <n>` reads the pull request with `gh pr view` and moves `land_commit` to the merge commit (`pull_request_link.py`). `compass check` never calls `gh`.
- **The landing.** `compass ship-commit` writes `land_commit` and status `completed` before any pull request exists. So the ship approval cannot be a landing refusal on a project that uses pull requests.
- **Approvals.** A `human-approval` record with no subject key in `approval_records.SUBJECT_KEYS` is a `G5` sign-off. The writers are the terminal, the prompt hook and a delegation (ADR-066, ADR-069, ADR-077).
- **Delegations.** `delegations.record_use` counts each use in the delegation file and appends a line to the issue's `devlog.md`. ADR-092 stopped every other new `devlog.md` write. The pre-tool hook refuses an agent's tools on `.compass/delegations/`.

What GitHub gives (checked with `gh` 2.103.3 on 7 Nov 2026):

- `gh pr view --json` gives `author`, `mergedAt`, `headRefOid` and `reviews`, but no bot flag on a reviewer.
- `gh api repos/<r>/pulls/<n>/reviews` gives each review's `id`, `state`, `submitted_at`, `commit_id`, `html_url` and `user.login` with `user.type` (`User` or `Bot`).
- An approval of an earlier commit than the merged head is common. On cli/cli#14976 the approval named commit `86ef0593`, and the merged head was `6ceb78a5`.
- This repository's merged pull requests have no reviews. #733 has `reviews: []`, and the 30 newest show `reviewDecision: ""`.

No archived issue may change its `compass check` verdict. None of the 622 archived manifests in the main checkout holds `evidence_required`.

## Decision

1. **Every delivery issue owes a ship approval.** `evidence_required.TOKENS` gains `ship-approval`, and `EVERY_ISSUE` gains it, so `RP-EVID-LIGHT`, `RP-EVID-DEFECT` and `RP-EVID-STANDARD` owe it. A spike owes nothing. No rule id is added. The token meets no gate, so `gates` and contract 2 do not move. An issue owes the approval only if its stored `evidence_required` lists the token, so no archived issue owes it.
2. **One check outside every gate.** `governance/check-set.yml` gains the check `ship-approval-present` (deterministic, blocking, `on_skipped: not-applicable`), the evidence type `pr-approval` and its display name. The check is in `never_waived`, because the typed approval is already the way a person excuses a missing review. `outside_gate.CHECKS` gains it last. `compass check` skips it with no row when the issue's `evidence_required` does not list `ship-approval`. No gate id changes. The check set version stays `9.0.0`, because 9.0.0 is not released, and `tests/fixtures/check-set-digests.yml` is repinned.
3. **The verdict.** In order:

   | Records show | Result |
   |---|---|
   | A `pr-approval` record for the linked pull request, or a `human-approval` record with `ship:` for this issue and generation, not withdrawn | pass, naming the approver, the time and the record id |
   | `pull_request.merged_at` is recorded and no approval is on record | fail, naming the pull request and `compass evidence request --ship` |
   | The issue is in flight | nothing to check: due at ship |
   | The issue has landed and no merge is recorded | nothing to check: names `compass issue link set --pr <n>` and `compass evidence request --ship` |

   A `G5` sign-off does not count. It is given before code, at specify. The issue asks for an approval of each change at ship, and a change with a label must not need less at ship than an ordinary one. When a `pr-approval` record's `reviewed_commit` differs from its `head_commit`, the pass detail says so.
4. **Compass reads the approval when the pull request link is set after the merge.** `compass issue link set --pr <n>` asks `gh pr view` for `number,state,mergeCommit,mergedAt,author,headRefOid,url`. When the pull request is merged, it reads the reviews with `gh api --paginate repos/<r>/pulls/<n>/reviews` and the reading account with `gh api user`, before it writes anything. If a call fails, nothing is written. `compass check` stays offline.
5. **Which reviews count.** A new module of the CLI package, the `ship_approval` module, picks the approvals. A reviewer counts when all of these hold:
   - the reviewer's latest `APPROVED`, `CHANGES_REQUESTED` or `DISMISSED` review at or before `mergedAt` is `APPROVED` (a `COMMENTED` review does not change the state, as on GitHub);
   - `user.type` is `User`, not `Bot`;
   - `user.login` is not the pull request's author.

   The command prints one line for each counting reviewer, and one line for each review it sets aside, with the reason (author, bot, after the merge, superseded).
6. **The `pr-approval` record.** In one save, the command writes:
   - `pull_request: {repo, number, merged_at, merge_commit, author}`. The manifest schema gains the three optional keys;
   - one `pr-approval` evidence record for each counting reviewer, with the pull request, `review_id`, `url`, `approver`, `pr_author`, `decision: approved`, `timestamp`, `reviewed_commit`, `head_commit`, `merge_commit`, `merged_at`, `read_at`, `read_as`, `via: github`, `issue` and `generation`. A second run replaces the record of the same `review_id`, so it writes nothing new;
   - `land_commit`, as before.

   `compass evidence add --type pr-approval` is refused.
7. **The typed ship approval.** For a project not on GitHub, and for an author who is the only reviewer:
   - `approvals.FORMS` gains `ship`. The record is a `human-approval` record with `ship: <slug>`, the `HEAD` commit, the approver, the role, `decision: approved`, the time, the issue and the generation;
   - `approval_records.SUBJECT_KEYS` gains `ship`, so the record never clears `G5`;
   - an agent asks with `compass evidence request --ship` and stops. A person answers by typing `/compass:approve`, or with `compass evidence approve --ship` at a terminal;
   - a delegation covers it only when typed `--for ship`, with the confirmation code typed back, as for `g5` and `waivers`;
   - `/compass:reject <record id>` withdraws it.
8. **The hook refuses an agent's review approval.** The pre-tool hook refuses, with the new reason `pr-review-protected`:
   - `gh pr review` with `--approve`, `-a` or `--approve=`;
   - `gh api` that names `pulls/<n>/reviews` with a `POST` or `PUT` method, or with a field `event=APPROVE`.

   A comment review and `gh pr view` stay allowed. So an agent with the person's credentials cannot approve a pull request in the person's name.
9. **Scenario sign-off comes before code.** On a path issue that owes `scenario-approval`, `compass tdd-red` refuses while the `specify` checkpoint has no person's answer. It refuses before the test runs, so no red record and no `.red` marker are written. The landing refusal stays. An issue that does not owe `scenario-approval` is not affected.
10. **The sign-off names what was approved.** A `checkpoint-approval` record for `specify` on a path issue holds `spec` (the spec's path) and `spec_sha256` (the `sha256sum` digest of its bytes). The request holds the same digest. The prompt hook refuses to record when the spec changed after the request was shown, as it does for a changed waiver.
11. **The scenarios freeze at the first red.** On a path delivery issue, each red record holds `spec_sha256`, inside its `content_digest`. The first red of the issue writes `scenario_freeze` into the manifest: the time, the red record, the spec's path, its digest and the scenario ids. The freeze is never rewritten. `compass check` prints one line, not a row, with the digest, and notes when the spec has changed since. A new module of the CLI package, the `scenario_freeze` module, holds the digest, the write and the line.
12. **Each delegation used is copied into the manifest.** In the same save as the record it authorized, the manifest's `delegations_used:` gets a copy of the delegation under its id. The copy holds `format`, `delegated_by`, `role`, `approver_source`, `created_at`, `agent` or `covers_session`, `until`, `issues`, `forms`, `labels` (on a 7.0.0 file), `max_uses`, `created_via`, `prompt_id` and a `sha256` of those fields. `covers_session` is kept as `true`, not as the id of the session the delegation was typed in, because a process that knows a session id can resume that session; the approval record already holds the `session_id` of the session that used the delegation. `format` and `labels` are kept because they decide how the delegation was read. The copy leaves out the nonce, the use count, the index of other issues' records, `session_id`, `requested_prompt_id` and `revoked_at`. A second use keeps the first copy when its `sha256` matches, and adds `<id>@2` when the fields changed. `record_use` stops writing `devlog.md`. No key and no folder is named `delegations`, so the hook's rule on that word does not refuse a read of the issue folder.

## Limits

These are the limits of the decisions above. `docs/safety-contract.md` states them, as ADR-069 decision 8 states the same-user limit for delegations.

- A process running as the same operating system user can edit `manifest.yml`, and so can write a `pr-approval` record by hand.
- A process running as the same user can put another program named `gh` on `PATH` before Compass runs it, and so can give Compass a review that GitHub does not hold.
- `compass check` does not read GitHub again. A reader checks a `pr-approval` record by its review id, with `gh api repos/<r>/pulls/<n>/reviews/<id>`.
- The rules exclude the pull request's author and any `Bot` account, but not a second human account the same person controls. `read_as` lets a reader see when the reviewer and the reading account are the same.

What this change does not do:

- It writes nothing to GitHub, in any case.
- It does not refuse `compass ship-commit`, `compass quick-fix finish` or any other landing for a missing ship approval.
- It does not make `compass check` call `gh`.
- It does not count a `G5` sign-off as the ship approval.
- It does not move the post-merge fields into the merged commit. #356 [Commit the issue record with the code and add trail.md] decides that.
- It does not change `controlled` autonomy's list of checkpoints.
- It does not change the gate ids, the check set version, `generation.RESOLVER_VERSION`, `tests/fixtures/frozen-digests.yml` or any compatibility corpus.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| A new guardrail `G6` for the ship approval | A guardrail is where Compass puts a rule every change must meet | Every archived issue that reads the check set would gain the row, and a gate's `when` cannot tell a path issue from an old one |
| A gate at ship, not a check outside every gate | The other ship evidence is checked by gates | ADR-092 keeps the gate ids, and a gate cannot skip an old issue with no row |
| Read the reviews in `compass check` | The verdict would always be up to date | `compass check` must stay offline, and a check that calls the network gives a different verdict when GitHub is down |
| A new verb to read the approval | One verb, one purpose | `compass issue link set --pr` already reads the pull request after the merge and moves `land_commit`; a second verb is a second step to forget |
| Count only an approval of the merged head commit | GitHub's "dismiss stale approvals" setting does this | An approval of an earlier commit is common (cli/cli#14976), and the record holds both commits so a reader can see the difference |
| Refuse `ship-commit` until an approval exists | The rule would hold at the moment of landing | The landing comes before the pull request exists, and #345 rules out a stop in the session; about 25 to 45 test files that land a path issue would need an approval first |
| Count a `G5` sign-off as the ship approval | A person already approved the issue | It is given before code exists, so a change with a label would need less at ship than an ordinary one |
| Let no delegation cover the typed ship approval | An approval at ship is a person's act | A solo owner with no reviewer would stop on every issue; a delegation typed `--for ship` with the code is the same rule as `g5` and `waivers` |
| Keep only the landing refusal for scenario sign-off | Fewer refusals | The `.red` marker unlocks code edits, so a sign-off after the red signs off nothing |
| Copy the delegation file into the issue folder | A byte-for-byte copy | The file holds a nonce and other issues' paths, and a folder named for delegations is refused by the hook |

## Consequences

What changes for a user:

- Every path delivery issue assessed after this change owes `ship-approval`. A path issue assessed on `v9` before it owes the approval from its next `compass approach evaluate --write`.
- `compass check` on such an issue shows one more row. The row reports "nothing to check" until the record says the pull request merged, and fails only after the merge with no approval on record.
- A project on GitHub gets the approval from a review by a person other than the author, read by `compass issue link set --pr <n>` after the merge. A project not on GitHub, or a solo author, gives a typed approval for each issue, or types a delegation `--for ship`.
- An agent cannot approve a pull request through `gh`: the hook refuses it.
- On an issue with a `G5` label or critical risk, `compass tdd-red` refuses until a person answers the `specify` checkpoint. About 10 test files that record a red on such an issue need the answer first.
- Each red record on a path issue holds the spec's digest, and the manifest holds the scenario freeze.
- A delegation's use is recorded in the manifest, not in `devlog.md`.

What old issues keep:

- Each verdict. No archived manifest holds `evidence_required`, so none owes the token and none gains the row. The 162 issues with a stored generation read their own `resolved.yml`, which does not declare the check. The archive comparison over 622 issue folders must show no change.
- Their red records. The freeze and the spec digest are written only on a path issue.
- Contracts 1 to 5. The new token meets no gate, the contract 3 sample owes no token, new flags add no contract 4 entry, and the contract 5 corpus holds no `gh pr review` or `gh api .../reviews` command.

For this repository:

- Its pull requests have no reviewer, so the owner gives the typed approval for each issue, or types a delegation `--for ship`. While `v9` is built locally with no pull requests, its path issues report the ship approval as nothing to check.
- `CLAUDE.md` does not change. Its "Approvals" rule holds as written, and the safety contract keeps seven guarantees, because the ship approval extends guarantee 5.

### As built

These decisions were taken while #355 was built. The decisions above hold them; each point says how the build differs from, or adds to, the first text of this record (commit 7764197f).

- **Question 8 was reversed before the build.** A `G5` sign-off does not count as the ship approval. The check reads only a `pr-approval` record and a typed `human-approval` record with `ship:`, and its corpus has a case in which a `G5` sign-off alone does not pass (`tests/fixtures/impls/ship-approval-present/g5-signoff/`). The other owner-named questions (6, 9, 11, 16 and 18) are built with their defaults.
- **Decisions 1 to 3** are built as written (commit 7edf228f). `governance/check-set.yml` stays `compass-checks@9.0.0`, and `tests/fixtures/check-set-digests.yml` is repinned. `ship-approval-present` and `pr-approval` are not in `governance/guardrails.yml`, because that file is frozen byte for byte (ADR-094). The tests that compare the check set with it leave the two out by name (`ADDED_AFTER_THE_FREEZE` in `tests/check_set_files.py`), and the Definition of Done data test lists the check as added after the freeze (commit bf9ec5a0).
- **Decision 4** adds two refusals (commit 723ad29d). A merged pull request whose answer has no merge time or no author is refused, and nothing is written. An open pull request records the link only. A second run replaces a record of the same review in place, and writes nothing new when only `read_at` or `read_as` would change.
- **Decision 5** compares a reviewer's login with the author's without letter case, as GitHub does. A review with no login, no id or no readable time is ignored.
- **Decision 7** is built in `approvals._record_ship` (commit e32fd9a1). It also refuses an issue whose `evidence_required` does not list `ship-approval`, a second approval while one stands, `--decision rejected`, and a name that is not a project approver. `head` is null outside a git repository. `approvals._head` runs `git rev-parse HEAD` with the person's environment, like every other git read of the CLI, so it is listed as a git call in `tests/test_directory_validator.py` (commit 26ed288e). A default delegation now says that it does not cover the ship approval.
- **Decision 8** refuses more than its first text named (commit 98468b52):
  - `gh api` on `pulls/<n>/reviews` with any method other than `GET` or `HEAD`, in any argument order. With no method, a field or `--input` makes the call a `POST`, as `gh` sends it. A field `event=APPROVE` is refused with any method;
  - `gh api graphql` with the mutation `addPullRequestReview` or `submitPullRequestReview`;
  - `-a` joined to other short options, such as `-ab`.

  Each command of a chain is read, and each quoted word that names a review is read again, so `bash -c`, `eval` and a pipe into `sh` are covered. The shell prefilter starts the guard for a command that names `gh` and then `review`, so a guard that cannot run refuses it. The cost: a command that is not simple and quotes a refused form, such as `grep 'gh pr review -a' docs`, is refused. `docs/safety-contract.md` states the cost and the limits (a path or body in a variable or a file, a `gh` alias, another HTTP client). Contract 5 does not change.
- **Decision 9** refuses with the new refusal code `scenarios-not-approved`, which names `compass evidence request --checkpoint specify` and `/compass:approve` (commit 13d4e9dc).
- **Decision 10**: the prompt hook also closes the request as stale when the spec changed after it was written.
- **Decision 11**: the default view of `compass check` prints the freeze line only when the spec has changed since the first red. The full view and the JSON document always print it.
- **Decision 12** keeps `covers_session` as `true` and keeps `format` and `labels`, which its first text did not list (commits a4d88eab and 28d4a699). Each approval writer, the typed ship approval included, calls `approvals.keep_authority` just before its save. A second use is matched by `sha256` against the copy under the id and each `<id>@<n>`. The delegation id gets its own code, `DL`, in `governance/terminology.yml` (commit 381aa24d).
- **`compass next` names the ship approval after the landing** (commit 69f4a6fb). On an issue closed as completed that owes `ship-approval` with none on record, it prints `all phases complete | next: <command>`. The command is `compass issue link set --pr <n> --issue <slug>` after the merge, or `compass evidence request --ship`; once the merge is recorded, only the second. `governance/terminology.yml` gains `ship-approval`, `pr-approval`, `scenario-freeze` and `delegation-copy`, at version `2.0.0-pre28`.
- **Three skills went over their 200-line ceiling** with the new text: `bdd-specification`, `compass-runtime` and `evidence-gates`. Each was cut back to 200 lines with no fact removed (commit c7ad0387).
- The archive comparison over 622 issue folders shows no verdict that moves after decisions 9 to 11 (commit 13d4e9dc).

## Open questions

Each question has the default this change builds. The owner decides questions 6, 9, 11 and 18 when accepting this record, because each changes what a user sees. Question 8 was reversed from the plan's default before the build. Question 16 is coordinated with #356.

1. **Where is the requirement recorded?** Default: a token, `ship-approval`, in every delivery row (decision 1). The other answer is a new guardrail `G6`, which every archived issue that reads the check set would gain as a row.
2. **Gate or check?** Default: one check outside every gate, skipped with no row when not owed, in `never_waived` (decision 2). A gate's `when` cannot tell a path issue from an old one, and ADR-092 keeps the gate ids.
3. **When does Compass read the approval?** Default: `compass issue link set --pr <n>`, run after the merge (decision 4). The other answers are a new verb, or a read in `compass check`, which must stay offline.
4. **Which reviews count?** Default: the reviewer's latest state at the merge is `APPROVED`, the account is a `User`, and it is not the author (decision 5). Each counting reviewer gets a record; one is enough.
5. **Must the approval name the merged head commit?** Default: no. It counts, the record holds `reviewed_commit` and `head_commit`, and the pass detail says when they differ. The other answer counts only an approval of the merged head.
6. **When does the check fail?** Default: only when the record says the pull request merged and no approval is on record. It never refuses a landing, because #345 rules out a stop in the session. The other answer refuses `ship-commit` on a project not on GitHub until a typed approval exists.
7. **What does a project without GitHub, or a solo author, do?** Default: the typed approval (decision 7), a `human-approval` record with the subject key `ship`.
8. **Does a `G5` sign-off count as the ship approval?** Decided: no. A `G5` sign-off is given before code, at specify. The issue asks for an approval of each change at ship, and a change with a label must not need less at ship than an ordinary one. Reversing it means accepting a `G5` sign-off record in the `ship_approval` module.
9. **Can a delegation cover the typed ship approval?** Default: only when typed `--for ship`, with the confirmation code, as for `g5` and `waivers`. The copy of decision 12 records the authority. The other answer lets no delegation cover it.
10. **Does `controlled` autonomy still wait at specify on every change?** Default: yes. It is the project's choice to wait at every hand-off, not the scenario sign-off rule. The other answer removes specify from `controlled`'s list when `scenario-approval` is not owed.
11. **Does `compass tdd-red` refuse before the scenarios are approved?** Default: yes, where `scenario-approval` is owed (decision 9), because the `.red` marker unlocks code edits and the issue says "before code". The other answer keeps the landing refusal only.
12. **What does the freeze cover?** Default: every path delivery issue, at its first red. Each red record also holds the spec digest, and `compass check` prints a line, not a row, when the spec changed (decision 11). The other answers write the freeze only where `scenario-approval` is not owed, or fail a row when the spec changed.
13. **Where does the delegation copy go?** Default: the manifest's `delegations_used:`, in the same save as the record, and the `devlog.md` line goes (decision 12). The other answer copies the file into the issue folder, which needs a folder name the hook does not guard.
14. **Does the record name who read it?** Default: yes, `read_as` from `gh api user`. It costs one call and lets a reader see when the reviewer and the reading account are the same.
15. **Does the check set version move?** Default: no. It stays `9.0.0` with a new digest pin, because 9.0.0 is not released. The other answer is `9.1.0`.
16. **How do the post-merge fields reach the default branch?** The approval, `merged_at` and the moved `land_commit` are written after the merge, so the merged commit does not hold them. Default: #355 writes them into the manifest, and `compass record sync` carries them. #356 decides how a committed record gets them, by a follow-up commit or by `trail.md` naming them.
17. **Does the hook refuse an agent's review approval?** Default: yes (decision 8). A comment review and `gh pr view` stay allowed.
18. **What does this repository do?** Its pull requests have no reviewer. Default: the owner gives the typed approval for each issue, or types a delegation `--for ship`. While `v9` is built locally with no pull requests, its path issues report the ship approval as nothing to check.

## References

- ayeo-io/compass-delivery#355 [Read the ship approval from the merged PR review] and its parent, #345 [Reposition Compass 9.0.0 as an ATDD framework with a proof trail], open question 2.
- Related issues:
  - #351, which added the `scenario-approval` token and the `specify` checkpoint for it (ADR-092);
  - #356 [Commit the issue record with the code and add trail.md], which decides how a committed record gets the post-merge fields;
  - #357 [Replace configuration layers and presets with one fixed check set], which made the check set this change adds to (ADR-094).
- ADR-066 (an approval names its subject), ADR-069 and ADR-077 (delegations, and the same-user limit), ADR-089 (the `sha256sum` digests of red and green records), ADR-092 (one path, and open questions 6 and 8), ADR-093 and ADR-094 (the check set, `never_waived` and the waiver subject).
- `cli/compass_pkg/evidence_required.py`, `cli/compass_pkg/pull_request_link.py`, `cli/compass_pkg/issue_link.py`, `cli/compass_pkg/approvals.py`, `cli/compass_pkg/approval_records.py`, `cli/compass_pkg/delegations.py`, `cli/compass_pkg/tdd.py`, `cli/compass_pkg/check_cmd.py`, `cli/compass_pkg/outside_gate.py`, `cli/compass_pkg/approval_guard.py`, `governance/check-set.yml`, `tests/fake_gh.py`.
