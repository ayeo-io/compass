# Eval comparison - Compass, Superpowers, Spec Kit and no framework

> **Run:** 2026-09-28 · **Issue:** `comparison-suite` ·
> **Harness and report:** `evals/harness.py`, `evals/compare.py` ·
> **Model:** `claude-opus-5-5` for every session, Claude Code 2.1.283

Six scenarios, each run twice under four conditions: 48 sessions. Every
condition got the same seed, prompt, model, budget, allow-list and reply
rule. The frameworks were pinned: Superpowers at `8ca22dba` (tag v6.4.2),
Spec Kit at `3b895d16` (tag v1.0.9), Compass at this repository's
`HEAD`. Correctness is measured by hidden tests the session never sees,
copied in after it ends.

## What the comparison found

- **On correctness, the four conditions tied.** 47 of 48 sessions passed
  every hidden test. These six scenarios are too easy to tell the
  frameworks apart on correctness; a harder set is needed before any
  framework can claim to produce better software.
- **Compass cost the most, by a wide margin.** Across its 12 sessions it
  used 7.19 million tokens and 1,126 seconds, against 0.95 million and
  290 seconds with no framework, 1.27 million and 409 seconds under Spec
  Kit, and 2.21 million and 760 seconds under Superpowers. Compass
  sessions ran its assessment, wrote its records and ran its checks,
  which the others did not; the records do not split the cost by step.
- **Compass was the only condition that did not complete a scenario.** On
  `cmp-risky`, a change to what customers pay, it chose its full pipeline
  in one of two runs, because its routing policy treats money as critical
  risk. After the one reply it wrote an intent and five acceptance
  scenarios, then stopped for sign-off before writing code. It needed the
  only intervention in the comparison.
- **No condition introduced a regression.**

## Results

| Measure | no framework | Compass | Spec Kit | Superpowers |
|---|---|---|---|---|
| Completed | 12 of 12 | 11 of 12 | 12 of 12 | 12 of 12 |
| Hidden-test pass rate, pooled | 100% | 97% | 100% | 100% |
| Regressions | 0 | 0 | 0 | 0 |
| Interventions (replies sent) | 0 | 1 | 0 | 0 |
| Wall time, total | 290 s | 1,126 s | 409 s | 760 s |
| Tokens, total | 952,569 | 7,190,804 | 1,271,088 | 2,210,882 |
| Cost, total | $1.43 | $6.49 | $1.84 | $2.76 |

The per-scenario tables, with each measure's lowest and highest value
across the two executions, are in the report `evals/compare.py` writes
from the run records. The two executions agreed on every correctness
result except Compass on `cmp-risky`. The widest spread in tokens was
`cmp-resume` under Spec Kit, from 156,165 to 263,788.

## How the runs were set up

- **Scenarios:** a small fix, a feature, unclear legacy behaviour, a risky
  change to money, a spike, and a resumed session. In the resumed
  session each condition got the record its own framework keeps for work
  in flight, in that framework's own words.
- **Frameworks:** Superpowers loaded as a plugin from its pinned commit.
  Spec Kit set up by its own `specify init` for Claude, from its pinned
  commit. Compass set up by `compass init` and its plugin, the repository
  opted in.
- **Tools:** one allow-list for all four, wide enough for each framework's
  own workflow: its scripts, branch creation and subagents.
- **Replies:** a session that stops to ask gets one reply, "Go ahead with
  whichever option you recommend.", under every condition, counted as an
  intervention. The maintainer chose this rule.

## What this does not show

- **Which framework produces better software.** Every condition passed
  every scenario but one. The scenarios did not separate them.
- **More than two executions.** Two runs per scenario and condition give
  a lowest and a highest value, not a rate.
- **A framework used as its authors intend in every respect.** Spec Kit's
  workflow starts when a person runs its commands; every condition got
  the same plain prompt, and no Spec Kit session ran them. Claude Code
  also refuses, under every condition, commands it cannot parse, which
  cost Superpowers some of its own script steps.
- **A clean home directory.** Every session could see the account's email
  address and git user name, as in the earlier pilot.
- **One execution with no reply.** An earlier execution without the reply
  rule is kept but not published: in it, Compass stopped to ask in two of
  six scenarios and did not complete them.

## Spend

| Item | Cost |
|---|---|
| The two published executions, 48 sessions, one cell re-run after a network failure | $12.53 |
| The earlier execution without the reply rule, 24 sessions | $5.32 |
| Real-run checks during review | about $2.40 |
