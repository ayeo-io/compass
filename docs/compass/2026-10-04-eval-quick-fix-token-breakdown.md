# Where a Compass quick fix spends its tokens

Rival products appear as codes R1 to R9; the maintainer holds the key.

> **Sessions:** the two Compass and the two no-framework sessions of `cmp-refactor` from the 4 October comparison run (`2026-10-04-eval-comparison-premium.md`) · **Compass:** `d1b9daa7` · **Model:** `claude-opus-5-5` · **Spend:** none; the run's own session transcripts were read

The 4 October run measured how much more a Compass quick fix costs than no framework, and in which stage. This breaks the cost down by what entered the model's context, before anything is cut. `cmp-refactor` was the scenario where Compass cost most relative to no framework in the 3 October routine run.

## Result

- **Most of every session is the resident load, read again on every request.** It is 63 to 72 percent of everything a Compass session reads, and 77 to 87 percent without a framework.
- **Compass adds about 2,600 tokens to the resident load** (18,585 against 16,004 at the first request). Because every request reads it again, this alone is about a quarter of Compass's extra tokens.
- **Compass CLI output and skill text enter early and are read again on every later request.** Together with the other text Compass injects, they are 27 to 28 percent of what a Compass session reads. Without a framework, test output and code reads fill that place at 8 to 14 percent.
- **Compass sessions make more requests:** 8 and 15, against 7 and 13. Each extra request reads the whole context again.

## By source

Each source's share of all tokens the session read. A token that enters the context at one request is counted again at every later request, because the model reads it again.

| Source | Compass, run 1 | Compass, run 2 | no framework, run 1 | no framework, run 2 |
|---|---|---|---|---|
| Resident load (system prompt, tools, instructions) | 72% | 63% | 87% | 77% |
| Compass CLI output | 13% | 11% | - | - |
| Skill text (skill reads and skill bodies) | 7% | 11% | - | - |
| Other injected text (prompt and hook messages) | 7% | 6% | - | - |
| Test output | - | 3% | 5% | 10% |
| Reading code | - | 3% | 3% | 4% |
| Writing and editing files | 2% | 3% | 2% | 5% |
| Other shell commands | - | - | 3% | 4% |

| Measure | Compass, run 1 | Compass, run 2 | no framework, run 1 | no framework, run 2 |
|---|---|---|---|---|
| Requests | 8 | 15 | 7 | 13 |
| Resident load at the first request | 18,585 | 18,585 | 16,004 | 15,998 |
| Context at the last request | 31,663 | 36,576 | 20,370 | 24,867 |
| Tokens read, all requests | 206,581 | 439,914 | 128,464 | 270,452 |

Where Compass's extra tokens come from, run 1 (78,117 extra) and run 2 (169,462 extra):

- the 2,600-token resident addition, read on every request: about 20,600 and 38,800;
- Compass's own output and skill text, read again after they enter: most of the rest;
- one and two extra requests, each reading the whole context again.

## How it was measured

- Each session's Claude Code transcript gives, for every request, its input, cache-write and cache-read tokens; their sum is the context that request read. A request written over several lines is counted once.
- What entered the context between two requests is the tool results and text the transcript records between them. Each tool result is assigned by its tool call: the `Skill` tool to skill text, a shell command running `compass` to CLI output, one running `pytest` to test output, `cat`, `ls` and `Read` to reading code, `Write` and `Edit` to writing files.
- A source's share is the growth it caused, multiplied by the number of later requests that read it again, over the session's total.
- Only numbers and categories were taken from the transcripts; none of their text is published.

## What this does not show

- Four sessions from one scenario. Other scenarios load other skills and run other commands; the 4 October run's stage split covers all eight.
- Growth is split evenly when several items enter between two requests, so a share is approximate to a few percent.
- The resident load's own contents - which parts of Compass's operating contract and plugin listing make up the 2,600 tokens - are not broken down here.
- It shows where tokens go, not which of them could go without losing the guardrails. Any cut is a separate spec, checked against the same scenarios.
