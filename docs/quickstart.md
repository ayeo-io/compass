# Compass - Quickstart

This walks you from an empty machine to a finished first issue. It is
deliberately concrete: real commands, in order, with the artifact each one
leaves on disk and what the gates feel like when you hit them. There are three
walkthroughs - an engineer, a product owner, a marketer - because Compass has
five roles and the entry point you use shapes the delivery approach the
assess stage composes.

This document uses Compass's vocabulary: the eight-stage pipeline, the four
dimensions, the default guardrails, the assess stage. Each term is
introduced as it comes up, so you can work through this page first and read
`docs/methodology.md` afterwards for the design reasoning behind any of them.

---

## 1. Install

There are two ways in. Pick one.

**The plugin marketplace is the fastest.** No clone, no install script:

```bash
# In Claude Code:
/plugin marketplace add jed72/compass
/plugin install compass@compass
```

Enabling the plugin namespaces the commands as `/compass:…`, registers the
hooks, and puts the `compass` CLI on your PATH. Skip to step 2.

**Install from source** if you want to read or edit the framework as you go.
`scripts/install.sh` wires everything in by symlink, so edits to your clone are
picked up live:

```bash
git clone https://github.com/jed72/compass.git
cd compass
pip install jsonschema                # optional - turns on full JSON Schema lint
bash scripts/install.sh --global      # or: bash scripts/install.sh  (project-local)
```

`install.sh` symlinks `commands/`, `agents/`, and `skills/` into your Claude
Code config as a `compass` subdirectory (so nothing collides with your own
files) and registers the four hooks - `pre-tool.sh`, `post-tool.sh`,
`stop.sh`, `session-start.sh` - in `settings.json`. It is idempotent: re-running refreshes the
links and never clobbers a file Compass did not create. `--global` makes the
`/compass:*` commands available in every project; `--copy` installs copies
instead of symlinks if you prefer. Compass needs Python 3. The YAML parser it
uses travels inside the plugin, so there is nothing to install. `jsonschema`
is a separate, genuinely optional library Compass does not bundle - install
it yourself for full JSON Schema validation in `compass policy lint` and
`compass issue lint` (without it the built-in linter still runs - see
`schemas/README.md`).

Unlike the plugin, `install.sh` does **not** change your PATH. If you want to
call `compass` directly from your shell, add `$COMPASS_HOME/bin` to your
`PATH` (or invoke the CLI as `python3 $COMPASS_HOME/cli/compass`). The slash
commands run the CLI on your behalf, so this only matters when you call it
directly.

Either way, what you have installed is three layers:

- the **methodology** - the markdown in `docs/`, `governance/*.md`,
  `approaches/` and `templates/`, read in place and never copied;
- the **kit** - `cli/compass`, `governance/*.yml`, `schemas/` and the
  `manifest.yml` manifest, which is the deterministic mechanism;
- the **Claude Code adapter** - `commands/`, `agents/`, `skills/`, `hooks/`,
  whose commands call the kit underneath.

`docs/methodology.md` §11 and `docs/portability.md` have the full picture;
you do not need it to continue.

One thing to know going in: the `pre-tool.sh` hook enforces the red-before-green
TDD strategy. Once Compass is installed, the hook blocks an edit to a
recognised code file when no failing test is on record for the current
issue - exit code 2, edit denied. That is not a bug to work around; it is
the TDD strategy, enforced by the hook, serving the tested-before-ship
guardrail (tested before it lands). The hook is approach-aware: on a
**Spike** the TDD strategy is suspended and the hook does not block. The
rest of this document is, in part, how to work with the hook rather than
against it.

## 2. Assess-and-go - `/compass:init` is optional

There is no required setup step between installing Compass and running your
first issue. The **five default guardrails** and the **default method
strategies** ship active with the framework, so `/compass:assess` works against
the shipped `governance/` defaults on day one. The shipped defaults are a
complete governance state on their own: "the shipped defaults and nothing
project-specific yet" is valid - see `governance/README.md`.

`/compass:init` is how a project adds its own governance later, not a
prerequisite. When you have opinions to encode, run it once from the project
root:

```
/compass:init
```

`init` is exempt from assessment - it changes no application code. It:

1. **Copies `governance/`** into the project - `guardrails.md`,
   `strategies.md`, `strategies-rationale.md`, `routing-policy.md` - so the
   team can extend the shipped defaults. It does not make you author anything: the defaults are real,
   in-force content from the moment they land. The team adds project
   guardrails and strategies whenever it is ready.
