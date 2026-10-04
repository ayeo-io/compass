# Run 3 of the multiagent protocol - comparison-suite

Rival products appear as codes R1 to R9; the maintainer holds the key.

> **Date:** 2026-09-27 to 2026-09-28 · **Issue:** `comparison-suite`, which
> adds other frameworks to the eval harness, six comparison scenarios and
> a report, and publishes the comparison · **Protocol:**
> `docs/multiagent-protocol.md`

The third recorded run under the protocol. Run 1 is
`docs/compass/2026-09-25-dispatch-protocol-run-1.md` and run 2 is
`docs/compass/2026-09-27-skill-prose-pressure-tests-run-2.md`. Three
subtasks ran in one wave, and a fourth in a second wave.

## The result

| Measure | Value |
|---|---|
| Wall-clock time | about 19 h 40 min, from provisioning wave 1 (about 14:25) to the last correction of the published report (10:01 the next day), including the paid runs |
| Subtasks | 4, in 2 waves; wave 2 was added after the first paid execution |
| Builder tries | 12 (subtask-1: 5, subtask-2: 4, subtask-3: 2, subtask-4: 1) |
| Reviews | 5 by reviewer agents: three of the integrated change, two of the published report's claims |
| Tokens, builders | 1,583,923, of which 100,061 for one try were lost from the manifest and are taken from the orchestrator's notes |
| Tokens, reviewers | 519,573 |
| Merge conflicts | 0, across 11 merges |
| Real model spend | $17.85 for 73 comparison sessions, including one execution without the reply rule and one re-run after a network failure; about $2.40 for real-run checks during review |

All builders ran on Sonnet, each handed only its brief file's path.

## Rework

The rework came from fairness, not from correctness. Each review's real
run found something that treated the frameworks unequally:

1. The harness could not clone either framework, because its own git
   safety setting blocked HTTPS; only Compass could run its own commands;
   only Compass got its plugin copy as a readable directory.
2. R1's own scripts and branch creation were refused; R3's
   resume record failed R3's own first step; Compass's resume
   record left out the keys the hidden tests read.
3. R1's scripts, written as `bash scripts/<name>`, matched no
   rule.

Between reviews the orchestrator confirmed two facts with real calls,
about $0.15: Claude Code does not expand `${CLAUDE_PLUGIN_ROOT}` in an
allow rule, and an absolute path does work.

## Steps that needed improvising

- The builders' `.compass/work/` records do not merge, so the
  orchestrator copied them into the main checkout after each merge.
- One builder's second try reworded R1's and R3's own
  headings to satisfy Compass's retired-word rule. The orchestrator first
  exempted those files in `governance/terminology.yml`, which the
  writing check never reads; a builder found this, and the exemption now
  sits in the check that reads it, by directory.
- The orchestrator assigned one change to a builder that did not own the
  file; the merge still applied cleanly.
- One try's cost was recorded after the try counter moved on, so it
  was filed under the next try and overwritten.

## Decisions

- Every condition gets the same allow-list, wide enough for each
  framework's own workflow. The orchestrator decided this, and recorded
  it in the design.
- The maintainer, asked, chose the reply every comparison scenario gives a
  session that stops to ask, counted as an intervention. That decision was
  the maintainer's.

## What this run does not show

- Whether one agent building the three parts in sequence would have cost
  less. No such build ran.
