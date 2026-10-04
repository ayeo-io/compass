# Comparison: eight scenarios, with tokens by stage

Rival products appear as codes R1 to R9; the maintainer holds the key.

> **Harness and report:** `evals/harness.py`, `evals/compare.py` · **Model:** `claude-opus-5-5`, Claude Code 2.1.288 · **Compass:** `d1b9daa7` · **R1:** `8ca22dba` · **R3:** `3b895d16` · **Run:** 4 October 2026, 64 sessions, $13.53, as uid 501 with Python 3.11.9

This run repeats the four scenarios of the 30 September run (`2026-09-30-eval-comparison-discriminating.md`) and adds four where careful process should beat a careless change. Each ran twice under four conditions: no framework, Compass, R1 and R3. Compass now records the tokens each quick fix spends in each stage. The decision rule in `evals/README.md` was written before the run.

## Result

- **Compass showed no edge in any of the four careful-process scenarios.** Every condition passed every hidden test in `cmp-late-tidy` and `cmp-resume-decision`. In `cmp-shared-helper` all passed, but Compass needed two replies and the others none. In `cmp-second-change` Compass missed one of six hidden tests; no framework and R1 missed none.
- **On the original four scenarios, Compass now costs about one and a half times no framework:** 1.56 times the tokens and 1.55 times the cost. On 30 September it was 3.48 times the tokens. The target for small work is 1.5 times or less.
- **On the four new scenarios, Compass costs four times the tokens of no framework** (3.99 times; 2.58 times the cost). `cmp-resume-decision` alone is 6.9 times.
- **Inside a Compass quick fix, assessing costs more than implementing:** a mean of 94,151 tokens in the assess stage against 64,433 in implement.

| Measure | no framework | Compass | R1 | R3 |
|---|---|---|---|---|
| Sessions that passed every hidden test | 16 of 16 | 15 of 16 | 16 of 16 | 15 of 16 |
| Regressions | 0 | 0 | 0 | 0 |
| Replies sent | 0 | 2 | 0 | 0 |
| Wall time, total | 478 s | 853 s | 613 s | 544 s |
| Tokens, total | 1,782,712 | 4,464,571 | 2,768,240 | 2,007,658 |
| Cost, total | $2.42 | $4.88 | $3.48 | $2.75 |

## The decision rule

A scenario shows an edge for Compass when Compass's hidden-test pass rate across its two runs is higher than every other condition's, or equal to the highest with fewer replies sent.

| Scenario | Compass | no framework | R1 | R3 | Verdict |
|---|---|---|---|---|---|
| `cmp-late-tidy` | 6/6, 0 replies | 6/6, 0 replies | 6/6, 0 replies | 6/6, 0 replies | no edge |
| `cmp-shared-helper` | 6/6, 2 replies | 6/6, 0 replies | 6/6, 0 replies | 6/6, 0 replies | no edge |
| `cmp-resume-decision` | 4/4, 0 replies | 4/4, 0 replies | 4/4, 0 replies | 4/4, 0 replies | no edge |
| `cmp-second-change` | 5/6, 0 replies | 6/6, 0 replies | 6/6, 0 replies | 4/6, 0 replies | no edge |

The rule now asks, within one week of this run, for each of the four scenarios: a spec to remove or simplify the Compass steps it exercises, or a recorded decision to keep them at their measured cost. That choice is the maintainer's.

## What the sessions did

- **`cmp-shared-helper`:** both Compass sessions stopped before editing to say the change would break the CSV export, which is the consumer the scenario hides. Each went ahead after the one reply. The rule counts these replies against Compass because it scores replies, not what a stop found; it is not changed after the run.
- **`cmp-second-change`:** the Compass session that missed a hidden test used Python's `round()`, which rounds halves to even, where the first change had recorded rounding half up. One R3 session missed two of the three hidden tests the same way.
- **`cmp-resume-decision`:** every condition honoured the rule only the record held, so the scenario did not separate them, and Compass spent the most to get there.

## Tokens by stage

Thirteen of the sixteen Compass sessions recorded tokens by stage. Two resumed an issue the seed had already started, so they have no start time; one recorded no usage, and its cause is not checked here.

| Stage | Mean tokens per quick fix | Requests per quick fix |
|---|---|---|
| Assess | 94,151 | 2 to 5 |
| Implement | 64,433 | 1 to 4 |
| `verify` and `ship` | not measured | inside one `quick-fix finish` call |

Where the assess tokens go - the instructions loaded at session start, skill reads, command output - is the next measurement (issue #377).

## Per scenario

Tokens relative to no framework, both runs together:

| Scenario | Compass | R1 | R3 |
|---|---|---|---|
| `cmp-hidden-requirement` | 2.00 | 1.58 | 0.86 |
| `cmp-call-sites` | 1.25 | 0.65 | 1.16 |
| `cmp-refactor` | 1.61 | 1.36 | 0.96 |
| `cmp-edge-case` | 1.47 | 0.83 | 0.70 |
| `cmp-late-tidy` | 2.26 | 1.37 | 1.21 |
| `cmp-shared-helper` | 2.87 | 1.13 | 1.23 |
| `cmp-resume-decision` | 6.90 | 4.05 | 1.45 |
| `cmp-second-change` | 2.56 | 1.55 | 1.82 |

## What this does not show

- Two runs per cell is enough to apply the rule, not to measure spread. A difference of one session is within what a repeat could change.
- R5 is not in this run. The maintainer decided it joins this comparison; its condition comes from the weekly routine's local harness, which this machine does not have yet.
- Code quality is measured by the static signals only (complexity added, duplicated lines, lint findings), and they did not separate the conditions. The model-scored rubric waits for a calibration the maintainer scores by hand.
- The same model ran every condition. A weaker model may make the careless changes these scenarios are built to catch.
- An earlier try at this run was discarded because the sessions had no `pytest` on their path, so no hidden test ran. Its records are not used here.
