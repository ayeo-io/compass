# Compass - Quickstart

This walks you from an empty machine to a finished first issue. It is
deliberately concrete: real commands, in order, with the artifact each one
leaves on disk and what happens when you reach each gate. There are three
walkthroughs - an engineer, a product owner, a marketer - because Compass has
five roles. Each entry point writes that role's document, and the documents
on disk shape the delivery approach.

This document uses Compass's vocabulary: the eight-stage pipeline, the three
scored dimensions, the default guardrails, the assess stage. Each term is
introduced as it comes up, so you can work through this page first and read
`docs/methodology.md` afterwards for the design reasoning behind any of them.

---

## 1. Install

There are two ways to install Compass. Pick one.

**The plugin marketplace is the fastest.** No clone, no install script:

```bash
claude plugin install compass --marketplace ayeo-io/compass
```

Or type two commands inside Claude Code:

```text
/plugin marketplace add ayeo-io/compass
/plugin install compass@compass
```

Enabling the plugin namespaces the commands as `/compass:…`, registers the
hooks, and puts the `compass` CLI on the PATH of the commands Claude Code runs,
inside Claude Code only. Your own terminal does not get it. The first session
start writes a launcher that does not change between versions, at
`~/.claude/plugins/data/compass-compass/compass` (under your profile's folder
if you use another one). When Compass asks you to run a command in your own
terminal, it names that launcher. To type `compass` instead, add the folder to
your `PATH`, for example with
`export PATH="$HOME/.claude/plugins/data/compass-compass:$PATH"` in `~/.zshrc`.
Skip to step 2.

**Install from source** if you want to read or edit the framework as you go.
`scripts/install.sh` installs everything as symlinks, so Compass uses each edit
to your clone at once:

```bash
git clone https://github.com/ayeo-io/compass.git
cd compass
pip install jsonschema                # optional - turns on full JSON Schema lint
bash scripts/install.sh --global      # or: bash scripts/install.sh  (project-local)
```

`install.sh` symlinks `commands/`, `agents/`, and `skills/` into your Claude
Code config as a `compass` subdirectory (so nothing collides with your own
files) and registers its hooks - `pre-tool.sh`, `post-tool.sh`, `stop.sh`,
`session-start.sh`, `prompt-approval.sh` and `approval-summary.sh` - in
`settings.json`. It is idempotent: re-running refreshes the
links and never overwrites a file Compass did not create. `--global` makes the
`/compass:*` commands available in every project; `--copy` installs copies
instead of symlinks if you prefer. Compass needs Python 3.10 or later. The YAML parser it
uses is included in the plugin, so there is nothing to install. `jsonschema`
is a separate, genuinely optional library Compass does not bundle - install
it yourself for full JSON Schema validation in `compass policy lint` and
`compass issue lint` (without it the built-in linter still runs - see
`schemas/README.md`).

Unlike the plugin, `install.sh` does **not** change your PATH. If you want to
call `compass` directly from your shell, add `<clone>/bin` to your `PATH`,
where `<clone>` is the folder you cloned Compass into (or invoke the CLI as
`python3 <clone>/cli/compass`). The slash
commands run the CLI on your behalf, so this only matters when you call it
directly.

Either way, what you have installed is three layers:

- the **methodology** - the markdown in `docs/`, `governance/*.md`,
  `approaches/` and `templates/`, read in place and never copied;
- the **kit** - `cli/compass`, `governance/*.yml`, `schemas/` and the
  `manifest.yml` manifest, which is the deterministic mechanism;
- the **Claude Code adapter** - `commands/`, `agents/`, `skills/`, `hooks/`,
  whose commands call the kit underneath.

`docs/methodology.md` §11 and `docs/portability.md` describe the layers in
full; you do not need them to continue.

