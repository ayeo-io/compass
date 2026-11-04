---
id: ADR-090
title: Compass runs in one session with no stage agents
status: accepted
date: 2026-11-04
supersedes: ''
superseded_by: ''
---

## Context

Compass 9.0.0 runs each issue in one session (ayeo-io/compass-delivery#345, decision 6, and #352). Before 9.0.0 a stage command handed its stage to one of ten agents in `agents/`, and the full and regular approaches split the build across worktrees. Five parts served that hand-off:

- the ten stage and role agents;
- the multiagent breakdown: the subtask record (`compass issue subtask`, `subtasks.py`), the check `multiagent-run-recorded` (`multiagent_check.py`), the scripts `scripts/multiagent.sh` and `scripts/integrate.sh`, and the `worktree-multiagent` skill;
- model tiers and effort per dispatch: the `model-tiers` and `model-floors` rule sets, the manifest's `models:` key, the `models` setting, `compass approach show --model` and `--effort`, and `compass retro --models`;
- execution profiles: `compass profile` and the `profiles` folder (ADR-076);
- the headless runner, `compass run` (ADR-030).

The spikes measured the cost. Stage subagents added 2 to 4 million tokens a run. Subtask records drove about 4 calls a run, and one run made 28 waiver calls (the 9.0.0 repositioning proposal of 31 October 2026, which #345 links: rows B, F and G).

Archived issues still hold records that name these parts. Their stored generations list `multiagent-run-recorded`, their manifests hold `subtasks:`, `models:` and `subtask_ceiling:`, and a project's `compass.yml` can hold `models:` and `multiagent:`. A record must stay readable, and no archived issue may go from pass to fail.

## Decision

1. **No stage agents.** The ten files in `agents/` are deleted, the reviewer with them. Each stage command runs its stage in the main session, with the skill the command names. The role entry points (`/compass:intent`, `/compass:position`, `/compass:consult`) take the role in the main session until #354 removes them.
2. **No multiagent breakdown.** `subtasks.py`, `multiagent_check.py`, `scripts/multiagent.sh`, `scripts/integrate.sh`, `scripts/lib/issue-docs.sh`, the `worktree-multiagent` skill and `docs/multiagent-protocol.md` are deleted. The session builds the units of a distribution map one after another, in its own tree. A distribution map no longer needs a `units:` line, and registering one writes no subtask record. The breakdown stage keeps its mode name `multiagent` in the routing policy until #351 replaces the stages. `worktree_lookup.py` stays, because delegations use it, and so does the pre-tool hook's reading of a worktree (ADR-078).
3. **The removed check.** `multiagent-run-recorded` moves to the table of removed checks (`check_registry.REMOVED`), with no replacement. A stored generation that lists it reports it as nothing to check, as `dashboard-current` is reported since 7.0.0. The shipped default no longer lists it.
4. **No model tiers or effort per dispatch.** `model_tiers.py` is deleted. The shipped default holds no `model-tiers` or `model-floors` rule set, and an assessment no longer writes `models:`. The two rule kinds stay valid in the catalogue, so a stored generation that holds them still reads. `compass approach show` prints the decision view only.
5. **No execution profiles.** `execution_profile.py`, `execution_profile_cmd.py`, `execution_profile_store.py`, `schemas/execution-profile.schema.json` and `docs/execution-profiles.md` are deleted. Nothing reads a `profiles` folder.
6. **No headless runner.** `run_cmd.py`, `docs/headless-runner.md`, `scripts/run-demo.sh`, `ci/headless-verify.yml` and `.github/workflows/compass-run-demo.yml` are deleted. `host_launch.py` and `redact.py` stay, because the eval harness and the delivery record use them.
7. **An agent review is advisory evidence, when a project turns it on.** The shipped default declares no judged check, so a project that does nothing runs no agent review. A project turns one on by putting the block that `docs/judged-checks.md` gives under "An agent review" into its own `compass.yml`: the judged check `agent-review` (`severity: advisory`, `reviewers: [agent]`, `inputs: [acceptance-criteria]`, `on_skipped: not-applicable`), added to the `ship` entry list:

   ```yaml
   checks:
     agent-review:
       statement: An agent that did not write the change reviewed it against the acceptance criteria.
       kind: judged
       reviewers: [agent]
       inputs: [acceptance-criteria]
       severity: advisory
       on_skipped: not-applicable
   stages:
     ship:
       set:
         entry: {add: [agent-review]}
   ```

   The reviewing agent records its verdict with `compass evidence review agent-review --verdict pass|fail --reason TEXT --reviewer agent`, which registers a `manual-review` record. A missing record, a `fail` or a changed input shows as ADVISORY and does not fail `compass check`. A person's record is set aside, because the check lists only `agent`. It is in no Definition of Done, so `dod-evidence-typed` does not read it. The rules the reviewer agent applied (comment labels, settled decisions, review rules, named patterns, clarity) move into `commands/verify.md`, which this session follows.
8. **Old records and settings.**
   - A manifest's `subtasks:`, `models:` and `subtask_ceiling:` keys are not read and stay valid in the manifest schema.
   - The `compass.yml` keys `models` and `multiagent` stay valid and are not read. `compass policy lint` names each one that a project file holds as removed in 9.0.0 (`L-SETTING-REMOVED`, a warning).
   - A removed verb or flag (`compass run`, `compass issue subtask`, `compass profile`, `compass approach show --model`, `--effort`, `compass retro --models`) fails to parse as an unknown command, and the error adds one line that names it as removed in 9.0.0 with this ADR.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| Keep the reviewer agent as required evidence | A second agent's review catches what the author misses | The parent issue's decision 6: the merged PR's human review is the review an auditor accepts, and a subagent adds tokens to every run |
| Keep the stage agents but dispatch them only on the full approach | Keeps the separation of roles where risk is highest | The full approach is where the token cost is highest, and #351 removes the approaches |
| Make an old `compass.yml` with `models:` or `multiagent:` fail | A clear signal that the setting does nothing | It would stop every command in a project that upgrades, for a key that changes no verdict; a lint warning names it without stopping work |
| Delete the `multiagent` check from the registry without a removed-check entry | Less code | A stored generation that lists it would fail with an unknown check, so an archived issue could go from pass to fail |
| Change the regular and full approaches to `breakdown: skipped` now | No mode name for a breakdown that no longer exists | It changes every route's stage list and every pinned route fixture, and #351 replaces the stages anyway |
| Turn the agent review on with a new capability switch | One line in `compass.yml` | A capability changes the shape of every stored generation, and the list operation already turns a check on |
| Ship `agent-review` in the default preset, listed nowhere | The project adds one line instead of a block | The shipped default declares no judged check, which a test of the judged-check feature holds (`test_jc_11`); a project that does nothing must read exactly as before |

## Consequences

- An issue runs in one session. A stage command names no agent and passes no model or effort.
- An archived issue keeps its verdict or moves from fail to pass, never from pass to fail. One that failed only on `multiagent-run-recorded` now passes it as nothing to check.
- The `loop_ceilings` rules for subtasks and runs (`builder_attempts`, `review_rounds`, `replans`, `repeated_error`, `run_cycles`, `run_minutes`, `run_cost_usd`) have no reader left. They stay in the configuration until #357 replaces the configuration layers.
- The assessment still writes `subtask_ceiling` and `max_worktrees`. Nothing binds on them. #351 removes them with the breakdown stage.

## Decisions on the open questions

The owner accepted each default on 4 November 2026:

1. The regular and full approaches keep the breakdown mode name `multiagent` until #351 replaces the stages.
2. The `compass.yml` keys `models` and `multiagent` are warned about by `compass policy lint` and not refused.
3. The `loop_ceilings` rules stay in the shipped default until #357 replaces the configuration layers.
4. A project lists `agent-review` at the `ship` entry, not in the Definition of Done.
5. The shipped default does not carry `agent-review`: a project declares the whole check, and the shipped default keeps no judged check.

## References

- ayeo-io/compass-delivery#352 [Remove the stage agents, multiagent breakdown and dispatch settings] and its parent, #345 [Reposition Compass 9.0.0 as an ATDD framework with a proof trail].
- The 9.0.0 repositioning proposal of 31 October 2026, which #345 links: rows B, F and G, and question 6.
- ADR-030 (the headless runner), ADR-071 (the one-unit breakdown), ADR-076 (execution profiles) and ADR-078 (a worktree's own pointer).
- `cli/compass_pkg/check_registry.py` (`REMOVED`), `cli/compass_pkg/removed_parts.py`, `docs/judged-checks.md` ("An agent review"), `tests/test_agent_review_advisory.py`, `tests/test_removed_parts_9_0_0.py`.
