# Comparison: four scenarios where a careless change fails

> **Harness and report:** `evals/harness.py`, `evals/compare.py` · **Model:** `claude-opus-5-5`, Claude Code 2.1.284 · **Compass:** `d35ba159` · **Superpowers:** `8ca22dba` · **Spec Kit:** `3b895d16` · **Run:** 30 September 2026, 32 sessions, $7.90

The first comparison (`2026-09-28-eval-comparison.md`) could not tell the frameworks apart: its scenarios were small enough that nearly every session got them right (47 of 48). This comparison adds four scenarios in which a careless change passes the visible tests and fails the hidden ones. Each ran under four conditions (no framework, Compass, Superpowers and Spec Kit), twice.

## Result

- **No condition made a careless change.** Every session that wrote code passed every hidden test, including the three rules a careless change misses: the money rule found only in `docs/CONVENTIONS.md`, the two callers the prompt does not name, and the behaviour a tidy-up must keep.
- **Compass was the only condition to fail a session, and it failed by writing nothing.** In one `cmp-edge-case` session, Compass gave the full feature process to a one-function change. The session stopped twice to ask whether to go ahead, and the harness sends only one reply, so it ended with no code.
- **Compass cost the most:** $3.76 against $1.20 to $1.57, 3.4 million tokens against 1.0 to 1.3 million, and twice the wall time. Three Compass sessions stopped to ask about the process, each after rating familiarity as something other than `brownfield-mapped`; no other condition stopped.

| Measure | no framework | Compass | Superpowers | Spec Kit |
|---|---|---|---|---|
| Sessions that passed every hidden test | 8 of 8 | 7 of 8 | 8 of 8 | 8 of 8 |
| Regressions | 0 | 0 | 0 | 0 |
| Sessions that stopped to ask | 0 | 3 | 0 | 0 |
| Wall time, total | 275 s | 589 s | 326 s | 307 s |
| Tokens, total | 973,801 | 3,391,983 | 1,317,323 | 1,026,031 |
| Cost, total | $1.20 | $3.76 | $1.57 | $1.37 |

## The scenarios

| Scenario | The prompt asks for | A careless change misses |
|---|---|---|
| `cmp-hidden-requirement` | a function to split a bill | the rule in `docs/CONVENTIONS.md`: whole pence, and the leftover pence go to the first people |
| `cmp-call-sites` | a currency argument for `format_price` | two callers the prompt does not name |
| `cmp-refactor` | a tidy-up of `parse_config` that keeps its behaviour | inline comments, lower-cased keys, and values that contain `=` |
| `cmp-edge-case` | a `page` function, with its edge rules stated | the `ValueError` for a page number or size below 1 |

`tests/test_eval_comparison_tasks.py` applies a careless change to each seed and checks that the seed's own tests pass and the hidden tests fail. It also checks that a correct change passes.

## Per scenario

| Scenario | no framework | Compass | Superpowers | Spec Kit |
|---|---|---|---|---|
| `cmp-hidden-requirement` | 2 of 2 | 2 of 2 | 2 of 2 | 2 of 2 |
| `cmp-call-sites` | 2 of 2 | 2 of 2 | 2 of 2 | 2 of 2 |
| `cmp-refactor` | 2 of 2 | 2 of 2, both after one reply | 2 of 2 | 2 of 2 |
| `cmp-edge-case` | 2 of 2 | 1 of 2 | 2 of 2 | 2 of 2 |

## Did the conditions differ?

On correctness, no. The one failed session did not write wrong code; it wrote none. The careless changes these scenarios are built to catch did not happen under any condition.

On cost, yes. Compass cost about two and a half to three times as much as the other conditions. In three of its eight sessions, the session first rated familiarity as something other than `brownfield-mapped` (`greenfield` once, `brownfield-unmapped` twice) for a change to a small, tested module. The routing policy gives the quick-fix process only to `brownfield-mapped` work, so these sessions got the full feature process and stopped to ask whether to go ahead.

On `cmp-refactor`, seven of the eight sessions added tests that pin `parse_config`'s behaviour, under every condition. Only one session with no framework added none. One Compass session also recorded why it changed its rating: it wrote 12 such tests, then re-assessed familiarity as `brownfield-mapped` with that reason on record.

## What this does not show

- Two executions per cell are too few to give a rate. A single session can change a cell's result.
- These scenarios still did not separate careful from careless work, because this model did not work carelessly on them. A scenario that does may need a bigger codebase or a longer task.
- The harness sends one reply to a session that stops to ask. A person could reply again, and the Compass session that wrote nothing could then have finished.
