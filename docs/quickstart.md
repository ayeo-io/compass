# Compass - Quickstart

This page takes you from an empty machine to a finished first issue. It also
says what `compass next`, the rail and the status line show. For one change
with its real output, read [Five minutes](five-minutes.md).

## 1. Install

Pick one of two ways.

**The plugin marketplace.** No clone, no install script:

```bash
claude plugin install compass --marketplace ayeo-io/compass
```

Or inside Claude Code:

```text
/plugin marketplace add ayeo-io/compass
/plugin install compass@compass
```

The plugin gives you the `/compass:…` commands and the hooks. It puts the
`compass` CLI on the PATH of the commands Claude Code runs, inside Claude
Code only. For your own terminal, the first session start writes a launcher
at `~/.claude/plugins/data/compass-compass/compass` (under your profile's
folder if you use another one). Compass names that launcher when it asks you
to run a command in a terminal. To type `compass`, add the folder to your
`PATH`:

```bash
export PATH="$HOME/.claude/plugins/data/compass-compass:$PATH"
```

**From source**, to read or edit Compass as you go:

```bash
git clone https://github.com/ayeo-io/compass.git
cd compass
pip install jsonschema                # optional - turns on full JSON Schema lint
bash scripts/install.sh --global      # or: bash scripts/install.sh  (project-local)
```

- `install.sh` symlinks `commands/` and `skills/` into your Claude Code
  config as a `compass` subdirectory. It registers `pre-tool.sh`,
  `post-tool.sh`, `stop.sh`, `session-start.sh`, `prompt-approval.sh` and
  `approval-summary.sh` in `settings.json`.
- A second run refreshes the links. It does not overwrite a file Compass did
  not create.
- `--global` gives every project the `/compass:*` commands. `--copy`
  installs copies, not symlinks.
- `install.sh` does **not** change your PATH. To call the CLI yourself, add
  `<clone>/bin` to your `PATH`, or run `python3 <clone>/cli/compass`.

Compass needs Python 3.10 or later. It bundles its YAML parser. The
optional `jsonschema` adds full JSON Schema validation to `compass policy
lint` and `compass issue lint` (`schemas/README.md`).

### The pre-tool hook guards code edits

In a project that has a `.compass/` folder, the pre-tool hook refuses an
Edit or Write to a recognized code file, with exit code 2, when:

- the current issue has no scenario; or
- its scenarios wait for a person's approval.

