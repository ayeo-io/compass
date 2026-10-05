# Comparison: the eight premium scenarios after #385, #386 and #395

> **Run:** 5 October 2026, 17:06 to 17:26, uid 501 · **Compass:** `a9da6c45` (main, 5 October) · **Model:** `claude-opus-5-5`, Claude Code 2.1.289 · **Conditions:** no framework and Compass, 2 runs each · **Sessions:** 32 · **Spend:** $6.56 (approved: about $7.30)
> **Compared with:** the run of 4 October (`2026-10-04-eval-comparison-premium.md`), at `d1b9daa7`, Claude Code 2.1.288.

This run measures #385, #386 and #395, the three quick-fix changes that landed after 4 October. It is also the baseline for the next token work: tokens per stage in the report, a flag when assess costs more than implement, a smaller install profile, and a shorter assess command.

## Result

- **Every session passed every hidden test**, in both conditions: 16 of 16 each, with no regressions.
- **On the four careful-process scenarios, Compass now costs 2.10 times the tokens of no framework**, down from 3.99 on 4 October. `cmp-resume-decision` is 2.09 times, down from 6.90.
- **On the original four, Compass costs 2.34 times the tokens**, up from 1.56. Most of the rise is `cmp-refactor`, at 3.21 times against 1.61. Both of its Compass sessions took the quick-fix route, with 15 and 18 tool calls.
- **Replies sent:** Compass needed 2, both in `cmp-shared-helper`, where it stops before a breaking change. That stop is kept by the decision of 4 October. No framework needed none.
- **Inside a Compass quick fix, assess still costs more than implement** in four of the six scenarios that record stages. In `cmp-hidden-requirement`, for example, assess used 113,330 tokens and implement 39,794 (mean of two runs).

## Per scenario: Compass tokens as a multiple of no framework

| Scenario | 4 October | 5 October |
|---|---|---|
| `cmp-call-sites` | 1.25 | 1.46 |
| `cmp-edge-case` | 1.47 | 1.75 |
| `cmp-hidden-requirement` | 2.00 | 2.80 |
| `cmp-refactor` | 1.61 | 3.21 |
| `cmp-late-tidy` | 2.26 | 1.80 |
| `cmp-shared-helper` | 2.87 | 2.62 |
| `cmp-resume-decision` | 6.90 | 2.09 |
| `cmp-second-change` | 2.56 | 1.85 |

Group totals (tokens, both runs together):

| Group | No framework | Compass | Multiple | Cost multiple |
|---|---|---|---|---|
| Original four | 816,994 | 1,915,562 | 2.34 | 2.00 |
| Careful-process four | 807,443 | 1,697,578 | 2.10 | 1.89 |

## How far to trust it

- Two runs per cell. On 4 October the same scenario varied by up to 1.8 times between its two runs, so a single scenario's change, `cmp-refactor` included, is inside that spread until a repeat confirms it. The group totals are steadier.
- The Claude Code version moved from 2.1.288 to 2.1.289 between the runs, and the no-framework sessions changed too. A ratio compares two moving numbers.
- Nothing here supports a public claim on its own. The decision rule needs a repeat before a claim.

## One run recorded as not contained, caused by the operator

`cmp-call-sites` no framework, run 1, is recorded as not contained. Its `escaped_paths` name `HEAD` and two branch refs in the checkout's git folder. The run used a worktree that shares that git folder with the main checkout, and a branch was created in the main checkout during the session. The session itself did not touch them. Its hidden tests passed, 5 of 5. Running from a worktree while working in the same repository will always cause this. A later run should come from a separate clone.

## Files

The 32 run records, the generated per-scenario tables (`compare.md`) and the run script with its $10 cap are in the delivery record, under `docs/compass/2026-10-05-eval-m1-runs/`. They were made with `evals/harness.py` and `evals/compare.py` at `a9da6c45`.
