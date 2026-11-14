# Compass - Quickstart

This page takes you from an empty machine to a finished first issue. For one
change with its real output, read [Five minutes](five-minutes.md).

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

## See where the issue stands

`compass next` prints the issue's stage, the first gate not yet passed and
the one command to run next. In a terminal it also draws the four stages as
a rail, and Claude Code's status line can show the same stage. The
[CLI reference](cli.md#compass-next) holds the detail: the table of `next:`
commands, [the rail](cli.md#the-rail) and
[the status line](cli.md#the-status-line) with its settings entry.

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
