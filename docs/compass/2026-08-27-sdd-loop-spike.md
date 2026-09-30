# Spike conclusion - the subagent-driven-development loop

> **Author:** jed72 · **Date:** 2026-08-27
> **Issue:** `sdd-loop-spike` (parent intent document:
> `docs/compass/2026-08-26-first-hour-intent.md`, INT-7)
> **Question:** which parts of Superpowers' subagent-driven-development loop
> should Compass's orchestrator/builder protocol adopt, which should it not,
> and why - so a follow-on issue can be sized honestly, or the question
> closed.
> **Time-box:** two working days. Used: under one.

---

## What was read

Superpowers at tag **v6.3.0**, commit `b36e082`, dated 2026-08-12 - cloned
from `github.com/obra/superpowers` and read from disk, not recalled. The
files that carry the loop:

Every path in this table is inside the **Superpowers** repository, not this
one, and is written repo-first so it stays openable: read it at
`https://github.com/obra/superpowers/blob/v6.3.0/<path>`.

| File | Lines |
|---|---|
| `obra/superpowers/skills/subagent-driven-development/SKILL.md` | 568 |
| `obra/superpowers/skills/subagent-driven-development/task-reviewer-prompt.md` | 207 |
| `obra/superpowers/skills/subagent-driven-development/implementer-prompt.md` | 154 |
| `obra/superpowers/skills/subagent-driven-development/re-review-prompt.md` | 115 |
| `obra/superpowers/skills/dispatching-parallel-agents/SKILL.md` | 167 |
| `obra/superpowers/skills/using-git-worktrees/SKILL.md` | 167 |
| `obra/superpowers/RELEASE-NOTES.md` (v6.2.0 and v6.3.0 sections) | - |

On the Compass side: `skills/worktree-multiagent/SKILL.md` (139),
`agents/orchestrator.md` (74), `agents/builder.md` (102),
`scripts/multiagent.sh` (13,353 bytes), `scripts/integrate.sh` (11,144 bytes),
and the archive of 28 issues whose breakdown stage was a multiagent
orchestration.

## The premise, checked

This spike set out to test the premise that Compass's orchestrator/builder
protocol runs builders in parallel across worktrees, which Superpowers
cannot do. That is two claims, and measuring them changes what this spike is
about.

### Compass does run builders in parallel - it has, for real

Not theoretical. `cross-task-architectural-integrity` ran **six builders
concurrently** on 2026-05-23, each in its own worktree, each with its own
copy of the issue directory so `compass tdd-red`/`tdd-green` evidence did not
race on a shared `.red` marker. All six subtasks came back green - 106, 113
and 107 tests on the first three - and `integrate.sh` merged them with a
combined regression of 161/161. Twenty-eight issues in the archive carry a
multiagent breakdown.

The run also found a real defect in the first try: `multiagent.sh` read the
distribution map's branch-name cell verbatim, so branch names wrapped in
markdown backticks produced git branches containing literal backticks. Git
accepted them. The worktrees were torn down and recreated.

### But `multiagent.sh` launches nothing

`scripts/multiagent.sh` creates the worktrees and the branches, and then **prints a
launch plan** - text naming one builder per worktree, its assignment and its
rule. Nothing spawns an agent. The parallelism is real because a session
carried the printed plan out by hand, not because the script did it.

That matters for sizing anything downstream: every mechanism below that
assumes a controller dispatching subagents is, in Compass today, a paragraph
of prose that a session either follows or does not. There is no code path to
change.

### Superpowers has not failed at parallel implementers - it banned them

This correction changes how the comparison reads. Superpowers ships
`dispatching-parallel-agents`, a whole skill about issuing several subagent
dispatches in one response so they run concurrently. It is not missing the
capability. Its SDD loop contains this line:

> Never dispatch multiple implementation subagents in parallel (conflicts).

And `dispatching-parallel-agents` is explicit that it is for independent
*investigation* domains, with "Don't use when... Shared state: Agents would
interfere (editing same files, using same resources)."

