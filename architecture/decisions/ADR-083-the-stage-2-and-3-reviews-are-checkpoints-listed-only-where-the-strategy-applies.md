---
id: ADR-083
title: The stage 2 and 3 reviews are checkpoints, listed only where the strategy applies
status: accepted
date: 2026-11-01
supersedes: ''
superseded_by: ''
---

## Context

Strategy `S17`, the four-layer acceptance strategy, has three stages, and the `atdd` skill gives a review for the end of each (`skills/atdd/references/stage-reviews.md`). Stage 1 ends at refine, which is a checkpoint. Stages 2 and 3 end at `implement` and `verify`, and `compass evidence request --checkpoint` took only assess, define, refine and plan, so a person had no form to answer the stage 2 and 3 reviews in. Every reader of a checkpoint keys it to a pipeline stage: `routing.route_checkpoints`, `checkpoint_outcomes`, `compass issue checkpoint add`, `compass evidence approve --checkpoint`, the `autonomy_checkpoints` lint and the landing refusal (ADR-063).

## Decision

1. **The stages.** `core.CHECKPOINT_STAGES` gains `implement` and `verify`. Every reader above accepts them with no other change, and the manifest and routing-policy schemas name the six stages.
2. **Where they are listed.** `routing.route_checkpoints` takes `strategy_applies`, false by default, and leaves `implement` and `verify` out unless it is true. `compass approach evaluate` passes true when the issue's `acceptance_strategy` block (ADR-079) says the strategy applies. An issue the strategy does not apply to, one with no block, and an evaluation with no issue list the four checkpoints they listed before.
3. **The preset.** The default preset lists `implement` and `verify` under `controlled` for the regular and full approaches only. `balanced` and `autonomous` do not change, and neither do quick-fix and hotfix, which have no stage 2 or 3 review.
4. **The review questions.** A request for the refine, `implement` or `verify` checkpoint of an in-scope issue (`acceptance_strategy.in_scope`) holds `review`: the stage it ends and the questions under that stage's heading in the skill's file. The command prints them, the Stop hook shows them, and the request's digest covers them when present.
5. **compass next.** On a judged issue, when the records show `implement` or `verify` done with no outcome, `compass next` stops at a listed checkpoint and names `compass evidence request --checkpoint <stage>`. When the checkpoint is not listed and the strategy applies, it goes on and names `compass issue checkpoint add <stage> --outcome skipped --by builder` (or `verifier`). `compass next` writes nothing; the stage command records the outcome.
6. **A rejection.** A person who answers a stage 2 or 3 review with `/compass:reject` closes the request as rejected with the reason. While that rejection is newer than the stage's outcome, `compass next` names the stage and the reason, so the issue goes back to it.
7. **Not an obligation.** `obligations` calls the evaluator with no issue, so its checkpoints never hold `implement` or `verify`. The classifier does not compare the strategy (its compare kind is `never`), so it does not compare the reviews the strategy brings either, and `compass policy diff` between `default@7` and the live preset finds no checkpoint change.
8. **No new failure.** `compass check` does not fail on a listed review with no outcome. `compass ship-commit` refuses it, as it refuses every listed checkpoint with no outcome.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| New checkpoint names `stage-2` and `stage-3` | They name the model's stages | Every reader would need a second key space, and "stage-2" reads as define, which is second in the pipeline |
| List `implement` and `verify` on every issue | One rule for all issues | An issue the strategy does not apply to would gain two hand-offs it has no review for |
| A check that fails an in-scope issue with no stage review | The review would be enforced at `compass check` | The product owner decided the landing refusal is enough (decision Q10 of the issue `atdd-strategy`) |
| `compass next` records the skipped outcome itself | The person sees no extra step | `compass next` is read-only, and the pre-tool hook imports it |

## Consequences

- A controlled issue on the regular or full approach that the strategy applies to now waits at `implement` and `verify`, and cannot land until both have an outcome.
- A project whose own `autonomy_checkpoints` table names `implement` or `verify` is accepted by the lint; before, it was refused. The classifier reads such a change as equivalent, because it does not compare the stage reviews.
- An issue assessed before this change keeps its stored `checkpoints:` list until it is re-assessed.

## References

- The technical design of the issue `atdd-strategy`, decision `DD-12`, and its requirements review, decisions Q5 and Q10. Both are issue documents kept in the delivery record (ayeo-io/compass-delivery#327).
- `cli/compass_pkg/core.py` (`CHECKPOINT_STAGES`), `cli/compass_pkg/routing.py` (`route_checkpoints`), `cli/compass_pkg/checkpoint_outcomes.py` (`review`, `next_review`), `cli/compass_pkg/approval_requests.py`.
- `tests/acceptance/atdd_strategy/test_stage_reviews.py` (`TRC-D1` to `TRC-D10`).
