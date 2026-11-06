---
id: ADR-093
title: Compass keeps only what a reviewer of one change needs
status: proposed
date: 2026-11-06
supersedes: ''
superseded_by: ''
---

## Context

Compass 9.0.0 is an ATDD framework with a proof trail, and sdd-bench is its only accepted measurement (ayeo-io/compass-delivery#354 [Remove role entry points, the board, retro reporting, evals and the Codex adapter], under #345 [Reposition Compass 9.0.0 as an ATDD framework with a proof trail]). Two owner decisions of #345 (31 October 2026) bind this change:

- decision 5: "9.0.0 supports Claude Code only. The Codex adapter stays on 8.x."
- decision 9: "Follow-ups stay, cut to one rule: an open Definition of Done item must link to an issue."

Before 9.0.0 Compass also served audiences and measurements outside one change:

- four role entry points, `/compass:intent`, `/compass:position`, `/compass:design` and `/compass:consult`, with `compass intent ingest` (`ingest.py`) and five role templates (`positioning`, `launch-readiness`, `ui-contract`, `product-owner-review`, `architecture-notes`), which ADR-091 left for this change;
- the HTML board (`compass board`, `compass flow --html`) and GitHub label sync (`compass issue github sync`, the label write after each command);
- cross-issue reports: `compass retro` and its views, calibration, `compass issue friction` and the friction capture at `quick-fix finish`, and `compass rework-scan`;
- `compass readiness`, `compass init --readiness`, the readiness floor at assess and the session-start readiness line;
- the autonomy ratio and cost reports, the `usage` block, the tokens per stage and the session ids the pre-tool hook writes;
- `evals/`, with the eval harness, `evals/compare.py`, `evals/judge.py` and `cli/compass_pkg/host_launch.py`, which only the harness calls;
- the `initiative-new-subsystem`, `feature-api-change` and `hotfix-regression` examples;
- the Codex adapter (`adapters/codex/`, `.codex-plugin/`);
- follow-ups with five rules: defer an item, block closing (`backfills-paid`), block another issue (`--target`), resolve a tag on a page, and warn on a hotfix.

None of these produces evidence that a reviewer of one change needs. Each costs code, tests and docs, and some cost a write on every run.

The archive must stay readable. In the main checkout's archive, 38 of 616 manifests hold follow-ups, 111 hold `readiness`, 228 hold `usage` and 36 hold `friction`. Frozen presets (`default@6`, `default@7`) and stored generations declare a `readiness:` catalogue. No archived issue may go from pass to fail.

## Decision

1. **The role entry points go.** The four commands, `ingest.py`, the `compass intent ingest` verb, `docs/roles-guide.md`, `skills/intent-interview/role-translation.md` and the five role templates are deleted. The four slash commands get no stub, as ADR-092 gave none for the six stage commands. `removed_parts.AGENT_NAMES` and `policy_lint.PERSPECTIVES` keep the role names, because a frozen catalogue names them as artifact owners. The `intent-interview` skill stays without its role parts.
2. **The HTML board and label sync go.** `compass board`, `compass flow --html`, `compass issue github sync`, the label write after each command and `github_sync_record.py` are deleted. The text `compass flow`, with `--json` and `--digest`, stays; the digest loses its rework and retro sections. `compass issue link set` stays: a new module, `issue_link.py`, takes the link code and the `gh` runner from `github_labels.py`, and `pull_request_link.py` imports them from it.
3. **Cross-issue reporting goes.** `compass retro` and every view, `calibration.py`, `compliance.py`, `agent_friction.py` (`compass issue friction`), the private `compass _friction-capture` and `compass rework-scan` are deleted. The friction step of `/compass:ship` and the contract rule "Record friction you observe" go. `compass lesson`, `compass issue raised-by` and the decision ledger stay, because a command or hook of one issue reads them.
4. **Readiness goes.** `compass readiness`, `compass init --readiness`, the readiness floor at `approach evaluate --write` and the session-start readiness line are deleted. The shipped default declares an empty `readiness:` catalogue, as ADR-091 did for `artifacts:`. `readiness_registry.py` stays, so lint, `compass policy diff` and the classifier still read a frozen preset or a stored generation.
5. **Autonomy and cost reporting goes.** `autonomy_cost.py`, `issue_usage.py`, `session_usage.py`, `session_record.py` and the pre-tool hook's session record are deleted. `compass issue diagnose` stays, without the cost and band lines. The interruptions log stays. `checkpoint_outcomes.py` and the landing refusal stay, and their doc, the autonomy and cost page, is renamed `docs/checkpoints.md`.
6. **The harness moves to sdd-bench.** `evals/harness.py` and `host_launch.py` are copied to sdd-bench `tools/` first, with the harness tests that need no Compass internals. Then `evals/`, `host_launch.py`, the `harness-root` CI job and the eval clauses of the slug and title guards are deleted. The hook keeps exempting `evals/*/seed/*` in any project.
7. **Three examples go.** `examples/initiative-new-subsystem/`, `examples/feature-api-change/` and `examples/hotfix-regression/` are deleted. `quick-fix-typo`, `spike-technical-unknown`, `atdd-adapters` and `bdd-adapters` stay.
8. **The Codex adapter goes.** `adapters/codex/`, `.codex-plugin/`, the Codex page in `docs/` and the `codex` column of `schemas/adapter-contract.yml` are deleted. 9.0.0 supports Claude Code only. `AGENTS.md` stays, reworded to say so.
9. **Follow-ups have one rule on a path issue.** On a path issue (a manifest with `evidence_required`, ADR-092), an open Definition of Done item is met only by a follow-up that names a GitHub issue:
   - `compass follow-up add FU-<id> --defers <item> --github owner/repo#N --summary "..."` writes `follow_ups[].github: {repo, number}`, parsed as `compass issue link set` parses a target;
   - on a path issue `--github` is required, and `--defers` must name an item of the build exit list;
   - a follow-up without `github` meets nothing, so `dod-evidence-typed` fails with a hint that names the command;
   - `backfills-paid` has nothing to check, because the linked issue tracks the work;
   - `--target` is removed, and the stop hook no longer warns about outstanding follow-ups on a path hotfix.
10. **Old issues keep every follow-up rule.** A manifest without `evidence_required` keeps `backfills-paid`, the block on another issue (`target_task`), the page tags and the hotfix warning. `compass follow-up resolve` stays: its function `cmd_backfill_pay` moves from `rework.py` to `follow_up_cmd.py` with its name, and the rest of `rework.py` is deleted.
11. **Old settings warn.** `cli/compass_pkg/removed_parts.py` names each removed key with ADR-093, and the reason "Compass keeps only what a reviewer of one change needs". `compass policy lint` warns with `L-SETTING-REMOVED`:
    - a project `readiness:` catalogue and `github_labels` are dropped by the merge of a project layer and a git parent;
    - the readiness-only commands `project.build_command`, `lint_command`, `format_check_command`, `typecheck_command`, `secret_scan` and `structured_logging` are named by a new table, `SETTING_FIELDS`, and the merge keeps them;
    - a waiver on `readiness.<signal>` is read as any removed catalogue entry;
    - `autonomy` and `project.test_micro_command` stay, because the checkpoints and the TDD commands read them.
12. **Old manifest keys stay valid.** `readiness`, `usage`, `friction`, `intent_source`, `role`, `claims`, `github`, `reassessments` and `follow_ups[].target_task` stay in `schemas/manifest.schema.json`. Compass no longer writes `readiness`, `usage`, `friction`, `intent_source` or `target_task`. `G3` (`claim-traces-to-scenario`) still reads `claims`, and the `verify.claims` gate definition stays.
13. **Removed verbs fail with one line.** Each removed verb is added to `removed_parts.COMMANDS`, so a command line that names it fails to parse with a line that names ADR-093 and what to do instead:

    | Tokens | Instead |
    |---|---|
    | `retro` | sdd-bench is the measurement; compass check and compass approach show read one issue |
    | `readiness` | nothing measures the repository; the hooks and compass check guard each change |
    | `init --readiness` | compass init sets up the project; nothing measures it |
    | `board` | compass flow lists every issue |
    | `flow --html` | compass flow prints the issues; no page is written |
    | `issue github sync` | compass issue link set keeps the link; no label is written |
    | `intent ingest` | write the Summary and Intent of acceptance-criteria.md from the brief |
    | `rework-scan` | nothing replaces it |
    | `issue friction` | nothing replaces it |
    | `follow-up add --target` | link the follow-up to a GitHub issue with --github |

    The ADR-090 line for `retro --models` comes first and does not change. The private `_friction-capture` gets no line. The six retro entries of contract 4 move to `tests/compat_commands.py` `REMOVED_IN_9_0_0`; the frozen corpus and its digest do not change.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| Keep `compass retro` and calibration as optional reports | They read the archive and cost nothing on one issue | sdd-bench is the only accepted measurement; a second measurement can disagree with it, and its code and tests still cost upkeep |
| Keep the readiness floor | It stops an autonomous assess on a project below the floor | No command writes a fresh readiness record after `compass readiness` goes, so a kept floor would refuse every autonomous assess, this repository included |
| Delete the `readiness:` catalogue field from the configuration schema | Less code | A frozen preset and every stored generation declare it, so an archived issue would fail to load; #357 owns the catalogues |
| Delete `compass flow` with the board | One less cross-issue view | `compass flow` is the read of what is blocked, and `/compass:flow` uses it; only the HTML page writes a file |
| A follow-up names a Compass issue slug | It is what `--target` did | It made one issue block another; a GitHub issue tracks the work without a cross-issue check |
| Delete follow-ups and `rework.py` completely | Fewer rules | Decision 9 of #345 keeps follow-ups, and 38 archived issues hold them; their verdicts must not move |
| Delete the harness from Compass without copying it | Less work now | #361 [Run the pre-registered sdd-bench measurement on the 9.0.0 release candidate] needs the harness in sdd-bench |
| Keep the Codex adapter on 9.0.0 | A Codex user keeps the newest Compass | Decision 5 of #345 keeps it on 8.x |

## Consequences

What breaks for a user:

- The role slash commands are gone. A product owner's brief opens the acceptance criteria through the `intent-interview` skill, written by hand.
- `compass board`, `compass flow --html`, `compass issue github sync`, `compass retro`, `compass readiness`, `compass init --readiness`, `compass rework-scan`, `compass issue friction`, `compass intent ingest` and `compass follow-up add --target` fail to parse, with a line naming ADR-093.
- GitHub labels are no longer written. `compass issue link set` still keeps the issue's link.
- Nothing refuses an assess under `autonomy: autonomous` on a project with no readiness record. The guardrails (`G1` to `G5`) and the owner sign-off still apply.
- A project `compass.yml` that sets `readiness:`, `github_labels` or a readiness-only `project.*` command gets an `L-SETTING-REMOVED` warning. This repository's `compass.yml` sets all three, and warns until the owner removes them.
- Each session's contract loses the friction rule, and the pre-tool hook writes no manifest.
- On a new issue, an open Definition of Done item needs a follow-up that names a GitHub issue. The follow-up need not be resolved before ship.
- Compass 9.0.0 runs only under Claude Code. A Codex user stays on 8.x.
- The eval harness runs from sdd-bench, `harness.py` in the sdd-bench `tools` folder, and names the Compass checkout it measures with `--plugin-source`.

What old issues keep:

- Each verdict. An archived issue keeps its verdict or moves from fail to pass, never from pass to fail.
- Their keys. Every removed writer's key stays valid in `schemas/manifest.schema.json`.
- Every follow-up rule, and `compass follow-up resolve`.
- Their configuration. A frozen preset and a stored generation still declare and lint their `readiness:` catalogue.

## Open questions

Each question has the default this change builds.

1. **Does `compass flow` go with the board?** Default: no. The HTML board (`compass board`, `flow --html`) goes. The text `compass flow`, `--json` and `--digest` stay; the digest loses its rework and retro sections.
2. **Does friction recording go?** Default: yes. `compass issue friction`, `_friction-capture`, the friction step of `/compass:ship` and the contract's "Record friction you observe" rule go; the `friction:` key stays valid. `compass lesson` stays.
3. **Does `compass issue diagnose` stay?** Default: yes, without the cost and band lines. It explains one run from its own records.
4. **Does the interruptions log stay?** Default: yes. `diagnose` reads it, and its writer is one append that cannot fail a command.
5. **Does the pre-tool hook stop recording session ids?** Default: yes. Nothing reads `usage.sessions` after `issue_usage.py` goes, and the hook then writes no manifest.
6. **Does the readiness floor go?** Default: yes. No command writes a fresh readiness record after `compass readiness` goes, so a kept floor would refuse every assess of an autonomous project.
7. **What happens to the readiness catalogue?** Default: as ADR-091 did for `artifacts:`. The shipped default declares an empty `readiness:`, the field stays valid in the configuration catalogue, `readiness_registry.py` stays for lint and the classifier, and a project's `readiness:` is dropped with a warning.
8. **What is "an issue" in the follow-up rule?** Default: a GitHub issue, given as `--github owner/repo#N` or its URL and parsed as `issue link set` parses it.
9. **Must a linked follow-up be resolved before ship?** Default: no, on a path issue. An old issue keeps `backfills-paid` and `compass follow-up resolve`.
10. **Does `--target` stay?** Default: no; it gets a removal line. The reader of old `target_task` entries stays.
11. **What does the stop hook say on a path hotfix?** Default: it keeps the warning about the reproduction scenario and drops the one about outstanding follow-ups.
12. **How are claims reviewed?** ADR-091 left this to #354. Default: keep `claims`, `G3` and the `verify.claims` gate definition. No shipped rule adds the gate; a project adds it with `add_gate`.
13. **Does the `intent-interview` skill stay?** Default: yes, without `role-translation.md` and the section on an ingested brief.
14. **Does `AGENTS.md` stay?** Default: yes, reworded to say 9.0.0 supports Claude Code only. Deleting it can come with #360 [Rewrite the README for 9.0.0 and test it with a first-time reader].
15. **Does the hook keep exempting `evals/*/seed/*`?** Default: yes. It is a hook rule for any project, and removing it is a separate change. Its comment stops naming the Compass harness.
16. **Where does the harness go in sdd-bench, and do its tests go with it?** Default: `harness.py` and `host_launch.py` in the sdd-bench `tools` folder, with the harness tests that need no Compass internals in its `tools/tests` folder. `--plugin-source` is required. The two lab patches are applied in the same commit. The sdd-bench script `run-pilot-8x.sh` still rebuilds the 8.x pilot runner from the `v8.0.4` tag.
17. **Do the five role templates go?** Default: yes (ADR-091 open question 1).
18. **Do the slug and title guards keep their eval clauses?** Default: no. A project's `evals/` folder is not a Compass concept once the harness leaves. The path and public-copy rules stay (ADR-091 open question 7).
19. **Do the readiness-only `project.*` commands get a lint warning?** Default: yes, through `SETTING_FIELDS`, and the merge keeps them.

## References

- ayeo-io/compass-delivery#354 [Remove role entry points, the board, retro reporting, evals and the Codex adapter] and its parent, #345 [Reposition Compass 9.0.0 as an ATDD framework with a proof trail], decisions 5 and 9.
- Related issues:
  - #355 [Read the ship approval from the merged PR review] and #356 [Commit the issue record with the code and add trail.md] build on `pull_request_link.py` and `issue_link.py`;
  - #357 [Replace configuration layers and presets with one fixed check set] owns the configuration catalogues and presets;
  - #359 [Add compass migrate and the 9.0.0 upgrade guide] rewrites old settings;
  - #361 [Run the pre-registered sdd-bench measurement on the 9.0.0 release candidate] uses the harness in sdd-bench.
- ADR-047 (generated views in the system temp folder, which held the board file), ADR-090 (one session, no stage agents), ADR-091 (only the acceptance criteria) and ADR-092 (one path of four stages).
- `cli/compass_pkg/removed_parts.py`, `cli/compass_pkg/follow_up_cmd.py`, `cli/compass_pkg/item_records.py`, `cli/compass_pkg/readiness_registry.py`, `governance/presets/default/readiness.yml`.