So Superpowers can dispatch in parallel and chooses not to for
implementation, because its workers share one workspace - its
`using-git-worktrees` skill creates **one** isolated workspace per plan, and
its first instruction is "detect existing isolation first... Do NOT create
another worktree."

**Compass's differentiator is not a capability Superpowers lacks. It is a
design choice Superpowers considered and rejected**: that one worktree per
subtask makes parallel implementers safe. The
`cross-task-architectural-integrity` run is one data point that it works.
One.

That is worth saying plainly because it changes how to read everything
below. Compass is not catching up to a more mature loop. It is running an
experiment the other framework decided against, with a sample size of
roughly one, against a loop shaped by donated sessions and eval campaigns
with published numbers.

## The mechanism walk

Fifteen mechanisms, each marked against `worktree-multiagent`,
`agents/orchestrator.md` and `agents/builder.md`.

| # | Mechanism | Verdict | One-line reason |
|---|---|---|---|
| 1 | File-based briefs and reports | **adopt** | Compass hands assignments as prose in a dispatch; nothing bounds what a session pastes. |
| 2 | Recorded base SHA before dispatch | **adopt** | Compass records no base SHA anywhere except `integrate.sh`'s merge-base. |
| 3 | Review package as a file | **adopt** | The verifier and reviewer re-derive the diff themselves, in the controller's context. |
| 4 | Ban on the controller coaching reviewers | **adopt** | Nothing in Compass forbids pre-judging a review, and this session did exactly that kind of thing while checking its own sweep. |
| 5 | Five-round fix breaker with adjudication | **adapt** | Compass has no fix loop at all - the reviewer renders a verdict and the protocol stops there. |
| 6 | Rulings, not stalls | **reject as written; adapt the ledger half** | Compass's stop conditions are guardrails, and a guardrail is not a thing an agent rules past. |
| 7 | The ledger as recovery map | **reject - already stronger** | `manifest.yml` plus `/compass:resume` is a structured, machine-checked version of the same idea. |
| 8 | Explicit model per dispatch | **adopt** | Compass pins a model in agent frontmatter but says nothing about scaling it to the work. |
| 9 | Batch small same-shape work | **adopt** | Compass's unit of dispatch is the subtask, with no guidance below it. |
| 10 | No-subagents contract for workers | **adopt** | Nothing stops a Compass builder spawning its own reviewer. |
| 11 | Never dispatch implementers in parallel | **reject** | This is the mechanism Superpowers rejected and Compass adopts. |
| 12 | "Rulings I made" exhaustive final list | **adapt** | Compass has the artifacts but no rule that decisions taken on the user's behalf are surfaced as a list. |
| 13 | Scoped re-review | **adapt** | Follows mechanism 5; meaningless without a fix loop. |
| 14 | Deferred-minors roll-up into the final review | **adapt** | Compass has `follow_ups:`, which is stronger, but nothing points the reviewer at it. |
| 15 | Bounded waits when idle | **reject** | Harness-specific, and Compass's orchestrator does not wait on anything. |

### The five that matter most

**1, 3 - artifacts as files.** Superpowers' rule is blunt: "Everything you
paste into a dispatch prompt - and everything a subagent prints back - stays
resident in your context for the rest of the session and is re-read on every
later turn. Hand artifacts over as files." It cites a real session whose
dispatch reached 42,000 characters, 99% of it pasted history.

Compass has the artifacts already - `delivery-approach.md`,
`technical-design.md`, `acceptance-criteria.md`, `distribution-map.md` - and
an orchestrator instruction to "hand each builder its assignment." What it does
not have is the rule that the assignment is a *path*, not a paste. This is the
cheapest adoption on the list and the one with the clearest payoff, because
Compass's instruction volume is already a live concern.

**4 - not coaching the reviewer.** Superpowers names the tells: "If the
prompt you are writing contains 'do not flag,' 'don't treat X as a defect,'
'at most Minor,' or 'the plan chose' - stop: you are pre-judging, usually to
spare yourself a review loop."