2. **Creates `.compass/config.yml`** - delivery-approach defaults, multiagent
   thresholds, worktree ceilings. The defaults are sane; `init` confirms
   them with you.
3. **Creates `.compass/work/`** - where every issue's state will live. Note
   that `.compass/work/` **is committed**. It is the audit trail, not scratch.

Until `init` is run, the framework's shipped `governance/` defaults apply
as-is. `init` adds to them; it is not a gate.

---

## 3. First issue - the engineer

You are an engineer. An issue: add rate limiting to the public API. You start
where every engineer starts - at the assess stage.

### Assess

```
/compass:assess "Add rate limiting to the public API"
```

Assess reads four dimensions - that part is judgement - and records them
in `.compass/work/add-rate-limiting/manifest.yml`. For this issue it scores
something like: size `standard` (several files, one or two design
decisions), risk `cross-cutting` (a misconfigured limiter degrades
something every API consumer touches), familiarity `brownfield-mapped`, role
`engineer`. It tags `labels: [public-api]`.

Then the mechanism takes over. `/compass:assess` shells out to
`compass approach evaluate --write`, which applies `governance/routing-policy.yml`
deterministically - composing the candidate delivery approach, applying the
floors and caps, assembling the gate set - and folds `delivery_approach`,
`stages`, and `gates` back into `manifest.yml`. For this issue it lands on
**feature, with the `security` review dimension turned on because risk is
cross-cutting**; no routing policy rule forces a heavier delivery approach.
Assess then writes the human-readable `delivery-approach.md` alongside it.
Same assessment + same policy would produce this exact delivery approach on
any machine - it is no longer something an agent composes in its head.
`/compass:assess` also drops a `.compass/current-task` pointer so the CLI
and the hooks know which issue is live.

It then **presents the delivery approach and waits**. It is advisory until
confirmed. You read the four assessment values, you read the de-scope ledger
- feature collapses nothing major, so the ledger is short - and you confirm,
or you override an assessment value and the override is recorded in
`delivery-approach.md` with your name and reason.

What the gate feels like: this is where the process shows its work and asks
you to agree the familiarity was read correctly. Confirming takes a
moment. The point is that the process for this issue is now *written down* -
any later session can read `delivery-approach.md` and know exactly what shape the pipeline
takes.

### Define the acceptance criteria

```
/compass:define
```

The `spec-author` agent reads `delivery-approach.md`, sees "small feature set," and writes
`acceptance-criteria.md` - Given/When/Then scenarios for the rate limiter: the happy
path (a client under the limit is served), the realistic edges (a client at
exactly the limit; the limit window rolling over), the failure modes that
matter (a client over the limit gets a clean 429, not a dropped connection).
Each scenario carries a traceability id and links back to an intent.

This file is the one every role would read if they were involved - but on a
solo engineering issue, you are reading it for tests. The scenarios here become
your acceptance suite and seed your TDD cycle.

### The requirements review

```
/compass:refine
```

On a feature, the requirements review is a light-to-full pass - never skipped. The `spec-author`
QAs the spec against itself (is "the limit" defined? per-client or global? what
about unauthenticated traffic?) and against governance. Each ambiguity is
resolved into `acceptance-criteria.md` or recorded in `requirements-review.md` with an
owner. An unresolved ambiguity is not allowed to pass silently into Plan.

### Plan

```
/compass:plan
```

The `planner` agent writes a real `technical-design.md`: the technical approach, each
design decision recorded ADR-style (token bucket vs. sliding window - what was
chosen, what was rejected, why), and a governance check run against all of
`governance/` - guardrails, strategies, and the routing policy. The work here
is one or two subtasks, not four, so the distribution map is a short list, not a
full `distribution-map.md`. The gate: the governance check passed - every
guardrail cleared with evidence - and you record its result and link it.

### Implement

```
/compass:implement
```

This is where the hook matters. The `builder` agent works one scenario
at a time, driving the cycle through the CLI:

1. **Red.** Write the failing test for the scenario. Then run
   `compass tdd-red -- <test cmd>`: the CLI runs the test, *asserts it actually
   fails*, writes the red record, and only then writes the
   `.red` marker. If the test passes, `tdd-red` refuses - there is no red to
   record. The marker only ever means a real failure was observed.
