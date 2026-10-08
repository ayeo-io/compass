---
description: Run the scenarios, apply the review, check the gates
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
---

# /compass:verify

The verify stage proves the work with evidence - recorded command output and artifacts
a reader can open, never assertion. "It works" is not a gate-passing statement on any delivery
approach. QA owns this gate.

## On a spike

Read `delivery-approach.md`. On a **spike**, the verify stage is **conclude** - not a
test gate but a findings check: *did we answer the question?* It runs none of
the review dimensions, because a spike ships nothing. Its one gate is "the
question is answered - or explicitly answered with 'inconclusive, here is
why' - and the finding is written down." If the approach is a spike, follow
`${CLAUDE_PLUGIN_ROOT}/approaches/spike.md`'s conclude step instead of the delivery procedure below.
The rest of this command is for delivery work.

## Setup

- Read `delivery-approach.md` for the gate set and which review dimensions
  apply. The dimension set scales with the approach (see the table in
  `${CLAUDE_PLUGIN_ROOT}/approaches/composition-reference.md`); `correctness`,
  `governance`, and `traceability` are always on for delivery work - they
  are the default guardrails in review form. The routing policy's
  `immovable_gates` are always added.
- Load the `evidence-gates` skill.
- Invoke the `verifier` agent (runs the suites) and the `reviewer` agent
  (applies the review dimensions).
- If the product-marketer role is in play, the `claims` dimension applies -
  `product-marketer` reviews here too.
- If this issue is itself a sweep, rename, or cleanup touching many files,
  check it the way `governance/strategies.md` `S9` describes: a fresh agent
  that has not seen the change, not its author.
- A guard offered as part of the change is accepted on a demonstrated failure
  rather than a passing test - `governance/strategies.md` `S10` states the
  method.
- Where a review comment and the author disagree about a quantity - how many
  call sites, how much output, how often it fires - measure the number and
  report it before defending either position
  (`governance/strategies.md` `S11`).
- QA owns this gate and can send the issue back to the define stage if
  scenarios are uncoverable.

## Procedure

1. **Scenarios as acceptance tests.** Run every scenario in
   `acceptance-criteria.md` as an acceptance check. They are the same
   artifact the spec was - read now at verification time.
2. **TDD suite.** Run the full test suite through `compass tdd-green -- <cmd>`,
   which confirms it passes and writes the record. Link that record from the
   report rather than reproducing the run inside it.
3. **Run `compass check`.** This is the **mechanical half** of the verify stage's
   gate: the CLI runs the `guardrails.yml` checks against `manifest.yml` and
   `evidence/` - every scenario has a test, the suite passed
   (a green record on file), every changed file traces to a scenario, every
   `pass` gate has resolving evidence, and so on. It exits non-zero on any
   failure. The `reviewer` agent still does the *judgement* dimensions
   (clarity, security depth, governance-as-assessed) - `compass check` is
   the mechanical part, not the whole gate.
4. **Review dimensions.** Apply each dimension `delivery-approach.md`
   lists - `correctness`, `governance`, `traceability`, and as the approach
   needs `regression`, `security` (scaled or full), `clarity`, `claims`.
   The `governance` dimension checks the work against `governance/`: the
   guardrails (hard, evidence-backed - `compass check` is the mechanical
   part) and the applicable strategies (assessed as judgement, reported
   distinctly). On a multiagent, check each subtask first, then again on the
   combined result.
5. **Update the gates in `manifest.yml`.** As each gate is cleared, the
   `verifier` sets its `status` to `pass` and points its `evidence:` at the
   artifact (the scenario-bound green record, a report path). `compass check`'s
   `gate-evidence-present` check checks every `pass` gate has a pointer
   that resolves - a gate marked pass with no evidence fails the check.
6. **Write `verification-report.md`** from the output of
   `compass issue template verification-report`, which renders the checklist from the
   issue's exit lists: each dimension, each gate, the evidence, pass/fail.

   **Where it goes.** `docs/compass/<created>-<issue-slug>/verification-report.md`, where the
   date is the manifest's `created:` field - not today's. Then register it:
   `compass issue artifact verification-report --status draft --path <that path>`. The CLI
   refuses a path that climbs out of the project, so the record is checked
   rather than claimed. If you had to create `docs/compass/`, **say so in one
   line** - a directory appearing with nothing said is how it gets deleted by
   hand or committed by accident.

## Voice

A verification report is evidence a person reads, not a status board. Say
what passed and what it means - never that the issue is "ready for the next
command." See `skills/compass-runtime/writing-voice.md`.

## Gate

- `compass check` passes (record its output with `compass evidence add` and link
  the record - that is the mechanical half);
- every required *judgement* dimension passed with evidence;
- every gate in `manifest.yml` is `pass` with a resolving evidence pointer;
- `verification-report.md` is written, and the first five items of its
  **Definition of Done** - every scenario passes, the TDD suite is green,
  coverage meets the tested-before-ship guardrail's floor, there are no
  lint/format/type errors, and traceability is intact - are fully checked.
  That is the exit gate out of verify.

The Definition of Done's remaining two items - living docs updated, and
every owed follow-up settled - are carried into ship. If anything
fails, the issue does not advance - fix it or send it back. Log to
`devlog.md`. Next: `/compass:ship`.

## Answering the reviewer

Load `receiving-code-review`. Check every suggestion against the code
before acting on it: a suggestion that is right about the symptom and wrong
about the cause is the normal case, and implementing it verbatim leaves the
symptom and adds a change nobody needed. Where the reviewer is wrong, push
back with technical reasoning rather than preference or seniority. Record
what you did with each comment - a resolved thread with no reply is a
decision nobody can audit.