Compass has one instance of exactly this shape already, in
`skills/governance-check/SKILL.md`: "If you are checking a Spike, do not flag
the..." That one is legitimate - a spike genuinely suspends the strategy -
but it is the pattern, and there is no rule keeping the legitimate case from
becoming the habit. Compass's `S9` (fresh eyes on a sweep) is the same
concern one level up, and this session's own verification report records
failing it.

**5, 13 - the fix loop.** This is the real gap. Compass's `reviewer` renders
a gate decision; `/compass:verify` says "If anything fails, the issue does
not advance - fix it or send it back." Who fixes it, how many tries are
allowed, what happens when tries stop converging, and where the decision
is recorded are all unspecified. Superpowers has a five-round cap, a
capability escalation at round four, a scoped re-review that checks fixes
without wandering, and a mandatory adjudication when the breaker trips, every
one of which is a ledger entry.

Adapt rather than adopt, because Compass already has better places to put
each half: the round count and its rulings belong in the manifest, not a
markdown ledger, so `compass check` can see them.

**6 - rulings, not stalls: the one to reject as written.** Superpowers'
change here came from a donated session that "sat blocked for almost nine
hours on a question the controller could have decided." The fix was to let
the controller rule on anything short of destructive, and record it.

Compass's stop conditions are different in kind. `G5` is a human sign-off on
irreversible change; a policy floor is a rule in
`governance/routing-policy.yml`; a re-assess happens because the assessment
was wrong. These are not questions an agent
should rule past, and the framework is built so it cannot. Adopting
"rulings, not stalls" wholesale would put an agent above a guardrail.

What *is* worth taking is the recording half. Compass already re-assesses
with a `--reason` that `compass retro` aggregates. Extending that habit - a
decision taken on the user's behalf is written where they will see it, not
only where it happened to be made - is mechanism 12, and it is an adapt.

**7 - the ledger: reject, because Compass already has better.** Superpowers
built the ledger because "conversation memory does not survive compaction"
and controllers were re-dispatching sequences of already-completed work.
Compass's
answer is `manifest.yml` - stages, gates with typed evidence, changed files,
scenarios - plus `/compass:resume`, which reads the delivery approach and
works out where things stand. It is structured where the ledger is prose, and
`compass check` can check it where nothing checks a ledger.

The one idea worth adopting is the *identity line*: Superpowers' ledger names
its plan on its first line because a follow-up plan in the same tree read the
previous plan's progress as its own. Compass has a filed defect of exactly
this shape - `work-dir-is-shared-across-branches`. That is already an issue;
it does not need a new one.

## Where each adoption would live, and what it costs

| # | Mechanism | Where it lives | Rough cost |
|---|---|---|---|
| 1 | Assignment as a file path | `skills/worktree-multiagent` (the dispatch rule), `agents/orchestrator.md` | Prose only. ~1 hour. |
| 3 | Review package as a file | A new review-package script under `scripts/` (does not exist yet); `agents/verifier.md` reads the path it prints | A script plus a test. ~half a day. |
| 2 | Base SHA per subtask | `manifest.yml` - a `base_sha` on each subtask in the orchestration block; written by `multiagent.sh`, read by the review package | Schema field, script change, migration row. ~half a day. |
| 4 | No coaching the reviewer | `agents/orchestrator.md` and `agents/reviewer.md`; ideally a `governance/strategies.md` entry beside `S9` | Prose, plus a strategy id. ~2 hours. |
| 5+13 | Fix loop, cap, scoped re-review | `manifest.yml` gains a `review_rounds:` list; `agents/reviewer.md` gains the re-review mode; `compass check` gains a check that a tripped breaker carries an adjudication | The big one. Schema, CLI check, two agent prompts, tests. **2-3 days.** |
| 8 | Model scaled to the work | `skills/worktree-multiagent`, agent frontmatter guidance | Prose. ~1 hour. |
| 9 | Batch small same-shape work | `skills/worktree-multiagent` decomposition heuristics | Prose. ~1 hour. |
| 10 | Workers spawn no subagents | `agents/builder.md` hard boundaries | Prose. ~30 minutes. |
| 12 | Decisions surfaced as a list | `agents/orchestrator.md` hand-off; the verification report template | Prose plus a template section. ~2 hours. |
| 14 | Point the final review at the follow-up ledger | `agents/reviewer.md`; `/compass:verify` | Prose. ~1 hour. |

