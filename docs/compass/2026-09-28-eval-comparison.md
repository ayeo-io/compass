# Eval comparison - Compass, Superpowers, Spec Kit and no framework

> **Run:** 2026-09-28 · **Issue:** `comparison-suite` ·
> **Harness and report:** `evals/harness.py`, `evals/compare.py` ·
> **Model:** `claude-opus-5-5` for every session, Claude Code 2.1.283

Six scenarios, each run twice under four conditions: 48 sessions. Every
condition got the same prompt, model, budget, allow-list and reply rule,
and the same seed repository, except in `cmp-resume`. There each framework
got the record it keeps for work in flight, and the condition with no
framework got a plain `NOTES.md`. The frameworks were pinned: Superpowers
at `8ca22dba` (tag v6.4.2), Spec Kit at `3b895d16` (tag v1.0.9), and
Compass at `99dfa86`, this checkout's `HEAD` throughout the runs; the run
records do not store Compass's commit. Correctness is measured by hidden
tests the session never sees, copied in after it ends.

## What the comparison found

- **On correctness, the conditions matched in 47 of 48 sessions.** Every
  session but one passed every hidden test. These six scenarios are too
  easy to tell the frameworks apart on correctness; a harder set is
  needed before any framework can claim to produce better software.
- **Compass cost the most, by a wide margin.** Across its 12 sessions it
  used 7.19 million tokens and 1,126 seconds, against 0.95 million and
  290 seconds with no framework, 1.27 million and 409 seconds under Spec
  Kit, and 2.21 million and 760 seconds under Superpowers. Compass
  sessions ran its assessment, wrote its records and ran its checks,
  which the others did not; the records do not split the cost by step.
- **Compass was the only condition that did not complete a scenario.** On
  `cmp-risky`, a change to what customers pay, the session scored the
  risk as critical in one of two runs and labelled the change `payments`;
  Compass's routing policy then sent it down the full pipeline. After the
  one reply it wrote an intent and five acceptance scenarios, and stopped
  for sign-off before writing code. In the other run the session scored
  the risk as contained, took the quick-fix route and completed. The
  stopped run needed the only intervention in the comparison.
- **No condition introduced a regression.**

## Results

| Measure | no framework | Compass | Spec Kit | Superpowers |
|---|---|---|---|---|
| Completed | 12 of 12 | 11 of 12 | 12 of 12 | 12 of 12 |
| Hidden tests passed | all | 33 of 38 | all | all |
| Regressions | 0 | 0 | 0 | 0 |
| Interventions (replies sent) | 0 | 1 | 0 | 0 |
| Tool calls refused | 2 | 25 | 4 | 14 |
| Wall time, total | 290 s | 1,126 s | 409 s | 760 s |
| Tokens, total | 952,569 | 7,190,804 | 1,271,088 | 2,210,882 |
| Cost, total | $1.43 | $6.49 | $1.84 | $2.76 |

Every refused tool call was a Bash command Claude Code refused, because
it was outside the allow-list or beyond its parser, except one of
Compass's 25: Compass's own pre-tool hook blocked an edit until the
issue's delivery approach existed.

Tokens count every token each call reported: input, output, and the
tokens read from and written to the prompt cache. Cost is the cost each
session reported. The per-scenario tables, with each measure's lowest and
highest value across the two executions, are in the report
`evals/compare.py` writes from the run records.

`compare.py` shows Compass's hidden-test pass rate as 97%: in the stopped
run the hidden test file could not import the function the session never
wrote, and the harness counted that as one failure where the file holds
five tests. The table above counts the five.

The two executions agreed on every correctness result except Compass on
`cmp-risky`. The widest spread in tokens was Compass on `cmp-risky`, from
665,970 to 876,904.

## How the runs were set up

- **Scenarios:** a small fix, a feature, unclear legacy behaviour, a risky
  change to money, a spike, and a resumed session.
- **Frameworks:** Superpowers loaded as a plugin from its pinned commit.
  Spec Kit set up by its own `specify init` for Claude, from its pinned
  commit. Compass set up by `compass init` and its plugin, the repository
  opted in.
- **Tools:** one allow-list for all four, wide enough for each framework's
  own workflow: its scripts, branch creation and subagents.
- **Replies:** a session that stops to ask gets one reply, "Go ahead with
  whichever option you recommend.", under every condition, counted as an
  intervention. The maintainer chose this rule. It caps any framework
  that stops for a second approval, as Compass did on `cmp-risky`.

## What this does not show

- **Which framework produces better software.** Every condition passed
  every scenario but one. The scenarios did not separate them.
- **More than two executions.** Two runs per scenario and condition give
  a lowest and a highest value, not a rate.
- **Each framework's own workflow, in most sessions.** Superpowers'
  skills ran in 2 of its 12 sessions, both in `cmp-resume`, which
  accounts for 58% of its tokens and 65% of its time. Spec Kit's workflow
  starts when a person runs its commands; every condition got the same
  plain prompt, and one Spec Kit session, in `cmp-resume`, ran its
  implement step. Claude Code refuses, under every condition, commands
  outside the allow-list or beyond its parser; it refused Compass most
  often.
- **A clean home directory.** Every session could see the account's email
  address and git user name, as in the earlier pilot,
  `docs/compass/2026-09-26-eval-pilot.md`.
- **One execution with no reply.** An earlier execution without the reply
  rule is kept but not published: in it, Compass stopped to ask in two of
  six scenarios and did not complete them.
- **The run records themselves.** They are not published, so a reader
  cannot check a figure against its record.

## Spend

| Item | Cost |
|---|---|
| The two published executions, 48 sessions, one cell re-run after a network failure | $12.52 |
| The earlier execution without the reply rule, 24 sessions | $5.32 |
| Real-run checks during review | about $2.40 |