On an issue assessed before 9.0.0 it also refuses the edit when no failing
test is on record. It detects writes made through the shell in common forms
only
([safety contract](safety-contract.md#shell-write-detection-is-best-effort)).
On a spike the hook does not block.

## 2. Assess-and-go - `/compass:init` is optional

You need no setup between the install and the first issue. The five
guardrails and the default strategies are active from the first command.

Run `/compass:init` once, from the project root, when you want to set the
project's name and test command or add the project's own rules. It changes
no application code. It:

1. **Writes a minimal `compass.yml`:** `schema`, an `owner` who approves
   waivers, `project.name` and `project.test_command`. It copies no
   `governance/` files. A setting in `compass.yml` can only add to the check
   set. See `docs/configuration.md`.
2. **Stops on an older project.** A project with a `.compass/config.yml` or
   copied `governance/` files from 5.x must run `compass policy migrate` on
   Compass 8.x first, because 9.0.0 removed that command. See
   `docs/upgrade-9-0-0.md`.
3. **Creates `.compass/work/`**, where the state of each issue goes. It is
   committed by default, with the code it records. Its `.gitignore` keeps
   out the per-checkout files: generations, lock files and markers.

`compass init`, which each entry point runs for you, writes only a state
file in `.compass/` and no settings file.

## 3. First issue - the engineer

An issue: add rate limiting to the public API. Each delivery issue runs four
stages in order: **assess**, **specify**, **build** and **ship** (ADR-092).
One command runs them all in this session:

```
/compass:go "Add rate limiting to the public API"
```

The session runs two `compass` commands (ADR-099). `compass quick-fix start`
opens the issue and `compass quick-fix finish` writes its record. The
`next:` line of each says what comes next.

### Assess

The session reads the code, then records the assessment, the intent and the
first scenario in one call:

```
compass quick-fix start add-rate-limiting \
  --risk "cross-cutting - a misconfigured limiter blocks every API consumer" \
  --familiarity "brownfield-mapped - the middleware is documented" \
  --size "medium - several files and one design decision" \
  --labels public-api \
  --intent "A client over the request limit gets a 429 response" \
  --scenario "Given a client has sent 100 requests this minute, When it sends one more, Then the response is 429" \
  --test tests/test_limiter.py::test_over_limit \
  --request https://github.com/acme/api/issues/42 --requester "Dana Smith"
```

`start` serves every size. It writes:

- `.compass/work/add-rate-limiting/manifest.yml`, with the three scored
  dimensions and the request link: who asked and where;
- `docs/compass/<date>-add-rate-limiting/acceptance-criteria.md`, with the
  scenario as `TRC-001`;
- the `.compass/current-task` pointer, which tells the CLI and the hooks
  which issue is active.

The CLI then computes the evidence the change owes, and writes
`delivery_approach: delivery`, `evidence_required` and the `gates` to the
manifest:

- Each delivery issue owes the same evidence row. Here the risk, the size
  and the label `public-api` add nothing.
- A `G5` label, critical risk or a `require_evidence` rule of the project
  adds to it. The four-layer acceptance strategy (`S17`) is guidance: its
  records are owed only where a `require_evidence` rule adds them.
- The same assessment and resolved configuration give the same evidence on
  any machine with the same Compass version
  ([safety contract](safety-contract.md#1-routing-is-deterministic-after-assessment)).

`compass approach show` prints the approach, the evidence and where the
files go. Its first line says whether the session waits for you. The
project's `autonomy` setting decides that:

- `balanced`, the default: under `balanced` a delivery issue goes on and
  does not wait, unless its scenarios owe a person's approval (a `G5` label,
  such as `payments`, or critical risk). Then it waits at specify: the
  pre-tool hook refuses a code edit until a person answers.
- `autonomous`: the same.
- `controlled`: under `controlled` it waits at assess and specify, and also
  at build and ship where the four-layer acceptance strategy applies.

To correct an assessment value, run `compass approach evaluate --write
--reason "..."` with the new `--assessment` values. It computes the evidence
again and logs the change in the manifest's `reassessments:` list.

### Specify

The session adds the Given/When/Then scenarios to `acceptance-criteria.md`:
the happy path, the edge cases and the failure modes that matter.

- Each scenario is a `### Scenario:` heading with a traceability id on the
  line below it, such as `<!-- traceability id: TRC-002 · serves: INT-1 -->`.
  `finish` reads each one from the file.
- An input class or failure mode that the intent implies and no scenario
  covers becomes a scenario, or is recorded with `compass scenario descope
  "<mode>" --reason "<why>"`.
- Each Non-functional requirements row names the scenarios that cover the
  concern, or the reason it does not apply.
- An ambiguity is settled in the criteria, or recorded with `compass issue
  decision add`.
- A design decision goes in a decision record beside the code, not in a
  Compass document.

### Build

The session writes the tests and the code and runs the tests directly. No
`compass` command comes between `start` and `finish`.

1. **Tests.** Write a test for each scenario. It must fail without the
   change: `finish` checks that.
2. **Code.** Write the smallest correct change. The pre-tool hook does not
   need a failing run on record first.
3. **Refactor** under a green suite.

`compass tdd-red` and `compass tdd-green` still work. A red recorded with
`compass tdd-red` is the only proof that a test was written before the code.

### Ship

```
compass quick-fix finish -m "Add rate limiting to the public API (#42)" -- python3 -m pytest -q
```

`finish` writes the whole record in one call:

1. It reads the scenarios from `acceptance-criteria.md` and the changed
   files from git.
2. It runs the test command on a copy of the commit the issue started from,
   with the test files of the change laid over it. The run must fail. Then
   it runs the command on the working tree, where it must pass. The red
   record says `proved_on: base-copy`: the tests fail without the change. It
   does not show the order of the work (`docs/base-copy.md`).
3. It runs `compass check` and passes the three gates each issue owes:
   `verify.correctness`, `verify.governance` and `verify.traceability`. Gate
   evidence is **typed**: a `{type, path}` record, such as `test-run` or
   `command-output`. The check set says which types each gate accepts, so a
   written note cannot clear a mechanical gate.
4. It writes the request for your approval and stops. Nothing is committed.

Under the default `adoption: enforced`, `finish` does not commit while a
check fails. Where a `require_evidence` rule adds evidence, `finish` writes
its own record, prints one `next:` line for each added item, commits nothing
and exits 1.

You type `/compass:approve 1`. The session runs the same `finish` again, and
it commits the code and the issue's record.

- On the default branch, the commit goes on a new branch named after the
  issue.
- With `--no-commit`, `finish` leaves the commit to `compass ship-commit
  --issue add-rate-limiting`.
- By default the same commit holds the record:
  `.compass/work/add-rate-limiting/` and the documents folder, with
  `trail.md`, which a reviewer checks with `sha256sum`.
  `docs/delivery-record.md` says how a project keeps the record out of the
  commit.
- The approval covers the change you saw. When the code or the tests change
  afterwards, one more `finish` proves the red and the green again, commits,
  and writes a new request. `compass check` fails the
  `ship-approval-present` row until you approve the new state.

The ship approval (`ship-approval`, ADR-095) can also come from the pull
request ([GitHub links](github-links.md)). After the merge, `compass issue
link set --pr <n> --issue add-rate-limiting` records a review that approves
the pull request, by a person who is not its author. An agent cannot approve
the pull request for you: the pre-tool hook refuses `gh pr review
--approve`. When the record ships with the code, `compass record commit
--issue add-rate-limiting` then commits the merge fields alone.

## 4. A brief from a product owner, and a public claim

A product owner often brings a brief, not a change: "Let finance pull their
month-end numbers without filing a data request". Start with `/compass:go`
as before. The `intent-interview` skill turns the brief into the Summary and
Intent links of `acceptance-criteria.md` before any scenario is written.

- Each statement in the intent comes from the brief or from an answer the
  product owner gave. Where the brief is silent, the session asks one
  question at a time.
- The intent states the outcome, not a solution such as "add a CSV export
  button". Each success signal in it must have a scenario that delivers it.

A change that makes a public claim, such as a line in the release notes,
records the claim in the manifest's `claims:` with the scenario that backs
it. The `claim-traces-to-scenario` check fails when a claim names no
scenario. Whether the scenario backs the claim is the reviewer's judgment
([safety contract](safety-contract.md#compass-does-not-prove-correctness)).
A project can add the claims gate to each issue in `compass.yml`
(`docs/configuration.md`).

## When you cannot frame it yet - a spike

Work that is a question, with no acceptance criteria yet, is a **spike**. A
spike is not on the path:

- Assess still runs, and records the question and a timebox.
- Build is exploration. The TDD strategy is suspended and the hook does not
  block.
- **Nothing lands from a spike.** To keep the code, re-assess the spike into
  a delivery issue, where the guardrails apply in full. Otherwise discard
  the code and record the finding.

See `approaches/spike.md`.

## See the issue's state in the status line

Compass can show the current issue in Claude Code's status line:

```text
compass · fix-login-redirect · delivery · Build · gates 1/3 · TRC-002 red
```

The last field says the second traced criterion has a failing test on
record. The line names the same stage as `compass next`. Only you see it,
not the model, so it costs no tokens.

Add it to your Claude Code settings file, your own or the project's. A
plugin cannot add it for you:

```json
{
  "statusLine": {
    "type": "command",
    "command": "~/.claude/plugins/data/compass-compass/compass-statusline"
  }
}
```

- That file is a launcher in the plugin's data folder, which Claude Code
  keeps across plugin updates. Each session start points it at the installed
  version, so the setting does not need a change.
- A plugin loaded with `--plugin-dir` keeps its launcher under
  `~/.claude/plugins/data/compass-inline/`.
- `/compass:init` offers to add the entry. It shows the change and writes it
  only when you say yes.
- Outside a Compass project, the line is empty.
- The line fits the terminal width that Claude Code passes in `COLUMNS`, and
  assumes 80 columns when it is not set.

## What `compass next` prints

`compass next` prints one line: the issue's stage, the first gate not yet
passed, and the one command to run next.

```text
Build [gate: verify.correctness] | next: write the tests and the code, then compass quick-fix finish -m "<commit message>" -- <test command>
```

The stage is a stage of the path (ADR-092). An issue assessed before the
path keeps its legacy stages, and each rule reads them as before. `compass
next`, the rail and the status line show each one as the path stage it maps
to:

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
| `request` owed, the link or the requester not recorded | `compass issue link set --issue <slug> --request <url> --requester <name>` |
| `scenario-approval` owed, no outcome and no request | write the scenarios in acceptance-criteria.md, then `compass evidence request --checkpoint specify`, then stop for `/compass:approve` |
| `scenario-approval` owed, a request pending | stop: the scenarios wait for the person's approval. Ask them to type `/compass:approve <n>` |
| a gate not passed, or no green | write the tests and the code, then `compass quick-fix finish -m "<commit message>" -- <test command>` |
| a request for the ship approval or the `G5` sign-off pending | stop and ask the person to type `/compass:approve <n>`. After the approval, run the same `finish` again: it commits |
| the same, after a change that differs from the one approved | stop and ask the person to type `/compass:approve <n>`. Nothing else to run now |
| `human-approval` owed, none on record and no request | `compass quick-fix finish -m "<commit message>" -- <test command>`, which asks for the `G5` sign-off |
| every approval on record, the issue open | `compass quick-fix finish -m "<commit message>" -- <test command>` (it commits), or `compass ship-commit` on the branch the person names |
| landed, `ship-approval` owed, none on record | `compass issue link set --pr <n> --issue <slug>` after the merge, or `compass evidence request --ship`, then stop for `/compass:approve`; only the second once the merge is recorded |
| landed with its record committed with the code, and the issue folder holds a change git has not committed (the merge fields `compass issue link set --pr` wrote) | `compass record commit --issue <slug>` |

What a path issue owes comes from its `evidence_required` list:

- The request comes first. It is not a stop: the check `request-recorded`
  fails until the link and the requester are recorded, and a waiver a person
  approves excuses it and ends the row.
- A spike first names `compass evidence add EV-SPIKE --type
  spike-conclusion`, then `compass gate pass spike.conclude`.
- A landed issue that owes the ship approval prints `all phases complete |
  next: <command>`.
- `compass next --json` gives the same command in a `next` field, and `null`
  on a closed issue that owes nothing more.

An issue assessed before 9.0.0 keeps the rows of its older record: a
scenario with no test, `compass tdd-red` and `compass tdd-green` for each
scenario, the `S17` records its `acceptance_strategy` block names, each open
Definition of Done item (when its verify stage is `thorough`) and each gate
not passed.

On a path issue, each verb that writes a record of the issue ends its text
output with the same `next: <command>` line: `compass scenario add`,
`scenario tests set`, `scenario descope`, `tdd-red`, `tdd-green`, `gate
pass`, `evidence add`, `changed-file add`, `isolation record`, `layering
record`, `evidence approve` and `quick-fix start` and `finish`. `--json` and
`--quiet` output do not change. An issue assessed before the path prints no
such line. Each new assessment is a path issue
(`governance/routing-policy.md`, "The path writer").

## See the path in your terminal

In a terminal, `compass next` shows the issue's stages as a rail, with the
current stage marked:

```text
delivery · fix-retry-header
Assess ✓ → Specify ✓ → Build ● → Ship ○

Build [gate: verify.correctness] | next: write the tests and the code, then
compass quick-fix finish -m "<commit message>" -- <test command>
```

Piped output, and any run inside Claude Code, keeps the one-line form. Two
environment variables change the rail:

- `NO_COLOR` removes the color.
- `COMPASS_COLOR=never` uses the ASCII markers `[x] [>] [ ] [-]` and no
  color. `COMPASS_COLOR=always` shows the rail even when the output is piped.
  `NO_COLOR` still removes the color.

The current stage is the first stage that the records do not show as done.
A stage is done:

- Assess, when `delivery_approach` and `evidence_required` are set.
- Specify, when each scenario has an id, an intent and a declared test, and
  the `specify` checkpoint has an outcome where it is listed.
- Build, when each scenario that is not `verifiable: narrative` has a red,
  then a green.
- Ship, when the issue is closed.

On an issue assessed before the path, a path stage shows as skipped only
when every legacy stage it maps to is skipped.

If a project turns on the capability `entry-exit-evaluation`, the line also
names the entry and exit checks of the current stage that are not met, after
`entry not met:` (`docs/entry-exit-evaluation.md`). A path issue owes no
Definition of Ready, so no `dor-*` check is named for it.

An issue at build can wait for another issue that has not reached the point
its `depends_on` entry names (`docs/issue-dependencies.md`):

- The line ends with what it waits for, for example
  `Build [gate: verify.correctness] | next: ... | blocked: waits for b to reach done`.
  Earlier stages show no wait.
- The pre-tool hook refuses production-code edits while it can read, in this
  checkout, that the wait is not met. A fault in reading it allows the edit
  with a warning
  ([safety contract](safety-contract.md#a-dependency-between-issues-is-read-from-this-checkout-and-a-fault-never-blocks)).
- A dependency `compass next` cannot judge, such as one on an issue with no
  manifest in this checkout, is left out of the line; `compass issue lint`
  names it.

## Decisions an agent took for you

When an agent resolves a requirement question itself, it records the
decision (`compass issue decision add`, or `--from-ledger` for the
requirements review). What happens next depends on the `autonomy` setting:

- On `balanced` and `controlled`, `compass next` stops at a listed
  checkpoint that holds unconfirmed decisions: assess and specify under
  `controlled`, and specify under `balanced` when the scenarios owe a
  person's approval. Its first line reads `Waiting at the specify
  checkpoint: 2 decision(s) to confirm`, and the lines below list each
  decision with its resolution.
- Confirm them all with `compass evidence approve --decisions --approver
  <you> --role <role>`. Reopen one with `compass issue decision set <id>
  --status reopened --reason "<why>"`; a reopened decision keeps the
  checkpoint waiting.
- On `autonomous`, `compass next` lists the decisions below its usual line
  and does not wait. They stay open.

## The stage 2 and 3 reviews

On an issue the four-layer acceptance strategy applies to, `build` and
`ship` each end with a review from the `atdd` skill. When the records show
one of those stages done and its review has no outcome, `compass next` says
so:

- On `controlled`, where the checkpoint is listed, its first line reads
  `Waiting at the build checkpoint: the stage 2 review has no outcome`,
  with the `compass evidence request --checkpoint build` command that asks
  you for it.
- Elsewhere it shows its usual line and adds the `compass issue checkpoint
  add` command that records the review as skipped.
- When you reject a review with `/compass:reject <n> <reason>`, `compass
  next` names that stage again, with your reason, until a new outcome is
  recorded.

Ship is done only once the issue is closed. Its review is due once every
gate has passed, and the `next:` command then names `compass evidence
request --checkpoint ship`. An issue assessed before the path has these
reviews at its legacy `implement` and `verify` hand-offs.

## Where to go next

- `docs/routing-deep-dive.md` - how assess selects the evidence a change
  owes, with worked examples and a spike from start to end.
- `docs/portability.md` - the three layers of Compass (methodology, kit and
  adapter), and how to port it to another runtime.
- `/compass:status` reports where each issue stands, `/compass:resume
  <issue-slug>` picks one up from disk, and `/compass:flow` shows triage and
  blockers across all issues.
- `compass ci` runs `policy lint`, then `issue lint` and `check` for each
  issue. It exits non-zero if anything fails, under the default `adoption:
  enforced`. To add Compass to CI, run it and honor the exit code
  (`ci/README.md`).
