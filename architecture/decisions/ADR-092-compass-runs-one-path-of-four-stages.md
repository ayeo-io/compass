---
id: ADR-092
title: Compass runs one path of four stages and assess selects the evidence
status: proposed
date: 2026-11-05
supersedes: ''
superseded_by: ''
---

## Context

Compass 9.0.0 replaces the five approaches and the eight stages with one path of four stages: assess, specify, build and ship (ayeo-io/compass-delivery#351 [Replace the approaches and eight stages with one four-stage path], under #345 [Reposition Compass 9.0.0 as an ATDD framework with a proof trail]). Before 9.0.0 assess picked an approach, and the approach decided the rest:

- The shipped default declares five approaches: `spike`, `quick-fix`, `regular`, `hotfix` and `full` (`governance/presets/default/approaches.yml`). Each one sets a mode per stage, a gate set, a `subtask_ceiling`, the `S17` routing and the checkpoints per autonomy value.
- The routing shapes (`RP-SHAPE-001` to `RP-SHAPE-FALLBACK`), the floors (`RP-FLOOR-001`, `RP-FLOOR-003`) and the caps (`RP-CAP-001`) pick the approach (`governance/presets/default/rules.yml`).
- The eight stages are `assess`, `define`, `refine`, `plan`, `breakdown`, `implement`, `verify` and `ship` (`stable_ids.STAGE_IDS`). Each has modes and entry and exit lists (`stages.yml`). `plan.entry` holds the seven Definition of Ready checks; `verify.exit` holds the Definition of Done.
- Six stage commands run the middle stages: `/compass:define`, `/compass:refine`, `/compass:plan`, `/compass:breakdown`, `/compass:implement` and `/compass:verify`.
- Readers decide from a stage mode. The `G2` hook blocks a code edit with no scenario only where `define` is `thorough`. `dod-evidence-typed` judges a new issue only where `verify` is `thorough`.

After ADR-090 (one session, no stage agents) and ADR-091 (only the acceptance criteria), the stages between assess and ship no longer hand work to anyone or write a document. What still differs between the approaches is the evidence each one owes. The approach is an indirection between the assessment and that evidence.

The archive must stay readable. The main checkout's local archive holds 622 issues: 304 quick fix, 178 regular, 69 full, 1 hotfix, 3 spike and 54 with no approach. Frozen presets (`default@6`, `default@7`) and stored generations declare the approaches and stages. No archived issue may go from pass to fail.

## Decision

1. **One path.** A delivery issue runs assess, specify, build and ship. The four stages are fixed in code (`stable_ids.PATH_STAGE_IDS`). The stages have no modes. A new manifest writes no `stages:` map.
2. **The approach key stays.** `delivery_approach` keeps its name, with the values `delivery` and `spike` for a new issue. The readers that only test whether it is set (the route probe hook, `compass next`, the stop hook) do not change.
3. **Assess selects the evidence.** Assess computes `evidence_required`, the list of evidence the change needs before it ships, and stores it in the manifest. `gates`, the `acceptance_strategy` block and `checkpoints` are derived from it, so every check keeps reading the keys it reads now.
   - The tokens are a closed set: `scenarios`, `red-before-green`, `suite-green`, `correctness`, `governance`, `traceability`, `regression`, `security`, `clarity`, `architecture`, `outer-loop`, `isolation`, `layering`, `definition-of-done`, `reproduce-first`, `scenario-approval` and `human-approval`. Each one names the record that meets it.
   - A new module of the CLI package, `evidence_required`, computes the list as a pure function of the assessment and the configuration. Rows, first match wins: `RP-EVID-SPIKE` (goal `exploration`), `RP-EVID-LIGHT` (small, low risk, no `G5` label), `RP-EVID-DEFECT` (urgency `live-defect`, small) and `RP-EVID-STANDARD` (any other delivery assessment). `RP-REQUIRE-003`, `RP-REQUIRE-004`, `RP-EVID-SIGNOFF` and `G5` add tokens on top.
   - The rows give the 8.x gate sets: light is the old quick fix, defect the old hotfix, standard the old regular and full. A test checks this on every point of the 1,200-point routing grid and every label subset.
   - Any `add_gate` floor or project guardrail of the configuration in force still adds its gate. The function never reads that configuration's approach, shapes, stage modes or caps.
   - `evidence_required` is an outcome key, so a re-assess that changes it commits a new generation and logs a re-assessment.
4. **Hotfix is a setting.** The hotfix is no longer an approach. The assessment dimension `urgency: live-defect` adds `reproduce-first` and the old hotfix evidence (`RP-EVID-DEFECT`). The first scenario is the reproduction, and its red is recorded first.
5. **The gates keep their ids and are passed at ship.** The gate ids keep the `verify.` prefix. In the preset's `gates.yml`, `G2` and `G3` move to specify, `G1` to build, and `G4`, `G5`, `S1`, `S2` and every review gate to ship.
6. **No Definition of Ready.** The seven `dor-*` checks and `plan.entry` leave the shipped default. The Definition of Done is the build exit list (`build.exit`).
7. **Six stage commands go.** `/compass:define`, `/compass:refine`, `/compass:plan`, `/compass:breakdown`, `/compass:implement` and `/compass:verify` are deleted. `/compass:go` runs the path, and `/compass:quick-fix` is its short form. The agent-review rules in `commands/verify.md` (ADR-090 decision 7) move to `commands/ship.md`.
8. **The next command.** Every verb that writes a record of the issue prints `next: <command>` as its last line in text mode. One new module of the CLI package, `next_step`, decides the command from the records, so the verbs and `compass next` cannot disagree.
9. **Old issues.** A manifest without `evidence_required` keeps every rule it had. A legacy stage it shows is mapped onto the path: `define`, `refine` and `plan` to `specify`; `breakdown` and `implement` to `build`; `verify` and `ship` to `ship`.
10. **Old configuration.** The approaches, shapes, stage modes, caps and lists of removed stages in a frozen preset or a stored generation stay valid and are not read for a new assessment. A project layer that sets one gets a warning (`L-SETTING-REMOVED`), and the merge drops it.
11. **Not written.** Compass no longer writes `subtask_ceiling`, `max_worktrees`, `orchestration`, the breakdown mode or the caps rule set `RP-CAP-001`.
12. **No devlog.** Compass writes no `devlog.md` for a new issue. An archived one stays, and the readers that read it now still read it.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| A pinned frozen preset keeps its approaches | A project on `default@6` or `default@7` would see no change | It keeps the approach writer alive until a later release, and this repository, which pins `default@6`, would not run the path |
| Name the path value `standard` | It reads as the usual case | `standard` is a retired alias of `regular`; `delivery` matches `goal: delivery` |
| Drop the `verify.` prefix from the gate ids | The verify stage goes | Every archived manifest, evidence record and compatibility contract names the gates by their ids |
| Freeze a `default@8` preset for the compatibility contracts | The contracts compare against a frozen preset | Packing the `v8.0.4` governance as a test fixture does the same job; #351 does not raise the preset version, the 9.0.0 release does |
| New verb names for `compass quick-fix start` and `finish` | The verbs now serve every size | A rename adds churn now; it can come with the release |
| Keep a Definition of Ready on the plan stage | It was a step before the code | The plan stage goes, and the scenarios with their declared tests are the readiness record |

## Consequences

What breaks for a user:

- The six stage commands are gone. A person or agent runs `/compass:go`, or follows the `next:` line.
- `compass approach show` prints `delivery` or `spike` and an evidence line, not `quick-fix`, `regular`, `hotfix` or `full`.
- `compass quick-fix start` no longer refuses heavier work. `compass quick-fix finish` works on any delivery issue, and refuses with exit 1 while other evidence is owed.
- The `G2` hook refuses a code edit on every path issue that has no scenario, not only where `define` was `thorough`. `compass quick-fix start` always writes a scenario, and the refusal names `compass scenario add`.
- Under `controlled`, assess and specify are always checkpoints, and build and ship are checkpoints where `S17` applies. Under `balanced`, the 8.x waits at define and plan on medium work go.
- A project `compass.yml` that sets `approaches:`, a legacy stage, `autonomy_checkpoints` naming a legacy stage or a caps rule gets an `L-SETTING-REMOVED` warning, and the merge drops the key.
- An issue writes no `devlog.md`, and no Definition of Ready is owed.

What old issues keep:

- Each verdict. No check changes its rule for a manifest without `evidence_required`. An archived issue keeps its verdict or moves from fail to pass, never from pass to fail.
- Their keys. `stages:`, `subtask_ceiling:`, `max_worktrees:` and `orchestration:` stay valid in `schemas/manifest.schema.json` and are read only on an old issue.
- A command to run. `compass next` on an old issue prints the mapped path stage and a `next:` command.
- Their checkpoints. `CHECKPOINT_STAGES` holds the path stages and the legacy ones, so an old outcome for `define` still reads and an old request still closes.
- A way onto the path. `compass approach evaluate --write --reason` on an old issue writes the path keys and logs the old approach in `reassessments`.

## Open questions

Each question has the default this change builds.

1. **Does the path apply under a pinned frozen preset (`default@6`, `default@7`, a copied 5.6.0 governance)?** Default: yes, as ADR-090 and ADR-091 did for removed parts. The configuration still adds its `add_gate` floors and project guardrails.
2. **What value names the one path?** Default: `delivery`, matching `goal: delivery`. Not `standard`, which is a retired alias of regular.
3. **Does the path keep the 8.x evidence for each assessment?** Default: yes, with two deliberate changes: no Definition of Ready, and `scenario-approval` for a `G5` label or critical risk.
4. **Where does the Definition of Done list live?** Default: the build exit list (`build.exit`). `item_records.LISTS["dod"]` reads `build.exit` and falls back to `verify.exit` for an old configuration.
5. **Do the gate ids lose the `verify.` prefix?** Default: no. Every archived manifest, evidence record and contract names them.
6. **Does #351 add the scenario sign-off, or #355?** Default: #351 adds the `scenario-approval` token and lists the `specify` checkpoint for it under every autonomy value. #355 adds the PR approval and the scenario digest freeze.
7. **Which checkpoints does each autonomy value list?** Default: `controlled` lists assess and specify, plus build and ship where `S17` applies (the stage 2 and 3 reviews). `balanced` and `autonomous` list nothing, except specify where `scenario-approval` is required.
8. **Does `devlog.md` stay?** Default: no new writes. `compass quick-fix start` writes `acceptance-criteria.md` with the one scenario and the intent. The delegation audit line moves with #355, so #351 leaves `delegations.py` as it is.
9. **What happens to `compass approach render` (the approach diagram)?** Default: keep the verb. It draws the path, the spike and the evidence rows, and `docs/approach-diagram.html` is derived again.
10. **Does `--json` output gain the next command?** Default: only `compass next --json`, as a `next` field.
11. **Do `skills/plan-authoring/` and `skills/flow-management/` stay?** Default: delete `plan-authoring` with the plan stage, and update `flow-management`.
12. **Freeze `default@8` or pack a fixture for the contracts?** Default: pack the `v8.0.4` governance as a test fixture. #351 does not raise the preset version; the 9.0.0 release does.
13. **New verb names for start and finish?** Default: no. `compass quick-fix start` and `finish` serve every size; a rename can come with the release.
14. **How does a person turn on the hotfix setting?** Default: `--urgency "live-defect - <reason>"` on `compass quick-fix start`, and the existing `--assessment urgency=live-defect` on `compass approach evaluate`.
15. **Does a re-assess move an old issue onto the path?** Default: yes, and the re-assessment log records the old approach.
16. **What do `depends_on` `until` values accept?** Default: the path stages and the legacy names, each judged through the stage mapping.

## References

- ayeo-io/compass-delivery#351 [Replace the approaches and eight stages with one four-stage path] and its parent, #345 [Reposition Compass 9.0.0 as an ATDD framework with a proof trail].
- Related issues: #354 (the role entry points and the readers it owns), #355 (the PR approval and the scenario digest freeze), #357 (the configuration layers and the presets) and #359 (`compass migrate` and the upgrade guide).
- ADR-062 (`depends_on` `until`), ADR-063 and ADR-083 (checkpoints), ADR-079 and ADR-081 (the `S17` acceptance strategy), ADR-088 (a red before the first green), ADR-090 (one session) and ADR-091 (only the acceptance criteria).
- `cli/compass_pkg/stable_ids.py`, `cli/compass_pkg/routing.py`, `cli/compass_pkg/removed_parts.py`, `governance/presets/default/approaches.yml`, `governance/presets/default/stages.yml`.