**Everything except 2, 3 and the fix loop is prose.** That is the headline
for sizing: roughly a day of writing gets seven of the ten rows in the table
above, and the remaining three are where the real work is.

## Recommendation

**Two follow-on issues, not one, and they are not the same size.**

### `multiagent-dispatch-is-a-protocol-not-a-script` - file it, and it is the bigger question

Before adopting mechanisms, settle what `multiagent.sh` is. Today it creates
worktrees and prints instructions. Every SDD mechanism about dispatch,
context and review packaging assumes a controller that actually dispatches.
Deciding whether Compass automates the launch, or commits to the printed
plan as the interface and writes the protocol properly around it, comes
first - it changes what mechanisms 1, 2, 3 and 5 even attach to.

Suggested assessment: risk **cross-cutting** (it changes the orchestrator's
job), familiarity **brownfield-mapped**, size **standard**, goal
**delivery**, role **engineer**. That computes to a feature.

### `orchestrator-loop-hardening` - file it, size it as a feature, not an initiative

The seven prose adoptions plus base SHA and the review package. Deliberately
excludes the fix loop.

Suggested assessment: risk **contained** (prose and two small scripts,
nothing an adopter's tooling depends on), familiarity
**brownfield-mapped**, size **small**, goal **delivery**, role **engineer**.

### The fix loop - do not file it yet

Mechanism 5 is 2-3 days and adds schema. Superpowers arrived at five rounds
and a capability bump at round four from eval campaigns with published
numbers. Compass has no measurement of how often a Compass review round even
repeats, because nothing records review rounds. Adopting a cap of five on
someone else's evidence is picking a number because another project picked
it.

**The honest order is: record the rounds first, then decide the cap.** That
is a small piece of mechanism 5 - a `review_rounds:` list in the manifest,
written by the reviewer - and it can go into `orchestrator-loop-hardening`.
Once enough review rounds are recorded, the cap is a decision with numbers
behind it, which is what `S11` (measure the disputed quantity before
deciding) asks for.

### What should not be adopted

Mechanisms 6 (as written), 7, 11 and 15. Three of those are cases where
Compass already has the stronger answer, and one - never dispatching
implementers in parallel - is the thing Compass exists to do differently.

## One thing this spike did not do, and it is the most important gap

Donated real sessions with numbers attached shaped Superpowers' loop: a
nine-hour stall, a 42,000-character dispatch, 6-13 tool calls of forensics
per resume, an eval where deleting a section moved test-first behaviour from
8/10 to 5/10.

**Compass has one recorded parallel multiagent run.** This spike compared two
designs by reading them. It did not compare them by running them, and it
could not have inside its time-box.

So every adopt above is an argument from the other project's evidence, not
from Compass's. That is a reasonable basis for the prose changes, which are
cheap and reversible. It is a poor basis for the fix loop, which is why the
recommendation defers it.

The measurement Compass is missing is not of Superpowers. It is of itself:
how often a multiagent orchestration is actually used, what the subtasks
cost, how often a review round repeats. `compass retro` already aggregates
re-assessments. Nothing aggregates the multiagent orchestration.

---

## Spike close-out

**Question answered:** yes. Twelve mechanisms to take, four to leave, with
where each lives and what it costs.

**Decision:** graduate-to-delivery, into two issues -
`multiagent-dispatch-is-a-protocol-not-a-script` first, because it changes what
the others attach to, then `orchestrator-loop-hardening`.

**Nothing built.** The `.spike` marker suspended the TDD strategy for
throwaway learning code, and no throwaway code was written - the spike was a
reading exercise. The only file this issue changes is this one.