2. **Green.** Now edit the production code. The `pre-tool.sh` hook sees the
   `.red` marker and allows the edit. Write the smallest correct change, then
   run `compass tdd-green -- <test cmd>`: the CLI asserts the test now passes,
   writes the green record, and clears the `.red` marker.

   **Where the record lands.** The binding decides the filename. Recorded
   `--scenario TRC-x`, the run writes `evidence/green-TRC-x.json`; with no
   binding it writes `evidence/green.json`. Only that one file is written, so
   recording one scenario never overwrites a record another gate is citing.
3. **Refactor** under a green suite - the marker is already cleared, which is
   the detectable hand-off to Verify.

If you skip red, the hook blocks you with a message telling you exactly what to
do. The fix is always the same: go write the test, then `compass tdd-red`.

### Verify

```
/compass:verify
```

The `verifier` runs the scenarios as the acceptance suite and runs the full
TDD suite, pasting the actual command output - "the tests pass" is the run,
not the sentence. It also runs `compass check`, which runs the
`governance/guardrails.yml` checks against `manifest.yml` and `evidence/` - every
scenario lists a test, the recorded suite passed, every changed file traces to
a scenario, every `pass` gate has resolving evidence. The `reviewer` then
applies the delivery approach's review dimensions: `correctness`, `governance`,
`traceability` always, plus `regression`, `clarity`, and `security` scaled to
the cross-cutting risk. The result is `verification-report.md`. A gate
passes only with evidence attached, and that evidence is **typed** - a
`{type, path}` record (`test-run`, `command-output`, `human-approval`,
`artifact`), and `guardrails.yml` says which types each gate accepts, so a
mechanical gate cannot be cleared with a written note. `compass check` fails an
empty or wrongly-typed evidence block automatically. If anything fails, the
issue does not advance - you fix it, or it goes back.

### Ship

```
/compass:ship
```

Solo orchestration, so shipping commits on the current branch, runs regression across the
result, updates any living docs the change touched, and checks the de-scope
ledger for owed follow-ups (feature owed none here). A final `devlog.md` entry
records what landed and how it was checked. The issue is closed.

That is the full feature approach, walked end to end. Seven artifacts on disk,
each one readable by anyone who picks the issue up later.

---

## 4. First issue - the product owner

You are a product owner. You do not start at the assess stage - you start
*upstream* of the spec, with intent.

### Intent

```
/compass:intent "Let finance pull their month-end numbers without filing a data request"
```

The `product-owner` agent adopts the product owner's vocabulary - outcomes and
users, not files and functions - and writes `intent.md`: the **problem**
(finance cannot self-serve; every month-end is a data request and a wait), the
**outcome** (finance gets their numbers directly), the **success signals**
(finance pulls month-end numbers without filing a request; the data team's
month-end ticket volume drops), the **constraints**, and the **non-goals** (we
are *not* building a full reporting suite). It checks the intent document
against the product strategies in `governance/strategies.md` - the ones the
product owner curates - and names any tension rather than passing it
downstream silently.

Notice what the intent document is *not*: it is not "add a CSV export
button." That is a solution. The intent document states the outcome, and
the difference matters - see the routing deep dive for how the same literal
request routes differently depending on the intent document behind it.

### Assess - now with an intent document

```
/compass:assess "CSV export for finance month-end numbers"
```

Assess reads `intent.md` as part of the goal and role dimensions - the goal is
the *actual outcome wanted*, not the literal request. The `product-owner`
entry point does two things to the delivery approach: it adds `intent.md` as
a required artifact, and it inserts the **intent-fidelity gate** before Plan.
The delivery approach comes out heavier than a bare engineering "add an
export" would - that extra weight is the framework working, not overhead.

### Define the acceptance criteria, then refine them

`/compass:define` writes `acceptance-criteria.md` against the intent document -
every success signal in it must have a scenario that delivers it. At
`/compass:refine`, the `product-owner` agent reviews: it walks every success
signal and finds the scenario behind it, flagging **drift** (a scenario that
solves the literal request but misses the outcome), **gaps** (a signal with no
scenario), and **scope creep** (scenarios beyond the intent document with no
recorded decision).

### The intent-fidelity gate at Plan

```
/compass:plan
```