Know this before you start: the `pre-tool.sh` hook enforces the red-before-green
TDD strategy. In a project that uses Compass (it has a `.compass/` folder,
which the first Compass command creates), the hook refuses an Edit or Write
to a recognized code file when no failing test is on record for the current
issue - exit code 2, edit denied. It detects writes made through the shell in
common forms only ([safety contract](safety-contract.md#shell-write-detection-is-best-effort)). That is not a bug to work around; it is
the TDD strategy, enforced by the hook, serving the tested-before-ship
guardrail (tested before it lands). The hook is approach-aware: on a
**Spike** the TDD strategy is suspended and the hook does not block. The
rest of this document is, in part, how to work with the hook rather than
against it.

## 2. Assess-and-go - `/compass:init` is optional

There is no required setup step between installing Compass and running your
first issue. The **five default guardrails** and the **default method
strategies** ship active with the framework, so `/compass:assess` works against
the shipped `governance/` defaults from the first issue. The shipped defaults are a
complete governance state on their own: "the shipped defaults and nothing
project-specific yet" is valid - see `governance/README.md`.

`/compass:init` writes the project's own configuration file later, not a
prerequisite. When you want to set the project's name and test command, or
record the project's own rules, run it once from the project root:

```
/compass:init
```

`init` is exempt from assessment - it changes no application code. It:

1. **Writes a minimal `compass.yml`** at the project root: `schema`, `extends:
   compass:default@8`, an `owner` who approves waivers, and `project.name` and
   `project.test_command`. It copies no `governance/` files. The file holds only
   what differs from the shipped defaults, and the defaults are real, in-force
   content from the moment you install Compass. The team adds its own edits
   whenever it is ready. See `docs/configuration.md`.
2. **Migrates an older project instead.** A project that has a
   `.compass/config.yml` or copied `governance/` files from a 5.x version gets
   `compass policy migrate`: a dry run first, and `--apply` only when you say
   yes. See `docs/policy-migrate.md`.
3. **Creates `.compass/work/`** - where every issue's state will live. Note
   that `.compass/work/` **is committed**. It is the audit trail, not temporary files.

`compass init`, which every entry point runs for you, writes only a state file
in `.compass/` and no settings file.

Until `/compass:init` is run, the framework's shipped defaults apply as-is.
`/compass:init` adds to them; it is not a gate.

---

## 3. First issue - the engineer

You are an engineer. An issue: add rate limiting to the public API. You start
where every engineer starts - at the assess stage.

### Assess

```
/compass:assess "Add rate limiting to the public API"
```

Assess scores three dimensions - that part is judgment - and records them
in `.compass/work/add-rate-limiting/manifest.yml`. For this issue it scores
something like: size `medium` (several files, one or two design
decisions), risk `cross-cutting` (a misconfigured limiter slows or blocks
requests from every API consumer), familiarity `brownfield-mapped`. It tags `labels: [public-api]`.

Then the CLI computes the rest. `/compass:assess` runs
`compass approach evaluate --write`, which applies the project's resolved
configuration (the shipped default, an optional git parent, `compass.yml`
and the issue's own `config:`) deterministically - composing the candidate delivery approach, applying the
floors and caps, assembling the gate set - and writes `delivery_approach`,
`stages`, and `gates` into `manifest.yml`. For this issue it computes
**the regular approach, whose gates include the security review, with the
architecture review added because risk is cross-cutting**; no routing
policy rule forces a heavier delivery approach.
Assess then writes the human-readable `delivery-approach.md` alongside it.
The same assessment, resolved configuration and documents on disk give this
exact delivery approach on any machine with the same Compass version - it is
no longer something an agent decides without a written record
([safety contract](safety-contract.md#1-routing-is-deterministic-after-assessment)).
`/compass:assess` also writes a `.compass/current-task` pointer so the CLI
and the hooks know which issue is active.

It then **presents the delivery approach**. It is advisory until confirmed,
and the session waits for you at assess only if the project's `autonomy`
setting lists assess, which `compass approach show` reports. Under the default,
`balanced`, a regular approach goes on and logs that it did not wait; it waits
at define and plan. You read the assessment values, you read the de-scope ledger
- the regular approach collapses nothing major, so the ledger is short - and you confirm,
or you override an assessment value and the override is recorded in
`delivery-approach.md` with your name and reason.

What happens at this gate: the process shows how it got the approach and asks
you to agree the familiarity was read correctly. Confirming takes a
moment. The point is that the process for this issue is now *written down* -
any later session can read `delivery-approach.md` and know exactly how the pipeline
runs.

### Define the acceptance criteria

```
/compass:define
```

The `spec-author` agent reads `delivery-approach.md`, sees "small feature set," and writes
`acceptance-criteria.md` - Given/When/Then scenarios for the rate limiter: the happy
path (a client under the limit is served), the realistic edge cases (a client at
exactly the limit; the limit window resetting), the failure modes that
matter (a client over the limit gets a 429 response, not a dropped connection).
Each scenario carries a traceability id and links back to an intent.

This file is the one every role would read if they were involved - but on a
solo engineering issue, you are reading it for tests. The scenarios here become
your acceptance suite and the first tests of your TDD cycle.

### The requirements review

```
/compass:refine
```

On the regular approach, the requirements review is a lightweight-to-thorough pass - never skipped. The `spec-author`
checks the spec against itself (is "the limit" defined? per-client or global? what
about unauthenticated traffic?) and against governance. Each ambiguity is
resolved into `acceptance-criteria.md` or recorded in `requirements-review.md` with an
owner, so no open question passes silently into Plan. With the
`entry-exit-evaluation` capability on, `compass next` also shows plan as not
ready while a question is open.

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
at a time, and runs the cycle through the CLI:

1. **Red.** Write the failing test for the scenario. Then run
   `compass tdd-red -- <test cmd>`: the CLI runs the test, *asserts it actually
   fails*, writes the red record, and only then writes the
   `.red` marker. If the test passes, `tdd-red` refuses - there is no red to
   record. The CLI writes the marker only after a real failure, but a file
   can be created by hand, so the hook also reads the red record and refuses
   the edit when it is missing.
2. **Green.** Now edit the production code. The `pre-tool.sh` hook sees the
   `.red` marker and the red record, and allows the edit. Write the smallest correct change, then
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
applies the delivery approach's review dimensions: `correctness`, `governance`
and `traceability` on every approach that ships; `regression`, `clarity` and
`security` on the regular approach; and `architecture` because risk is
cross-cutting. The result is `verification-report.md`. A gate
passes only with evidence attached, and that evidence is **typed** - a
`{type, path}` record, such as `test-run`, `command-output`,
`human-approval` or `artifact`, and `guardrails.yml` says which types each gate accepts, so a
mechanical gate cannot be cleared with a written note. `compass check` fails an
empty or wrongly-typed evidence block automatically. Under the default
`adoption: enforced`, the issue does not advance while anything fails - you
fix it, or it goes back.

### Ship

```
/compass:ship
```

Solo orchestration, so shipping commits on the current branch, runs regression across the
result, updates any living docs the change touched, and checks the de-scope
ledger for owed follow-ups (the regular approach owed none here). A final `devlog.md` entry
records what changed and how it was checked. The issue is closed.

That is the whole regular approach, from start to end. Seven artifacts on disk,
each one readable by anyone who picks the issue up later.

---

## 4. First issue - the product owner

You are a product owner. You do not start at the assess stage - you start
*before* the spec, with intent.

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
product owner curates - and names any conflict rather than passing it
on to later stages without a record.

Notice what the intent document is *not*: it is not "add a CSV export
button." That is a solution. The intent document states the outcome, and
the difference matters - see the routing deep dive for how the same literal
request gets a different approach depending on the intent document behind it.

### Assess - now with an intent document

```
/compass:assess "CSV export for finance month-end numbers"
```

Assess reads `intent.md` as part of the goal dimension - the goal is
the *actual outcome wanted*, not the literal request. The `intent.md`
on disk makes the approach name a check of the spec against it before Plan
(the **intent-fidelity gate**), which the `product-owner` agent runs. The approach is the one the three scored dimensions give;
the document adds the check, not extra weight.

### Define the acceptance criteria, then refine them

`/compass:define` writes `acceptance-criteria.md` against the intent document -
every success signal in it must have a scenario that delivers it. At
`/compass:refine`, the `product-owner` agent reviews: it takes each success
signal in turn and finds the scenario behind it, flagging **drift** (a scenario that
solves the literal request but misses the outcome), **gaps** (a signal with no
scenario), and **scope creep** (scenarios beyond the intent document with no
recorded decision).

### The intent-fidelity gate at Plan

```
/compass:plan
```

Per the routing policy's artifact rule RP-ART-002, when `intent.md` is present the
spec **must be checked against `intent.md` before Plan completes**. The
`product-owner` agent runs that check. If the spec drifts from the intent
document - well-formed scenarios that nonetheless miss the outcome - the
spec goes back to define. Well-formed and faithful are different tests, and
this gate is where an agent checks the difference; no CLI check refuses Plan
on it.

From here the pipeline continues as the approach specifies - implement,
verify, ship -
with the engineer doing the work. The product owner's involvement was not a
review added at the end; it changed the delivery approach from the start
and put a gate before Plan.

---

## 5. First issue - the product marketer

You are a product marketer. You work *at the same time* as the spec is
written - not after a finished engineering process.

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
  blank when there is nothing behind the claim yet - an empty slot shows
  the missing work, which is the point.
- **`launch-readiness.md`** - the claims ledger: every claim, its backing
  scenario, and that scenario's verification status.

### How this shapes the approach, and the gate at ship time

A `positioning.md` on disk turns on the `claims` review dimension and -
per the artifact rule RP-ART-001 - **holds shipping until every claim recorded
in the manifest names a scenario that exists, and the reviewer has judged at
the `verify` stage that the scenario passes and backs the claim**. `verify.claims` is a blocking gate: the
artifact rule adds it on every delivery approach while `positioning.md` is present.
On an issue already assessed, re-assess after writing `positioning.md`.

So the marketer's gate applies until the last stage. At `/compass:ship`, the
`product-marketer` agent checks each row of `launch-readiness.md`. Every row must be green: a
claim, a backing scenario, that scenario passing at Verify. A red row - a
claim whose scenario is missing, failing, or skipped - and the
`product-marketer` agent does not pass the claims gate, so ship does not close
the issue. The marketer's moves at that point are to soften the claim, cut
it, or file the missing scenario. Compass checks that each recorded claim
names a scenario that exists; whether that scenario backs the claim is the
reviewer's judgment ([safety contract](safety-contract.md#compass-does-not-prove-correctness)).

---

## When you cannot frame it yet - a spike

Some work is not a known change - it is a question. Finding the cause of a
defect nobody understands, evaluating whether an approach is even viable, learning an unfamiliar
API. You cannot state acceptance criteria for it because the behavior is the
unknown. That is not an exemption from assessment; it is the **spike**.
Assess still runs (`delivery-approach.md` records the question and a
timebox), but the define stage collapses to the question, the
requirements review is skipped, and implementation becomes exploration -
the
TDD strategy is suspended and the hook does not block, because red-before-green
is the wrong discipline for code you are writing to learn something and may
throw away. What limits the risk: **nothing lands from a Spike**. The
only exit that keeps code is *graduating* - reassessing into a delivery
approach where the guardrails apply in full - or discarding it with the
finding recorded. See `approaches/spike.md`.

## See the issue's state in the status line

Compass can show the current issue in Claude Code's status line, for
example:

```text
compass · fix-login-redirect · quick fix · Implement · gates 1/3 · TRC-002 red
```

The last field says the second traced criterion has a failing test on
record. The line is shown to you, never to the model, so it costs no
tokens, and it names the same stage as `compass next`.

A plugin cannot add a status line itself, so add it to your Claude Code
settings file, either your own or the project's:

```json
{
  "statusLine": {
    "type": "command",
    "command": "~/.claude/plugins/data/compass-compass/compass-statusline"
  }
}
```

That file is a launcher the session-start hook keeps in the plugin's data
folder, which Claude Code keeps across plugin updates. Each session start
points it at the installed version, so the setting never needs editing. A
plugin loaded with `--plugin-dir` keeps its launcher under
`~/.claude/plugins/data/compass-inline/` instead. `/compass:init` offers to
add the entry for you: it shows the change and writes it only when you say
yes. Outside a
Compass project, the line is empty. The line fits the terminal width that
Claude Code passes in `COLUMNS`, and assumes 80 columns when it is not set.

## See the approach in your terminal

When you run `compass next` in a terminal, it shows the issue's approach as a
rail, with the current stage marked:

```text
regular · feature-implementing
Assess ✓ → Define ✓ → Refine ✓ → Plan ✓ → Breakdown ✓ → Implement ● → Verify ○ → Ship ○

Implement [gate: verify.correctness]
Next: /compass:implement
```

Piped output, and any run inside Claude Code, keeps the plain one-line form,
so scripts and the model see no change. Two environment variables change the
rail:

- `NO_COLOR` removes the color.
- `COMPASS_COLOR=never` uses the ASCII markers `[x] [>] [ ] [-]` and no
  color. `COMPASS_COLOR=always` shows the rail even when the output is piped.
  `NO_COLOR` still removes the color.

If a project turns on the capability `entry-exit-evaluation`, the line also
names the entry checks of the current stage that are not met, for example
`Plan | entry not met: dor-no-open-questions`
(`docs/entry-exit-evaluation.md`). With the capability `artifact-freshness`
on, it names a stale document the stage consumes, for example
`Implement | entry not met: technical-design is stale`
(`docs/artifact-freshness.md`).

If the issue is at implement and waits for another issue that has not reached
the point its `depends_on` entry names (`compass issue depends add`), the line
ends with what it waits for, for example
`Implement [gate: verify.correctness] | blocked: waits for b to reach done`.
The pre-tool hook refuses production-code edits while it can read, in this
checkout, that the wait is not met, until the dependency is removed. A fault
in reading it allows the edit with a warning
([safety contract](safety-contract.md#a-dependency-between-issues-is-read-from-this-checkout-and-a-fault-never-blocks)). Earlier stages show no wait, so a spec and a design can
be written while the other issue is open. A dependency `compass next` cannot
judge, such as one on an issue with no manifest in this checkout, is left out
of the line; `compass issue lint` names it.

## Decisions an agent took for you

When an agent resolves a requirement question itself, it records the decision
(`compass issue decision add`, or `--from-ledger` for the requirements review).
What happens next depends on the project's `autonomy` setting:

- On `balanced` and `controlled`, `compass next` stops at a checkpoint that holds
  unconfirmed decisions. Its first line reads `Waiting at the define checkpoint:
  2 decision(s) to confirm`, and the lines below list each decision with its
  resolution. Confirm them all with `compass evidence approve --decisions
  --approver <you> --role <role>`, or reopen one with `compass issue decision
  set <id> --status reopened --reason "<why>"`. A reopened decision keeps the
  checkpoint waiting.
- On `autonomous`, `compass next` lists the decisions below its usual line and
  does not wait. They stay open.

`compass retro --decisions` reports, across all issues, how many of these
decisions were confirmed as taken, how many were changed, and how many were
never confirmed on a finished issue.

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
issue - and exits non-zero if anything fails, under the default
`adoption: enforced`; to add Compass to CI, you only
"run `compass ci`, honor the exit code" (see `ci/README.md`). And
`compass retro` reads the re-assessment log across every issue and
reports whether assessment is systematically over- or under-sizing the
process - the way you find out, from the framework's own records, if the
routing policy needs changes.
