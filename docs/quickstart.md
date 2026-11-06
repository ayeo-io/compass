# Compass - Quickstart

This walks you from an empty machine to a finished first issue. It is
deliberately concrete: real commands, in order, with the artifact each one
leaves on disk and what happens when you reach each gate. There are three
walkthroughs - an engineer, a product owner, a marketer - because Compass has
five roles. Each entry point writes that role's document, and the documents
on disk add the gates that check them.

This document uses Compass's vocabulary: the four-stage path, the three
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

`install.sh` symlinks `commands/` and `skills/` into your Claude
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
- the **Claude Code adapter** - `commands/`, `skills/`, `hooks/`,
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
guardrail (tested before it lands). On a **spike** the TDD strategy is
suspended and the hook does not block. The
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

You are an engineer. An issue: add rate limiting to the public API. Every
delivery issue runs the same four stages, in order: **assess**, **specify**,
**build** and **ship** (ADR-092). One command runs them all in this session:

```
/compass:go "Add rate limiting to the public API"
```

`/compass:assess` does the assessment alone, and the `next:` lines take you
from there. Either way the session follows the same steps.

### Assess

Assess scores three dimensions - that part is judgment - and records them
with a reason for each. For this issue the session reads the code first, then
scores: size `medium` (several files, one design decision), risk
`cross-cutting` (a misconfigured limiter blocks every API consumer),
familiarity `brownfield-mapped`. It tags `labels: [public-api]`. It records
the ratings, the intent and the first scenario in one call:

```
compass quick-fix start add-rate-limiting \
  --risk "cross-cutting - a misconfigured limiter blocks every API consumer" \
  --familiarity "brownfield-mapped - the middleware is documented" \
  --size "medium - several files and one design decision" \
  --labels public-api \
  --intent "A client over the request limit gets a 429 response" \
  --scenario "Given a client has sent 100 requests this minute, When it sends one more, Then the response is 429" \
  --test tests/test_limiter.py::test_over_limit
```

`compass quick-fix start` serves every size, not only a small fix. It writes
`.compass/work/add-rate-limiting/manifest.yml` and the acceptance criteria at
`docs/compass/<date>-add-rate-limiting/acceptance-criteria.md`, with the one
scenario as `TRC-001`. It also writes a `.compass/current-task` pointer, so
the CLI and the hooks know which issue is active.