Per the routing policy's `role_rules`, when a product owner is involved the
spec **must be checked against `intent.md` before Plan completes**. The
`product-owner` agent runs that check. If the spec drifts from the intent
document - well-formed scenarios that nonetheless miss the outcome - Plan
does not proceed; the spec goes back. Well-formed and faithful are different
tests, and this gate is where the difference is enforced.

From here the pipeline continues as the approach specifies - implement,
verify, ship -
with the engineer carrying it. The product owner's involvement was not a
review added at the end; it changed the delivery approach from the start
and put a gate before Plan.

---

## 5. First issue - the product marketer

You are a product marketer. You work *parallel* to the spec - not downstream
of a finished engineering process.

### Position

```
/compass:position "The finance self-serve export"
```

The `product-marketer` agent adopts the marketer's vocabulary - claims, voice,
audience - reads the voice & positioning strategies in
`governance/strategies.md` (the ones the marketer curates), reads
`acceptance-criteria.md` if it exists yet, and writes two artifacts:

- **`positioning.md`** - the audience, the value proposition, and the claim
  set. For **every claim**, it names the scenario in `acceptance-criteria.md` that
  backs it. A claim with no backing scenario is not yet a claim: it is either
  a scenario that needs writing (raised with `spec-author` at the define stage) or a
  claim that has to be cut. The template leaves the backing-scenario slot
  blank when there is nothing behind the claim yet - an empty slot is a
  visible debt, which is the point.
- **`launch-readiness.md`** - the claims ledger: every claim, its backing
  scenario, and that scenario's verification status.

### How this shapes the route, and the gate at ship time

The `product-marketer` entry point turns on the `claims` review dimension and -
per the `role_rules` - **blocks shipping until every claim in `positioning.md`
traces to a passing scenario**. `verify.claims` is a blocking role gate: the
role rule adds it on every delivery approach while a marketer is in play.

So the marketer's gate applies right up to the end. At `/compass:ship`, the
`product-marketer` agent walks `launch-readiness.md`. Every row must be green: a
claim, a backing scenario, that scenario passing at Verify. A red row - a
claim whose scenario is missing, failing, or skipped - and ship refuses to
close the issue. The marketer's only moves at that point are to soften the
claim, cut it, or file the missing scenario. What cannot happen is a launch
claim shipping on a scenario that does not back it.

---

## When you cannot frame it yet - a spike

Some work is not a known change - it is a question. Root-causing a mysterious
defect, evaluating whether an approach is even viable, learning an unfamiliar
API. You cannot state acceptance criteria for it because the behaviour is the
unknown. That is not an exemption from assessment; it is the **spike**.
Assess still runs (`delivery-approach.md` records the question and a
timebox), but the define stage collapses to the question, the
requirements review is skipped, and implementation becomes exploration -
the
TDD strategy is suspended and the hook does not block, because red-before-green
is the wrong discipline for code you are writing to learn something and may
throw away. What keeps it honest: **nothing lands from a Spike**. The
only exit that keeps code is *graduating* - reassessing into a delivery
approach where the guardrails apply in full - or discarding it with the
finding recorded. See `approaches/spike.md`.

## Where to go next

- **`docs/routing-deep-dive.md`** - how the assess stage actually composes an
  approach, with worked examples, including the same literal request routing
  four different ways, and a spike worked through end to end.
- **`docs/roles-guide.md`** - one concrete scenario read through all five
  roles, and what each role owns.
- **`docs/portability.md`** - the three layers (methodology / kit / adapter),
  and what porting Compass to another runtime involves: rewrite the adapter,
  keep the methodology and the kit untouched.

When a session leaves an issue half-finished, `/compass:status` reports where
every issue stands, and `/compass:resume <issue-slug>` picks one up from disk -
the artifacts were written precisely so the process never has to be
re-derived. Once you are running more than one issue at a time, `/compass:flow`
is the view across all of them - triage, blockers, and a periodic digest;
`docs/roles-guide.md` explains why it is a capability rather than a role.

Two more CLI commands work across the whole board. `compass ci` runs the full
mechanical gate suite - `policy lint`, then `issue lint` and `check` for every
issue - and exits non-zero if anything fails; wiring Compass into CI is just
"run `compass ci`, honour the exit code" (see `ci/README.md`). And
`compass retro` reads the re-assessment log across every issue and
reports whether assessment is systematically over- or under-sizing the
process - the framework's own feedback loop, the way you find out if the
routing policy needs tuning.
