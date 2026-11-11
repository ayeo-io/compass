---
id: ADR-099
title: Compass keeps the record itself and a change takes two commands
status: accepted
date: 2026-11-10
supersedes: ''
superseded_by: ''
---

## Context

Compass 9.0.0 must pass a measurement before it is released (ayeo-io/compass-delivery#361 [Run the pre-registered sdd-bench measurement on the 9.0.0 release candidate]). On every scenario, three things must hold:

1. the median tokens of a session with Compass are at most 1.5 times those of a session without it;
2. Compass reaches the target about as often;
3. every record passes a checker that reads only the files.

The release candidate (v9 `71efbb89`) failed on 10 November 2026. Compass used 3.6 to 14.2 times the tokens on all four scenarios, and 9 of 12 records failed a check. The results are in the sdd-bench repository, in its results page for 9.0.0 dated 10 November 2026.

The transcripts show one cause. The session keeps the record by hand, one command at a time:

- a session made 16 to 133 `compass` commands in a run, where a session without Compass made 14 to 45 tool calls in all;
- most were record keeping: `changed-file add`, `evidence add`, `gate pass`, `scenario add`, `tdd-red`, `tdd-green`, `waiver add` and `--help`;
- 13 to 18 commands in a run failed and were tried again;
- the session wrote its own security, governance and clarity reviews to pass the review gates.

Each tool call sends the whole context again, so the tokens grow with the number of calls.

An experiment branch, `exp-lean`, moved the record keeping into Compass. On the same four scenarios it used 0.77 to 1.29 times the tokens of a session without Compass, all 12 runs reached the target, and all 12 records passed the checker (its results page for the four scenarios, same date, in sdd-bench). The owner chose on 10 November to make it the basis of 9.0.0.

The built version (v9 `ac859818`) was measured on 11 November 2026, with both arms side by side. It passed the three rules on all four scenarios: 1.48, 1.32, 0.61 and 0.76 times the tokens of a session without Compass, all 12 runs reached the target, and all 12 records passed the checker (its results page for the two-command record, dated 11 November 2026, in sdd-bench). The owner accepted this record on 11 November 2026.

## Decision

1. **A change takes two commands.** `compass quick-fix start` opens the issue. `compass quick-fix finish -m "<message>" -- <test command>` writes the record. Between them the session writes tests and code and runs the tests directly. No other command is needed for a complete record.

2. **`finish` proves the red itself.** It copies the base commit to a temporary directory, lays the change's test files over it, and runs the test command there. The command must fail: the tests fail without the change. It then runs the command in the working tree, which must pass. The red record says `proved_on: base-copy`. A red recorded earlier with `compass tdd-red` still counts, and is the only proof that a test was written before the code: `finish` keeps it while the test files it names are unchanged, and adds the green. A change with no natural red, such as a refactor, declares an acceptance before the change with `compass acceptance start`; `finish` records that acceptance in place of the red and the green.

3. **`finish` reads the changed files from git** and records them. Test-run output, such as `.coverage`, is never part of the change. The change is what the working tree holds uncommitted. A committed file counts only when the manifest traces it already, from an earlier `finish` or from `compass changed-file add`, so a commit that a pull, a rebase or another person adds after `start` does not enter the change.

4. **Every delivery issue owes the same evidence**: the request link, the scenarios, the red before the green, a green suite, and the ship approval. `finish` also passes the three gates every issue has (`verify.correctness`, `verify.governance`, `verify.traceability`) from the test records and the output of `compass check`. Risk, size, familiarity and urgency add no review and no record. The one evidence row is `RP-EVID-COMMON` in `cli/compass_pkg/evidence_required.py`.

5. **A person's approval before code stays** for an issue with the label `auth`, `payments`, `personal-data` or `migrations`, for a label in the project's `signoff_labels`, and for `critical` risk. The session writes the scenarios, requests the `specify` approval (`compass evidence request --checkpoint specify`) and stops. The pre-tool hook refuses a code edit with the code `code-before-approval` until the approval is on record. An issue with such a label also owes the `G5` sign-off before it lands. `critical` risk alone owes the scenario approval and not the `G5` sign-off, as before this record.

6. **An approval covers the change the person saw.** `finish` writes a digest of the change in the manifest (`change_sha256`): the sha256 over the path and the content digest of each code and test file of the change, without the issue's record, its documents and the files a test run leaves. The request for the ship approval or the `G5` sign-off holds that digest, and the approval record copies the one the manifest holds when the person approves. When the code or the tests change afterwards, the next `finish`:

   - proves the red and the green again and commits on the branch, in the same call;
   - writes a new request for each approval, which replaces the pending one;
   - ends with one `next:` line that names the request and says nothing else is to run now.

   The earlier approval record is not edited or withdrawn. It is marked by the digests alone: `compass check` fails `ship-approval-present`, and `human-approval-present` on an issue with such a label, while the only approval on record names a digest that differs from the manifest's. Each passes again when a person approves the new state with `/compass:approve`. `ship-approval-present` also passes when `compass issue link set --pr` reads the approving review of the merged pull request (ADR-095), which is given after the change stopped moving. An approval given before the first `finish` covers no code, so the first `finish` asks again and does not commit. An approval record with no digest, and an issue whose manifest holds none, keep the meaning they had before this record.

7. **`finish` commits once the first ship approval is on record** (and the first `G5` sign-off, where one is owed), and on each later run. A commit on a branch is not a landing. On the default branch it makes a branch named after the issue first.

8. **One request is one issue.** A second `start` with a request that an issue already has makes that issue current again and creates nothing.

9. **No longer owed by default**: the gate reviews that the session wrote for itself, the Definition of Done items, and the records of the four-layer acceptance strategy `S17` (outer loop, isolation, layering). The `atdd` skill stays as guidance. The review tokens `regression`, `security`, `clarity` and `architecture`, and `reproduce-first` for a live defect, are not owed by default either. A project that wants one of these adds its token in `compass.yml` (`require_evidence`), and pays its cost in commands. A label in `signoff_labels` and a floor of the project's own that adds a gate are honored as before. The routing of `S17` is read from the tokens owed; with none it is `guidance`, a new value: no check of the strategy runs. The fixed check set no longer holds the floors `RP-REQUIRE-003` and `RP-REQUIRE-004`; the comparison with 8.0.4 puts them back in the test helper `tests/compat_baseline.py`.

10. **The older record commands stay and are not taught**: `tdd-red`, `tdd-green`, `scenario add`, `changed-file add`, `evidence add`, `gate pass`. Records they wrote still read and check.

## Alternatives considered

| Alternative | Why not |
|---|---|
| Keep 9.0.0 as built and fix the commands that fail | The failed commands are 13 to 18 of about 100. The count itself is the cost. |
| Record reds and greens from a hook that watches test commands | It depends on the test output the session chose to show, and it cannot tell which test failed when the output is cut. The base copy needs neither. |
| Keep the gate reviews | A review that the author of the change writes for itself is not evidence a reviewer can use, and each costs two or three calls. |
| Ask for no new approval after a change | The approval is what Compass adds over an agent alone. An approval that covers code the person never saw is worth less than none. |
| Cut Compass to the approval gate alone | The red, the request link and the committed record cost about 0.2 to 0.3 times the tokens of the change. The measurement shows that fits the rule. |

## Consequences

- "Red before green" in a record made by `finish` means "the tests fail without the change". It does not show the order of the work.
- Every changed file traces to every scenario of the issue. The trace by scenario is gone unless the session records it with `changed-file add`.
- An adopter's `compass check` passes on less evidence than in the release candidate. `docs/upgrade-9-0-0.md` says which checks no longer apply.
- A project whose tests need untracked build output, or an editable install of itself, can get a false red or a refusal from the base copy. `docs/base-copy.md` names the limit and the setting that links more paths in, `project.base_copy_links` in `compass.yml`.
- The digest of decision 6 is written by `finish` only. An issue whose record is kept by hand with the commands of decision 10 has no digest, so its approvals are not compared with the change.
- A new approval after a change is written to the manifest in the working tree. `finish` does not run again for it, so the next commit that holds the record carries it.
- ADR-092 (one path of four stages) and ADR-095 (the ship approval from the merged pull request) stay. This record changes who writes the evidence, not which approvals a change owes.
- The smallest scenario passes at 1.48 against the limit of 1.5. A change that adds a fixed cost to every session must be measured before it is released.

## Open questions

1. Should the commands in decision 10 be removed in a later release?
2. Should `finish` and `start` get shorter names, since "quick fix" now names the only path?

## References

- ayeo-io/compass-delivery#361 [Run the pre-registered sdd-bench measurement on the 9.0.0 release candidate].
- ADR-085 (the candidate and client of an outer-loop green), ADR-092 (one path of four stages), ADR-094 (the fixed check set), ADR-095 (the ship approval from the merged pull request), ADR-096 (the committed record and the request link).
- `cli/compass_pkg/finish_record.py`, `cli/compass_pkg/lean.py`, `cli/compass_pkg/evidence_required.py`, `cli/compass_pkg/approval_records.py`, `cli/compass_pkg/ship_approval.py`, `cli/compass_pkg/next_step.py`, `hooks/py/pre_tool_acceptance_verdict.py`.
- `docs/base-copy.md`, `docs/upgrade-9-0-0.md`, `compass-contract.md`, `commands/quick-fix.md`.
- `tests/test_two_command_change.py`, `scripts/two-command-e2e.py`.