Then the CLI computes the rest. It applies the project's resolved
configuration (the shipped default, an optional git parent, `compass.yml` and
the issue's own `config:`) to the assessment, picks the first evidence row
that matches and adds what the risk and labels add. It writes
`delivery_approach: delivery`, `evidence_required` (the evidence the change
owes before it ships) and the `gates` derived from it into `manifest.yml`.
For this issue that is **the standard evidence row, which owes the
regression, security and clarity reviews and the Definition of Done, with the
architecture review added because risk is cross-cutting**. The session shows
you the three lines of `compass approach show` before it edits any file:

```text
Approach: delivery (risk cross-cutting, familiarity brownfield-mapped, size medium) - does not stop to wait for you
Evidence: scenarios, red-before-green, suite-green, correctness, governance, traceability, regression, security, clarity, architecture, outer-loop, isolation, layering, definition-of-done
Writes: .compass/work/add-rate-limiting/ and docs/compass/2026-11-06-add-rate-limiting/
```

The same assessment and resolved configuration give this exact evidence on
any machine with the same Compass version - it is no longer something an
agent decides without a written record
([safety contract](safety-contract.md#1-routing-is-deterministic-after-assessment)).
`outer-loop`, `isolation` and `layering` are owed by the four-layer
acceptance strategy (`S17`), because the change is behavior a real client can
observe.

The session waits for you only at the checkpoints the project's `autonomy`
setting lists, and the first line of `compass approach show` says whether it
does. The default is `balanced`: under `balanced` a delivery issue goes on
and does not wait, unless its scenarios owe a person's approval (a `G5` label,
such as `payments`, or critical risk), and then it waits at specify. The same
holds under `autonomous`. A stricter project can set `controlled`: under
`controlled` it waits at assess and specify, and also at build and ship where
the four-layer acceptance strategy applies. Read the three lines. If an
assessment value is wrong, correct it with `/compass:assess --reassess
--reason "..."`, which recomputes the evidence and logs the change in the
manifest's `reassessments:` list.

### Specify

Specify writes the scenarios. The session adds to `acceptance-criteria.md`
the Given/When/Then scenarios for the rate limiter: the happy path (a client
under the limit is served), the realistic edge cases (a client at exactly the
limit; the limit window resetting) and the failure modes that matter (a
client over the limit gets a 429 response, not a dropped connection). Each
scenario has a traceability id, links to an intent and declares the test that
checks it:

```
compass scenario add TRC-002 --intent INT-1 --test tests/test_limiter.py::test_at_limit
```

The session also asks which input classes and failure modes the intent
implies that no scenario covers. Each one becomes a scenario, or is recorded
with `compass scenario descope "<mode>" --reason "<why>"`. It fills the
Non-functional requirements rows of the spec: the scenarios that cover each
concern, or the reason it does not apply. Ambiguities ("the limit" -
per-client or global? what about unauthenticated traffic?) are settled in the
criteria, or recorded as a decision with `compass issue decision add`.

This file is the one every role would read if they were involved - but on a
solo engineering issue, you are reading it for tests. The scenarios become
your acceptance suite and the first tests of your TDD cycle. A design
decision worth keeping, such as token bucket against sliding window, goes in
a decision record beside the code, not in a Compass document.

### Build

This is where the hook matters. The session works one scenario at a time,
and runs the cycle through the CLI:

1. **Red.** Write the failing test for the scenario. Then run
   `compass tdd-red --scenario TRC-001 -- <test cmd>`: the CLI runs the test,
   *asserts it actually fails*, writes the red record, and only then writes
   the `.red` marker. If the test passes, `tdd-red` refuses - there is no red
   to record. The CLI writes the marker only after a real failure, but a file
   can be created by hand, so the hook also reads the red record and refuses
   the edit when it is missing.
2. **Green.** Now edit the production code. The `pre-tool.sh` hook sees the
   `.red` marker and the red record, and allows the edit. Write the smallest
   correct change, then run `compass tdd-green --scenario TRC-001 -- <test cmd>`:
   the CLI asserts the test now passes, writes the green record, and clears
   the `.red` marker.

   **Where the record lands.** The binding decides the filename. Recorded
   `--scenario TRC-x`, the run writes `evidence/green-TRC-x.json`; with no
   binding it writes `evidence/green.json`. With `--loop outer` the file name
   ends in `.outer.json` instead of `.json`. Only that one file is written, so
   recording one scenario never overwrites a record another gate is citing,
   and an inner-loop record never replaces an outer-loop one.
3. **Refactor** under a green suite.

Where the four-layer acceptance strategy applies, the acceptance test runs
as the outer loop: `compass tdd-red --loop outer` first, and
`compass tdd-green --loop outer --candidate <build id>|local --client api|web|cli`
last, so the green says what it ran against and through. The isolation proof
(`compass isolation record`) and the layering record
(`compass layering record`) follow, where they are owed.

If you skip red, the hook blocks you with a message telling you exactly what to
do. The fix is always the same: go write the test, then `compass tdd-red`.

### Ship

```
/compass:ship
```

Ship passes the gates with evidence. The session runs the suites and the
review in this session and pastes the actual command output - "the tests
pass" is the run, not the sentence. It applies the review dimensions the
evidence list names: `correctness`, `governance` and `traceability` on every
issue; `regression`, `security` and `clarity` on the standard row; and
`architecture` because risk is cross-cutting. Each one passes its gate with
evidence attached, and that evidence is **typed** - a `{type, path}` record,
such as `test-run`, `command-output`, `human-approval` or `artifact`, and
`guardrails.yml` says which types each gate accepts, so a mechanical gate
cannot be cleared with a written note.

`compass quick-fix finish` runs the suite, records it and passes the three
gates every issue owes. While anything else is owed, it refuses with exit 1
before it writes anything, and prints one `next:` line for each owed item.
`compass check` runs the `governance/guardrails.yml` checks against
`manifest.yml` and `evidence/` - every scenario lists a test, the recorded
suite passed, every changed file traces to a scenario, every `pass` gate has
resolving evidence. Under the default `adoption: enforced`, the issue does
not close while anything fails.

The session commits only when you ask. Until then it passes `--no-commit`,
and the last line names the traced files to stage. Then
`compass ship-commit --issue add-rate-limiting -m "<message>" --release-note "<release line>"`
commits on the current branch and closes the issue.

That is the whole path, from start to end. The manifest, the evidence and
`acceptance-criteria.md` are on disk, readable by anyone who picks the issue
up later.

---

## 4. A brief from a product owner, and a public claim

A product owner often arrives with a brief, not a change: "Let finance pull
their month-end numbers without filing a data request". Start the issue with
`/compass:go` as before. The session loads the `intent-interview` skill,
which turns the brief into the Summary and Intent links of
`acceptance-criteria.md` before any scenario is written. Every statement in
the intent comes from the brief or from an answer the product owner gave.
Where the brief is silent, the session asks one question at a time.

Notice what the intent is *not*: it is not "add a CSV export button." That is
a solution. The intent states the outcome, and every success signal in it
must have a scenario that delivers it.

A change that makes a public claim, such as a line in the release notes,
records the claim in the manifest's `claims:` with the scenario that backs
it. The `claim-traces-to-scenario` check fails when a claim names no
scenario. Whether that scenario backs the claim is the reviewer's judgment
([safety contract](safety-contract.md#compass-does-not-prove-correctness)).
A project that wants the claims gate on every issue adds it in `compass.yml`
(`docs/configuration.md`).

---

## When you cannot frame it yet - a spike

Some work is not a known change - it is a question. Finding the cause of a
defect nobody understands, evaluating whether an approach is even viable, learning an unfamiliar
API. You cannot state acceptance criteria for it because the behavior is the
unknown. That is not an exemption from assessment; it is the **spike**, the
one approach that is not on the path. Assess still runs and records the
question and a timebox. Build becomes exploration: the TDD strategy is
suspended and the hook does not block, because red-before-green is the wrong
discipline for code you are writing to learn something and may throw away.
Ship becomes conclude. What limits the risk: **nothing lands from a spike**.
The only exit that keeps code is *graduating* - re-assessing into a delivery
issue, where the guardrails apply in full - or discarding it with the finding
recorded. See `approaches/spike.md`.

## See the issue's state in the status line

Compass can show the current issue in Claude Code's status line, for
example:

```text
compass · fix-login-redirect · delivery · Build · gates 1/3 · TRC-002 red
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

## What `compass next` prints

`compass next` prints one line: the issue's stage, the first gate not yet
passed, and the one command to run next.

```text
Build [gate: verify.correctness] | next: compass tdd-red --scenario TRC-001 -- <test command>
```

The stage is a stage of the path (ADR-092): assess, specify, build or
ship. An issue assessed before the path keeps its legacy stages, and
every rule reads them as before; `compass next`, the rail and the status line
show each one as the path stage it maps to:

| Legacy stage | Shown as |
|---|---|
| `assess` | Assess |
| `define`, `refine`, `plan` | Specify |
| `breakdown`, `implement` | Build |
| `verify`, `ship` | Ship |

The `next:` command comes from the issue's records, the first row that
matches (`cli/compass_pkg/next_step.py`):

| The records show | `next:` |
|---|---|
| no scenario | `compass scenario add TRC-001 --intent <intent id> --test <path::name>` |
| a scenario with no test | `compass scenario tests set <id> --test <path::name>` |
| a path issue's spec fails `nfr-rows-resolved` | fill the Non-functional requirements rows of the spec named |
| `scenario-approval` owed, no outcome | `compass evidence request --checkpoint specify`, then stop for `/compass:approve` |
| `S17` applies, no outer-loop red | `compass tdd-red --loop outer --scenario <id> -- <acceptance test command>`; where `layering` is owed, write the layering test and `git add` it first |
| a scenario with no red | `compass tdd-red --scenario <id> -- <test command>` |
| `S17` applies, no outer-loop green | `compass tdd-green --loop outer --scenario <id> --candidate <build id>\|local --client api\|web\|cli -- <acceptance test command>` |
| a red with no green | `compass tdd-green --scenario <id> -- <test command>` |
| `isolation` owed | `compass isolation record --candidate <the green's> --client <the green's> --parallel "..." --repeat "... {tests}"` |
| `layering` owed | `compass layering record --test-path <path> -- <layering test command>` |
| a Definition of Done item open | `compass evidence add <EV-id> --type <type> --path <path> --meets <item>` |
| a gate not passed (on a path issue, not one of the three immovable gates) | `compass gate pass <gate> --evidence <EV-id>` |
| `human-approval` owed | `compass evidence request --check human-approval-present` |
| a listed checkpoint with no outcome | `compass evidence request --checkpoint <stage>`, then stop for `/compass:approve` |
| a path issue with only the three immovable gates pending | `compass quick-fix finish -m "<commit message>" --no-commit -- <test command>` |
| every gate passes | `compass check`, then `git add -- <the traced files>`, then `compass ship-commit -m "<message>"` |

What a path issue owes comes from its `evidence_required` list. The
requirement rows and the layering test come before the red because the spec
and the staged test files are part of the tree the outer-loop green, the
isolation proof and the layering record are bound to;
`compass quick-fix start` fills them with a reason only for a change that owes
no Definition of Done. An issue
assessed before the path owes the `S17` records its `acceptance_strategy` block
names, and the Definition of Done when its verify stage is `thorough`. A spike
first names `compass evidence add EV-SPIKE --type spike-conclusion`, then
`compass gate pass spike.conclude`. `compass next --json` gives the same
command in a `next` field, and `null` on a closed issue.

On a path issue, each verb that writes a record of the issue ends its text
output with the same line, `next: <command>`: `compass scenario add`,
`scenario tests set`, `scenario descope`, `tdd-red`, `tdd-green`, `gate pass`,
`evidence add`, `changed-file add`, `isolation record`, `layering record`,
`evidence approve` and `quick-fix start` and `finish`. `--json` and `--quiet`
output do not change, and an issue assessed before the path prints no such
line. `compass quick-fix finish` on a path issue refuses with exit 1, before it
writes anything, while the issue owes anything but the three immovable gates
and the green it records, and prints one `next:` line for each owed item. With
`--no-commit` it leaves the change unstaged, so its last line names the traced
files to stage before `compass ship-commit`. Every new assessment is a path
issue (`governance/routing-policy.md`, "The path writer").

## See the path in your terminal

When you run `compass next` in a terminal, it shows the issue's stages as a
rail, with the current stage marked:

```text
delivery · fix-retry-header
Assess ✓ → Specify ✓ → Build ● → Ship ○

Build [gate: verify.correctness] | next: compass tdd-red --loop outer --scenario
TRC-001 -- <acceptance test command>
```

Piped output, and any run inside Claude Code, keeps the plain one-line form.
Two environment variables change the rail:

- `NO_COLOR` removes the color.
- `COMPASS_COLOR=never` uses the ASCII markers `[x] [>] [ ] [-]` and no
  color. `COMPASS_COLOR=always` shows the rail even when the output is piped.
  `NO_COLOR` still removes the color.

The current stage is the first stage that the records do not show as done:

- Assess, when `delivery_approach` and `evidence_required` are set.
- Specify, when each scenario has an id, an intent and a declared test, and
  the `specify` checkpoint has an outcome where it is listed.
- Build, when each scenario that is not `verifiable: narrative` has a red,
  then a green.
- Ship, when the issue is closed.

An issue assessed before the path keeps its legacy stages, and the rail shows
each one as the path stage it maps to. A path stage shows as skipped only
when every legacy stage it maps to is skipped.

If a project turns on the capability `entry-exit-evaluation`, the line also
names the entry and exit checks of the current stage that are not met, after
`entry not met:` (`docs/entry-exit-evaluation.md`). A path issue owes no
Definition of Ready, so no `dor-*` check is named for it.

If the issue is at build and waits for another issue
that has not reached the point its `depends_on` entry names (`compass issue
depends add`), the line ends with what it waits for, for example
`Build [gate: verify.correctness] | next: ... | blocked: waits for b to reach done`.
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

- On `balanced` and `controlled`, `compass next` stops at a listed checkpoint
  that holds unconfirmed decisions: assess and specify under `controlled`, and
  specify under `balanced` when the scenarios owe a person's approval. Its
  first line reads `Waiting at the specify checkpoint: 2 decision(s) to
  confirm`, and the lines below list each decision with its
  resolution. Confirm them all with `compass evidence approve --decisions
  --approver <you> --role <role>`, or reopen one with `compass issue decision
  set <id> --status reopened --reason "<why>"`. A reopened decision keeps the
  checkpoint waiting.
- On `autonomous`, `compass next` lists the decisions below its usual line and
  does not wait. They stay open.

## The stage 2 and 3 reviews

On an issue the four-layer acceptance strategy applies to, `build` and `ship`
each end with a review from the `atdd` skill. When the records show one of
those stages done and its review has no outcome, `compass next` says so:

- On `controlled`, where the checkpoint is listed, its first line reads
  `Waiting at the build checkpoint: the stage 2 review has no outcome`,
  with the `compass evidence request --checkpoint build` command that asks
  you for it.
- Elsewhere it shows its usual line and adds the `compass issue checkpoint add`
  command that records the review as skipped.
- When you reject a review with `/compass:reject <n> <reason>`, `compass next`
  names that stage again, with your reason, until a new outcome is recorded.

An issue assessed before the path has these reviews at its legacy
`implement` and `verify` hand-offs.

Ship is done only once the
issue is closed, so its review is due once every gate has passed, and the
`next:` command then names `compass evidence request --checkpoint ship`.

## Where to go next

- **`docs/routing-deep-dive.md`** - how assess selects the evidence a change
  owes, with worked examples, including the same literal request owing
  different evidence, and a spike worked through end to end.
- **`docs/portability.md`** - the three layers (methodology / kit / adapter),
  and what porting Compass to another runtime involves: rewrite the adapter,
  keep the methodology and the kit untouched.

When a session leaves an issue half-finished, `/compass:status` reports where
every issue stands, and `/compass:resume <issue-slug>` picks one up from disk -
the artifacts were written precisely so the process never has to be
re-derived. Once you are running more than one issue at a time, `/compass:flow`
is the view across all of them - triage, blockers, and a periodic digest.

One more CLI command works across the whole board. `compass ci` runs the full
mechanical gate suite - `policy lint`, then `issue lint` and `check` for every
issue - and exits non-zero if anything fails, under the default
`adoption: enforced`; to add Compass to CI, you only
"run `compass ci`, honor the exit code" (see `ci/README.md`).
